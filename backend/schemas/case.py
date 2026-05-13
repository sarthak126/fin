"""
Pydantic schemas for Case API requests/responses.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, model_validator

from models import CaseStatus


def _trim_optional(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


class CaseCreateRequest(BaseModel):
    name: str | None = None
    status: CaseStatus = CaseStatus.DRAFT
    applicant_name: str | None = None
    applicant_email: str | None = None
    applicant_phone: str | None = None

    @model_validator(mode="after")
    def _normalize_optional_strings(self) -> "CaseCreateRequest":
        self.name = _trim_optional(self.name)
        self.applicant_name = _trim_optional(self.applicant_name)
        self.applicant_email = _trim_optional(self.applicant_email)
        self.applicant_phone = _trim_optional(self.applicant_phone)
        return self


class CaseApplicantInfoUpdateRequest(BaseModel):
    applicant_name: str | None = None
    applicant_email: str | None = None
    applicant_phone: str | None = None

    @model_validator(mode="after")
    def _normalize_and_require_values(self) -> "CaseApplicantInfoUpdateRequest":
        provided_fields = set(self.model_fields_set)
        self.applicant_name = _trim_optional(self.applicant_name)
        self.applicant_email = _trim_optional(self.applicant_email)
        self.applicant_phone = _trim_optional(self.applicant_phone)

        if not provided_fields.intersection({"applicant_name", "applicant_email", "applicant_phone"}):
            raise ValueError("At least one applicant field must be provided")

        return self


class CaseListItem(BaseModel):
    id: str
    name: str | None = None
    status: CaseStatus
    applicant_name: str | None = None
    applicant_email: str | None = None
    applicant_phone: str | None = None
    legacy_source_document_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CaseDetail(CaseListItem):
    user_id: str
    org_id: str

    model_config = {"from_attributes": True}
