from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole


class SellerCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8, max_length=128)
    company_id: int | None = None


class SellerRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    company_id: int | None = None
    company_role: str | None = None

    model_config = {"from_attributes": True}


class CompanyUserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8, max_length=128)
    company_id: int | None = None
    company_role: str = Field(default="ANALYST", max_length=64)


class CompanyUserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    company_id: int | None = None
    company_role: str | None = None

    model_config = {"from_attributes": True}
