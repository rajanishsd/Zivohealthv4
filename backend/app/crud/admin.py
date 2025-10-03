from typing import Optional
from sqlalchemy.orm import Session
from app.models import Admin


class CRUDAdmin:
    def get(self, db: Session, admin_id: int) -> Optional[Admin]:
        return db.query(Admin).filter(Admin.id == admin_id).first()

    def get_by_email(self, db: Session, email: str) -> Optional[Admin]:
        return db.query(Admin).filter(Admin.email == email).first()

    def create(self, db: Session, *, email: str, full_name: Optional[str], hashed_password: str, is_superadmin: bool = False) -> Admin:
        obj = Admin(email=email, full_name=full_name, hashed_password=hashed_password, is_superadmin=is_superadmin)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def is_active(self, admin: Admin) -> bool:
        return bool(admin.is_active)

    def is_super_admin(self, admin: Admin) -> bool:
        return bool(admin.is_superadmin)


admin = CRUDAdmin()


