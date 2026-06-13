import asyncio
import sys
from contextlib import asynccontextmanager

# psycopg3 requires SelectorEventLoop on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .database import init_db, AsyncSessionLocal
from .routers import admin, auth, chat, history, opportunities, profile, tracker, users
from . import scheduler
from .services import embedding_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler.start()
    # Pre-warm the embedding model so the first request doesn't pay the load cost
    import asyncio
    await asyncio.get_event_loop().run_in_executor(None, embedding_service._get_model)
    yield
    scheduler.stop()


app = FastAPI(
    title="Mitra — Career Intelligence OS",
    description="Multi-agent AI system for ML/AI internship search, skill gap analysis, and career roadmapping.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(users.router)
app.include_router(profile.router)
app.include_router(history.router)
app.include_router(opportunities.router)
app.include_router(tracker.router)
app.include_router(chat.router)


@app.get("/api/health")
async def health():
    db_status = "ok"
    opportunity_count = 0
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(text("SELECT COUNT(*) FROM opportunities"))
            opportunity_count = result.scalar_one()
    except Exception:
        db_status = "error"

    model_loaded = embedding_service._get_model.cache_info().currsize > 0

    payload = {
        "status": "ok" if db_status == "ok" else "error",
        "db": db_status,
        "opportunity_count": opportunity_count,
        "embedding_model": "loaded" if model_loaded else "unloaded",
    }
    status_code = 503 if db_status == "error" else 200
    return JSONResponse(content=payload, status_code=status_code)


@app.get("/")
async def root():
    return {
        "name": "Mitra Career Intelligence OS",
        "version": "1.0.0",
        "agents": [
            "Opportunity Hunter",
            "Resume Analyzer",
            "Gap Detector",
            "Roadmap Planner",
            "Application Tracker",
            "Interview Coach",
        ],
        "docs": "/docs",
    }
