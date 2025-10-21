from .user import User
from .user_identity import UserIdentity
from .login_event import LoginEvent
from .password_reset_token import PasswordResetToken
from .doctor import Doctor, ConsultationRequest
from .chat_session import ChatSession, ChatMessage, Prescription
from .clinical_notes import ClinicalNotes
from .appointment import Appointment
from .health_indicator import (
    HealthIndicatorCategory,
    HealthIndicator,
    PatientHealthRecord,
    HealthDataHistory,
    PatientHealthSummary
)
from .vitals_data import (
    VitalsRawData,
    VitalsHourlyAggregate,
    VitalsDailyAggregate,
    VitalsWeeklyAggregate,
    VitalsMonthlyAggregate,
    VitalsSyncStatus,
    VitalMetricType,
    VitalDataSource
)
from .nutrition_data import (
    NutritionRawData,
    NutritionDailyAggregate,
    NutritionWeeklyAggregate,
    NutritionMonthlyAggregate,
    NutritionSyncStatus,
    NutritionDataSource,
    MealType,
    DishType,
    NutritionMealPlan
)
from .nutrition_goals import (
    NutritionObjective,
    NutritionNutrientCatalog,
    NutritionGoal,
    NutritionGoalTarget,
    UserNutrientFocus
)
from .health_data import (
    LabReport,
    LabReportCategorized,
    PharmacyBill,
    PharmacyMedication,
    DocumentProcessingLog,
    OpenTelemetryTrace,
    AgentMemory,
    MedicalImage
)
from .lab_test_mapping import LabTestMapping
from .lab_aggregation import LabReportDaily, LabReportMonthly, LabReportQuarterly, LabReportYearly
from .user_profile import (
    UserProfile,
    Condition,
    Allergen,
    UserCondition,
    UserAllergy,
    UserLifestyle,
    UserNotificationPreferences,
    UserConsent,
    UserMeasurementPreferences,
)
from .feedback import FeedbackScreenshot
from .admin import Admin
from .user_device import UserDevice
from .timezone import TimezoneDictionary
from .country_code import CountryCodeDictionary
from .mental_health import (
    MentalHealthEntry,
    MentalHealthDailyAggregate,
    MentalHealthFeelingDictionary,
    MentalHealthImpactDictionary,
    MentalHealthPleasantnessDictionary,
    MentalHealthEntryTypeDictionary,
)

# Health scoring models (internal)
from app.health_scoring.models import (
    HealthScoreSpec,
    MetricAnchorRegistry,
    HealthScoreResultDaily,
    HealthScoreCalcLog,
)
