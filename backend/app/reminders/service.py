from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from .api import router as reminders_router
from .config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="Reminder Service")
    app.include_router(reminders_router, prefix="/api/v1/reminders", tags=["reminders"])
    if settings.METRICS_ENABLED:
        Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    return app


app = create_app()


