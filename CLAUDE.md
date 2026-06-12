# Mitra — CLAUDE.md

Project context for AI-assisted development. Read this before making any changes.

## What this project is

Mitra is a **multi-agent career intelligence system** for ML/AI students in India. It is a portfolio project designed to demonstrate:

- Multi-agent orchestration with LangGraph
- Semantic search with pgvector
- Episodic memory across sessions
- Skill gap recommendation with reciprocal matching
- LLM fine-tuning (QLoRA, Qwen2.5-3B, knowledge distillation)
- Production-ready FastAPI backend with SSE streaming

This is NOT a generic chatbot. It is a domain-specific agentic system with a real use case.

## Project layout

```
mitra/
├── backend/                   FastAPI backend (primary codebase)
│   ├── app/
│   │   ├── main.py            entry point — registers routers, runs init_db() on startup
│   │   ├── config.py          pydantic-settings — reads from .env
│   │   ├── database.py        async SQLAlchemy engine + init_db()
│   │   ├── agents/
│   │   │   ├── state.py       AgentState TypedDict — shared across all nodes
│   │   │   ├── graph.py       LangGraph StateGraph — all wiring lives here
│   │   │   ├── opportunity_hunter.py
│   │   │   ├── resume_analyzer.py
│   │   │   ├── gap_detector.py
│   │   │   ├── roadmap_planner.py
│   │   │   ├── application_tracker.py
│   │   │   └── interview_coach.py
│   │   ├── routers/
│   │   │   ├── chat.py        SSE streaming + sync chat endpoints
│   │   │   ├── profile.py     resume upload + skill profile
│   │   │   ├── opportunities.py
│   │   │   ├── tracker.py     application CRUD
│   │   │   └── users.py
│   │   ├── services/
│   │   │   ├── llm_client.py  ONLY place that imports anthropic — all agents use this
│   │   │   ├── embedding_service.py  sentence-transformers singleton
│   │   │   ├── memory_service.py     pgvector store/retrieve
│   │   │   └── skill_graph.py        skill extraction + match scoring
│   │   └── models/
│   │       ├── db.py          SQLAlchemy ORM (7 tables)
│   │       └── schemas.py     Pydantic request/response schemas
│   ├── db/
│   │   └── seed_opportunities.py   run once to populate opportunity data
│   └── requirements.txt
├── ml/
│   ├── generate_synthetic_data.py  Claude → 500 training pairs
│   ├── train_skill_gap_classifier.py  QLoRA fine-tuning (run on Colab T4)
│   └── requirements.txt
├── SRS.md                     Full Software Requirements Specification
├── CLAUDE.md                  This file
└── README.md                  Setup instructions
```

## Key architecture rules

1. **All LLM calls go through `services/llm_client.py`**. Never import `anthropic` directly in agents or routers.

2. **All embedding operations go through `services/embedding_service.py`**. The model is loaded once as a singleton.

3. **DB session injection**: Routers get `db` via `Depends(get_db)`. Agent nodes get `db` passed in via `_bind_db()` in `graph.py`. Never create a new session inside an agent.

4. **AgentState is the single source of truth during a graph run**. Agents read from state and return partial dicts to update it. Do not use global variables or module-level caches for request state.

5. **Each agent is in its own file** under `agents/`. The only file that wires agents together is `graph.py`.

6. **The `responder` node is the final synthesis node**. All agent paths (except `interview_coach` which sets `final_response` itself) terminate at `responder → END`.

## Database

- **Host:** Neon (free PostgreSQL + pgvector). Connection string in `.env` as `DATABASE_URL`.
- **Driver:** psycopg3 (`psycopg[asyncio]`). Connection string must start with `postgresql+psycopg://`.
- **pgvector:** enabled via `CREATE EXTENSION IF NOT EXISTS vector` in `init_db()`.
- **Tables:** created automatically on startup. Never run raw `CREATE TABLE` statements manually.
- **Migrations:** no Alembic yet (Phase 2). For schema changes, drop and recreate in dev.

## LangGraph specifics

- **Version:** 0.2.x
- **Graph is rebuilt per request** inside `build_graph(db)`. This is intentional — it binds the DB session.
- **Stream mode:** `stream_mode="updates"` in the chat SSE endpoint — emits `{node_name: state_update}` per step.
- **State updates:** each node returns a partial dict; LangGraph merges it into state.
- **`messages` field** uses `Annotated[list, add_messages]` — LangGraph accumulates messages, do not return the full list from a node.

## Naming conventions

- Agent node functions: `{agent_name}_node(state, db)` — always async, always accept `db` as kwarg
- Router functions: snake_case FastAPI endpoint functions
- DB models: PascalCase (`SkillProfile`, `MemoryEpisode`)
- Pydantic schemas: `{Model}Read`, `{Model}Create`, `{Model}Update`

## Adding a new agent

1. Create `backend/app/agents/my_agent.py` with `async def my_agent_node(state: AgentState, db: AsyncSession) -> dict`
2. Add to `graph.py`: register node, add edges, add intent label in `intent_router`
3. Add intent label to `llm_client.classify_intent()` prompt
4. Add new fields to `AgentState` in `state.py` if needed

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | psycopg3-format PostgreSQL URL |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `LANGSMITH_API_KEY` | No | LangSmith tracing (optional) |
| `LANGSMITH_TRACING` | No | `true` to enable tracing |
| `CLAUDE_MODEL` | No | defaults to `claude-sonnet-4-6` |
| `EMBEDDING_MODEL` | No | defaults to `all-MiniLM-L6-v2` |

## Running locally

```bash
cd backend

# .venv already exists (created with: uv venv --python 3.12)
# Activate it:
source .venv/bin/activate          # macOS / Linux
.venv\Scripts\activate             # Windows

uv pip install -r requirements.txt
cp .env.example .env               # fill in DATABASE_URL + ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```

Seed data (run once):
```bash
python -m db.seed_opportunities
```

## Common tasks

**Test the full agent pipeline:**
```bash
curl -X POST http://localhost:8000/api/users -H "Content-Type: application/json" \
  -d '{"name": "Test", "goal": "ML internships India"}'
# copy the returned id as USER_ID

curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "USER_ID", "message": "Find me ML internships and show my skill gaps"}'
```

**Upload a resume:**
```bash
curl -X POST http://localhost:8000/api/profile/upload \
  -F "user_id=USER_ID" \
  -F "file=@/path/to/resume.pdf"
```

**Stream chat (SSE):**
```bash
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"user_id": "USER_ID", "message": "What should I learn next?"}'
```

## What NOT to do

- Don't add authentication middleware until Phase 3 — it would break the single-tenant model
- Don't switch from psycopg3 back to asyncpg — pgvector integration is cleaner with psycopg3
- Don't load the embedding model inside request handlers — it's a singleton in `embedding_service.py`
- Don't store secrets in code — all config goes through `Settings` in `config.py`
- Don't add synchronous SQLAlchemy sessions — all DB access is async
