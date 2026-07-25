"""خدمة الصرف متعدد المصادر (المرحلة D).

خط العمل كاملًا اشتقاقي ولا يُكتب فيه شيء يدويًا:

    نص الإصدار الموثق ──ترميز──▶ tokens
                                   │
    مصدر صرفي (بصمة + رخصة) ──استيراد──▶ morphological_analyses
                                   │
                     مقارنة المصادر كلمةً كلمة
                                   │
             ┌─────────────────────┴────────────────────┐
        اتفاق/مصدر واحد                            اختلاف
             │                                          │
             ▼                                          ▼
      root_occurrences ◀──── قرار مراجعة معتمد ──── يبقى معلّقًا

قاعدتان لا تُخترقان:
  1. لا يُشتق نص قرآني من التحليل — نص العرض من `Ayah.uthmani_text` وحده.
  2. الاختلاف بين المصادر لا يُحسم آليًا ولا يُخفى؛ يبقى ظاهرًا حتى يقرره
     مراجعان مستقلان.
"""

from __future__ import annotations

import gzip
import json
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.audit import record_audit
from app.db.base import utcnow
from app.models.enums import ConfidenceLevel, RecordStatus
from app.models.language import Root, RootDerivation, RootOccurrence
from app.models.morphology import (
    GoldenRootCase,
    MorphologicalAnalysis,
    MorphologySource,
    Token,
    TokenRootDecision,
    TokenRootDecisionRoot,
)
from app.models.quran import Ayah, QuranTextVersion, Surah
from app.utils.arabic import normalize_arabic_search, tokenize_ayah
from app.utils.morphology_tags import parse_features, pos_label

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
MORPHOLOGY_BUNDLE_PATH = _DATA_DIR / "morphology_qac04.json.gz"
GOLDEN_CASES_PATH = _DATA_DIR / "golden_roots.json"

# الأدوار المؤهلة لاقتراح قرار جذر واعتماده (مراجعة لغوية)
DECISION_PROPOSER_ROLES = {
    "linguistic_reviewer",
    "quality_manager",
    "tech_admin",
    "researcher",
}
DECISION_APPROVER_ROLES = {
    "linguistic_reviewer",
    "quality_manager",
    "arbitration_committee",
}

_INSERT_BATCH = 2000


class MorphologyError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message


def load_morphology_bundle(path: Path | None = None) -> dict:
    target = path or MORPHOLOGY_BUNDLE_PATH
    if not target.exists():
        raise MorphologyError(
            "BUNDLE_MISSING",
            "حزمة الصرف غير موجودة. ابنِها بـ scripts/import-quran/"
            "build_morphology_bundle.py",
        )
    with gzip.open(target, "rt", encoding="utf-8") as handle:
        return json.load(handle)


class MorphologyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- مساعدات ---------------------------------------------------------
    async def _active_version_id(self) -> uuid.UUID:
        version_id = await self.session.scalar(
            select(QuranTextVersion.id).where(QuranTextVersion.is_active.is_(True))
        )
        if version_id is None:
            raise MorphologyError("NO_ACTIVE_VERSION", "لا يوجد إصدار نص مفعَّل.")
        return version_id

    async def _ayah_rows(
        self, version_id: uuid.UUID, surahs: set[int] | None = None
    ) -> list[tuple[uuid.UUID, int, int, str]]:
        stmt = select(
            Ayah.id, Ayah.surah_number, Ayah.ayah_number, Ayah.uthmani_text
        ).where(Ayah.text_version_id == version_id)
        if surahs:
            stmt = stmt.where(Ayah.surah_number.in_(sorted(surahs)))
        return list(
            (await self.session.execute(stmt.order_by(Ayah.surah_number, Ayah.ayah_number))).all()
        )

    async def _bulk_insert(self, table: Any, rows: list[dict]) -> None:
        """إدراج مجمّع على دفعات — يتفادى حد متغيرات SQLite."""
        for start in range(0, len(rows), _INSERT_BATCH):
            await self.session.execute(insert(table), rows[start : start + _INSERT_BATCH])

    # ---- 1) الترميز ------------------------------------------------------
    async def tokenize_version(
        self,
        version_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        surahs: set[int] | None = None,
    ) -> dict:
        """يبني جدول الكلمات من نص الإصدار. عملية حتمية وقابلة للإعادة."""
        version_id = version_id or await self._active_version_id()
        ayahs = await self._ayah_rows(version_id, surahs)
        if not ayahs:
            raise MorphologyError("NO_AYAHS", "لا توجد آيات في هذا الإصدار.")

        ayah_ids = [row[0] for row in ayahs]
        for start in range(0, len(ayah_ids), _INSERT_BATCH):
            await self.session.execute(
                delete(Token).where(Token.ayah_id.in_(ayah_ids[start : start + _INSERT_BATCH]))
            )

        rows: list[dict] = []
        for ayah_id, _surah, _ayah, text in ayahs:
            for index, (start, end, word) in enumerate(tokenize_ayah(text), start=1):
                rows.append(
                    {
                        "id": uuid.uuid4(),
                        "ayah_id": ayah_id,
                        "word_number": index,
                        "surface_text": word,
                        "normalized_text": normalize_arabic_search(word),
                        "char_start": start,
                        "char_end": end,
                    }
                )
        await self._bulk_insert(Token, rows)

        # حذف الكلمات يصفّر `token_id` في التحليلات (ON DELETE SET NULL)،
        # فيختفي التمييز في كل ما أُعيد ترميزه. تُعاد الروابط فورًا حيث
        # تصح المحاذاة (عدد كلمات المنصة = أكبر رقم كلمة عند المصدر).
        relinked = await self._relink_analyses([row[0] for row in ayahs])

        record_audit(
            self.session,
            action="morphology_tokenize",
            entity_type="quran_text_version",
            entity_id=version_id,
            actor_id=actor_id,
            new_data={
                "ayahs": len(ayahs),
                "tokens": len(rows),
                "relinked_analyses": relinked,
            },
        )
        await self.session.commit()
        return {
            "ayahs": len(ayahs),
            "tokens": len(rows),
            "relinked_analyses": relinked,
        }

    async def _relink_analyses(self, ayah_ids: list[uuid.UUID]) -> int:
        """يعيد ربط التحليلات بالكلمات بعد إعادة الترميز.

        الربط يقع فقط حيث تصح المحاذاة: عدد كلمات المنصة في الآية يساوي
        أكبر رقم كلمة عند المصدر. وإلا بقي `token_id` فارغًا فلا يُدَّعى
        تمييز في آية مختلَف في حدود كلماتها."""
        relinked = 0
        for start in range(0, len(ayah_ids), _INSERT_BATCH):
            chunk = ayah_ids[start : start + _INSERT_BATCH]
            tokens: dict[tuple[uuid.UUID, int], uuid.UUID] = {}
            token_counts: dict[uuid.UUID, int] = {}
            for tid, aid, wnum in (
                await self.session.execute(
                    select(Token.id, Token.ayah_id, Token.word_number).where(
                        Token.ayah_id.in_(chunk)
                    )
                )
            ).all():
                tokens[(aid, wnum)] = tid
                token_counts[aid] = token_counts.get(aid, 0) + 1

            source_words: dict[tuple[uuid.UUID, uuid.UUID], int] = {}
            for aid, sid, max_word in (
                await self.session.execute(
                    select(
                        MorphologicalAnalysis.ayah_id,
                        MorphologicalAnalysis.source_id,
                        func.max(MorphologicalAnalysis.word_number),
                    )
                    .where(MorphologicalAnalysis.ayah_id.in_(chunk))
                    .group_by(
                        MorphologicalAnalysis.ayah_id,
                        MorphologicalAnalysis.source_id,
                    )
                )
            ).all():
                source_words[(aid, sid)] = max_word

            rows = (
                await self.session.execute(
                    select(
                        MorphologicalAnalysis.id,
                        MorphologicalAnalysis.ayah_id,
                        MorphologicalAnalysis.source_id,
                        MorphologicalAnalysis.word_number,
                    ).where(MorphologicalAnalysis.ayah_id.in_(chunk))
                )
            ).all()
            updates = []
            for analysis_id, aid, sid, wnum in rows:
                aligned = source_words.get((aid, sid)) == token_counts.get(aid)
                token_id = tokens.get((aid, wnum)) if aligned else None
                updates.append({"_id": analysis_id, "token_id": token_id})
                if token_id is not None:
                    relinked += 1
            for offset in range(0, len(updates), _INSERT_BATCH):
                await self.session.execute(
                    update(MorphologicalAnalysis)
                    .where(MorphologicalAnalysis.id == bindparam("_id"))
                    .values(token_id=bindparam("token_id")),
                    updates[offset : offset + _INSERT_BATCH],
                )
        return relinked

    # ---- 2) المصادر ------------------------------------------------------
    async def upsert_source(self, meta: dict) -> MorphologySource:
        code = meta["source_code"]
        source = await self.session.scalar(
            select(MorphologySource).where(MorphologySource.code == code)
        )
        if source is None:
            source = MorphologySource(code=code)
            self.session.add(source)
        source.name = meta["name"]
        source.url = meta.get("url")
        source.source_version = meta.get("source_version")
        source.license_note = meta.get("license")
        source.file_sha256 = meta.get("file_sha256")
        source.notice = meta.get("notice")
        await self.session.flush()
        return source

    async def list_sources(self) -> list[dict]:
        rows = (
            await self.session.execute(
                select(MorphologySource).order_by(MorphologySource.code)
            )
        ).scalars()
        out = []
        for source in rows:
            count = await self.session.scalar(
                select(func.count(MorphologicalAnalysis.id)).where(
                    MorphologicalAnalysis.source_id == source.id
                )
            )
            out.append(
                {
                    "id": str(source.id),
                    "code": source.code,
                    "name": source.name,
                    "url": source.url,
                    "source_version": source.source_version,
                    "license_note": source.license_note,
                    "file_sha256": source.file_sha256,
                    "notice": source.notice,
                    "status": source.status.value,
                    "confidence": source.confidence.value,
                    "is_enabled": source.is_enabled,
                    "analysis_count": count or 0,
                }
            )
        return out

    # ---- 3) الاستيراد ----------------------------------------------------
    async def _root_id_map(self, root_keys: set[str], displays: dict[str, str]) -> dict:
        existing = {
            key: rid
            for key, rid in (
                await self.session.execute(
                    select(Root.normalized_root, Root.id).where(
                        Root.normalized_root.in_(sorted(root_keys))
                    )
                )
            ).all()
        }
        missing = sorted(root_keys - set(existing))
        if missing:
            new_rows = []
            for key in missing:
                rid = uuid.uuid4()
                existing[key] = rid
                new_rows.append(
                    {
                        "id": rid,
                        "display_root": displays.get(key, " ".join(key)),
                        "normalized_root": key,
                        "root_length": len(key),
                        "status": RecordStatus.IMPORTED.value,
                        "confidence": ConfidenceLevel.MACHINE_ONLY.value,
                        "created_at": utcnow(),
                    }
                )
            await self._bulk_insert(Root, new_rows)
        return existing

    async def import_bundle(
        self,
        bundle: dict,
        version_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        surahs: set[int] | None = None,
    ) -> dict:
        """يستورد تحليل مصدر كامل ويربطه بكلمات الإصدار حيث تصح المحاذاة."""
        version_id = version_id or await self._active_version_id()
        source = await self.upsert_source(bundle["meta"])

        ayahs = await self._ayah_rows(version_id, surahs)
        ayah_map = {(s, a): aid for aid, s, a, _t in ayahs}
        if not ayah_map:
            raise MorphologyError("NO_AYAHS", "لا توجد آيات في هذا الإصدار.")

        # عدد كلمات المنصة لكل آية (من جدول الكلمات — يجب أن يكون مبنيًا)
        token_counts: dict[uuid.UUID, int] = {}
        token_map: dict[tuple[uuid.UUID, int], uuid.UUID] = {}
        ayah_ids = list(ayah_map.values())
        for start in range(0, len(ayah_ids), _INSERT_BATCH):
            chunk = ayah_ids[start : start + _INSERT_BATCH]
            for tid, aid, wnum in (
                await self.session.execute(
                    select(Token.id, Token.ayah_id, Token.word_number).where(
                        Token.ayah_id.in_(chunk)
                    )
                )
            ).all():
                token_map[(aid, wnum)] = tid
                token_counts[aid] = token_counts.get(aid, 0) + 1
        if not token_map:
            raise MorphologyError(
                "NOT_TOKENIZED", "يجب ترميز الإصدار قبل استيراد تحليل صرفي."
            )

        source_words = {
            (s, a): count for s, a, count in bundle.get("source_words_per_ayah", [])
        }

        segments = bundle["segments"]
        root_keys: set[str] = set()
        displays: dict[str, str] = {}
        for seg in segments:
            if surahs and seg[0] not in surahs:
                continue
            if seg[11]:
                root_keys.add(seg[11])
                displays.setdefault(seg[11], " ".join(seg[11]))
        root_ids = await self._root_id_map(root_keys, displays)

        # حذف تحليل هذا المصدر في النطاق المستورد — الاستيراد يعيد بناءه كاملًا
        scope_ayah_ids = list(ayah_map.values())
        for start in range(0, len(scope_ayah_ids), _INSERT_BATCH):
            await self.session.execute(
                delete(MorphologicalAnalysis).where(
                    MorphologicalAnalysis.source_id == source.id,
                    MorphologicalAnalysis.ayah_id.in_(
                        scope_ayah_ids[start : start + _INSERT_BATCH]
                    ),
                )
            )

        rows: list[dict] = []
        skipped_missing_ayah = 0
        aligned_ayahs = 0
        misaligned: list[tuple[int, int]] = []
        checked: set[tuple[int, int]] = set()

        for seg in segments:
            (
                surah, ayah_num, word, segment_number, form_bw, tag, features,
                pos, lemma, lemma_index, root_ar, root_key,
            ) = seg
            if surahs and surah not in surahs:
                continue
            ayah_id = ayah_map.get((surah, ayah_num))
            if ayah_id is None:
                skipped_missing_ayah += 1
                continue

            key = (surah, ayah_num)
            if key not in checked:
                checked.add(key)
                if source_words.get(key) == token_counts.get(ayah_id):
                    aligned_ayahs += 1
                else:
                    misaligned.append(key)

            aligned = source_words.get(key) == token_counts.get(ayah_id)
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "source_id": source.id,
                    "ayah_id": ayah_id,
                    "word_number": word,
                    "segment_number": segment_number,
                    "token_id": token_map.get((ayah_id, word)) if aligned else None,
                    "form_source": form_bw,
                    "tag": tag,
                    "features": features,
                    "pos": pos,
                    "is_stem": pos is not None,
                    "lemma": lemma,
                    "lemma_index": lemma_index,
                    "root_id": root_ids.get(root_key) if root_key else None,
                    "source_root_text": root_ar,
                    **parse_features(features),
                }
            )

        await self._bulk_insert(MorphologicalAnalysis, rows)

        result = {
            "source_code": source.code,
            "segments": len(rows),
            "ayahs_in_scope": len(checked),
            "aligned_ayahs": aligned_ayahs,
            "misaligned_ayahs": len(misaligned),
            "roots_total": len(root_keys),
            "skipped_missing_ayah": skipped_missing_ayah,
        }
        record_audit(
            self.session,
            action="morphology_import",
            entity_type="morphology_source",
            entity_id=source.id,
            actor_id=actor_id,
            new_data=result | {"file_sha256": source.file_sha256},
        )
        await self.session.commit()
        return result

    # ---- 4) المقارنة والاشتقاق ------------------------------------------
    async def _decision_map(
        self, ayah_ids: list[uuid.UUID]
    ) -> dict[tuple[uuid.UUID, int], frozenset[uuid.UUID]]:
        """قرارات معتمدة فقط: (آية، كلمة) → مجموعة الجذور المقررة."""
        allowed = set(ayah_ids)
        # استعلام صريح بلا اعتماد على تحميل العلاقات — يبقى العمل داخل سياق
        # غير متزامن واحد ولا يقع تحميل كسول في وقت غير مناسب
        rows = (
            await self.session.execute(
                select(
                    TokenRootDecision.id,
                    TokenRootDecision.ayah_id,
                    TokenRootDecision.word_number,
                ).where(TokenRootDecision.status == RecordStatus.APPROVED)
            )
        ).all()
        out: dict[tuple[uuid.UUID, int], frozenset[uuid.UUID]] = {}
        for decision_id, ayah_id, word_number in rows:
            if ayah_id not in allowed:
                continue
            root_ids = (
                await self.session.execute(
                    select(TokenRootDecisionRoot.root_id).where(
                        TokenRootDecisionRoot.decision_id == decision_id
                    )
                )
            ).scalars()
            out[(ayah_id, word_number)] = frozenset(root_ids)
        return out

    async def _source_root_sets(
        self, ayah_ids: list[uuid.UUID]
    ) -> tuple[
        dict[tuple[uuid.UUID, int], dict[uuid.UUID, frozenset[uuid.UUID]]],
        dict[tuple[uuid.UUID, int], uuid.UUID],
    ]:
        """يعيد ((آية، كلمة) → {مصدر: مجموعة جذوره}) و((آية، كلمة) → الكلمة المربوطة).

        الربط بالكلمة يؤخذ من التحليل نفسه لا من جدول الكلمات: التحليل لا
        يحمل `token_id` إلا حيث صحّت المحاذاة، فلا يُدَّعى تمييز في آية
        يختلف فيها عدّ الكلمات بين المصدر والنص. المصادر المعطلة مستبعدة."""
        enabled = set(
            (
                await self.session.execute(
                    select(MorphologySource.id).where(
                        MorphologySource.is_enabled.is_(True)
                    )
                )
            ).scalars()
        )
        grouped: dict[tuple[uuid.UUID, int], dict[uuid.UUID, set[uuid.UUID]]] = (
            defaultdict(lambda: defaultdict(set))
        )
        linked: dict[tuple[uuid.UUID, int], uuid.UUID] = {}
        # كل الكلمات التي لها تحليل — حتى ما لا جذر له (لتمييز «لا جذر» عن «لا تحليل»)
        for start in range(0, len(ayah_ids), _INSERT_BATCH):
            chunk = ayah_ids[start : start + _INSERT_BATCH]
            rows = (
                await self.session.execute(
                    select(
                        MorphologicalAnalysis.ayah_id,
                        MorphologicalAnalysis.word_number,
                        MorphologicalAnalysis.source_id,
                        MorphologicalAnalysis.root_id,
                        MorphologicalAnalysis.token_id,
                    ).where(MorphologicalAnalysis.ayah_id.in_(chunk))
                )
            ).all()
            for ayah_id, word_number, source_id, root_id, token_id in rows:
                if source_id not in enabled:
                    continue
                position = (ayah_id, word_number)
                bucket = grouped[position][source_id]
                if root_id is not None:
                    bucket.add(root_id)
                if token_id is not None:
                    linked[position] = token_id
        return (
            {
                position: {sid: frozenset(roots) for sid, roots in per_source.items()}
                for position, per_source in grouped.items()
            },
            linked,
        )

    async def rebuild_occurrences(
        self,
        version_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        surahs: set[int] | None = None,
    ) -> dict:
        """يعيد بناء `root_occurrences` اشتقاقًا من التحليلات والقرارات.

        الكلمة المختلَف عليها بين المصادر لا تُنتج موضعًا حتى تُقرَّر.
        `surahs` يحصر الحذف وإعادة البناء في نطاقها فلا تُمس بقية المصحف."""
        version_id = version_id or await self._active_version_id()
        ayahs = await self._ayah_rows(version_id, surahs)
        ayah_ids = [row[0] for row in ayahs]

        per_position, linked_tokens = await self._source_root_sets(ayah_ids)
        if not per_position:
            if surahs is None:
                raise MorphologyError(
                    "NO_ANALYSES", "لا توجد تحليلات صرفية مستوردة لهذا الإصدار."
                )
            # نطاق محصور بلا تحليل: لا شيء يُشتق ولا شيء يُمس
            return {
                "positions": 0,
                "human_decision": 0,
                "source_agreement": 0,
                "single_source": 0,
                "unresolved_conflicts": 0,
                "no_root": 0,
                "occurrences": 0,
                "ayahs_rebuilt": 0,
                "ayahs_untouched": len(ayah_ids),
            }
        decisions = await self._decision_map(ayah_ids)

        # القرار البشري المعتمد ينفَّذ ولو لم يحلّل الموضعَ أي مصدر مفعَّل:
        # هو أعلى من المصدر لا تابع له، وإلا ضاع القرار بتعطيل مصدر.
        for position in decisions:
            per_position.setdefault(position, {})

        rows: list[dict] = []
        counters = {
            "positions": len(per_position),
            "human_decision": 0,
            "source_agreement": 0,
            "single_source": 0,
            "unresolved_conflicts": 0,
            "no_root": 0,
        }
        for position, per_source in sorted(
            per_position.items(), key=lambda item: (str(item[0][0]), item[0][1])
        ):
            ayah_id, word_number = position
            if position in decisions:
                chosen = decisions[position]
                derivation = RootDerivation.HUMAN_DECISION
                counters["human_decision"] += 1
            else:
                distinct = set(per_source.values())
                if len(distinct) > 1:
                    counters["unresolved_conflicts"] += 1
                    continue
                chosen = next(iter(distinct))
                if len(per_source) > 1:
                    derivation = RootDerivation.SOURCE_AGREEMENT
                    counters["source_agreement"] += 1
                else:
                    derivation = RootDerivation.SINGLE_SOURCE
                    counters["single_source"] += 1

            if not chosen:
                counters["no_root"] += 1
                continue
            token_id = linked_tokens.get(position)
            for root_id in chosen:
                rows.append(
                    {
                        "id": uuid.uuid4(),
                        "root_id": root_id,
                        "ayah_id": ayah_id,
                        "word_number": word_number,
                        "is_highlight_safe": token_id is not None,
                        "token_id": token_id,
                        "derivation": derivation.value,
                    }
                )

        # الحذف محصور بالآيات التي لها تحليل فعلًا: إعادة اشتقاق نطاق لم
        # يُستورد تحليله يجب ألا تمحو مواضعه المبذورة بلا بديل.
        analysed_ayah_ids = sorted(
            {position[0] for position in per_position}, key=str
        )
        for start in range(0, len(analysed_ayah_ids), _INSERT_BATCH):
            await self.session.execute(
                delete(RootOccurrence).where(
                    RootOccurrence.ayah_id.in_(
                        analysed_ayah_ids[start : start + _INSERT_BATCH]
                    )
                )
            )
        await self._bulk_insert(RootOccurrence, rows)
        counters["ayahs_rebuilt"] = len(analysed_ayah_ids)
        counters["ayahs_untouched"] = len(ayah_ids) - len(analysed_ayah_ids)

        counters["occurrences"] = len(rows)
        record_audit(
            self.session,
            action="morphology_rebuild_occurrences",
            entity_type="quran_text_version",
            entity_id=version_id,
            actor_id=actor_id,
            new_data=counters,
        )
        await self.session.commit()
        return counters

    # ---- 5) عرض التحليل للباحث ------------------------------------------
    async def ayah_analysis(self, surah: int, ayah: int) -> dict:
        version_id = await self._active_version_id()
        row = (
            await self.session.execute(
                select(Ayah.id, Ayah.uthmani_text).where(
                    Ayah.text_version_id == version_id,
                    Ayah.surah_number == surah,
                    Ayah.ayah_number == ayah,
                )
            )
        ).first()
        if row is None:
            raise MorphologyError("AYAH_NOT_FOUND", "الآية غير موجودة في الإصدار المفعَّل.")
        ayah_id, text = row
        surah_name = await self.session.scalar(
            select(Surah.arabic_name).where(Surah.number == surah)
        )

        tokens = (
            await self.session.execute(
                select(Token).where(Token.ayah_id == ayah_id).order_by(Token.word_number)
            )
        ).scalars().all()

        analyses = (
            await self.session.execute(
                select(MorphologicalAnalysis, MorphologySource.code, Root.display_root)
                .join(
                    MorphologySource,
                    MorphologySource.id == MorphologicalAnalysis.source_id,
                )
                .outerjoin(Root, Root.id == MorphologicalAnalysis.root_id)
                .where(MorphologicalAnalysis.ayah_id == ayah_id)
                .order_by(
                    MorphologicalAnalysis.word_number,
                    MorphologySource.code,
                    MorphologicalAnalysis.segment_number,
                )
            )
        ).all()

        by_word: dict[int, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
        roots_by_word: dict[int, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for analysis, source_code, root_display in analyses:
            by_word[analysis.word_number][source_code].append(
                {
                    "segment_number": analysis.segment_number,
                    "form_source": analysis.form_source,
                    "tag": analysis.tag,
                    "pos": analysis.pos,
                    # السوابق واللواحق بلا POS صريح؛ وسمها هو قسمها
                    "pos_label": pos_label(analysis.pos or analysis.tag),
                    "features": analysis.features,
                    "lemma": analysis.lemma,
                    "lemma_index": analysis.lemma_index,
                    "root": root_display,
                    "source_root_text": analysis.source_root_text,
                    "is_linked_to_token": analysis.token_id is not None,
                }
            )
            if root_display:
                roots_by_word[analysis.word_number][source_code].add(root_display)

        decisions = {
            d.word_number: d
            for d in (
                await self.session.execute(
                    select(TokenRootDecision).where(TokenRootDecision.ayah_id == ayah_id)
                )
            ).scalars()
        }

        words = []
        for token in tokens:
            per_source = by_word.get(token.word_number, {})
            root_sets = {
                code: frozenset(values)
                for code, values in roots_by_word.get(token.word_number, {}).items()
            }
            decision = decisions.get(token.word_number)
            words.append(
                {
                    "word_number": token.word_number,
                    "surface_text": token.surface_text,
                    "char_start": token.char_start,
                    "char_end": token.char_end,
                    "analyses_by_source": per_source,
                    # «لا تحليل» غير «لا جذر»: الحرف والاسم العلم محلَّلان
                    # ولا جذر لهما، بخلاف كلمة لم يستوردها أي مصدر بعد.
                    "root_agreement": (
                        "no_analysis"
                        if not per_source
                        else "no_root"
                        if not root_sets
                        else "conflict"
                        if len(set(root_sets.values())) > 1
                        else "single_source"
                        if len(root_sets) == 1
                        else "agreement"
                    ),
                    "decision": (
                        None
                        if decision is None
                        else {
                            "status": decision.status.value,
                            "rationale": decision.rationale,
                        }
                    ),
                }
            )

        return {
            "surah_number": surah,
            "surah_name": surah_name,
            "ayah_number": ayah,
            "uthmani_text": text,
            "word_count": len(tokens),
            "words": words,
            "notice": (
                "التحليل الصرفي منقول عن مصادره ومنسوب إليها، وحالته «مستورد — "
                "غير معتمد» ما لم يُذكر خلاف ذلك. نص الآية وحده هو المرجع."
            ),
        }

    # ---- 5ب) البحث بالصيغة الصرفية ---------------------------------------
    # الأبعاد القابلة للترشيح: اسم البُعد ← عمود الجدول
    SEARCH_DIMENSIONS = (
        "pos",
        "aspect",
        "verb_form",
        "voice",
        "mood",
        "person",
        "gender",
        "grammatical_number",
        "case_marking",
        "definiteness",
        "nominal_form",
    )

    async def search_analyses(
        self,
        filters: dict[str, str | None],
        root_query: str | None = None,
        lemma: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> dict:
        """يبحث في التحليل الصرفي بأبعاده.

        النتيجة **تحليل منقول** لا حكم منصة: كل صف يحمل مصدره وسماته
        الحرفية كما وردت. المصادر المعطَّلة مستبعدة."""
        from app.utils.arabic import normalize_root_input

        version_id = await self._active_version_id()
        if not any(filters.values()) and not root_query and not lemma:
            raise MorphologyError(
                "NO_FILTERS", "حدّد بُعدًا واحدًا على الأقل للبحث."
            )

        stmt = (
            select(
                Ayah.surah_number,
                Ayah.ayah_number,
                Surah.arabic_name,
                MorphologicalAnalysis.word_number,
                MorphologicalAnalysis.segment_number,
                MorphologicalAnalysis.pos,
                MorphologicalAnalysis.features,
                MorphologicalAnalysis.lemma,
                MorphologicalAnalysis.token_id,
                Root.display_root,
                MorphologySource.code,
                Token.surface_text,
            )
            .join(Ayah, Ayah.id == MorphologicalAnalysis.ayah_id)
            .join(Surah, Surah.number == Ayah.surah_number)
            .join(
                MorphologySource,
                MorphologySource.id == MorphologicalAnalysis.source_id,
            )
            .outerjoin(Root, Root.id == MorphologicalAnalysis.root_id)
            .outerjoin(Token, Token.id == MorphologicalAnalysis.token_id)
            .where(
                Ayah.text_version_id == version_id,
                MorphologySource.is_enabled.is_(True),
            )
        )

        for dimension, value in filters.items():
            if not value or dimension not in self.SEARCH_DIMENSIONS:
                continue
            column = getattr(MorphologicalAnalysis, dimension)
            if dimension == "verb_form" and value == "I":
                # المصدر لا يوسم الوزن المجرد صراحةً: غيابه هو علامته.
                # يُترجم الترشيح ولا يُخزَّن استنتاجًا في البيانات.
                stmt = stmt.where(
                    column.is_(None), MorphologicalAnalysis.pos == "V"
                )
            else:
                stmt = stmt.where(column == value)

        if root_query:
            key = normalize_root_input(root_query)
            if not key:
                raise MorphologyError("INVALID_ROOT", "مدخل الجذر غير صالح.")
            root_id = await self.session.scalar(
                select(Root.id).where(Root.normalized_root == key)
            )
            if root_id is None:
                raise MorphologyError("ROOT_NOT_FOUND", "لا يوجد جذر بهذا المدخل.")
            stmt = stmt.where(MorphologicalAnalysis.root_id == root_id)

        if lemma:
            stmt = stmt.where(MorphologicalAnalysis.lemma == lemma.strip())

        total = await self.session.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        rows = (
            await self.session.execute(
                stmt.order_by(
                    Ayah.surah_number,
                    Ayah.ayah_number,
                    MorphologicalAnalysis.word_number,
                    MorphologicalAnalysis.segment_number,
                )
                .offset(offset)
                .limit(limit)
            )
        ).all()

        items = []
        for (
            surah,
            ayah,
            surah_name,
            word,
            segment,
            pos,
            features,
            lemma_value,
            token_id,
            root_display,
            source_code,
            surface,
        ) in rows:
            items.append(
                {
                    "surah_number": surah,
                    "surah_name": surah_name,
                    "ayah_number": ayah,
                    "word_number": word,
                    "segment_number": segment,
                    "surface_text": surface,
                    "pos": pos,
                    "pos_label": pos_label(pos) if pos else None,
                    "lemma": lemma_value,
                    "root": root_display,
                    "source": source_code,
                    "features": features,
                    "is_linked_to_token": token_id is not None,
                }
            )

        return {
            "total": total or 0,
            "offset": offset,
            "limit": limit,
            "items": items,
            "notice": (
                "نتيجة بحث في تحليل صرفي منقول عن مصادره ومنسوب إليها، "
                "حالته «مستورد — غير معتمد» ما لم يُذكر خلاف ذلك. "
                "السمات معروضة حرفيًا كما وردت في المصدر."
            ),
        }

    # ---- 6) التعارضات والقرارات -----------------------------------------
    async def list_conflicts(self, offset: int = 0, limit: int = 20) -> dict:
        """يعدّد مواضع اختلاف المصادر.

        لا تُحمَّل التحليلات كلها: التعارض مستحيل إلا حيث حلَّل الموضعَ
        أكثرُ من مصدر مفعَّل، وهي فئة صغيرة تُنتقى في قاعدة البيانات أولًا."""
        version_id = await self._active_version_id()
        ayahs = await self._ayah_rows(version_id)
        ayah_info = {row[0]: (row[1], row[2]) for row in ayahs}

        multi_source_positions = (
            await self.session.execute(
                select(
                    MorphologicalAnalysis.ayah_id,
                    MorphologicalAnalysis.word_number,
                )
                .join(
                    MorphologySource,
                    MorphologySource.id == MorphologicalAnalysis.source_id,
                )
                .where(MorphologySource.is_enabled.is_(True))
                .group_by(
                    MorphologicalAnalysis.ayah_id,
                    MorphologicalAnalysis.word_number,
                )
                .having(func.count(func.distinct(MorphologicalAnalysis.source_id)) > 1)
            )
        ).all()
        candidate_ayah_ids = sorted(
            {ayah_id for ayah_id, _w in multi_source_positions}, key=str
        )
        if not candidate_ayah_ids:
            return {"total": 0, "offset": offset, "limit": limit, "items": []}

        per_position, _linked = await self._source_root_sets(candidate_ayah_ids)
        decisions = await self._decision_map(candidate_ayah_ids)
        candidates = set(multi_source_positions)

        conflicts = []
        for position, per_source in per_position.items():
            if position not in candidates:
                continue
            if len(set(per_source.values())) <= 1:
                continue
            ayah_id, word_number = position
            # التحليلات قد تعود لآيات إصدار آخر بعد تبديل الإصدار المفعَّل؛
            # تُتجاهل بدل أن ترفع خطأً يسقط المسار كله.
            if ayah_id not in ayah_info:
                continue
            surah, ayah_num = ayah_info[ayah_id]
            conflicts.append(
                {
                    "ayah_id": str(ayah_id),
                    "surah_number": surah,
                    "ayah_number": ayah_num,
                    "word_number": word_number,
                    "source_count": len(per_source),
                    "resolved": (ayah_id, word_number) in decisions,
                }
            )
        conflicts.sort(
            key=lambda c: (c["surah_number"], c["ayah_number"], c["word_number"])
        )
        return {
            "total": len(conflicts),
            "offset": offset,
            "limit": limit,
            "items": conflicts[offset : offset + limit],
        }

    async def propose_decision(
        self,
        surah: int,
        ayah: int,
        word_number: int,
        root_queries: list[str],
        rationale: str,
        actor_id: uuid.UUID,
    ) -> dict:
        from app.utils.arabic import normalize_root_input

        if not rationale or not rationale.strip():
            raise MorphologyError("RATIONALE_REQUIRED", "تعليل القرار مطلوب.")

        version_id = await self._active_version_id()
        ayah_id = await self.session.scalar(
            select(Ayah.id).where(
                Ayah.text_version_id == version_id,
                Ayah.surah_number == surah,
                Ayah.ayah_number == ayah,
            )
        )
        if ayah_id is None:
            raise MorphologyError("AYAH_NOT_FOUND", "الآية غير موجودة في الإصدار المفعَّل.")

        token_exists = await self.session.scalar(
            select(Token.id).where(
                Token.ayah_id == ayah_id, Token.word_number == word_number
            )
        )
        if token_exists is None:
            raise MorphologyError(
                "WORD_NOT_FOUND", "رقم الكلمة خارج نطاق كلمات الآية في ترميز المنصة."
            )

        root_ids: list[uuid.UUID] = []
        for query in root_queries:
            key = normalize_root_input(query)
            if not key:
                raise MorphologyError("INVALID_ROOT", f"جذر غير صالح: {query!r}")
            rid = await self.session.scalar(
                select(Root.id).where(Root.normalized_root == key)
            )
            if rid is None:
                raise MorphologyError("ROOT_NOT_FOUND", f"لا يوجد جذر بالمفتاح {key!r}")
            if rid not in root_ids:
                root_ids.append(rid)

        existing = await self.session.scalar(
            select(TokenRootDecision).where(
                TokenRootDecision.ayah_id == ayah_id,
                TokenRootDecision.word_number == word_number,
            )
        )
        if existing is not None and existing.status == RecordStatus.APPROVED:
            raise MorphologyError(
                "DECISION_EXISTS", "يوجد قرار معتمد لهذه الكلمة؛ يلزم تصحيح موثق."
            )
        if existing is not None:
            # اقتراح غير معتمد يُستبدل، ويُسجَّل استبداله حتى لا يضيع أثره
            record_audit(
                self.session,
                action="root_decision_replace",
                entity_type="token_root_decision",
                entity_id=existing.id,
                actor_id=actor_id,
                old_data={
                    "status": existing.status.value,
                    "rationale": existing.rationale,
                    "proposed_by": str(existing.proposed_by),
                },
            )
            await self.session.delete(existing)
            await self.session.flush()

        decision = TokenRootDecision(
            ayah_id=ayah_id,
            word_number=word_number,
            rationale=rationale.strip(),
            status=RecordStatus.UNDER_REVIEW,
            proposed_by=actor_id,
        )
        self.session.add(decision)
        await self.session.flush()
        for rid in root_ids:
            self.session.add(
                TokenRootDecisionRoot(decision_id=decision.id, root_id=rid)
            )

        record_audit(
            self.session,
            action="root_decision_propose",
            entity_type="token_root_decision",
            entity_id=decision.id,
            actor_id=actor_id,
            new_data={
                "surah": surah,
                "ayah": ayah,
                "word_number": word_number,
                "roots": [str(r) for r in root_ids],
            },
            reason=rationale.strip(),
        )
        await self.session.commit()
        return await self.get_decision(decision.id)

    async def approve_decision(
        self, decision_id: uuid.UUID, reviewer_id: uuid.UUID, note: str | None = None
    ) -> dict:
        decision = await self.session.get(TokenRootDecision, decision_id)
        if decision is None:
            raise MorphologyError("DECISION_NOT_FOUND", "القرار غير موجود.")
        if decision.status == RecordStatus.APPROVED:
            raise MorphologyError("ALREADY_APPROVED", "القرار معتمد بالفعل.")
        if decision.proposed_by == reviewer_id:
            raise MorphologyError(
                "SELF_REVIEW_FORBIDDEN",
                "لا يعتمد المراجع قراره؛ يلزم مراجع ثانٍ مستقل.",
            )
        decision.status = RecordStatus.APPROVED
        decision.approved_by = reviewer_id
        decision.approved_at = utcnow()
        decision.review_note = (note or "").strip() or None

        record_audit(
            self.session,
            action="root_decision_approve",
            entity_type="token_root_decision",
            entity_id=decision.id,
            actor_id=reviewer_id,
            new_data={"status": decision.status.value},
            reason=decision.review_note,
        )
        await self.session.commit()
        return await self.get_decision(decision.id)

    async def get_decision(self, decision_id: uuid.UUID) -> dict:
        decision = await self.session.get(TokenRootDecision, decision_id)
        if decision is None:
            raise MorphologyError("DECISION_NOT_FOUND", "القرار غير موجود.")
        position = (
            await self.session.execute(
                select(Ayah.surah_number, Ayah.ayah_number).where(
                    Ayah.id == decision.ayah_id
                )
            )
        ).first()
        roots = list(
            (
                await self.session.execute(
                    select(Root.display_root)
                    .join(
                        TokenRootDecisionRoot,
                        TokenRootDecisionRoot.root_id == Root.id,
                    )
                    .where(TokenRootDecisionRoot.decision_id == decision.id)
                    .order_by(Root.normalized_root)
                )
            ).scalars()
        )
        return {
            "id": str(decision.id),
            "surah_number": position[0] if position else None,
            "ayah_number": position[1] if position else None,
            "word_number": decision.word_number,
            "roots": roots,
            "rationale": decision.rationale,
            "status": decision.status.value,
            "proposed_by": str(decision.proposed_by),
            "approved_by": str(decision.approved_by) if decision.approved_by else None,
            "review_note": decision.review_note,
        }

    async def list_decisions(self, offset: int = 0, limit: int = 20) -> dict:
        total = await self.session.scalar(select(func.count(TokenRootDecision.id)))
        rows = (
            await self.session.execute(
                select(TokenRootDecision.id)
                .order_by(TokenRootDecision.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars()
        items = [await self.get_decision(rid) for rid in rows]
        return {"total": total or 0, "offset": offset, "limit": limit, "items": items}

    # ---- 7) الجذور الذهبية ----------------------------------------------
    async def seed_golden_cases(self, actor_id: uuid.UUID | None = None) -> dict:
        """يحمّل المواضع المرجعية من ملفها (عملية idempotent)."""
        if not GOLDEN_CASES_PATH.exists():
            raise MorphologyError("GOLDEN_FILE_MISSING", "ملف المواضع المرجعية مفقود.")
        data = json.loads(GOLDEN_CASES_PATH.read_text(encoding="utf-8"))
        existing = {
            (case.surah_number, case.ayah_number, case.word_number): case
            for case in (await self.session.execute(select(GoldenRootCase))).scalars()
        }
        added = 0
        in_file: set[tuple[int, int, int]] = set()
        for item in data["cases"]:
            key = (item["surah"], item["ayah"], item["word"])
            in_file.add(key)
            expected = ",".join(sorted(item["roots"]))
            case = existing.get(key)
            if case is None:
                case = GoldenRootCase(
                    surah_number=key[0], ayah_number=key[1], word_number=key[2]
                )
                self.session.add(case)
                added += 1
            case.expected_roots = expected
            case.citation = item["citation"]
            case.note = item.get("note")

        # الملف مولَّد وهو مصدر الحقيقة: موضع حُذف منه يُحذف من القاعدة،
        # وإلا بقيت مراسٍ لا يعرف أحد من أين جاءت ولا ماذا تحرس.
        removed = 0
        for key, case in existing.items():
            if key not in in_file:
                await self.session.delete(case)
                removed += 1

        record_audit(
            self.session,
            action="golden_cases_seed",
            entity_type="golden_root_case",
            actor_id=actor_id,
            new_data={"total": len(in_file), "added": added, "removed": removed},
        )
        await self.session.commit()
        return {"total": len(in_file), "added": added, "removed": removed}

    async def golden_check(self) -> dict:
        version_id = await self._active_version_id()
        cases = (
            await self.session.execute(
                select(GoldenRootCase).order_by(
                    GoldenRootCase.surah_number,
                    GoldenRootCase.ayah_number,
                    GoldenRootCase.word_number,
                )
            )
        ).scalars().all()
        if not cases:
            return {"total": 0, "passed": 0, "failed": 0, "failures": [], "cases": []}

        results = []
        failures = []
        for case in cases:
            ayah_id = await self.session.scalar(
                select(Ayah.id).where(
                    Ayah.text_version_id == version_id,
                    Ayah.surah_number == case.surah_number,
                    Ayah.ayah_number == case.ayah_number,
                )
            )
            actual: set[str] = set()
            if ayah_id is not None:
                actual = {
                    key
                    for key in (
                        await self.session.execute(
                            select(Root.normalized_root)
                            .join(RootOccurrence, RootOccurrence.root_id == Root.id)
                            .where(
                                RootOccurrence.ayah_id == ayah_id,
                                RootOccurrence.word_number == case.word_number,
                            )
                        )
                    ).scalars()
                }
            expected = case.expected_set
            ok = actual == expected
            entry = {
                "surah_number": case.surah_number,
                "ayah_number": case.ayah_number,
                "word_number": case.word_number,
                "expected": sorted(expected),
                "actual": sorted(actual),
                "citation": case.citation,
                "note": case.note,
                "passed": ok,
            }
            results.append(entry)
            if not ok:
                failures.append(entry)

        return {
            "total": len(results),
            "passed": len(results) - len(failures),
            "failed": len(failures),
            "failures": failures,
            "cases": results,
        }
