"""Health scoring package.

This module contains:
- SQLAlchemy models used only by the scoring feature
- Pydantic schemas for importing/exporting configuration
- A small, explicit engine for scoring based on anchors/specs
- Services to fetch data from existing domain tables and persist results

All endpoints in this package are internal-only and gated by admin auth.
"""

from .models import (
    HealthScoreSpec,
    MetricAnchorRegistry,
    HealthScoreResultDaily,
    HealthScoreCalcLog,
)


