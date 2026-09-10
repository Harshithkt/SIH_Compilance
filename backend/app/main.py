from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import evidence, rules, scans, system, worklist


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scans.router)
app.include_router(evidence.router)
app.include_router(worklist.router)
app.include_router(rules.router)
app.include_router(system.router)


@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "tagline": "The enforcement case-file for Legal Metrology",
        "docs": "/docs",
    }
