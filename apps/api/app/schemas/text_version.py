from pydantic import BaseModel, Field


class AyahIn(BaseModel):
    surah: int = Field(ge=1, le=114)
    ayah: int = Field(ge=1, le=286)
    text: str = Field(min_length=1, max_length=4000)


class ImportVersionRequest(BaseModel):
    version_code: str = Field(min_length=2, max_length=80)
    title: str = Field(min_length=2, max_length=200)
    riwayah: str = Field(min_length=2, max_length=80)
    script_type: str = Field(min_length=2, max_length=40)
    counting_system: str = Field(min_length=2, max_length=40)
    source_name: str = Field(min_length=2, max_length=200)
    source_reference: str | None = Field(default=None, max_length=500)
    ayahs: list[AyahIn] = Field(min_length=1)


class CompareRequest(BaseModel):
    other_version_id: str


class ActivateRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ValidateRequest(BaseModel):
    require_full: bool = True
