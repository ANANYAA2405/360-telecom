from fastapi import APIRouter, Depends

from app.core.rbac import require_roles
from app.models.enums import UserRole
from app.models.user import User

router = APIRouter()


@router.get("/home")
def company_home(current_user: User = Depends(require_roles([UserRole.COMPANY]))) -> dict[str, str]:
    return {"message": "Company operations intelligence center", "role": current_user.role}
