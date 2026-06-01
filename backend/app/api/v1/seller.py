from fastapi import APIRouter, Depends

from app.core.rbac import require_roles
from app.models.enums import UserRole
from app.models.user import User

router = APIRouter()


@router.get("/home")
def seller_home(current_user: User = Depends(require_roles([UserRole.SELLER]))) -> dict[str, str]:
    return {"message": "Seller KYC and activation inbox", "role": current_user.role}

