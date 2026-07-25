from pydantic import BaseModel, Field


class TokenizeRequest(BaseModel):
    surahs: list[int] | None = Field(default=None, description="حصر النطاق بسور")


class ImportMorphologyRequest(BaseModel):
    surahs: list[int] | None = None


class RebuildRequest(BaseModel):
    surahs: list[int] | None = None


class ProposeDecisionRequest(BaseModel):
    surah: int = Field(ge=1, le=114)
    ayah: int = Field(ge=1)
    word_number: int = Field(ge=1)
    # قائمة فارغة = قرار «لا جذر لهذه الكلمة»
    roots: list[str] = Field(default_factory=list, max_length=5)
    rationale: str = Field(min_length=10, max_length=1000)


class ApproveDecisionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class SourceToggleRequest(BaseModel):
    is_enabled: bool
