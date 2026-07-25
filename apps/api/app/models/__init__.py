"""تجميع كل نماذج ORM حتى تكتمل البيانات الوصفية (metadata) للمخطط."""

from app.models.audit import AuditLog
from app.models.enums import ConfidenceLevel, RecordStatus, UserRole
from app.models.language import Root, RootDerivation, RootOccurrence
from app.models.morphology import (
    GoldenRootCase,
    MorphologicalAnalysis,
    MorphologySource,
    Token,
    TokenRootDecision,
    TokenRootDecisionRoot,
)
from app.models.project import (
    Project,
    ProjectClaim,
    ProjectMember,
    ProjectRole,
    ProjectVisibility,
    Report,
    ReportVersion,
)
from app.models.quran import Ayah, QuranTextVersion, Surah
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
from app.models.session import RefreshSession
from app.models.user import (
    ConflictOfInterestDeclaration,
    ReviewerQualification,
    User,
    UserRoleAssignment,
)

__all__ = [
    "AuditLog",
    "AssignmentStatus",
    "Ayah",
    "Citation",
    "CitationStance",
    "Claim",
    "ClaimCitation",
    "ClaimSubject",
    "ClaimType",
    "ConfidenceLevel",
    "ConflictOfInterestDeclaration",
    "Correction",
    "CorrectionStatus",
    "Dispute",
    "DisputeStatus",
    "GoldenRootCase",
    "MorphologicalAnalysis",
    "MorphologySource",
    "Project",
    "ProjectClaim",
    "ProjectMember",
    "ProjectRole",
    "ProjectVisibility",
    "QuranTextVersion",
    "RecordStatus",
    "RefreshSession",
    "Report",
    "ReportVersion",
    "ReviewAssignment",
    "ReviewComment",
    "ReviewTarget",
    "ReviewerQualification",
    "Root",
    "RootDerivation",
    "RootOccurrence",
    "SourceWork",
    "Surah",
    "Token",
    "TokenRootDecision",
    "TokenRootDecisionRoot",
    "User",
    "UserRole",
    "UserRoleAssignment",
    "WorkType",
]
