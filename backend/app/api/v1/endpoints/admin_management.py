from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Body, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.api import deps
from app.db.session import get_db
from app.models import Admin
from app.crud import admin as crud_admin
from app.core import security

router = APIRouter()


# Pydantic models for request/response
class AdminCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    middle_name: str | None = None
    last_name: str
    full_name: str | None = None


class AdminPasswordChange(BaseModel):
    admin_id: int
    new_password: str
    current_password: str | None = None


class AdminResponse(BaseModel):
    id: int
    email: str
    first_name: str | None
    middle_name: str | None
    last_name: str | None
    full_name: str | None
    is_superadmin: bool
    is_active: bool


@router.get("/admins", response_model=List[AdminResponse])
def list_admins(
    *,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(deps.get_current_active_admin),
) -> List[AdminResponse]:
    """
    List all admin users.
    
    Requires: Super admin authentication
    
    Only the super admin can view and manage other admins.
    """
    # Check if current admin is super admin
    if not crud_admin.is_super_admin(current_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can access admin management"
        )
    
    admins = db.query(Admin).all()
    result = []
    
    for admin in admins:
        # Compose full_name from parts
        parts = [p for p in [admin.first_name, admin.middle_name, admin.last_name] if p]
        full_name = " ".join(parts) if parts else None
        
        result.append(AdminResponse(
            id=admin.id,
            email=admin.email,
            first_name=admin.first_name,
            middle_name=admin.middle_name,
            last_name=admin.last_name,
            full_name=full_name,
            is_superadmin=admin.is_superadmin,
            is_active=admin.is_active
        ))
    
    return result


@router.post("/admins/create", response_model=Dict[str, Any])
def create_admin(
    *,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(deps.get_current_active_admin),
    admin_data: AdminCreate,
) -> Dict[str, Any]:
    """
    Create a new admin user (regular admin, not super admin).
    
    Requires: Super admin authentication
    
    Note: Super admin cannot be created via this endpoint.
    Only one super admin exists in the system.
    """
    # Check if current admin is super admin
    if not crud_admin.is_super_admin(current_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can create new admins"
        )
    
    # Check if admin with email already exists
    existing_admin = crud_admin.get_by_email(db, email=admin_data.email)
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An admin with this email already exists"
        )
    
    # Hash the password
    hashed_password = security.get_password_hash(admin_data.password)
    
    # Create the admin (is_superadmin=False by default)
    new_admin = crud_admin.create(
        db,
        email=admin_data.email,
        first_name=admin_data.first_name,
        middle_name=admin_data.middle_name,
        last_name=admin_data.last_name,
        full_name=admin_data.full_name,
        hashed_password=hashed_password,
        is_superadmin=False  # Regular admins only
    )
    
    # Compose full_name
    parts = [p for p in [new_admin.first_name, new_admin.middle_name, new_admin.last_name] if p]
    full_name = " ".join(parts) if parts else None
    
    return {
        "message": "Admin created successfully",
        "admin": {
            "id": new_admin.id,
            "email": new_admin.email,
            "full_name": full_name,
            "is_superadmin": new_admin.is_superadmin
        }
    }


@router.post("/admins/change-password", response_model=Dict[str, Any])
def change_admin_password(
    *,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(deps.get_current_active_admin),
    password_data: AdminPasswordChange,
) -> Dict[str, Any]:
    """
    Change password for an admin user.
    
    Requires: Super admin authentication
    
    Rules:
    - Only super admin can change passwords
    - When changing super admin's own password, current password is required
    - When changing regular admin's password, no current password needed
    """
    # Get the target admin
    target_admin = crud_admin.get(db, admin_id=password_data.admin_id)
    if not target_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    # Check if current admin is super admin
    is_super_admin = crud_admin.is_super_admin(current_admin)
    is_self = current_admin.id == password_data.admin_id
    
    if not is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can change admin passwords"
        )
    
    # If changing the super admin's password, require current password and only allow self-change
    if crud_admin.is_super_admin(target_admin):
        if not is_self:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the super admin can change their own password"
            )
        
        # Require current password
        if not password_data.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is required to change super admin password"
            )
        
        # Verify current password
        if not security.verify_password(password_data.current_password, target_admin.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )

    # Update password
    new_hashed_password = security.get_password_hash(password_data.new_password)
    target_admin.hashed_password = new_hashed_password
    db.commit()
    
    return {
        "message": f"Password changed successfully for admin {target_admin.email}"
    }


@router.delete("/admins/{admin_id}", response_model=Dict[str, Any])
def delete_admin(
    *,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(deps.get_current_active_admin),
    admin_id: int,
) -> Dict[str, Any]:
    """
    Delete an admin user.
    
    Requires: Super admin authentication
    
    Rules:
    - Only super admin can delete admins
    - Cannot delete super admin
    - Only one super admin exists in the system
    - Super admin cannot be deleted for system safety
    """
    # Check if current admin is super admin
    if not crud_admin.is_super_admin(current_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can delete admins"
        )
    # Get the target admin
    target_admin = crud_admin.get(db, admin_id=admin_id)
    if not target_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    # Check if target is super admin
    if crud_admin.is_super_admin(target_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete super admin. Super admin is protected and cannot be removed."
        )
    
    # Check if trying to delete self
    if current_admin.id == admin_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own admin account"
        )
    
    # Delete the admin
    admin_email = target_admin.email
    db.delete(target_admin)
    db.commit()
    
    return {
        "message": f"Admin {admin_email} deleted successfully"
    }


@router.get("/admins/me", response_model=Dict[str, Any])
def get_current_admin_info(
    *,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(deps.get_current_active_admin),
) -> Dict[str, Any]:
    """
    Get information about the currently logged-in admin.
    
    Requires: Admin authentication
    
    Returns information including whether the current admin is a super admin.
    This is used by the frontend to show/hide admin management features.
    """
    # Compose full_name
    parts = [p for p in [current_admin.first_name, current_admin.middle_name, current_admin.last_name] if p]
    full_name = " ".join(parts) if parts else None
    
    return {
        "id": current_admin.id,
        "email": current_admin.email,
        "full_name": full_name,
        "is_superadmin": crud_admin.is_super_admin(current_admin),
        "is_active": current_admin.is_active
    }


@router.get("/admins/check-superadmin", response_model=Dict[str, Any])
def check_superadmin_exists(
    *,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(deps.get_current_active_admin),
) -> Dict[str, Any]:
    """
    Check if a super admin exists in the system.
    
    Requires: Super admin authentication
    """
    # Check if current admin is super admin
    if not crud_admin.is_super_admin(current_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can access admin management"
        )
    super_admin = db.query(Admin).filter(Admin.is_superadmin == True).first()
    
    return {
        "exists": super_admin is not None,
        "email": super_admin.email if super_admin else None,
        "id": super_admin.id if super_admin else None
    }

