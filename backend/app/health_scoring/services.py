from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models import (
    VitalsDailyAggregate,
    VitalsRawData,
    NutritionDailyAggregate,
    LabReportCategorized,
    LabTestMapping,
    Prescription,
    UserProfile,
    MentalHealthDailyAggregate,
)
from app.models.nutrition_goals import NutritionGoal, NutritionGoalTarget, NutritionNutrientCatalog
from app.models.health_data import PharmacyBill
from .models import HealthScoreSpec, MetricAnchorRegistry, HealthScoreResultDaily, HealthScoreCalcLog
from .engine import interpolate_piecewise, exponential_decay_weight


@dataclass
class ModalityScore:
    score: float
    confidence: float
    detail: Dict[str, Any]


class HealthScoringService:
    def __init__(self, db: Session):
        self.db = db

    # Spec management
    def get_default_spec(self) -> HealthScoreSpec:
        spec = (
            self.db.query(HealthScoreSpec)
            .filter(HealthScoreSpec.is_default == True)
            .order_by(desc(HealthScoreSpec.updated_at))
            .first()
        )
        return spec

    # High-level compute API
    def compute_daily(self, user_id: int, day: date) -> HealthScoreResultDaily:
        spec = self.get_default_spec()
        if not spec:
            raise RuntimeError("No default health score spec configured")

        # Compute chronic and acute by modality using existing aggregates
        chronic_detail: Dict[str, Any] = {}
        acute_detail: Dict[str, Any] = {}

        # Helper to attach modality-level score/confidence into detail
        def with_meta(detail_dict: Dict[str, Any], score_val: float, conf_val: float) -> Dict[str, Any]:
            enriched = dict(detail_dict or {})
            enriched["score"] = float(score_val)
            enriched["confidence"] = float(conf_val)
            return enriched

        # Vitals (acute)
        vitals_today_score = self._score_vitals_today(user_id, day, spec)
        acute_detail["vitals_today"] = with_meta(vitals_today_score.detail, vitals_today_score.score, vitals_today_score.confidence)

        # Sleep (last night)
        sleep_today_score = self._score_sleep(user_id, day, spec)
        acute_detail["sleep_last_night"] = with_meta(sleep_today_score.detail, sleep_today_score.score, sleep_today_score.confidence)

        # Activity (today progress)
        activity_today_score = self._score_activity_today(user_id, day, spec)
        acute_detail["activity_today"] = with_meta(activity_today_score.detail, activity_today_score.score, activity_today_score.confidence)

        # Chronic stack
        biomarkers_score = self._score_biomarkers(user_id, day, spec)
        chronic_detail["biomarkers"] = with_meta(biomarkers_score.detail, biomarkers_score.score, biomarkers_score.confidence)

        vitals_30d_score = self._score_vitals_chronic(user_id, day, spec)
        chronic_detail["vitals_30d"] = with_meta(vitals_30d_score.detail, vitals_30d_score.score, vitals_30d_score.confidence)

        activity_7d_score = self._score_activity_chronic(user_id, day, spec)
        chronic_detail["activity"] = with_meta(activity_7d_score.detail, activity_7d_score.score, activity_7d_score.confidence)

        sleep_7d_score = self._score_sleep_chronic(user_id, day, spec)
        chronic_detail["sleep"] = with_meta(sleep_7d_score.detail, sleep_7d_score.score, sleep_7d_score.confidence)

        nutrition_7d_score = self._score_nutrition(user_id, day, spec)
        chronic_detail["nutrition"] = with_meta(nutrition_7d_score.detail, nutrition_7d_score.score, nutrition_7d_score.confidence)

        meds_30d_score = self._score_medications(user_id, day, spec)
        chronic_detail["medications"] = with_meta(meds_30d_score.detail, meds_30d_score.score, meds_30d_score.confidence)

        # Blend
        acute_weights = spec.spec_json["scoring"]["overall"]["acuteWeights"]
        acute = (
            vitals_today_score.score * acute_weights.get("vitals_today", 0)
            + sleep_today_score.score * acute_weights.get("sleep_last_night", 0)
            + activity_today_score.score * acute_weights.get("activity_today", 0)
        )

        # Age-based chronic weights
        user_profile: Optional[UserProfile] = self.db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        age_band = self._infer_age_band(user_profile)
        chronic_weights = spec.spec_json["scoring"]["overall"]["chronicWeightsByAge"][age_band]
        chronic = (
            biomarkers_score.score * chronic_weights.get("biomarkers", 0)
            + vitals_30d_score.score * chronic_weights.get("vitals_30d", 0)
            + activity_7d_score.score * chronic_weights.get("activity", 0)
            + sleep_7d_score.score * chronic_weights.get("sleep", 0)
            + nutrition_7d_score.score * chronic_weights.get("nutrition", 0)
            + meds_30d_score.score * chronic_weights.get("medications", 0)
        )

        blend = spec.spec_json["scoring"]["overall"]["blend"]
        overall = chronic * blend["chronic"] + acute * blend["acute"]

        # Confidence: naive average of modality confidences weighted by chronic+acute weights
        overall_conf = (
            (biomarkers_score.confidence * chronic_weights.get("biomarkers", 0))
            + (vitals_30d_score.confidence * chronic_weights.get("vitals_30d", 0))
            + (activity_7d_score.confidence * chronic_weights.get("activity", 0))
            + (sleep_7d_score.confidence * chronic_weights.get("sleep", 0))
            + (nutrition_7d_score.confidence * chronic_weights.get("nutrition", 0))
            + (meds_30d_score.confidence * chronic_weights.get("medications", 0))
            + (vitals_today_score.confidence * blend["acute"] * acute_weights.get("vitals_today", 0))
            + (sleep_today_score.confidence * blend["acute"] * acute_weights.get("sleep_last_night", 0))
            + (activity_today_score.confidence * blend["acute"] * acute_weights.get("activity_today", 0))
        )

        # Derive reasons and actions for explainability
        reasons, actions = self._derive_reasons_and_actions(
            acute_detail=acute_detail,
            chronic_detail=chronic_detail,
            acute_score=acute,
            chronic_score=chronic,
        )

        detail = {
            "acute": acute_detail,
            "chronic": chronic_detail,
            "insights": {
                "reasons": reasons,
                "actions": actions,
            },
        }

        # Upsert daily result
        existing = (
            self.db.query(HealthScoreResultDaily)
            .filter(and_(HealthScoreResultDaily.user_id == user_id, HealthScoreResultDaily.date == day))
            .first()
        )
        if existing:
            existing.chronic_score = float(chronic)
            existing.acute_score = float(acute)
            existing.overall_score = float(overall)
            existing.confidence = float(overall_conf)
            existing.detail = detail
            existing.spec_version = spec.version
        else:
            existing = HealthScoreResultDaily(
                user_id=user_id,
                date=day,
                chronic_score=float(chronic),
                acute_score=float(acute),
                overall_score=float(overall),
                confidence=float(overall_conf),
                detail=detail,
                spec_version=spec.version,
            )
            self.db.add(existing)

        self.db.add(
            HealthScoreCalcLog(
                user_id=user_id,
                calculated_at=datetime.utcnow(),
                window_start=datetime.combine(day - timedelta(days=30), datetime.min.time()),
                window_end=datetime.combine(day, datetime.max.time()),
                spec_version=spec.version,
                inputs_summary={},
                result_overall=float(overall),
                confidence=float(overall_conf),
            )
        )
        self.db.commit()
        self.db.refresh(existing)
        return existing

    # --- Modality scorers (initial minimal implementations; extend later) ---
    def _score_vitals_today(self, user_id: int, day: date, spec: HealthScoreSpec) -> ModalityScore:
        # Use last available values on the day for HR, BP, SpO2, Temp
        metrics = [
            ("Heart Rate", "resting_hr", "vitals"),
            ("Blood Pressure Systolic", "bp_systolic", "vitals"),
            ("Blood Pressure Diastolic", "bp_diastolic", "vitals"),
            ("Oxygen Saturation", "spo2_pct", "vitals"),
            ("Temperature", "temperature_c", "vitals"),
        ]
        sub_details = {}
        subscores: List[float] = []
        confidences: List[float] = []
        for metric_type, key, domain in metrics:
            row = (
                self.db.query(VitalsRawData)
                .filter(
                    and_(
                        VitalsRawData.user_id == user_id,
                        VitalsRawData.metric_type == metric_type,
                        VitalsRawData.start_date >= datetime.combine(day, datetime.min.time()),
                        VitalsRawData.start_date <= datetime.combine(day, datetime.max.time()),
                    )
                )
                .order_by(desc(VitalsRawData.start_date))
                .first()
            )
            if not row:
                continue
            reg = (
                self.db.query(MetricAnchorRegistry)
                .filter(MetricAnchorRegistry.domain == domain, MetricAnchorRegistry.key == key, MetricAnchorRegistry.active == True)
                .first()
            )
            if not reg:
                continue
            score = interpolate_piecewise(row.value, reg.anchors)
            subscores.append(score)
            confidences.append(1.0)
            sub_details[key] = {"value": row.value, "unit": row.unit, "score": score}
        score = sum(subscores) / len(subscores) if subscores else 0.0
        conf = sum(confidences) / len(confidences) if confidences else 0.0
        return ModalityScore(score=score, confidence=conf, detail=sub_details)

    def _score_sleep(self, user_id: int, day: date, spec: HealthScoreSpec) -> ModalityScore:
        # Use daily aggregates of Sleep duration (minutes)
        agg = (
            self.db.query(VitalsDailyAggregate)
            .filter(and_(VitalsDailyAggregate.user_id == user_id, VitalsDailyAggregate.metric_type == "Sleep", VitalsDailyAggregate.date == day))
            .first()
        )
        if not agg:
            return ModalityScore(0.0, 0.0, {})
        
        # Try to get sleep duration from duration_minutes (preferred) or fall back to total_value
        hours = None
        if agg.duration_minutes is not None and agg.duration_minutes > 0:
            # Duration is in minutes, convert to hours
            hours = float(agg.duration_minutes) / 60.0
        elif agg.total_value is not None and agg.total_value > 0:
            # Fall back to total_value - check unit to determine if conversion needed
            unit = (agg.unit or "").lower()
            if unit == "minutes" or unit == "mins":
                hours = float(agg.total_value) / 60.0
            elif unit == "hours" or unit == "hrs" or unit == "h":
                hours = float(agg.total_value)
            else:
                # Assume hours if unit not specified or unknown
                hours = float(agg.total_value)
        
        if hours is None or hours <= 0:
            return ModalityScore(0.0, 0.0, {})
        
        reg = (
            self.db.query(MetricAnchorRegistry)
            .filter(MetricAnchorRegistry.domain == "sleep", MetricAnchorRegistry.key == "duration_h", MetricAnchorRegistry.active == True)
            .first()
        )
        if not reg:
            return ModalityScore(0.0, 0.0, {})
        score = interpolate_piecewise(hours, reg.anchors)
        return ModalityScore(score=score, confidence=1.0, detail={"duration_h": hours, "score": score})

    def _score_activity_today(self, user_id: int, day: date, spec: HealthScoreSpec) -> ModalityScore:
        steps = (
            self.db.query(VitalsDailyAggregate)
            .filter(and_(VitalsDailyAggregate.user_id == user_id, VitalsDailyAggregate.metric_type == "Steps", VitalsDailyAggregate.date == day))
            .first()
        )
        if not steps or not steps.total_value:
            return ModalityScore(0.0, 0.0, {})
        reg = (
            self.db.query(MetricAnchorRegistry)
            .filter(MetricAnchorRegistry.domain == "activity", MetricAnchorRegistry.key == "steps_per_day", MetricAnchorRegistry.active == True)
            .first()
        )
        if not reg:
            return ModalityScore(0.0, 0.0, {})
        score = interpolate_piecewise(steps.total_value, reg.anchors)
        return ModalityScore(score=score, confidence=1.0, detail={"steps": steps.total_value, "score": score})

    def _score_biomarkers(self, user_id: int, day: date, spec: HealthScoreSpec) -> ModalityScore:
        # Example: A1c and LDL if available
        detail: Dict[str, Any] = {}
        subs: List[float] = []
        keys = [
            ("a1c_pct", "glycemic", None),
            ("ldl_mgdl", "lipids", "13457-7"),  # example LOINC for LDL-C
        ]
        expected_units = {
            "a1c_pct": ["%", "percent", "%pct"],
            "ldl_mgdl": ["mg/dL", "mgdl"],
        }
        plausible_ranges = {
            "a1c_pct": (3.0, 20.0),
            "ldl_mgdl": (10.0, 500.0),
        }
        for key, group, loinc in keys:
            # Prefer LOINC if provided
            q = self.db.query(LabReportCategorized).filter(LabReportCategorized.user_id == user_id)
            if loinc:
                q = q.filter(LabReportCategorized.loinc_code == loinc)
            else:
                # map via LabTestMapping if needed
                pass
            row = q.order_by(desc(LabReportCategorized.test_date)).first()
            if not row:
                continue
            reg = (
                self.db.query(MetricAnchorRegistry)
                .filter(MetricAnchorRegistry.domain == "biomarker", MetricAnchorRegistry.key == key, MetricAnchorRegistry.active == True)
                .first()
            )
            if not reg:
                continue
            try:
                value = float(row.test_value)
            except Exception:
                continue
            # Unit & plausibility checks to avoid OCR/unit mismatches
            unit_clean = (row.test_unit or "").strip()
            if key in expected_units and expected_units[key]:
                allowed = expected_units[key]
                if unit_clean and all(unit_clean.lower() != u.lower() for u in allowed):
                    # Skip if unit is clearly incompatible
                    continue
            if key in plausible_ranges:
                lo, hi = plausible_ranges[key]
                if not (lo <= value <= hi):
                    continue
            sc = interpolate_piecewise(value, reg.anchors)
            subs.append(sc)
            detail[key] = {"value": value, "unit": unit_clean, "score": sc}
        score = sum(subs) / len(subs) if subs else 0.0
        conf = 1.0 if subs else 0.0
        return ModalityScore(score=score, confidence=conf, detail=detail)

    def _score_vitals_chronic(self, user_id: int, day: date, spec: HealthScoreSpec) -> ModalityScore:
        # 30-day average HR as a placeholder
        start = day - timedelta(days=30)
        rows = (
            self.db.query(VitalsDailyAggregate)
            .filter(
                and_(
                    VitalsDailyAggregate.user_id == user_id,
                    VitalsDailyAggregate.metric_type == "Heart Rate",
                    VitalsDailyAggregate.date >= start,
                    VitalsDailyAggregate.date <= day,
                )
            )
            .all()
        )
        if not rows:
            return ModalityScore(0.0, 0.0, {})
        reg = (
            self.db.query(MetricAnchorRegistry)
            .filter(MetricAnchorRegistry.domain == "vitals", MetricAnchorRegistry.key == "resting_hr", MetricAnchorRegistry.active == True)
            .first()
        )
        if not reg:
            return ModalityScore(0.0, 0.0, {})
        vals = [r.average_value for r in rows if r.average_value is not None]
        if not vals:
            return ModalityScore(0.0, 0.0, {})
        avg = sum(vals) / len(vals)
        sc = interpolate_piecewise(avg, reg.anchors)
        return ModalityScore(sc, 1.0, {"hr_30d_avg": avg, "score": sc})

    def _score_activity_chronic(self, user_id: int, day: date, spec: HealthScoreSpec) -> ModalityScore:
        # 7-day steps average
        start = day - timedelta(days=6)
        rows = (
            self.db.query(VitalsDailyAggregate)
            .filter(
                and_(
                    VitalsDailyAggregate.user_id == user_id,
                    VitalsDailyAggregate.metric_type == "Steps",
                    VitalsDailyAggregate.date >= start,
                    VitalsDailyAggregate.date <= day,
                )
            )
            .all()
        )
        if not rows:
            return ModalityScore(0.0, 0.0, {})
        reg = (
            self.db.query(MetricAnchorRegistry)
            .filter(MetricAnchorRegistry.domain == "activity", MetricAnchorRegistry.key == "steps_per_day", MetricAnchorRegistry.active == True)
            .first()
        )
        if not reg:
            return ModalityScore(0.0, 0.0, {})
        vals = [r.total_value for r in rows if r.total_value is not None]
        if not vals:
            return ModalityScore(0.0, 0.0, {})
        avg = sum(vals) / len(vals)
        sc = interpolate_piecewise(avg, reg.anchors)
        return ModalityScore(sc, 1.0, {"steps_7d_avg": avg, "score": sc})

    def _score_sleep_chronic(self, user_id: int, day: date, spec: HealthScoreSpec) -> ModalityScore:
        start = day - timedelta(days=6)
        rows = (
            self.db.query(VitalsDailyAggregate)
            .filter(and_(VitalsDailyAggregate.user_id == user_id, VitalsDailyAggregate.metric_type == "Sleep", VitalsDailyAggregate.date >= start, VitalsDailyAggregate.date <= day))
            .all()
        )
        if not rows:
            return ModalityScore(0.0, 0.0, {})
        reg = (
            self.db.query(MetricAnchorRegistry)
            .filter(MetricAnchorRegistry.domain == "sleep", MetricAnchorRegistry.key == "duration_h", MetricAnchorRegistry.active == True)
            .first()
        )
        if not reg:
            return ModalityScore(0.0, 0.0, {})
        
        # Extract sleep hours from each row, handling both duration_minutes and total_value
        vals_h = []
        for r in rows:
            if r.duration_minutes is not None and r.duration_minutes > 0:
                vals_h.append(r.duration_minutes / 60.0)
            elif r.total_value is not None and r.total_value > 0:
                # Check unit for conversion
                unit = (r.unit or "").lower()
                if unit == "minutes" or unit == "mins":
                    vals_h.append(r.total_value / 60.0)
                elif unit == "hours" or unit == "hrs" or unit == "h":
                    vals_h.append(r.total_value)
                else:
                    # Assume hours
                    vals_h.append(r.total_value)
        
        if not vals_h:
            return ModalityScore(0.0, 0.0, {})
        avg_h = sum(vals_h) / len(vals_h)
        sc = interpolate_piecewise(avg_h, reg.anchors)
        return ModalityScore(sc, 1.0, {"sleep_7d_avg_h": avg_h, "score": sc})

    def _score_nutrition(self, user_id: int, day: date, spec: HealthScoreSpec) -> ModalityScore:
        start = day - timedelta(days=6)
        rows = (
            self.db.query(NutritionDailyAggregate)
            .filter(and_(NutritionDailyAggregate.user_id == user_id, NutritionDailyAggregate.date >= start, NutritionDailyAggregate.date <= day))
            .all()
        )
        if not rows:
            return ModalityScore(0.0, 0.0, {})
        # Use energy balance vs personalized calorie target
        total_cals = [r.total_calories for r in rows if r.total_calories is not None]
        if not total_cals:
            return ModalityScore(0.0, 0.0, {})
        avg_cals = sum(total_cals) / len(total_cals)
        # Look up energy balance anchors; expect anchors expressed as % deviation
        reg = (
            self.db.query(MetricAnchorRegistry)
            .filter(MetricAnchorRegistry.domain == "nutrition", MetricAnchorRegistry.key == "energy_balance_pct_abs", MetricAnchorRegistry.active == True)
            .first()
        )
        if not reg:
            return ModalityScore(0.0, 0.0, {})
        target = self._get_daily_calorie_target(user_id)
        deviation_pct = abs((avg_cals - target) / target * 100.0)
        sc = interpolate_piecewise(deviation_pct, reg.anchors)
        return ModalityScore(sc, 1.0, {"avg_calories": avg_cals, "target": target, "deviation_pct": deviation_pct, "score": sc})

    def _score_medications(self, user_id: int, day: date, spec: HealthScoreSpec) -> ModalityScore:
        """Compute a PDC-like adherence proxy using PharmacyBill records when raw fills are unavailable.

        Assumption: each bill provides up to 30 days of coverage starting from bill_date.
        Coverage across multiple bills is unioned. If no bills in the last 30 days, return 0/conf=0.
        """
        window_days = 30
        window_start = day - timedelta(days=window_days)
        bills = (
            self.db.query(PharmacyBill)
            .filter(
                and_(
                    PharmacyBill.user_id == user_id,
                    PharmacyBill.bill_date >= window_start - timedelta(days=30),  # allow earlier bill to cover into window
                    PharmacyBill.bill_date <= day,
                )
            )
            .all()
        )
        if not bills:
            return ModalityScore(0.0, 0.0, {})

        covered = set()
        for b in bills:
            start_d = b.bill_date
            if not start_d:
                continue
            assumed_days_supply = 30
            for i in range(assumed_days_supply):
                d = start_d + timedelta(days=i)
                if window_start <= d <= day:
                    covered.add(d)
        covered_days = len(covered)
        pdc = min(1.0, covered_days / float(window_days)) if window_days > 0 else 0.0

        # Map PDC to score using anchors
        reg = (
            self.db.query(MetricAnchorRegistry)
            .filter(MetricAnchorRegistry.domain == "medication", MetricAnchorRegistry.key == "pdc", MetricAnchorRegistry.active == True)
            .first()
        )
        if not reg:
            # Fallback simple mapping
            score = 100.0 * pdc
        else:
            # Anchors are defined on 0..1; interpolate on that scale
            score = interpolate_piecewise(pdc, reg.anchors)
        return ModalityScore(score=float(score), confidence=0.6, detail={"pdc": pdc, "covered_days": covered_days, "window_days": window_days, "source": "pharmacy_bills"})

    # --- Explainability helpers ---
    def _derive_reasons_and_actions(
        self,
        *,
        acute_detail: Dict[str, Any],
        chronic_detail: Dict[str, Any],
        acute_score: float,
        chronic_score: float,
    ) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
        reasons: list[Dict[str, Any]] = []
        actions: list[Dict[str, Any]] = []

        def is_missing_modality(d: Any) -> bool:
            if not d or not isinstance(d, dict):
                return True
            # If only meta keys exist (score/confidence) and no payload keys, treat as missing
            payload_keys = [k for k in d.keys() if k not in ("score", "confidence")]
            if len(payload_keys) == 0:
                return True
            # Additionally, zero confidence indicates no usable data
            try:
                if float(d.get("confidence", 0)) == 0:
                    return True
            except Exception:
                pass
            return False

        # Biomarkers
        biomarkers = chronic_detail.get("biomarkers", {})
        a1c = biomarkers.get("a1c_pct")
        if a1c and a1c.get("score", 100) <= 60:
            reasons.append({
                "driver": "Biomarkers",
                "metric": "HbA1c",
                "message": f"HbA1c elevated ({a1c.get('value')} {a1c.get('unit') or '%'})",
                "impact": 0.3,
            })
            actions += [
                {"driver": "Biomarkers", "action": "Confirm HbA1c with correct units (%) in lab", "priority": "high"},
                {"driver": "Biomarkers", "action": "Review diabetes meds/adherence with clinician", "priority": "high"},
                {"driver": "Biomarkers", "action": "Target ≥150 min/week moderate activity", "priority": "medium"},
                {"driver": "Biomarkers", "action": "Align calories to goal; added sugar <10% kcal", "priority": "medium"},
            ]
        # Generic biomarker guidance if no payload
        bm_score = float(biomarkers.get("score", 0) or 0)
        bm_conf = float(biomarkers.get("confidence", 0) or 0)
        if bm_conf == 0:
            reasons.append({"driver": "Biomarkers", "metric": "biomarkers", "message": "No recent biomarker results on file", "impact": 0.15})
            actions.append({"driver": "Biomarkers", "action": "Upload lab reports or connect lab integration", "priority": "medium"})
        elif bm_score < 70 and not any(r.get("driver") == "Biomarkers" for r in reasons):
            reasons.append({"driver": "Biomarkers", "metric": "biomarkers", "message": "Some biomarkers outside target range", "impact": 0.2})
            actions.append({"driver": "Biomarkers", "action": "Review abnormal markers with your clinician", "priority": "high"})

        # Medications adherence
        meds = chronic_detail.get("medications", {})
        pdc = meds.get("pdc")
        if isinstance(pdc, (int, float)) and pdc < 0.8:
            reasons.append({
                "driver": "Medications",
                "metric": "PDC",
                "message": f"Low adherence (PDC ~{round(pdc,2)})",
                "impact": 0.2,
            })
            actions += [
                {"driver": "Medications", "action": "Set refill reminders and daily dose schedule", "priority": "high"},
                {"driver": "Medications", "action": "Confirm current prescriptions and quantities", "priority": "medium"},
            ]
        md_conf = float(meds.get("confidence", 0) or 0)
        md_score = float(meds.get("score", 0) or 0)
        if md_conf == 0:
            reasons.append({"driver": "Medications", "metric": "pdc", "message": "No pharmacy data linked", "impact": 0.1})
            actions.append({"driver": "Medications", "action": "Add medications in profile or connect pharmacy", "priority": "medium"})
        elif md_score < 70 and not any(r.get("driver") == "Medications" for r in reasons):
            reasons.append({"driver": "Medications", "metric": "pdc", "message": "Medication adherence could be improved", "impact": 0.15})
            actions.append({"driver": "Medications", "action": "Use reminders and pill organizer", "priority": "medium"})

        # Missing acute data
        for k, label in (("vitals_today", "Today’s vitals"), ("activity_today", "Today’s activity"), ("sleep_last_night", "Last-night sleep")):
            if is_missing_modality(acute_detail.get(k)):
                reasons.append({
                    "driver": "Data Gaps",
                    "metric": k,
                    "message": f"{label} missing; acute score limited",
                    "impact": 0.15,
                })
        if any(r.get("driver") == "Data Gaps" for r in reasons):
            actions.append({"driver": "Data Gaps", "action": "Connect device/enable permissions to capture vitals, steps, and sleep", "priority": "high"})

        # Acute modality guidance when present but low
        vt = acute_detail.get("vitals_today") or {}
        at = acute_detail.get("activity_today") or {}
        sl = acute_detail.get("sleep_last_night") or {}
        if not is_missing_modality(vt) and float(vt.get("score", 100) or 100) < 60:
            reasons.append({"driver": "Today’s vitals", "metric": "vitals_today", "message": "Today’s vitals outside target range", "impact": 0.2})
            actions.append({"driver": "Today’s vitals", "action": "Recheck BP/HR/SpO₂ after 5 minutes rest", "priority": "medium"})
        if not is_missing_modality(at) and float(at.get("score", 100) or 100) < 60:
            reasons.append({"driver": "Today’s activity", "metric": "activity_today", "message": "Low activity today", "impact": 0.15})
            actions.append({"driver": "Today’s activity", "action": "Take a 10–15 minute walk now", "priority": "medium"})
        if not is_missing_modality(sl) and float(sl.get("score", 100) or 100) < 60:
            reasons.append({"driver": "Last-night sleep", "metric": "sleep_last_night", "message": "Short or disrupted sleep last night", "impact": 0.15})
            actions.append({"driver": "Last-night sleep", "action": "Aim 7–9 hours; keep consistent bedtime", "priority": "medium"})

        # Chronic modality guidance from meta scores
        sv = chronic_detail.get("vitals_30d") or {}
        sa = chronic_detail.get("activity") or {}
        ss = chronic_detail.get("sleep") or {}
        sn = chronic_detail.get("nutrition") or {}
        if float(sv.get("confidence", 0) or 0) == 0:
            reasons.append({"driver": "Vitals", "metric": "vitals_30d", "message": "No 30d vitals trend available", "impact": 0.05})
        elif float(sv.get("score", 100) or 100) < 70:
            reasons.append({"driver": "Vitals", "metric": "vitals_30d", "message": "Vitals trend (30d) outside target", "impact": 0.1})
        if float(sa.get("confidence", 0) or 0) == 0:
            reasons.append({"driver": "Activity", "metric": "activity_7d", "message": "No weekly activity data", "impact": 0.05})
        elif float(sa.get("score", 100) or 100) < 70:
            reasons.append({"driver": "Activity", "metric": "activity_7d", "message": "Low average activity (7d)", "impact": 0.1})
            actions.append({"driver": "Activity", "action": "Target ≥7k average daily steps", "priority": "medium"})
        if float(ss.get("confidence", 0) or 0) == 0:
            reasons.append({"driver": "Sleep", "metric": "sleep_7d", "message": "No weekly sleep data", "impact": 0.05})
        elif float(ss.get("score", 100) or 100) < 70:
            reasons.append({"driver": "Sleep", "metric": "sleep_7d", "message": "Low sleep duration/quality (7d)", "impact": 0.1})
            actions.append({"driver": "Sleep", "action": "Keep a wind-down routine; reduce late caffeine", "priority": "medium"})
        if float(sn.get("confidence", 0) or 0) == 0:
            reasons.append({"driver": "Nutrition", "metric": "nutrition_7d", "message": "No recent nutrition data", "impact": 0.05})
        elif float(sn.get("score", 100) or 100) < 70:
            reasons.append({"driver": "Nutrition", "metric": "nutrition_7d", "message": "Calories off personalized target (7d)", "impact": 0.1})
            actions.append({"driver": "Nutrition", "action": "Track meals; aim within ±10% of daily target", "priority": "medium"})

        # Limit to reasonable counts overall
        reasons = reasons[:10]
        actions = actions[:10]
        return reasons, actions

    def _get_daily_calorie_target(self, user_id: int) -> float:
        """Find calorie target by fallback: active goal (daily calories) → user profile TDEE → default 2000."""
        # 1) Active goal → daily timeframe target for nutrient 'calories'
        goal = (
            self.db.query(NutritionGoal)
            .filter(and_(NutritionGoal.user_id == user_id, NutritionGoal.status == "active"))
            .order_by(NutritionGoal.effective_at.desc())
            .first()
        )
        if goal:
            target_row = None
            for t in goal.targets:
                try:
                    if not t.is_active or t.timeframe != "daily":
                        continue
                    if t.nutrient and t.nutrient.key == "calories":
                        target_row = t
                        break
                except Exception:
                    continue
            if target_row:
                if target_row.target_type == "exact" and target_row.target_max is not None:
                    return float(target_row.target_max)
                # midpoint if range else min/max fallback
                if target_row.target_min is not None and target_row.target_max is not None:
                    return float((target_row.target_min + target_row.target_max) / 2.0)
                if target_row.target_min is not None:
                    return float(target_row.target_min)
                if target_row.target_max is not None:
                    return float(target_row.target_max)

        # 2) Derive from user profile with Mifflin-St Jeor + activity factor
        profile = self.db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if profile and profile.weight_kg and profile.height_cm and profile.date_of_birth and profile.gender:
            age = self._age_years(profile.date_of_birth)
            s = 5 if str(profile.gender).lower().startswith("m") else -161
            bmr = 10 * float(profile.weight_kg) + 6.25 * float(profile.height_cm) - 5 * float(age) + s
            activity_level = (profile.activity_level or "sedentary").lower()
            multiplier = {
                "sedentary": 1.2,
                "lightly_active": 1.375,
                "moderately_active": 1.55,
                "very_active": 1.725,
                "extra_active": 1.9,
            }.get(activity_level, 1.2)
            tdee = bmr * multiplier
            return float(max(1200.0, min(4000.0, tdee)))

        # 3) Default
        return 2000.0

    @staticmethod
    def _age_years(dob) -> int:
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    # --- Sync anchors from LabTestMapping (LOINC) ---
    def sync_metric_anchors_from_lab_mapping(self) -> int:
        """Ensure MetricAnchorRegistry rows exist for key biomarkers where LOINC is known.

        We consult LabTestMapping to discover available tests/LOINC and upsert registry
        rows with our default anchors/spec for: A1c, LDL, HDL, TG, eGFR, ALT, AST, hs-CRP, Vitamin D, glucose.
        Returns number of upserts.
        """
        # Default anchors per key (value->score) consistent with the earlier spec
        default_anchors = {
            "a1c_pct": [[5.0,100],[5.6,95],[5.7,90],[6.0,75],[6.5,55],[7.0,45],[8.0,30],[9.0,20],[10.0,10]],
            "ldl_mgdl": [[70,100],[100,90],[130,70],[160,45],[190,25],[220,10]],
            "hdl_mgdl_male": [[25,25],[35,55],[40,70],[50,85],[60,100]],
            "hdl_mgdl_female": [[30,35],[40,60],[50,80],[60,95],[70,100]],
            "triglycerides_mgdl": [[100,100],[150,85],[200,70],[300,50],[400,35],[500,20],[1000,5]],
            "egfr_ml_min_1_73m2": [[15,20],[30,35],[45,50],[60,70],[75,85],[90,100]],
            "alt_u_l": [[25,100],[40,90],[60,75],[80,60],[120,40],[200,20],[300,10]],
            "ast_u_l": [[25,100],[40,90],[60,75],[80,60],[120,40],[200,20],[300,10]],
            "hs_crp_mg_l": [[1.0,100],[3.0,75],[5.0,60],[10,40],[20,20],[50,5]],
            "vitd_25oh_ngml": [[10,10],[15,30],[20,50],[25,65],[30,100],[50,100],[60,90],[80,70],[100,50]],
            "fasting_glucose_mgdl": [[50,10],[60,20],[70,95],[80,100],[99,100],[100,85],[110,75],[126,55],[150,35],[200,15],[250,5]],
        }
        # Map common test names -> (key, group, optional sex variant)
        name_to_key = {
            "hbA1c": ("a1c_pct", "glycemic"),
            "hba1c": ("a1c_pct", "glycemic"),
            "ldl": ("ldl_mgdl", "lipids"),
            "ldl cholesterol": ("ldl_mgdl", "lipids"),
            "hdl": ("hdl_mgdl_male", "lipids"),  # will not set sex here; consumer should choose
            "hdl cholesterol": ("hdl_mgdl_male", "lipids"),
            "triglycerides": ("triglycerides_mgdl", "lipids"),
            "egfr": ("egfr_ml_min_1_73m2", "renal"),
            "alt": ("alt_u_l", "hepatic"),
            "ast": ("ast_u_l", "hepatic"),
            "hs-crp": ("hs_crp_mg_l", "inflammation"),
            "vitamin d": ("vitd_25oh_ngml", "vitamin_d"),
            "vitamin d 25(oh)": ("vitd_25oh_ngml", "vitamin_d"),
            "fasting glucose": ("fasting_glucose_mgdl", "glycemic"),
            "glucose fasting": ("fasting_glucose_mgdl", "glycemic"),
        }

        upserts = 0
        mappings = self.db.query(LabTestMapping).filter(LabTestMapping.is_active == True).all()
        # Track keys we've already inserted/updated in this run to avoid duplicates
        processed_keys: set[str] = set(
            [r.key for r in self.db.query(MetricAnchorRegistry.key).filter(MetricAnchorRegistry.domain == "biomarker").all()]
        )
        for m in mappings:
            test_name_norm = (m.test_name or "").strip().lower()
            loinc = (m.loinc_code or "").strip() or None
            if not loinc:
                continue
            nk = name_to_key.get(test_name_norm)
            if not nk:
                # Try standardized name if available
                tn = (m.test_name_standardized or "").strip().lower()
                nk = name_to_key.get(tn)
            if not nk:
                continue
            key, group_key = nk
            anchors = default_anchors.get(key)
            if not anchors:
                continue
            # Skip if this key already handled in this sync run
            if key in processed_keys:
                # Optionally update loinc for existing row if missing
                existing_once = (
                    self.db.query(MetricAnchorRegistry)
                    .filter(MetricAnchorRegistry.domain == "biomarker", MetricAnchorRegistry.key == key)
                    .first()
                )
                if existing_once and not existing_once.loinc_code and loinc:
                    existing_once.loinc_code = loinc
                    existing_once.group_key = group_key
                    upserts += 1
                continue
            existing = (
                self.db.query(MetricAnchorRegistry)
                .filter(
                    MetricAnchorRegistry.domain == "biomarker",
                    MetricAnchorRegistry.key == key,
                )
                .first()
            )
            if existing:
                # Update LOINC if not set
                if not existing.loinc_code:
                    existing.loinc_code = loinc
                    existing.group_key = group_key
                    upserts += 1
                processed_keys.add(key)
            else:
                row = MetricAnchorRegistry(
                    domain="biomarker",
                    key=key,
                    loinc_code=loinc,
                    unit=m.common_units,
                    pattern="lower" if key in ("ldl_mgdl", "triglycerides_mgdl", "hs_crp_mg_l", "fasting_glucose_mgdl") else ("higher" if key.startswith("hdl_") else "range"),
                    anchors=anchors,
                    half_life_days=180,
                    danger=None,
                    group_key=group_key,
                    active=True,
                    introduced_in="v1",
                )
                self.db.add(row)
                # Flush so subsequent iterations can see this row
                self.db.flush()
                upserts += 1
                processed_keys.add(key)
        if upserts:
            self.db.commit()
        return upserts

    @staticmethod
    def _infer_age_band(profile: Optional[UserProfile]) -> str:
        if not profile or not profile.date_of_birth:
            return "40-64"  # neutral default
        today = date.today()
        age = today.year - profile.date_of_birth.year - ((today.month, today.day) < (profile.date_of_birth.month, profile.date_of_birth.day))
        if age < 40:
            return "18-39"
        if age < 65:
            return "40-64"
        return "65+"


