from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

from app.db.base import Base
from app.utils.timezone import local_now_db_expr, local_now_db_func


class HealthScoreSpec(Base):
    __tablename__ = "health_score_specs"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(32), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    spec_json = Column(JSONB, nullable=False)
    is_default = Column(Boolean, nullable=False, default=False, index=True)

    created_at = Column(DateTime, server_default=local_now_db_expr(), nullable=False)
    updated_at = Column(DateTime, server_default=local_now_db_expr(), onupdate=local_now_db_func(), nullable=False)

    __table_args__ = (
        UniqueConstraint("version", name="uq_health_score_spec_version"),
    )


class MetricAnchorRegistry(Base):
    __tablename__ = "metric_anchor_registry"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(32), nullable=False, index=True)  # vital, biomarker, sleep, activity, nutrition, medication, mental
    key = Column(String(64), nullable=False, index=True)  # e.g., ldl_mgdl, spo2_pct
    loinc_code = Column(String(20), nullable=True, index=True)  # for biomarkers; prefer LOINC as canonical key
    unit = Column(String(32), nullable=True)
    pattern = Column(String(24), nullable=False)  # lower | higher | u_shaped | range
    anchors = Column(JSONB, nullable=False)  # [[value, score], ...]
    half_life_days = Column(Integer, nullable=True)
    danger = Column(JSONB, nullable=True)  # [{condition, penalty, durationHours}]
    group_key = Column(String(64), nullable=True)  # e.g., lipids, glycemic
    active = Column(Boolean, nullable=False, default=True)
    introduced_in = Column(String(32), nullable=True)

    created_at = Column(DateTime, server_default=local_now_db_expr(), nullable=False)
    updated_at = Column(DateTime, server_default=local_now_db_expr(), onupdate=local_now_db_func(), nullable=False)

    __table_args__ = (
        UniqueConstraint("domain", "key", name="uq_metric_anchor_domain_key"),
        Index("idx_metric_anchor_loinc", "loinc_code"),
    )


class HealthScoreResultDaily(Base):
    __tablename__ = "health_score_results_daily"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)

    chronic_score = Column(Float, nullable=True)
    acute_score = Column(Float, nullable=True)
    overall_score = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    detail = Column(JSONB, nullable=False)  # per-modality breakdown
    spec_version = Column(String(32), nullable=False)

    created_at = Column(DateTime, server_default=local_now_db_expr(), nullable=False)
    updated_at = Column(DateTime, server_default=local_now_db_expr(), onupdate=local_now_db_func(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_health_score_results_daily_user_date"),
        Index("idx_health_score_results_daily_user_date", "user_id", "date"),
    )


class HealthScoreCalcLog(Base):
    __tablename__ = "health_score_calculations_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    calculated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    window_start = Column(DateTime, nullable=True)
    window_end = Column(DateTime, nullable=True)
    spec_version = Column(String(32), nullable=False)
    inputs_summary = Column(JSONB, nullable=True)
    result_overall = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)

    created_at = Column(DateTime, server_default=local_now_db_expr(), nullable=False)


