from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import KycStatus


class KycSubmitRequest(BaseModel):
    sim_record_id: int
    full_name: str = Field(min_length=2, max_length=160)
    date_of_birth: date
    document_type: str = Field(min_length=2, max_length=60)
    document_number: str = Field(min_length=4, max_length=120)
    address: str = Field(min_length=8)
    document_upload_placeholder: str | None = None
    selfie_placeholder: str | None = None

    @field_validator("date_of_birth")
    @classmethod
    def validate_adult(cls, value: date) -> date:
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 18:
            raise ValueError("Customer must be at least 18 years old for KYC")
        return value


class KycReviewRequest(BaseModel):
    status: KycStatus
    rejection_reason: str | None = None
    correction_reason: str | None = None


class KycSubmissionRead(BaseModel):
    id: int
    customer_id: int
    sim_record_id: int
    full_name: str
    date_of_birth: date | None
    document_type: str
    document_number: str
    address: str
    document_upload_placeholder: str | None
    selfie_placeholder: str | None
    status: KycStatus
    reviewed_by_user_id: int | None
    rejection_reason: str | None
    correction_reason: str | None
    created_at: datetime
    reviewed_at: datetime | None
    msisdn: str | None = None
    company_name: str | None = None
    customer_email: str | None = None

    model_config = {"from_attributes": True}
