"""خدمة المصادر والاستشهادات والادعاءات (المرحلة E).

القواعد المفروضة هنا لا في الواجهة:

  1. مصدر بلا طبعة أو بلا رخصة لا يُقبل (سياسة 8).
  2. لا يتحقق من المصدر مُدخِله (فصل الإدخال عن التحقق).
  3. لا يُرفع ادعاء إلى المراجعة بلا دليل مؤيد من مصدر متحقَّق منه (سياسة 9).
  4. لا يعتمد صاحب الادعاء ادعاءه، ويلزم مراجعان مستقلان (سياسة 6 و7).
  5. الدليل المعارض يُحفظ ويُعرض ولا يمنع الاعتماد — يوثَّق الخلاف.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.audit import record_audit
from app.db.base import utcnow
from app.models.enums import ConfidenceLevel, RecordStatus
from app.models.language import Root
from app.models.quran import Ayah, QuranTextVersion
from app.models.scholarship import (
    Citation,
    CitationStance,
    Claim,
    ClaimCitation,
    ClaimSubject,
    ClaimType,
    SourceWork,
    WorkType,
)
from app.models.user import User
from app.utils.arabic import normalize_root_input

# الأدوار المؤهلة للتحقق من المصادر واعتماد الادعاءات
SOURCE_VERIFIER_ROLES = {"quality_manager", "tech_admin", "sharia_reviewer"}
CLAIM_REVIEWER_ROLES = {
    "linguistic_reviewer",
    "sharia_reviewer",
    "quality_manager",
    "arbitration_committee",
}


class ScholarshipError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message


class ScholarshipService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- المصادر ---------------------------------------------------------
    @staticmethod
    def _source_dict(work: SourceWork) -> dict:
        return {
            "id": str(work.id),
            "code": work.code,
            "title": work.title,
            "author": work.author,
            "work_type": work.work_type.value,
            "edition": work.edition,
            "publisher": work.publisher,
            "publication_year": work.publication_year,
            "isbn": work.isbn,
            "language": work.language,
            "license_note": work.license_note,
            "access_url": work.access_url,
            "status": work.status.value,
            "is_verified": work.is_verified,
            "added_by": str(work.added_by),
            "verified_by": str(work.verified_by) if work.verified_by else None,
            "rejection_reason": work.rejection_reason,
        }

    async def add_source(self, data: dict, actor_id: uuid.UUID) -> dict:
        for field in ("code", "title", "author", "edition", "license_note"):
            if not str(data.get(field, "")).strip():
                raise ScholarshipError(
                    "SOURCE_INCOMPLETE",
                    "المصدر يلزمه رمز وعنوان ومؤلف وطبعة ورخصة — "
                    "لا يُقبل مصدر مجهول الطبعة أو بلا إذن.",
                )
        exists = await self.session.scalar(
            select(SourceWork.id).where(SourceWork.code == data["code"].strip())
        )
        if exists:
            raise ScholarshipError("SOURCE_CONFLICT", "رمز المصدر مستخدم بالفعل.")

        work = SourceWork(
            code=data["code"].strip(),
            title=data["title"].strip(),
            author=data["author"].strip(),
            work_type=WorkType(data.get("work_type", WorkType.OTHER.value)),
            edition=data["edition"].strip(),
            publisher=(data.get("publisher") or None),
            publication_year=data.get("publication_year"),
            isbn=(data.get("isbn") or None),
            language=data.get("language") or "ar",
            license_note=data["license_note"].strip(),
            access_url=(data.get("access_url") or None),
            notes=(data.get("notes") or None),
            status=RecordStatus.DRAFT,
            added_by=actor_id,
        )
        self.session.add(work)
        await self.session.flush()
        record_audit(
            self.session,
            action="source_add",
            entity_type="source_work",
            entity_id=work.id,
            actor_id=actor_id,
            new_data={"code": work.code, "title": work.title, "edition": work.edition},
        )
        await self.session.commit()
        await self.session.refresh(work)
        return self._source_dict(work)

    async def _require_source(self, source_id: uuid.UUID) -> SourceWork:
        work = await self.session.get(SourceWork, source_id)
        if work is None:
            raise ScholarshipError("SOURCE_NOT_FOUND", "المصدر غير موجود.")
        return work

    async def verify_source(
        self, source_id: uuid.UUID, verifier_id: uuid.UUID
    ) -> dict:
        work = await self._require_source(source_id)
        if work.added_by == verifier_id:
            raise ScholarshipError(
                "SELF_VERIFICATION_FORBIDDEN",
                "لا يتحقق من المصدر مُدخِله؛ يلزم متحقِّق مستقل.",
            )
        if work.status == RecordStatus.APPROVED:
            raise ScholarshipError("ALREADY_VERIFIED", "المصدر متحقَّق منه بالفعل.")
        work.status = RecordStatus.APPROVED
        work.verified_by = verifier_id
        work.verified_at = utcnow()
        work.rejection_reason = None
        record_audit(
            self.session,
            action="source_verify",
            entity_type="source_work",
            entity_id=work.id,
            actor_id=verifier_id,
        )
        await self.session.commit()
        await self.session.refresh(work)
        return self._source_dict(work)

    async def reject_source(
        self, source_id: uuid.UUID, verifier_id: uuid.UUID, reason: str
    ) -> dict:
        if not reason or not reason.strip():
            raise ScholarshipError("REASON_REQUIRED", "سبب الرفض مطلوب.")
        work = await self._require_source(source_id)
        if work.added_by == verifier_id:
            raise ScholarshipError(
                "SELF_VERIFICATION_FORBIDDEN", "لا يفصل في المصدر مُدخِله."
            )
        work.status = RecordStatus.REJECTED
        work.rejection_reason = reason.strip()
        work.verified_by = verifier_id
        work.verified_at = utcnow()
        record_audit(
            self.session,
            action="source_reject",
            entity_type="source_work",
            entity_id=work.id,
            actor_id=verifier_id,
            reason=reason.strip(),
        )
        await self.session.commit()
        await self.session.refresh(work)
        return self._source_dict(work)

    async def list_sources(self, offset: int = 0, limit: int = 20) -> dict:
        total = await self.session.scalar(select(func.count(SourceWork.id)))
        rows = (
            await self.session.execute(
                select(SourceWork)
                .order_by(SourceWork.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars()
        return {
            "total": total or 0,
            "offset": offset,
            "limit": limit,
            "items": [self._source_dict(w) for w in rows],
        }

    # ---- الاستشهادات -----------------------------------------------------
    async def add_citation(self, data: dict, actor_id: uuid.UUID) -> dict:
        if not str(data.get("locator", "")).strip():
            raise ScholarshipError(
                "LOCATOR_REQUIRED",
                "الاستشهاد يلزمه موضع دقيق (جزء/صفحة/مادة) — "
                "النسبة بلا موضع ليست توثيقًا.",
            )
        work = await self._require_source(uuid.UUID(str(data["source_work_id"])))
        if not (data.get("quoted_text") or data.get("paraphrase")):
            raise ScholarshipError(
                "CITATION_EMPTY", "يلزم نص منقول أو تلخيص للاستشهاد."
            )

        citation = Citation(
            source_work_id=work.id,
            locator=str(data["locator"]).strip(),
            quoted_text=(data.get("quoted_text") or None),
            paraphrase=(data.get("paraphrase") or None),
            added_by=actor_id,
        )
        self.session.add(citation)
        await self.session.flush()
        record_audit(
            self.session,
            action="citation_add",
            entity_type="citation",
            entity_id=citation.id,
            actor_id=actor_id,
            new_data={"source": work.code, "locator": citation.locator},
        )
        await self.session.commit()
        return await self.get_citation(citation.id)

    async def get_citation(self, citation_id: uuid.UUID) -> dict:
        row = (
            await self.session.execute(
                select(Citation, SourceWork)
                .join(SourceWork, SourceWork.id == Citation.source_work_id)
                .where(Citation.id == citation_id)
            )
        ).first()
        if row is None:
            raise ScholarshipError("CITATION_NOT_FOUND", "الاستشهاد غير موجود.")
        citation, work = row
        return {
            "id": str(citation.id),
            "locator": citation.locator,
            "quoted_text": citation.quoted_text,
            "paraphrase": citation.paraphrase,
            "source": {
                "id": str(work.id),
                "code": work.code,
                "title": work.title,
                "author": work.author,
                "edition": work.edition,
                "is_verified": work.is_verified,
                "status": work.status.value,
            },
        }

    # ---- الادعاءات -------------------------------------------------------
    async def _resolve_subject(self, data: dict) -> dict:
        subject = ClaimSubject(data["subject_type"])
        fields: dict = {
            "subject_type": subject,
            "root_id": None,
            "ayah_id": None,
            "word_number": None,
            "lemma": None,
        }
        if subject == ClaimSubject.ROOT:
            key = normalize_root_input(str(data.get("root") or ""))
            if not key:
                raise ScholarshipError("SUBJECT_INVALID", "جذر الادعاء غير صالح.")
            root_id = await self.session.scalar(
                select(Root.id).where(Root.normalized_root == key)
            )
            if root_id is None:
                raise ScholarshipError("ROOT_NOT_FOUND", f"لا يوجد جذر بالمفتاح {key!r}")
            fields["root_id"] = root_id
        elif subject == ClaimSubject.LEMMA:
            lemma = str(data.get("lemma") or "").strip()
            if not lemma:
                raise ScholarshipError("SUBJECT_INVALID", "أصل الادعاء مطلوب.")
            fields["lemma"] = lemma
        else:  # WORD أو AYAH
            surah, ayah = data.get("surah"), data.get("ayah")
            if not surah or not ayah:
                raise ScholarshipError("SUBJECT_INVALID", "موضع الآية مطلوب.")
            # الموضع يُربط بآية الإصدار المفعَّل حصرًا
            ayah_id = await self.session.scalar(
                select(Ayah.id)
                .join(
                    QuranTextVersion,
                    QuranTextVersion.id == Ayah.text_version_id,
                )
                .where(
                    QuranTextVersion.is_active.is_(True),
                    Ayah.surah_number == int(surah),
                    Ayah.ayah_number == int(ayah),
                )
            )
            if ayah_id is None:
                raise ScholarshipError(
                    "AYAH_NOT_FOUND", "الآية غير موجودة في الإصدار المفعَّل."
                )
            fields["ayah_id"] = ayah_id
            if subject == ClaimSubject.WORD:
                word_number = data.get("word_number")
                if not word_number:
                    raise ScholarshipError("SUBJECT_INVALID", "رقم الكلمة مطلوب.")
                fields["word_number"] = int(word_number)
        return fields

    async def create_claim(self, data: dict, actor_id: uuid.UUID) -> dict:
        statement = str(data.get("statement", "")).strip()
        if len(statement) < 20:
            raise ScholarshipError(
                "STATEMENT_TOO_SHORT", "نص الادعاء قصير جدًا ليكون دعوى علمية."
            )
        fields = await self._resolve_subject(data)
        claim = Claim(
            statement=statement,
            claim_type=ClaimType(data.get("claim_type", ClaimType.SEMANTIC.value)),
            status=RecordStatus.DRAFT,
            confidence=ConfidenceLevel.LOW,
            author_id=actor_id,
            **fields,
        )
        self.session.add(claim)
        await self.session.flush()
        record_audit(
            self.session,
            action="claim_create",
            entity_type="claim",
            entity_id=claim.id,
            actor_id=actor_id,
            new_data={"subject_type": claim.subject_type.value},
        )
        await self.session.commit()
        return await self.get_claim(claim.id)

    async def _require_claim(self, claim_id: uuid.UUID) -> Claim:
        claim = await self.session.get(Claim, claim_id)
        if claim is None:
            raise ScholarshipError("CLAIM_NOT_FOUND", "الادعاء غير موجود.")
        return claim

    async def attach_citation(
        self,
        claim_id: uuid.UUID,
        citation_id: uuid.UUID,
        stance: str,
        note: str | None,
        actor_id: uuid.UUID,
    ) -> dict:
        claim = await self._require_claim(claim_id)
        if claim.status in (RecordStatus.APPROVED, RecordStatus.PUBLISHED):
            raise ScholarshipError(
                "CLAIM_LOCKED", "الادعاء المعتمد لا تُضاف أدلته إلا بتصحيح موثق."
            )
        # الدليل جزء من دعوى صاحبها مسؤول عنها: لا يعدّلها مستخدم آخر
        actor = await self.session.get(User, actor_id)
        is_reviewer = bool(actor and (actor.role_values & CLAIM_REVIEWER_ROLES))
        if claim.author_id != actor_id and not is_reviewer:
            raise ScholarshipError(
                "NOT_CLAIM_AUTHOR", "أدلة الادعاء يديرها صاحبه أو مراجع مختص."
            )
        citation = await self.session.get(Citation, citation_id)
        if citation is None:
            raise ScholarshipError("CITATION_NOT_FOUND", "الاستشهاد غير موجود.")
        duplicate = await self.session.scalar(
            select(ClaimCitation.id).where(
                ClaimCitation.claim_id == claim.id,
                ClaimCitation.citation_id == citation.id,
            )
        )
        if duplicate:
            raise ScholarshipError("EVIDENCE_EXISTS", "هذا الدليل مرتبط بالادعاء أصلًا.")

        link = ClaimCitation(
            claim_id=claim.id,
            citation_id=citation.id,
            stance=CitationStance(stance),
            note=(note or None),
            added_by=actor_id,
        )
        self.session.add(link)
        record_audit(
            self.session,
            action="claim_evidence_add",
            entity_type="claim",
            entity_id=claim.id,
            actor_id=actor_id,
            new_data={"citation_id": str(citation.id), "stance": stance},
        )
        await self.session.commit()
        return await self.get_claim(claim.id)

    async def _supporting_verified_count(self, claim_id: uuid.UUID) -> int:
        return (
            await self.session.scalar(
                select(func.count(ClaimCitation.id))
                .join(Citation, Citation.id == ClaimCitation.citation_id)
                .join(SourceWork, SourceWork.id == Citation.source_work_id)
                .where(
                    ClaimCitation.claim_id == claim_id,
                    ClaimCitation.stance == CitationStance.SUPPORTS,
                    SourceWork.status == RecordStatus.APPROVED,
                    SourceWork.verified_by.is_not(None),
                )
            )
            or 0
        )

    async def submit_claim(self, claim_id: uuid.UUID, actor_id: uuid.UUID) -> dict:
        claim = await self._require_claim(claim_id)
        if claim.author_id != actor_id:
            raise ScholarshipError(
                "NOT_CLAIM_AUTHOR", "لا يرفع الادعاء إلى المراجعة إلا صاحبه."
            )
        if claim.status != RecordStatus.DRAFT:
            raise ScholarshipError("CLAIM_NOT_DRAFT", "الادعاء ليس مسودة.")
        if await self._supporting_verified_count(claim.id) == 0:
            raise ScholarshipError(
                "EVIDENCE_REQUIRED",
                "لا يُرفع ادعاء بلا دليل مؤيد واحد على الأقل من مصدر متحقَّق منه.",
            )
        claim.status = RecordStatus.UNDER_REVIEW
        record_audit(
            self.session,
            action="claim_submit",
            entity_type="claim",
            entity_id=claim.id,
            actor_id=actor_id,
        )
        await self.session.commit()
        return await self.get_claim(claim.id)

    async def approve_claim(self, claim_id: uuid.UUID, reviewer_id: uuid.UUID) -> dict:
        claim = await self._require_claim(claim_id)
        if claim.status != RecordStatus.UNDER_REVIEW:
            raise ScholarshipError(
                "CLAIM_NOT_UNDER_REVIEW", "لا يُعتمد إلا ادعاء قيد المراجعة."
            )
        if claim.author_id == reviewer_id:
            raise ScholarshipError(
                "SELF_REVIEW_FORBIDDEN", "لا يعتمد الباحث ادعاءه بنفسه."
            )
        if claim.approved_by_first is None:
            claim.approved_by_first = reviewer_id
            action = "claim_approve_first"
        else:
            if claim.approved_by_first == reviewer_id:
                raise ScholarshipError(
                    "SECOND_REVIEW_REQUIRED",
                    "يلزم مراجع ثانٍ مختلف عن الأول.",
                )
            claim.approved_by_second = reviewer_id
            claim.status = RecordStatus.APPROVED
            claim.approved_at = utcnow()
            claim.confidence = ConfidenceLevel.HIGH
            action = "claim_approve_second"

        record_audit(
            self.session,
            action=action,
            entity_type="claim",
            entity_id=claim.id,
            actor_id=reviewer_id,
        )
        await self.session.commit()
        return await self.get_claim(claim.id)

    async def dispute_claim(
        self, claim_id: uuid.UUID, reviewer_id: uuid.UUID, reason: str
    ) -> dict:
        if not reason or not reason.strip():
            raise ScholarshipError("REASON_REQUIRED", "سبب الخلاف مطلوب وموثق.")
        claim = await self._require_claim(claim_id)
        if claim.author_id == reviewer_id:
            raise ScholarshipError(
                "SELF_REVIEW_FORBIDDEN", "لا يفصل الباحث في ادعائه."
            )
        claim.status = RecordStatus.DISPUTED
        claim.confidence = ConfidenceLevel.DISPUTED
        claim.resolution_note = reason.strip()
        record_audit(
            self.session,
            action="claim_dispute",
            entity_type="claim",
            entity_id=claim.id,
            actor_id=reviewer_id,
            reason=reason.strip(),
        )
        await self.session.commit()
        return await self.get_claim(claim.id)

    async def get_claim(self, claim_id: uuid.UUID) -> dict:
        claim = await self._require_claim(claim_id)
        subject: dict = {"type": claim.subject_type.value}
        if claim.root_id:
            subject["root"] = await self.session.scalar(
                select(Root.display_root).where(Root.id == claim.root_id)
            )
        if claim.ayah_id:
            position = (
                await self.session.execute(
                    select(Ayah.surah_number, Ayah.ayah_number).where(
                        Ayah.id == claim.ayah_id
                    )
                )
            ).first()
            if position:
                subject["surah"], subject["ayah"] = position
        if claim.word_number:
            subject["word_number"] = claim.word_number
        if claim.lemma:
            subject["lemma"] = claim.lemma

        evidence_rows = (
            await self.session.execute(
                select(ClaimCitation, Citation, SourceWork)
                .join(Citation, Citation.id == ClaimCitation.citation_id)
                .join(SourceWork, SourceWork.id == Citation.source_work_id)
                .where(ClaimCitation.claim_id == claim.id)
                .order_by(ClaimCitation.created_at)
            )
        ).all()
        evidence = [
            {
                "citation_id": str(citation.id),
                "stance": link.stance.value,
                "note": link.note,
                "locator": citation.locator,
                "quoted_text": citation.quoted_text,
                "paraphrase": citation.paraphrase,
                "source": {
                    "code": work.code,
                    "title": work.title,
                    "author": work.author,
                    "edition": work.edition,
                    "is_verified": work.is_verified,
                },
            }
            for link, citation, work in evidence_rows
        ]

        author_name = await self.session.scalar(
            select(User.display_name).where(User.id == claim.author_id)
        )
        return {
            "id": str(claim.id),
            "statement": claim.statement,
            "claim_type": claim.claim_type.value,
            "subject": subject,
            "status": claim.status.value,
            "confidence": claim.confidence.value,
            "author": {"id": str(claim.author_id), "display_name": author_name},
            "approved_by_first": (
                str(claim.approved_by_first) if claim.approved_by_first else None
            ),
            "approved_by_second": (
                str(claim.approved_by_second) if claim.approved_by_second else None
            ),
            "resolution_note": claim.resolution_note,
            "evidence": evidence,
            "supporting_count": sum(1 for e in evidence if e["stance"] == "supports"),
            "opposing_count": sum(1 for e in evidence if e["stance"] == "opposes"),
            "notice": (
                "الادعاء رأي باحث موثق بأدلته، وليس نصًا قرآنيًا ولا حكمًا "
                "شرعيًا. حالته وأدلته المؤيدة والمعارضة معروضة كاملة."
            ),
        }

    async def list_claims(
        self, offset: int = 0, limit: int = 20, status: str | None = None
    ) -> dict:
        stmt = select(Claim.id).order_by(Claim.created_at.desc())
        count_stmt = select(func.count(Claim.id))
        if status:
            stmt = stmt.where(Claim.status == RecordStatus(status))
            count_stmt = count_stmt.where(Claim.status == RecordStatus(status))
        total = await self.session.scalar(count_stmt)
        ids = (await self.session.execute(stmt.offset(offset).limit(limit))).scalars()
        return {
            "total": total or 0,
            "offset": offset,
            "limit": limit,
            "items": [await self.get_claim(cid) for cid in ids],
        }
