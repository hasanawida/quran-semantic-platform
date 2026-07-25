from pydantic import BaseModel, Field

from app.models.scholarship import CitationStance, ClaimSubject, ClaimType, WorkType


class SourceWorkRequest(BaseModel):
    code: str = Field(min_length=2, max_length=60)
    title: str = Field(min_length=2, max_length=300)
    author: str = Field(min_length=2, max_length=200)
    work_type: WorkType = WorkType.OTHER
    # الطبعة والرخصة إلزاميتان: لا مصدر مجهول الطبعة ولا بلا إذن
    edition: str = Field(min_length=1, max_length=200)
    license_note: str = Field(min_length=2, max_length=500)
    publisher: str | None = Field(default=None, max_length=200)
    publication_year: int | None = Field(default=None, ge=600, le=2200)
    isbn: str | None = Field(default=None, max_length=20)
    language: str = Field(default="ar", max_length=40)
    access_url: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)


class RejectSourceRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class CitationRequest(BaseModel):
    source_work_id: str
    locator: str = Field(min_length=1, max_length=200)
    # النقل للاستشهاد لا لإعادة نشر المصدر — الطول محدود عمدًا
    quoted_text: str | None = Field(default=None, max_length=1000)
    paraphrase: str | None = Field(default=None, max_length=4000)


class ClaimRequest(BaseModel):
    statement: str = Field(min_length=20, max_length=8000)
    claim_type: ClaimType = ClaimType.SEMANTIC
    subject_type: ClaimSubject
    root: str | None = Field(default=None, max_length=40)
    lemma: str | None = Field(default=None, max_length=120)
    surah: int | None = Field(default=None, ge=1, le=114)
    ayah: int | None = Field(default=None, ge=1)
    word_number: int | None = Field(default=None, ge=1)


class AttachEvidenceRequest(BaseModel):
    citation_id: str
    stance: CitationStance = CitationStance.SUPPORTS
    note: str | None = Field(default=None, max_length=1000)


class DisputeRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)
