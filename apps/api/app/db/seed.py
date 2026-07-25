"""بذر قاعدة البيانات من حزمة القرآن الموثقة (المصدر نفسه المتحقق منه بنيويًا).

لا يكتب نصًا قرآنيًا يدويًا؛ كل المحتوى من الحزمة المبنية عبر
scripts/import-quran/build_bundle.py. البيانات المبذورة حالتها «مستورد»
(imported) — لم تعتمد بمراجعة المنصة المزدوجة بعد.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import uuid

from sqlalchemy import insert

from app.db.session import SessionFactory
from app.models.audit import AuditLog
from app.models.enums import ConfidenceLevel, RecordStatus
from app.models.language import Root, RootDerivation, RootOccurrence
from app.models.quran import Ayah, QuranTextVersion, Surah
from app.core.paths import data_file, describe_search
from app.utils.arabic import normalize_arabic_search

BUNDLE_NAME = "quran_bundle.json.gz"


def _resolve_bundle():
    """مسار الحزمة، أو خطأ **يقول أين بُحث**.

    كان الغياب يُعالَج بعودة صامتة `{"seeded": False}`، فتمضي التهيئة
    وتبدو ناجحة ثم تسقط الاستعلامات لاحقًا بـ`NO_ACTIVE_VERSION` بعيدًا
    عن السبب. وهو ما جعل تشخيص أول فشل لـCI أطول مما يجب. والصمت هنا
    أسوأ من الفشل: منصةٌ بلا نص مصحف ليست منصة."""
    target = data_file(BUNDLE_NAME)
    if not target.exists():
        raise FileNotFoundError(
            "حزمة النص غير موجودة، فلا يمكن بذر المصحف.\n"
            + describe_search(BUNDLE_NAME)
        )
    return target


def _load_bundle() -> dict:
    with gzip.open(_resolve_bundle(), "rt", encoding="utf-8") as f:
        return json.load(f)


async def seed_from_bundle() -> dict:
    bundle_path = _resolve_bundle()
    bundle = _load_bundle()
    meta = bundle["meta"]

    version_id = uuid.uuid4()

    async with SessionFactory() as session:
        # 1) إصدار النص (مستورد ونشط في التطوير؛ التفعيل الرسمي في المرحلة C)
        version = QuranTextVersion(
            id=version_id,
            version_code=meta["version_code"],
            title=meta["title"],
            riwayah=meta["riwayah"],
            script_type=meta["script_type"],
            counting_system=meta["counting_system"],
            source_name=meta["sources"][0]["name"],
            source_reference=meta["sources"][0]["url"],
            sha256_hash=hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
            status=RecordStatus.IMPORTED,
            is_active=True,
        )
        session.add(version)

        # 2) السور (مع نص البسملة المفصول عن الآية الأولى)
        session.add_all(
            [
                Surah(
                    number=s["number"],
                    arabic_name=s["arabic_name"],
                    revelation_type=s.get("revelation_type", ""),
                    basmala_text=s.get("basmala"),
                )
                for s in bundle["surahs"]
            ]
        )
        await session.flush()

        # 3) الآيات — إدراج مجمّع مع توليد المعرفات عميلًا لربط المواضع
        safe = {(s, a) for s, a in bundle["safe_highlight"]}
        ayah_id_map: dict[tuple[int, int], uuid.UUID] = {}
        ayah_rows = []
        for surah, ayah_num, text in bundle["ayahs"]:
            aid = uuid.uuid4()
            ayah_id_map[(surah, ayah_num)] = aid
            ayah_rows.append(
                {
                    "id": aid,
                    "text_version_id": version_id,
                    "surah_number": surah,
                    "ayah_number": ayah_num,
                    "uthmani_text": text,
                    "plain_search_text": normalize_arabic_search(text),
                    "text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                }
            )
        await session.execute(insert(Ayah), ayah_rows)

        # 4) الجذور والمواضع
        # المواضع هنا بذر أولي مباشر من الحزمة (derivation=bundle_import).
        # خط المرحلة D يعيد بناءها اشتقاقًا من التحليلات الصرفية والقرارات.
        occ_rows = []
        root_rows = []
        for normalized, entry in bundle["roots"].items():
            rid = uuid.uuid4()
            root_rows.append(
                {
                    "id": rid,
                    "display_root": entry["display"],
                    "normalized_root": normalized,
                    "root_length": len(normalized),
                    "status": RecordStatus.IMPORTED.value,
                    "confidence": ConfidenceLevel.MACHINE_ONLY.value,
                    "created_at": version.created_at,
                }
            )
            seen_positions: set[tuple[int, int, int]] = set()
            for surah, ayah_num, word in entry["occurrences"]:
                key = (surah, ayah_num)
                aid = ayah_id_map.get(key)
                if aid is None or (surah, ayah_num, word) in seen_positions:
                    continue
                seen_positions.add((surah, ayah_num, word))
                occ_rows.append(
                    {
                        "id": uuid.uuid4(),
                        "root_id": rid,
                        "ayah_id": aid,
                        "word_number": word,
                        "is_highlight_safe": key in safe,
                        "token_id": None,
                        "derivation": RootDerivation.BUNDLE_IMPORT.value,
                    }
                )
        await session.execute(insert(Root), root_rows)
        # إدراج المواضع على دفعات لتفادي حدود المتغيرات في SQLite
        for i in range(0, len(occ_rows), 5000):
            await session.execute(insert(RootOccurrence), occ_rows[i : i + 5000])

        session.add(
            AuditLog(
                action="seed_import",
                entity_type="quran_text_version",
                entity_id=str(version_id),
                new_data={
                    "version_code": meta["version_code"],
                    "ayahs": len(ayah_rows),
                    "roots": len(root_rows),
                    "occurrences": len(occ_rows),
                    "sources": [s["name"] for s in meta["sources"]],
                },
                reason="بذر أولي من حزمة موثقة",
            )
        )

        await session.commit()

    return {
        "seeded": True,
        "surahs": len(bundle["surahs"]),
        "ayahs": len(ayah_rows),
        "roots": len(root_rows),
        "occurrences": len(occ_rows),
    }
