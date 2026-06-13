import asyncio
import sys
from contextlib import asynccontextmanager

# psycopg3 requires SelectorEventLoop on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .routers import admin, auth, chat, history, opportunities, profile, tracker, users
from . import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler.start()
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
