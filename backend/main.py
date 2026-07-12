"""OmniOps backend FastAPI application entrypoint."""

from fastapi import FastAPI

from api.routes.health import router as health_router
from api.routes.jobs import router as jobs_router
from api.routes.uploads import router as uploads_router
from config.settings import get_settings

settings = get_settings()

app = FastAPI(title=settings.fastapi.app_name)
app.include_router(health_router)
app.include_router(uploads_router)
app.include_router(jobs_router)
