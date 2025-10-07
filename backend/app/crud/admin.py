from typing import Optional
from sqlalchemy.orm import Session
from app.models import Admin


class CRUDAdmin:
    def get(self, db: Session, admin_id: int) -> Optional[Admin]:
        return db.query(Admin).filter(Admin.id == admin_id).first()

    def get_by_email(self, db: Session, email: str) -> Optional[Admin]:
        return db.query(Admin).filter(Admin.email == email).first()

    def create(self, db: Session, *, email: str, first_name: Optional[str], middle_name: Optional[str], last_name: Optional[str], full_name: Optional[str], hashed_password: str, is_superadmin: bool = False) -> Admin:
        # Prefer split fields; fallback to parsing full_name
        fn = first_name
        mn = middle_name
        ln = last_name
        if (not fn and not ln) and full_name:
            parts = full_name.strip().split()
            if parts:
                fn = parts[0]
                if len(parts) > 1:
                    ln = parts[-1]
                if len(parts) > 2:
                    mn = " ".join(parts[1:-1])
        obj = Admin(email=email, first_name=fn, middle_name=mn, last_name=ln, hashed_password=hashed_password, is_superadmin=is_superadmin)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def is_active(self, admin: Admin) -> bool:
        return bool(admin.is_active)

    def is_super_admin(self, admin: Admin) -> bool:
        return bool(admin.is_superadmin)


admin = CRUDAdmin()


