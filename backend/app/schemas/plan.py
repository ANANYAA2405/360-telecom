from decimal import Decimal

from pydantic import BaseModel, Field


class PlanCreate(BaseModel):
    company_id: int | None = None
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=2)
    monthly_price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    data_gb: int = Field(default=28, ge=0)
    voice_minutes: int = Field(default=1000, ge=0)
    sms_count: int = Field(default=100, ge=0)
    validity_days: int = Field(default=28, ge=1)


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, min_length=2)
    monthly_price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    data_gb: int | None = Field(default=None, ge=0)
    voice_minutes: int | None = Field(default=None, ge=0)
    sms_count: int | None = Field(default=None, ge=0)
    validity_days: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class PlanRead(BaseModel):
    id: int
    company_id: int
    name: str
    description: str
    monthly_price: Decimal
    data_gb: int
    voice_minutes: int
    sms_count: int
    validity_days: int
    is_active: bool

    model_config = {"from_attributes": True}
