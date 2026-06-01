from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import SimStatus


class SimRead(BaseModel):
    id: int
    msisdn: str
    company_id: int
    company_name: str | None = None
    seller_id: int | None = None
    plan_id: int | None = None
    status: SimStatus

    model_config = {"from_attributes": True}


class ReservedSimRead(SimRead):
    iccid: str
    imsi: str
    reserved_until: datetime | None
    reserved_by_user_id: int | None


class ReserveNumberRequest(BaseModel):
    sim_record_id: int
    plan_id: int


class GenerateSimInventoryRequest(BaseModel):
    company_id: int | None = None
    start_msisdn: str = Field(pattern=r"^\d{10}$")
    end_msisdn: str | None = Field(default=None, pattern=r"^\d{10}$")
    count: int = Field(default=1000, ge=1, le=1000)
    seller_id: int | None = None


class NumberSeriesRead(BaseModel):
    id: int
    company_id: int
    prefix: str
    start_number: str
    end_number: str

    model_config = {"from_attributes": True}


class InventorySummary(BaseModel):
    companies: int
    sellers: int
    plans: int
    sim_records: int
    available_sims: int
    series: int


class GeneratedInventoryResponse(BaseModel):
    company_id: int
    series_id: int
    start_msisdn: str
    end_msisdn: str
    created: int
