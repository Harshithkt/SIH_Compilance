from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import bootstrap_users
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import admin, auth, cases, evidence, physical_verifications, public, rules, scans, signals, system, worklist
from app.schema_sync import sync_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    sync_schema(engine)
    with SessionLocal() as db:
        bootstrap_users(db)
    yield


app = FastAPI(
    title="LabelLens",
    description=(
        "Evidence-grade field inspection and enforcement intelligence for Legal Metrology. "
        "Scan → prove → prioritise."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(scans.router)
app.include_router(evidence.router)
app.include_router(worklist.router)
app.include_router(rules.router)
app.include_router(system.router)
app.include_router(cases.router)
app.include_router(admin.router)
app.include_router(physical_verifications.router)
app.include_router(signals.router)
app.include_router(public.router)


@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "tagline": "The enforcement case-file for Legal Metrology",
        "docs": "/docs",
    }
