from fastapi import APIRouter

from app.api.v1 import activation, admin, auth, companies, company, customer, dashboard, kyc, lifecycle, management, otp, seller, sims, usage

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(companies.router, prefix="/companies", tags=["companies"])
api_router.include_router(sims.router, prefix="/sims", tags=["sims"])
api_router.include_router(usage.router, prefix="/usage", tags=["usage"])
api_router.include_router(otp.router, prefix="/otp", tags=["otp"])
api_router.include_router(kyc.router, prefix="/kyc", tags=["kyc"])
api_router.include_router(activation.router, prefix="/activation", tags=["activation"])
api_router.include_router(management.router, prefix="/management", tags=["management"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(lifecycle.router, prefix="/lifecycle", tags=["lifecycle"])
api_router.include_router(customer.router, prefix="/customer", tags=["customer"])
api_router.include_router(seller.router, prefix="/seller", tags=["seller"])
api_router.include_router(company.router, prefix="/company", tags=["company"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
