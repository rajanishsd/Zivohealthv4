from fastapi import APIRouter

from app.api.v1.endpoints import auth
from app.api.v1.endpoints import dual_auth
from app.api.v1.endpoints import chat_sessions
from app.api.v1.endpoints import doctors
from app.api.v1.endpoints import health
from app.api.v1.endpoints import appointments
from app.api.v1.endpoints import vitals
from app.api.v1.endpoints import nutrition
from app.api.v1.endpoints import nutrition_goals
from app.api.v1.endpoints import agents
from app.api.v1.endpoints import lab_reports
from app.api.v1.endpoints import files
from app.api.v1.endpoints import feedback
from app.api.v1.endpoints import video
from app.api.v1.endpoints import dashboard as dashboard_v1
from app.api.v1.endpoints import admin_users
from app.api.v1.endpoints import password_reset
from app.api.v1.endpoints import onboarding
from app.api.v1.endpoints import profile
from app.api.v1.endpoints import account
from app.api.v1.endpoints import devices
from app.api.v1.endpoints import notifications
# Reminders are handled by a separate microservice - no need to import here
from app.routes import audit
from app.routes import dashboard

# from app.routes import telemetry_dashboard

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(dual_auth.router, prefix="/auth", tags=["dual-auth"])
api_router.include_router(password_reset.router, prefix="/auth", tags=["auth"])
api_router.include_router(chat_sessions.router, prefix="/chat-sessions", tags=["chat-sessions"])
api_router.include_router(doctors.router, prefix="/doctors", tags=["doctors"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(vitals.router, prefix="/vitals", tags=["vitals"])
api_router.include_router(nutrition.router, prefix="/nutrition", tags=["nutrition"])
api_router.include_router(nutrition_goals.router, prefix="/nutrition-goals", tags=["nutrition-goals"])
api_router.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(lab_reports.router, prefix="/lab-reports", tags=["lab-reports"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
api_router.include_router(video.router, prefix="/video", tags=["video"])
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])
api_router.include_router(account.router, prefix="/account", tags=["account"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(dashboard_v1.router, prefix="/dashboard", tags=["dashboard-v1"])
# Admin users management
api_router.include_router(admin_users.router, prefix="/admin", tags=["admin-users"])
# Reminders are handled by a separate microservice at http://localhost:8085 

# api_router.include_router(telemetry_dashboard.router, prefix="/telemetry-audit", tags=["telemetry-dashboard"])