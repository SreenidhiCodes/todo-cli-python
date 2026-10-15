from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import get_settings
from app.database import engine
from app.routers import auth, family_tasks, groceries, projects, tasks

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.environment == "production" and len(settings.secret_key) < 32:
        raise RuntimeError("Set a SECRET_KEY with at least 32 characters before running in production.")
    yield
    engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "A multi-user task management API with JWT authentication, projects, priorities, "
        "due dates, tags, shared household grocery planning, filtering, and statistics."
    ),
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(tasks.router, prefix=settings.api_prefix)
app.include_router(projects.router, prefix=settings.api_prefix)
app.include_router(groceries.router, prefix=settings.api_prefix)
app.include_router(family_tasks.router, prefix=settings.api_prefix)
app.mount("/static", StaticFiles(directory="web"), name="static")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse("web/index.html")


@app.get("/healthz", tags=["operations"], summary="Check application and database health")
def health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ok", "service": settings.app_name}
