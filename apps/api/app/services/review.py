"""خدمة صندوق المراجعة والخلافات والتصحيحات (المرحلة G).

القواعد المفروضة هنا:

  1. لا يُكلَّف أحد بمراجعة عمله (SELF_REVIEW_FORBIDDEN).
  2. لا يُكلَّف من أقرّ بتضارب مصلحة في هذا الكيان (CONFLICT_OF_INTEREST).
  3. الخلاف يبقى مفتوحًا ظاهرًا، ولا يحسمه رافعه، ولا يُغلق بلا تعليل.
  4. التصحيح يحفظ «قبل» و«بعد»، ويعتمده غير مقترحه.
  5. **تصحيح ادعاء معتمد يُبطل اعتماده** ويعيده إلى المراجعة — المحتوى
     تغيّر فلا تنتقل إليه شهادة المراجعين السابقة.
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.audit import record_audit
from app.db.base import utcnow
from app.models.enums import ConfidenceLevel, RecordStatus
from app.models.morphology import TokenRootDecision
from app.models.project import ReportVersion
from app.models.review import (
    AssignmentStatus,
    Correction,
    CorrectionStatus,
    Dispute,
    DisputeStatus,
    ReviewAssignment,
    ReviewComment,
    ReviewTarget,
)
from app.models.scholarship import Claim, SourceWork
from app.models.user import ConflictOfInterestDeclaration, User

ASSIGNER_ROLES = {"quality_manager", "tech_admin", "arbitration_committee"}
ARBITER_ROLES = {"arbitration_committee", "quality_manager"}


class ReviewError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message


def coi_subject(target_type: ReviewTarget, target_id: uuid.UUID) -> str:
    """الصيغة القياسية لموضوع إقرار تضارب المصالح."""
    return f"{target_type.value}:{target_id}"


class ReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- الكيانات المراجَعة ----------------------------------------------
    async def _target_owner(
        self, target_type: ReviewTarget, target_id: uuid.UUID
    ) -> uuid.UUID:
        """صاحب العمل — لا يجوز أن يراجعه."""
        if target_type == ReviewTarget.CLAIM:
            owner = await self.session.scalar(
                select(Claim.author_id).where(Claim.id == target_id)
            )
        elif target_type == ReviewTarget.SOURCE_WORK:
            owner = await self.session.scalar(
                select(SourceWork.added_by).where(SourceWork.id == target_id)
            )
        elif target_type == ReviewTarget.ROOT_DECISION:
            owner = await self.session.scalar(
                select(TokenRootDecision.proposed_by).where(
                    TokenRootDecision.id == target_id
                )
            )
        else:
            owner = await self.session.scalar(
                select(ReportVersion.published_by).where(
                    ReportVersion.id == target_id
                )
            )
        if owner is None:
            raise ReviewError("TARGET_NOT_FOUND", "الكيان المطلوب مراجعته غير موجود.")
        return owner

    async def _has_conflict(
        self, user_id: uuid.UUID, target_type: ReviewTarget, target_id: uuid.UUID
    ) -> bool:
        subject = coi_subject(target_type, target_id)
        found = await self.session.scalar(
            select(func.count(ConflictOfInterestDeclaration.id)).where(
                ConflictOfInterestDeclaration.user_id == user_id,
                ConflictOfInterestDeclaration.subject.in_([subject, str(target_id)]),
            )
        )
        return bool(found)

    async def declare_conflict(
        self,
        user_id: uuid.UUID,
        target_type: ReviewTarget,
        target_id: uuid.UUID,
        details: str,
    ) -> dict:
        if not details.strip():
            raise ReviewError("DETAILS_REQUIRED", "بيان تضارب المصلحة مطلوب.")
        await self._target_owner(target_type, target_id)  # يتحقق من وجود الكيان
        declaration = ConflictOfInterestDeclaration(
            user_id=user_id,
            subject=coi_subject(target_type, target_id),
            details=details.strip(),
        )
        self.session.add(declaration)
        record_audit(
            self.session,
            action="conflict_declare",
            entity_type=target_type.value,
            entity_id=target_id,
            actor_id=user_id,
            reason=details.strip(),
        )
        await self.session.commit()
        return {
            "subject": declaration.subject,
            "details": declaration.details,
            "user_id": str(user_id),
        }

    # ---- التكليفات -------------------------------------------------------
    @staticmethod
    def _assignment_dict(assignment: ReviewAssignment) -> dict:
        return {
            "id": str(assignment.id),
            "target_type": assignment.target_type.value,
            "target_id": str(assignment.target_id),
            "reviewer_id": str(assignment.reviewer_id),
            "assigned_by": str(assignment.assigned_by),
            "status": assignment.status.value,
            "decline_reason": assignment.decline_reason,
            "due_at": assignment.due_at.isoformat() if assignment.due_at else None,
        }

    async def assign(
        self,
        target_type: ReviewTarget,
        target_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        assigner: User,
    ) -> dict:
        owner = await self._target_owner(target_type, target_id)
        if reviewer_id == owner:
            raise ReviewError(
                "SELF_REVIEW_FORBIDDEN", "لا يُكلَّف صاحب العمل بمراجعة عمله."
            )
        reviewer = await self.session.get(User, reviewer_id)
        if reviewer is None or not reviewer.is_active:
            raise ReviewError("REVIEWER_NOT_FOUND", "المراجع غير موجود أو غير مفعَّل.")
        if await self._has_conflict(reviewer_id, target_type, target_id):
            raise ReviewError(
                "CONFLICT_OF_INTEREST",
                "المراجع أقرّ بتضارب مصلحة في هذا الكيان فلا يُكلَّف به.",
            )
        existing = await self.session.scalar(
            select(ReviewAssignment).where(
                ReviewAssignment.target_type == target_type,
                ReviewAssignment.target_id == target_id,
                ReviewAssignment.reviewer_id == reviewer_id,
            )
        )
        if existing is not None:
            raise ReviewError("ASSIGNMENT_EXISTS", "المراجع مكلَّف بهذا الكيان أصلًا.")

        assignment = ReviewAssignment(
            target_type=target_type,
            target_id=target_id,
            reviewer_id=reviewer_id,
            assigned_by=assigner.id,
        )
        self.session.add(assignment)
        await self.session.flush()
        record_audit(
            self.session,
            action="review_assign",
            entity_type=target_type.value,
            entity_id=target_id,
            actor_id=assigner.id,
            new_data={"reviewer_id": str(reviewer_id)},
        )
        await self.session.commit()
        await self.session.refresh(assignment)
        return self._assignment_dict(assignment)

    async def respond(
        self,
        assignment_id: uuid.UUID,
        reviewer: User,
        accept: bool,
        reason: str | None = None,
    ) -> dict:
        assignment = await self.session.get(ReviewAssignment, assignment_id)
        if assignment is None:
            raise ReviewError("ASSIGNMENT_NOT_FOUND", "التكليف غير موجود.")
        if assignment.reviewer_id != reviewer.id:
            raise ReviewError("NOT_ASSIGNEE", "هذا التكليف ليس لك.")
        if assignment.status != AssignmentStatus.PENDING:
            raise ReviewError("ASSIGNMENT_CLOSED", "التكليف لم يعد معلقًا.")
        if not accept and not (reason or "").strip():
            raise ReviewError("REASON_REQUIRED", "سبب الاعتذار مطلوب.")

        assignment.status = (
            AssignmentStatus.ACCEPTED if accept else AssignmentStatus.DECLINED
        )
        assignment.decline_reason = None if accept else reason.strip()
        record_audit(
            self.session,
            action="review_accept" if accept else "review_decline",
            entity_type=assignment.target_type.value,
            entity_id=assignment.target_id,
            actor_id=reviewer.id,
            reason=assignment.decline_reason,
        )
        await self.session.commit()
        await self.session.refresh(assignment)
        return self._assignment_dict(assignment)

    async def complete(self, assignment_id: uuid.UUID, reviewer: User) -> dict:
        assignment = await self.session.get(ReviewAssignment, assignment_id)
        if assignment is None:
            raise ReviewError("ASSIGNMENT_NOT_FOUND", "التكليف غير موجود.")
        if assignment.reviewer_id != reviewer.id:
            raise ReviewError("NOT_ASSIGNEE", "هذا التكليف ليس لك.")
        if assignment.status != AssignmentStatus.ACCEPTED:
            raise ReviewError("NOT_ACCEPTED", "يلزم قبول التكليف قبل إتمامه.")
        assignment.status = AssignmentStatus.COMPLETED
        assignment.completed_at = utcnow()
        record_audit(
            self.session,
            action="review_complete",
            entity_type=assignment.target_type.value,
            entity_id=assignment.target_id,
            actor_id=reviewer.id,
        )
        await self.session.commit()
        await self.session.refresh(assignment)
        return self._assignment_dict(assignment)

    async def my_queue(self, reviewer: User) -> list[dict]:
        rows = (
            await self.session.execute(
                select(ReviewAssignment)
                .where(
                    ReviewAssignment.reviewer_id == reviewer.id,
                    ReviewAssignment.status.in_(
                        [AssignmentStatus.PENDING, AssignmentStatus.ACCEPTED]
                    ),
                )
                .order_by(ReviewAssignment.created_at)
            )
        ).scalars()
        return [self._assignment_dict(a) for a in rows]

    # ---- التعليقات -------------------------------------------------------
    async def add_comment(
        self,
        target_type: ReviewTarget,
        target_id: uuid.UUID,
        body: str,
        author: User,
    ) -> dict:
        if not body.strip():
            raise ReviewError("BODY_REQUIRED", "نص التعليق مطلوب.")
        await self._target_owner(target_type, target_id)
        comment = ReviewComment(
            target_type=target_type,
            target_id=target_id,
            author_id=author.id,
            body=body.strip(),
        )
        self.session.add(comment)
        await self.session.flush()
        record_audit(
            self.session,
            action="review_comment",
            entity_type=target_type.value,
            entity_id=target_id,
            actor_id=author.id,
        )
        await self.session.commit()
        return {
            "id": str(comment.id),
            "body": comment.body,
            "author_id": str(author.id),
            "resolved": False,
        }

    async def list_thread(
        self, target_type: ReviewTarget, target_id: uuid.UUID
    ) -> dict:
        comments = (
            await self.session.execute(
                select(ReviewComment, User.display_name)
                .join(User, User.id == ReviewComment.author_id)
                .where(
                    ReviewComment.target_type == target_type,
                    ReviewComment.target_id == target_id,
                )
                .order_by(ReviewComment.created_at)
            )
        ).all()
        disputes = (
            await self.session.execute(
                select(Dispute)
                .where(
                    Dispute.target_type == target_type,
                    Dispute.target_id == target_id,
                )
                .order_by(Dispute.created_at)
            )
        ).scalars()
        assignments = (
            await self.session.execute(
                select(ReviewAssignment).where(
                    ReviewAssignment.target_type == target_type,
                    ReviewAssignment.target_id == target_id,
                )
            )
        ).scalars()
        return {
            "target_type": target_type.value,
            "target_id": str(target_id),
            "comments": [
                {
                    "id": str(comment.id),
                    "body": comment.body,
                    "author": name,
                    "resolved": comment.resolved_at is not None,
                    "created_at": comment.created_at.isoformat(),
                }
                for comment, name in comments
            ],
            "disputes": [self._dispute_dict(d) for d in disputes],
            "assignments": [self._assignment_dict(a) for a in assignments],
        }

    # ---- الخلافات --------------------------------------------------------
    @staticmethod
    def _dispute_dict(dispute: Dispute) -> dict:
        return {
            "id": str(dispute.id),
            "target_type": dispute.target_type.value,
            "target_id": str(dispute.target_id),
            "raised_by": str(dispute.raised_by),
            "reason": dispute.reason,
            "status": dispute.status.value,
            "resolution": dispute.resolution,
            "resolved_by": str(dispute.resolved_by) if dispute.resolved_by else None,
        }

    async def raise_dispute(
        self,
        target_type: ReviewTarget,
        target_id: uuid.UUID,
        reason: str,
        actor: User,
    ) -> dict:
        if len(reason.strip()) < 10:
            raise ReviewError("REASON_REQUIRED", "سبب الخلاف مطلوب ومفصَّل.")
        owner = await self._target_owner(target_type, target_id)
        if owner == actor.id:
            raise ReviewError(
                "SELF_DISPUTE_FORBIDDEN",
                "لا يرفع صاحب العمل خلافًا على عمله؛ يُصحّحه بتصحيح موثق.",
            )
        dispute = Dispute(
            target_type=target_type,
            target_id=target_id,
            raised_by=actor.id,
            reason=reason.strip(),
            status=DisputeStatus.OPEN,
        )
        self.session.add(dispute)
        await self.session.flush()

        # الادعاء المتنازع عليه يُوسم فورًا فلا يُعرض نتيجةً مستقرة.
        # المسودة لا تُوسم: هي ليست نتيجة أصلًا، ووسمها «مختلفًا فيه»
        # ينشرها للعموم في قائمة الخلافات — عكس المقصود تمامًا.
        if target_type == ReviewTarget.CLAIM:
            claim = await self.session.get(Claim, target_id)
            if claim is not None:
                if claim.status == RecordStatus.DRAFT:
                    raise ReviewError(
                        "CLAIM_IS_DRAFT",
                        "لا يُرفع خلاف على مسودة لم تُرفع للمراجعة بعد.",
                    )
                claim.status = RecordStatus.DISPUTED
                claim.confidence = ConfidenceLevel.DISPUTED

        record_audit(
            self.session,
            action="dispute_raise",
            entity_type=target_type.value,
            entity_id=target_id,
            actor_id=actor.id,
            reason=reason.strip(),
        )
        await self.session.commit()
        await self.session.refresh(dispute)
        return self._dispute_dict(dispute)

    async def resolve_dispute(
        self, dispute_id: uuid.UUID, resolution: str, arbiter: User
    ) -> dict:
        dispute = await self.session.get(Dispute, dispute_id)
        if dispute is None:
            raise ReviewError("DISPUTE_NOT_FOUND", "الخلاف غير موجود.")
        if dispute.status == DisputeStatus.RESOLVED:
            raise ReviewError("ALREADY_RESOLVED", "الخلاف محسوم بالفعل.")
        if dispute.raised_by == arbiter.id:
            raise ReviewError(
                "SELF_ARBITRATION_FORBIDDEN", "لا يحسم الخلافَ رافعُه."
            )
        # ولا يحسمه **صاحب المحلّ**. كان الشرط يستثني الرافع وحده، فمن
        # كتب الادعاء وحمل دور التحكيم يرفع الوسم عن عمله بنفسه — وهو
        # الاعتماد الذاتي عينه، وإن دخل من باب الخلاف لا باب الاعتماد.
        owner = await self._target_owner(dispute.target_type, dispute.target_id)
        if owner == arbiter.id:
            raise ReviewError(
                "SELF_ARBITRATION_FORBIDDEN",
                "لا يحسم الخلافَ صاحبُ العمل المختلَف فيه.",
            )
        if len(resolution.strip()) < 10:
            raise ReviewError("RESOLUTION_REQUIRED", "قرار الحسم يجب أن يكون معللًا.")

        dispute.status = DisputeStatus.RESOLVED
        dispute.resolution = resolution.strip()
        dispute.resolved_by = arbiter.id
        dispute.resolved_at = utcnow()

        # حسم الخلاف يخرج الادعاء من حالة «مختلف فيه» — وإلا بقي موسومًا
        # بها إلى الأبد. يعود إلى المراجعة لا إلى الاعتماد: المحتوى مرّ
        # باعتراض، فيلزم اعتماد جديد بمراجعَين.
        if dispute.target_type == ReviewTarget.CLAIM:
            others = await self.session.scalar(
                select(func.count(Dispute.id)).where(
                    Dispute.target_type == ReviewTarget.CLAIM,
                    Dispute.target_id == dispute.target_id,
                    Dispute.status != DisputeStatus.RESOLVED,
                    Dispute.id != dispute.id,
                )
            )
            claim = await self.session.get(Claim, dispute.target_id)
            if claim is not None and not others:
                claim.status = RecordStatus.UNDER_REVIEW
                claim.confidence = ConfidenceLevel.LOW
                claim.approved_by_first = None
                claim.approved_by_second = None
                claim.approved_at = None
                claim.resolution_note = resolution.strip()

        record_audit(
            self.session,
            action="dispute_resolve",
            entity_type=dispute.target_type.value,
            entity_id=dispute.target_id,
            actor_id=arbiter.id,
            reason=resolution.strip(),
        )
        await self.session.commit()
        await self.session.refresh(dispute)
        return self._dispute_dict(dispute)

    async def open_disputes(self) -> list[dict]:
        rows = (
            await self.session.execute(
                select(Dispute)
                .where(Dispute.status != DisputeStatus.RESOLVED)
                .order_by(Dispute.created_at)
            )
        ).scalars()
        return [self._dispute_dict(d) for d in rows]

    # ---- التصحيحات -------------------------------------------------------
    async def _snapshot(
        self, target_type: ReviewTarget, target_id: uuid.UUID
    ) -> str:
        if target_type == ReviewTarget.CLAIM:
            claim = await self.session.get(Claim, target_id)
            if claim is None:
                raise ReviewError("TARGET_NOT_FOUND", "الادعاء غير موجود.")
            payload = {
                "statement": claim.statement,
                "status": claim.status.value,
                "confidence": claim.confidence.value,
                "approved_by_first": str(claim.approved_by_first or ""),
                "approved_by_second": str(claim.approved_by_second or ""),
            }
        else:
            payload = {"target_type": target_type.value, "target_id": str(target_id)}
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _correction_dict(correction: Correction) -> dict:
        return {
            "id": str(correction.id),
            "target_type": correction.target_type.value,
            "target_id": str(correction.target_id),
            "description": correction.description,
            "before": json.loads(correction.before_snapshot),
            "after": (
                json.loads(correction.after_snapshot)
                if correction.after_snapshot
                else None
            ),
            "status": correction.status.value,
            "proposed_by": str(correction.proposed_by),
            "approved_by": (
                str(correction.approved_by) if correction.approved_by else None
            ),
            "applied_at": (
                correction.applied_at.isoformat() if correction.applied_at else None
            ),
        }

    async def propose_correction(
        self,
        target_type: ReviewTarget,
        target_id: uuid.UUID,
        description: str,
        new_statement: str | None,
        actor: User,
        dispute_id: uuid.UUID | None = None,
    ) -> dict:
        if len(description.strip()) < 10:
            raise ReviewError("DESCRIPTION_REQUIRED", "وصف التصحيح مطلوب ومفصَّل.")
        if target_type == ReviewTarget.CLAIM and not (new_statement or "").strip():
            raise ReviewError(
                "NEW_STATEMENT_REQUIRED", "تصحيح الادعاء يلزمه النص المصحَّح."
            )
        before = await self._snapshot(target_type, target_id)
        correction = Correction(
            target_type=target_type,
            target_id=target_id,
            description=description.strip(),
            before_snapshot=before,
            after_snapshot=(
                json.dumps(
                    {"statement": new_statement.strip()},
                    ensure_ascii=False,
                    sort_keys=True,
                )
                if new_statement
                else None
            ),
            status=CorrectionStatus.PROPOSED,
            proposed_by=actor.id,
            dispute_id=dispute_id,
        )
        self.session.add(correction)
        await self.session.flush()
        record_audit(
            self.session,
            action="correction_propose",
            entity_type=target_type.value,
            entity_id=target_id,
            actor_id=actor.id,
            old_data=json.loads(before),
            reason=description.strip(),
        )
        await self.session.commit()
        await self.session.refresh(correction)
        return self._correction_dict(correction)

    async def approve_correction(
        self, correction_id: uuid.UUID, approver: User
    ) -> dict:
        correction = await self.session.get(Correction, correction_id)
        if correction is None:
            raise ReviewError("CORRECTION_NOT_FOUND", "التصحيح غير موجود.")
        if correction.status != CorrectionStatus.PROPOSED:
            raise ReviewError("CORRECTION_CLOSED", "التصحيح لم يعد مقترحًا.")
        if correction.proposed_by == approver.id:
            raise ReviewError(
                "SELF_REVIEW_FORBIDDEN", "لا يعتمد التصحيحَ مقترحُه."
            )
        # ولا يعتمده **صاحب المحلّ المصحَّح**. كان الشرط يستثني المقترح
        # وحده، فلو اقترح غيري تصحيحًا على ادعائي، اعتمدتُه أنا بنفسي —
        # فأحكم على تصحيح عملي. والتصحيح يُبطل الاعتماد ويعيد إلى
        # المراجعة (apply_correction)، فالباب يمسّ حالة العمل لا حاشيته.
        owner = await self._target_owner(correction.target_type, correction.target_id)
        if owner == approver.id:
            raise ReviewError(
                "SELF_REVIEW_FORBIDDEN",
                "لا يعتمد التصحيحَ صاحبُ العمل المصحَّح.",
            )
        correction.status = CorrectionStatus.APPROVED
        correction.approved_by = approver.id
        record_audit(
            self.session,
            action="correction_approve",
            entity_type=correction.target_type.value,
            entity_id=correction.target_id,
            actor_id=approver.id,
        )
        await self.session.commit()
        await self.session.refresh(correction)
        return self._correction_dict(correction)

    async def apply_correction(self, correction_id: uuid.UUID, actor: User) -> dict:
        """يطبّق التصحيح المعتمد.

        تصحيح ادعاء معتمد **يُبطل اعتماده** ويعيده إلى المراجعة: المحتوى
        تغيّر، فشهادة المراجعين السابقة لا تنتقل إلى نص جديد."""
        correction = await self.session.get(Correction, correction_id)
        if correction is None:
            raise ReviewError("CORRECTION_NOT_FOUND", "التصحيح غير موجود.")
        if correction.status != CorrectionStatus.APPROVED:
            raise ReviewError("NOT_APPROVED", "لا يُطبَّق إلا تصحيح معتمد.")
        if correction.target_type != ReviewTarget.CLAIM:
            # التطبيق منفَّذ للادعاءات وحدها. تسجيل «طُبّق» على كيان لا
            # يتغير شيء فيه يكذب على سجل التدقيق، وهو أسوأ من رفض صريح.
            raise ReviewError(
                "TARGET_NOT_APPLICABLE",
                "تطبيق التصحيح متاح للادعاءات فقط؛ تصحيح غيرها يوثَّق "
                "ويُنفَّذ عبر مساره الخاص (استيراد إصدار، قرار جذر، تقرير).",
            )

        applied_payload: dict | None = None
        if correction.target_type == ReviewTarget.CLAIM:
            claim = await self.session.get(Claim, correction.target_id)
            if claim is None:
                raise ReviewError("TARGET_NOT_FOUND", "الادعاء غير موجود.")
            after = json.loads(correction.after_snapshot or "{}")
            new_statement = after.get("statement")
            if not new_statement:
                raise ReviewError(
                    "NEW_STATEMENT_REQUIRED", "لا يوجد نص مصحَّح للتطبيق."
                )
            claim.statement = new_statement
            claim.status = RecordStatus.UNDER_REVIEW
            claim.approved_by_first = None
            claim.approved_by_second = None
            claim.approved_at = None
            claim.confidence = ConfidenceLevel.LOW
            applied_payload = {
                "statement": claim.statement,
                "status": claim.status.value,
                "confidence": claim.confidence.value,
                "approved_by_first": "",
                "approved_by_second": "",
            }
            correction.after_snapshot = json.dumps(
                applied_payload, ensure_ascii=False, sort_keys=True
            )

        correction.status = CorrectionStatus.APPLIED
        correction.applied_at = utcnow()
        record_audit(
            self.session,
            action="correction_apply",
            entity_type=correction.target_type.value,
            entity_id=correction.target_id,
            actor_id=actor.id,
            old_data=json.loads(correction.before_snapshot),
            new_data=applied_payload,
        )
        await self.session.commit()
        await self.session.refresh(correction)
        return self._correction_dict(correction)

    async def list_corrections(
        self, target_type: ReviewTarget, target_id: uuid.UUID
    ) -> list[dict]:
        rows = (
            await self.session.execute(
                select(Correction)
                .where(
                    Correction.target_type == target_type,
                    Correction.target_id == target_id,
                )
                .order_by(Correction.created_at)
            )
        ).scalars()
        return [self._correction_dict(c) for c in rows]
