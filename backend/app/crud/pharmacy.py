from typing import List, Optional, Dict, Any
from datetime import date, datetime
from app.utils.timezone import now_local
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func

from app.crud.base import CRUDBase
from app.models.pharmacy_data import (
    PharmacyRawData, PharmacyDailyAggregate, PharmacyWeeklyAggregate,
    PharmacyMonthlyAggregate, PharmacyDataSource, MedicationType
)
from app.schemas.pharmacy import PharmacyDataCreate, PharmacyDataUpdate


class CRUDPharmacyData(CRUDBase[PharmacyRawData, PharmacyDataCreate, PharmacyDataUpdate]):
    """CRUD operations for pharmacy raw data"""

    def get_by_user(
        self,
        db: Session,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[PharmacyRawData]:
        """Get pharmacy data for a specific user"""
        query = db.query(self.model).filter(self.model.user_id == user_id)
        
        if start_date:
            query = query.filter(self.model.purchase_date >= start_date)
        if end_date:
            query = query.filter(self.model.purchase_date <= end_date)
            
        return query.order_by(desc(self.model.purchase_date)).offset(skip).limit(limit).all()

    def get_by_medication_name(
        self,
        db: Session,
        *,
        user_id: int,
        medication_name: str,
        skip: int = 0,
        limit: int = 100
    ) -> Optional[PharmacyRawData]:
        """Get pharmacy data by medication name"""
        return db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                self.model.medication_name.ilike(f"%{medication_name}%")
            )
        ).order_by(desc(self.model.purchase_date)).offset(skip).limit(limit).all()

    def get_by_pharmacy(
        self,
        db: Session,
        *,
        user_id: int,
        pharmacy_name: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[PharmacyRawData]:
        """Get pharmacy data by pharmacy name"""
        return db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                self.model.pharmacy_name.ilike(f"%{pharmacy_name}%")
            )
        ).order_by(desc(self.model.purchase_date)).offset(skip).limit(limit).all()

    def get_by_medication_type(
        self,
        db: Session,
        *,
        user_id: int,
        medication_type: MedicationType,
        skip: int = 0,
        limit: int = 100
    ) -> List[PharmacyRawData]:
        """Get pharmacy data by medication type"""
        return db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                self.model.medication_type == medication_type.value
            )
        ).order_by(desc(self.model.purchase_date)).offset(skip).limit(limit).all()

    def get_spending_summary(
        self,
        db: Session,
        *,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get spending summary for a user"""
        query = db.query(
            func.sum(self.model.total_cost).label('total_spent'),
            func.sum(self.model.insurance_coverage).label('total_insurance'),
            func.sum(self.model.copay_amount).label('total_copay'),
            func.count(self.model.id).label('total_medications'),
            func.count(func.distinct(self.model.pharmacy_name)).label('unique_pharmacies')
        ).filter(self.model.user_id == user_id)
        
        if start_date:
            query = query.filter(self.model.purchase_date >= start_date)
        if end_date:
            query = query.filter(self.model.purchase_date <= end_date)
            
        result = query.first()
        
        return {
            'total_spent': float(result.total_spent or 0),
            'total_insurance': float(result.total_insurance or 0),
            'total_copay': float(result.total_copay or 0),
            'total_medications': int(result.total_medications or 0),
            'unique_pharmacies': int(result.unique_pharmacies or 0)
        }

    def get_recent_purchases(
        self,
        db: Session,
        *,
        user_id: int,
        days: int = 30,
        limit: int = 10
    ) -> List[PharmacyRawData]:
        """Get recent pharmacy purchases"""
        from datetime import timedelta
        cutoff_date = now_local().date() - timedelta(days=days)
        
        return db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                self.model.purchase_date >= cutoff_date
            )
        ).order_by(desc(self.model.purchase_date)).limit(limit).all()

    def get_medication_history(
        self,
        db: Session,
        *,
        user_id: int,
        medication_name: str,
        limit: int = 10
    ) -> List[PharmacyRawData]:
        """Get medication purchase history"""
        return db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                self.model.medication_name.ilike(f"%{medication_name}%")
            )
        ).order_by(desc(self.model.purchase_date)).limit(limit).all()

    def search_medications(
        self,
        db: Session,
        *,
        user_id: int,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[PharmacyRawData]:
        """Search medications by name, brand, or generic name"""
        search_pattern = f"%{search_term}%"
        return db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                (
                    self.model.medication_name.ilike(search_pattern) |
                    self.model.brand_name.ilike(search_pattern) |
                    self.model.generic_name.ilike(search_pattern)
                )
            )
        ).order_by(desc(self.model.purchase_date)).offset(skip).limit(limit).all()

    def get_pending_aggregation(
        self,
        db: Session,
        *,
        user_id: Optional[int] = None,
        limit: int = 1000
    ) -> List[PharmacyRawData]:
        """Get records pending aggregation"""
        query = db.query(self.model).filter(self.model.aggregation_status == 'pending')
        
        if user_id:
            query = query.filter(self.model.user_id == user_id)
            
        return query.order_by(self.model.created_at).limit(limit).all()

    def mark_as_aggregated(
        self,
        db: Session,
        *,
        record_ids: List[int]
    ) -> int:
        """Mark records as aggregated"""
        updated_count = db.query(self.model).filter(
            self.model.id.in_(record_ids)
        ).update({
            'aggregation_status': 'completed',
            'aggregated_at': datetime.utcnow()
        }, synchronize_session=False)
        
        db.commit()
        return updated_count


class CRUDPharmacyDailyAggregate(CRUDBase[PharmacyDailyAggregate, dict, dict]):
    """CRUD operations for pharmacy daily aggregates"""

    def get_by_user_date_range(
        self,
        db: Session,
        *,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[PharmacyDailyAggregate]:
        """Get daily aggregates for a user within date range"""
        return db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                self.model.date >= start_date,
                self.model.date <= end_date
            )
        ).order_by(self.model.date).all()

    def get_or_create_for_date(
        self,
        db: Session,
        *,
        user_id: int,
        date: date
    ) -> PharmacyDailyAggregate:
        """Get or create daily aggregate for specific date"""
        existing = db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                self.model.date == date
            )
        ).first()
        
        if existing:
            return existing
        
        new_aggregate = self.model(
            user_id=user_id,
            date=date
        )
        db.add(new_aggregate)
        db.commit()
        db.refresh(new_aggregate)
        return new_aggregate


class CRUDPharmacyWeeklyAggregate(CRUDBase[PharmacyWeeklyAggregate, dict, dict]):
    """CRUD operations for pharmacy weekly aggregates"""

    def get_by_user_date_range(
        self,
        db: Session,
        *,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[PharmacyWeeklyAggregate]:
        """Get weekly aggregates for a user within date range"""
        return db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                self.model.week_start_date <= end_date,
                self.model.week_end_date >= start_date
            )
        ).order_by(self.model.week_start_date).all()


class CRUDPharmacyMonthlyAggregate(CRUDBase[PharmacyMonthlyAggregate, dict, dict]):
    """CRUD operations for pharmacy monthly aggregates"""

    def get_by_user_year_month(
        self,
        db: Session,
        *,
        user_id: int,
        year: int,
        month: Optional[int] = None
    ) -> List[PharmacyMonthlyAggregate]:
        """Get monthly aggregates for a user by year and optionally month"""
        query = db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                self.model.year == year
            )
        )
        
        if month:
            query = query.filter(self.model.month == month)
            
        return query.order_by(self.model.year, self.model.month).all()


# Create instances
pharmacy = CRUDPharmacyData(PharmacyRawData)
pharmacy_daily = CRUDPharmacyDailyAggregate(PharmacyDailyAggregate)
pharmacy_weekly = CRUDPharmacyWeeklyAggregate(PharmacyWeeklyAggregate)
pharmacy_monthly = CRUDPharmacyMonthlyAggregate(PharmacyMonthlyAggregate)

# For existing tables (PharmacyBill and PharmacyMedication from health_data.py)
from app.models.health_data import PharmacyBill, PharmacyMedication

class CRUDPharmacyBill(CRUDBase[PharmacyBill, dict, dict]):
    """CRUD operations for pharmacy bills"""
    
    def get_by_user(
        self,
        db: Session,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[PharmacyBill]:
        """Get pharmacy bills for a specific user"""
        return db.query(self.model).filter(
            self.model.user_id == user_id
        ).order_by(desc(self.model.bill_date)).offset(skip).limit(limit).all()


class CRUDPharmacyMedication(CRUDBase[PharmacyMedication, dict, dict]):
    """CRUD operations for pharmacy medications"""
    
    def get_by_user(
        self,
        db: Session,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[PharmacyMedication]:
        """Get pharmacy medications for a specific user"""
        return db.query(self.model).filter(
            self.model.user_id == user_id
        ).order_by(desc(self.model.created_at)).offset(skip).limit(limit).all()

    def get_by_bill(
        self,
        db: Session,
        *,
        bill_id: int
    ) -> List[PharmacyMedication]:
        """Get medications for a specific bill"""
        return db.query(self.model).filter(
            self.model.bill_id == bill_id
        ).all()


# Additional instances for existing tables
pharmacy_bill = CRUDPharmacyBill(PharmacyBill)
pharmacy_medication = CRUDPharmacyMedication(PharmacyMedication)