# Mitra: Career Intelligence OS

A production-grade multi-agent AI system for ML/AI students. Finds internships, maps skill gaps, builds learning roadmaps, coaches interviews, and tracks applications — purpose-built for the Indian ML/AI job market.

**Stack:** FastAPI · LangGraph 0.2 · pgvector · Claude Sonnet 4.6 + Haiku 4.5 · sentence-transformers · Next.js 14 · TypeScript

---

## Architecture

### Agent graph (as implemented)

```
POST /api/chat/stream
         │
         ▼
   FastAPI SSE endpoint  (rate-limited: 10 req/user/min)
         │
         ▼
   build_graph(db)       ← compiled per request, binds AsyncSession
         │
    ┌────┴────┐
    │         │   parallel superstep
    ▼         ▼
memory_   intent_        memory_retriever: hybrid pgvector search
retriever router         intent_router:    Haiku classifies one of 7 intents
    │         │
    └────┬────┘
         ▼
     router_node         fan-in join; fires conditional routing
         │
    ┌────┼─────────────────────────────────────┐
    │    │            │           │             │
    ▼    ▼            ▼           ▼             ▼
oppty_ resume_    gap_       roadmap_  app_tracker  interview_
hunter analyzer  detector   planner               coach
    │    │            │           │             │
    └────┴────────────┴───────────┴─────────────┘
                        │
                   responder         ← Sonnet synthesis
                        │
                 memory_writer       ← stores episode to pgvector
                        │
                       END
```

**What happens on every request:**

1. `memory_retriever` and `intent_router` run **in parallel** — vector DB search overlaps with Haiku LLM call (~2–3s saved)
2. Intent is classified into one of 7 labels; the conditional edge routes to the correct agent
3. The agent executes, updates shared `AgentState`, and passes to `responder`
4. `responder` synthesises a final response using all accumulated state
5. The response is streamed word-by-word to the client as SSE `token` events
6. `memory_writer` persists the interaction as a pgvector episode

**Important constraint:** `build_graph(db)` is called per request so each node gets the request-scoped `AsyncSession` — no shared state across concurrent requests.

---

## Agent Nodes

| Node | File | What it actually does |
|---|---|---|
| `memory_retriever` | `graph.py` | Hybrid pgvector query: `importance × (0.7 × cosine + 0.3 × recency)`. Also retrieves relevant resume chunks. |
| `intent_router` | `graph.py` + `llm_client.py` | Haiku `classify_intent()` → one of `opportunities \| resume \| gaps \| roadmap \| track \| interview \| general`. Optional: replaced by QLoRA fine-tuned Qwen2.5-3B when `USE_LOCAL_CLASSIFIER=true`. |
| `opportunity_hunter` | `agents/opportunity_hunter.py` | Detects "latest/recent/new" keywords → triggers `quick_fetch()` (8-second live scrape). Then cosine search over embeddings. |
| `resume_analyzer` | `agents/resume_analyzer.py` | Reads stored resume text, re-runs Sonnet extraction, normalises through skill taxonomy, recomputes profile embedding. |
| `gap_detector` | `agents/gap_detector.py` | 4-stage matching: taxonomy normalise → exact → substring → fuzzy (SequenceMatcher ≥ 0.82). Tier-weighted scoring (Python/PyTorch = 2×). Sonnet ranks missing skills by hours-to-learn. |
| `roadmap_planner` | `agents/roadmap_planner.py` | Sonnet generates time-boxed roadmap with real resources (Coursera, GitHub, Kaggle). Persists to DB. |
| `application_tracker` | `agents/application_tracker.py` | Fetches all applications. If message contains "applied to/for", uses Sonnet to extract details and creates a DB record. |
| `interview_coach` | `agents/interview_coach.py` | Detects answering vs asking. Generates role-specific questions (2 technical, 1 system design, 1 project, 1 behavioural) or evaluates an answer on 3 dimensions. |
| `responder` | `graph.py` | Builds contextual prompt from accumulated state, calls Sonnet, returns final response. |
| `memory_writer` | `graph.py` | Stores structured episode with importance scaling based on interaction richness. |

---

## Skill Matching Pipeline

The `gap_detector` uses a four-stage matching algorithm so "sklearn" matches "scikit-learn" and "pytorch" matches "PyTorch":

```
Required skill: "sklearn"
   ↓
1. Taxonomy normalisation:  "sklearn" → "scikit-learn"
2. Exact match:             is "scikit-learn" in candidate? → check
3. Substring match:         is "scikit" in any candidate skill (bidirectional)?
4. Fuzzy match:             SequenceMatcher ratio ≥ 0.82 against all candidates
```

Scoring is tier-weighted, not a naive percentage:
- **Tier 1** (Python, PyTorch, SQL, Git, Deep Learning, etc.) → weight **2.0×**
- **Tier 2** (scikit-learn, FastAPI, Docker, RAG, Hugging Face, etc.) → weight **1.5×**
- **Tier 3** (everything else) → weight **1.0×**

---

## Memory System

Episodic memory uses a custom hybrid scoring formula in PostgreSQL:

```sql
ORDER BY importance * (
    0.7 * (1.0 - (embedding <=> query_vec))   -- semantic similarity
    + 0.3 * (1.0 / (1.0 + days_since_created)) -- recency decay
) DESC
```

Memories with cosine distance ≥ 0.75 are filtered out. Importance scales with interaction richness (base 1.0, +0.5 for gap analysis, +0.5 for roadmap, +0.3 for opportunities).

---

## Job Fetching

Five data sources, all running concurrently:

| Source | Method | Notes |
|---|---|---|
| Internshala | HTTP scrape (BeautifulSoup) | 6 ML/AI category pages, 1.5s polite delay |
| Adzuna | REST API | Requires `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` |
| Himalayas | REST API | Remote-friendly tech roles |
| Remotive | REST API | Remote ML/data roles |
| Unstop | REST API | India-focused hackathons + internships |

**Scheduled refresh:** 6:00 and 18:00 IST daily (APScheduler CronTrigger, 5-minute misfire grace).

**On-demand live fetch:** when a user asks for "latest/recent/new" internships in chat, `opportunity_hunter` triggers `quick_fetch()` — all 5 sources with a hard 8-second timeout, top 3 per source upserted before semantic search runs.

**Upsert key:** `(source, external_id)` — idempotent across refreshes. Manual/seeded listings (`source IS NULL`) are never pruned.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI 0.110, Python 3.12 |
| Agent orchestration | LangGraph 0.2 |
| Primary LLM | Claude Sonnet 4.6 (`claude-sonnet-4-6`) |
| Routing LLM | Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) |
| Intent routing (optional) | Qwen2.5-3B-Instruct, QLoRA fine-tuned |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`, 384-dim) |
| Database | PostgreSQL + pgvector (Neon free tier) |
| ORM | SQLAlchemy 2.0 async + psycopg3 |
| PDF parsing | pdfplumber |
| ML fine-tuning | QLoRA via PEFT + TRL (Colab T4) |
| Frontend | Next.js 14, TypeScript, CSS Modules |
| Deployment | Render (backend) + Vercel (frontend) |

---

## Quick Start

### 1. Database

Create a free project at [neon.tech](https://neon.tech). Copy the psycopg connection string — pgvector is pre-enabled on Neon.

### 2. Backend

```bash
cd backend

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env             # fill in DATABASE_URL + ANTHROPIC_API_KEY

uvicorn app.main:app --reload --port 8000
```

Tables and the pgvector extension are created automatically on startup.

Swagger UI: `http://localhost:8000/docs`

### 3. Seed opportunity data

```bash
python -m db.seed_opportunities
```

Seeds curated Indian ML/AI internship listings with pgvector embeddings.

### 4. Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` or point to your deployed backend.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | psycopg3-format PostgreSQL URL (starts with `postgresql://` or `postgres://`) |
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-6` | Primary model for agent tasks |
| `FAST_MODEL` | No | `claude-haiku-4-5-20251001` | Fast model for intent routing |
| `EMBEDDING_MODEL` | No | `all-MiniLM-L6-v2` | sentence-transformers model name |
| `JWT_SECRET_KEY` | No | dev default | Change to a random 32-char string in production |
| `ADZUNA_APP_ID` | No | — | Adzuna developer credentials |
| `ADZUNA_APP_KEY` | No | — | Adzuna developer credentials |
| `USE_LOCAL_CLASSIFIER` | No | `false` | `true` to use QLoRA Qwen2.5-3B for intent routing |
| `LOCAL_CLASSIFIER_PATH` | No | — | Absolute path to QLoRA adapter directory |
| `LANGSMITH_API_KEY` | No | — | LangSmith tracing |
| `LANGSMITH_TRACING` | No | `false` | `true` to enable LangSmith traces |

---

## API Reference

### Auth
```
POST  /api/auth/register   {name, email, password, goal?} → {access_token, user}
POST  /api/auth/login      {email, password}              → {access_token, user}
GET   /api/auth/me         (Bearer token)                 → user
```

### Users
```
POST   /api/users          {name?, email?, goal?}     → user  (201)
GET    /api/users/{id}     → user
PATCH  /api/users/{id}     {name?, goal?, target_role?} → user
```

### Profile
```
POST  /api/profile/upload  multipart: user_id=<id> + file=<PDF or .txt>
                           → {skills, projects, experience_text, chunk_count}
GET   /api/profile/{user_id} → {skills, projects, experience_text}
```

### Chat
```
POST  /api/chat            {user_id, message} → {user_id, response, intent, data}
POST  /api/chat/stream     {user_id, message} → text/event-stream (SSE)
GET   /api/chat/health     → {"status": "ok"}
```

Rate limit on `/api/chat/stream`: 10 requests per `user_id` per 60 seconds. Exceeding returns HTTP 429.

SSE event stream from `/api/chat/stream`:
```
data: {"type": "progress", "node": "memory_retriever", "detail": "Recalled 3 memories"}
data: {"type": "progress", "node": "intent_router",    "detail": "Searching for internships"}
data: {"type": "progress", "node": "opportunity_hunter","detail": "Found 6 matching internships"}
data: {"type": "data",     "key": "opportunities",      "value": [{...}, ...]}
data: {"type": "data",     "key": "gap_score",          "value": 74}
data: {"type": "progress", "node": "responder",         "detail": "Writing response…"}
data: {"type": "token",    "chunk": "Based "}
data: {"type": "token",    "chunk": "on "}
...
data: {"type": "done"}
```

### Opportunities
```
GET   /api/opportunities              ?type=internship&limit=20 → list
POST  /api/opportunities/search       {query, user_id?, limit?} → list (semantic)
POST  /api/opportunities              {title, company, required_skills, ...} → opportunity (201)
```

### Tracker
```
GET    /api/tracker/{user_id}         → list of applications
POST   /api/tracker                   {user_id, company, role, status?, applied_date?, notes?, url?} (201)
PATCH  /api/tracker/{app_id}          {status?, notes?, deadline?} → application
DELETE /api/tracker/{app_id}          (204)
```

Valid statuses: `applied | interview | offered | rejected | withdrawn`

### Chat History
```
GET    /api/history/conversations/{user_id}       → [{id, title, message_count, updated_at}]
POST   /api/history/conversations                 {user_id, title?} → conversation (201)
GET    /api/history/conversations/{conv_id}/messages → conversation with messages array
PATCH  /api/history/conversations/{conv_id}       {title} → conversation
DELETE /api/history/conversations/{conv_id}       (204)
POST   /api/history/messages                      {conversation_id, role, content} → message (201)
```

### Admin (Bearer token required)
```
POST  /api/admin/refresh-jobs
      → {fetched, upserted, pruned, source_counts: {internshala: N, ...}, errors: []}

GET   /api/admin/scheduler-status
      → {running: true, jobs: [{id, name, next_run_time, trigger}]}
```

### System
```
GET   /                → {name, version, agents: [...]}
GET   /api/health      → {status, db, opportunity_count, embedding_model}
                         HTTP 503 if DB is unreachable
```

---

## ML Fine-tuning Pipeline

Knowledge distillation: Claude (teacher) generates labeled training data; Qwen2.5-3B is fine-tuned via QLoRA to handle intent classification locally.

```
Claude Sonnet  (teacher)
     │  generates 500 labeled career queries across 7 intents
     ▼
ml/data/training_pairs.jsonl
     │  QLoRA fine-tuning — Colab T4 GPU, ~25 min
     │  4-bit NF4 quantisation, rank-16 LoRA, Paged AdamW 8-bit
     ▼
ml/checkpoints/intent-classifier/final/   ← LoRA adapter (~30 MB)
     │
     ▼
distill_intent.classify_intent(message)   ← loaded lazily, runs in thread pool
```

**Activate:**
```bash
# backend/.env
USE_LOCAL_CLASSIFIER=true
LOCAL_CLASSIFIER_PATH=/absolute/path/to/intent-classifier/final
```

**Generate training data:**
```bash
python ml/generate_synthetic_data.py
```

**Fine-tune (run in Colab):**
```python
!pip install -q "transformers>=4.45" "peft>=0.13" "trl>=0.12" \
    "bitsandbytes>=0.43" "datasets>=2.19" "accelerate>=0.34"
# upload training_pairs.jsonl, then run ml/train_skill_gap_classifier.py
```

**Standalone inference:**
```bash
python ml/distill_intent.py "Find me ML internships in Bangalore"
# → [opportunities]  Find me ML internships in Bangalore
```

**Why it matters:** eliminates one API call per message, runs at ~0.05s vs ~0.3s for Haiku. Not feasible on Render free tier (3B model weights need ~6 GB RAM) — suitable for GPU server or local dev.

---

## Project Structure

```
mitra/
├── backend/
│   ├── app/
│   │   ├── main.py                    FastAPI + lifespan (init_db, scheduler, embedding pre-warm)
│   │   ├── config.py                  pydantic-settings (.env)
│   │   ├── database.py                async SQLAlchemy engine + session factory
│   │   ├── scheduler.py               APScheduler (6:00 and 18:00 IST)
│   │   ├── agents/
│   │   │   ├── state.py               AgentState TypedDict
│   │   │   ├── graph.py               LangGraph StateGraph — all wiring + responder
│   │   │   ├── opportunity_hunter.py  live fetch + cosine search
│   │   │   ├── resume_analyzer.py     skill extraction + profile embedding
│   │   │   ├── gap_detector.py        4-stage matching + tier-weighted scoring
│   │   │   ├── roadmap_planner.py     time-boxed plan with real resources
│   │   │   ├── application_tracker.py NL extraction + CRUD
│   │   │   └── interview_coach.py     Q-generation + answer evaluation
│   │   ├── routers/
│   │   │   ├── chat.py                SSE streaming + rate limiter
│   │   │   ├── admin.py               refresh-jobs + scheduler-status
│   │   │   ├── auth.py                JWT register / login / me
│   │   │   ├── profile.py             PDF upload + chunking
│   │   │   ├── opportunities.py       list + semantic search + add
│   │   │   ├── tracker.py             application CRUD
│   │   │   ├── history.py             conversation + message CRUD
│   │   │   └── users.py               user CRUD
│   │   ├── services/
│   │   │   ├── llm_client.py          Anthropic SDK — Sonnet + Haiku tiers
│   │   │   ├── embedding_service.py   sentence-transformers singleton
│   │   │   ├── memory_service.py      hybrid-scored pgvector episodic memory
│   │   │   ├── skill_graph.py         taxonomy + 4-stage matching + scoring
│   │   │   ├── resume_service.py      chunk store + cosine retrieval
│   │   │   ├── resume_chunker.py      section-aware + size-split chunking
│   │   │   └── job_fetcher/
│   │   │       ├── __init__.py        run() + quick_fetch() + ingest_jobs()
│   │   │       ├── normalizer.py      FetchedJob dataclass + embed_text
│   │   │       ├── adzuna.py
│   │   │       ├── internshala.py     BeautifulSoup scraper
│   │   │       ├── himalayas.py
│   │   │       ├── remotive.py
│   │   │       └── unstop.py
│   │   └── models/
│   │       ├── db.py                  9 SQLAlchemy ORM tables
│   │       └── schemas.py             Pydantic request/response schemas
│   ├── db/
│   │   └── seed_opportunities.py      curated ML/AI listings with embeddings
│   └── requirements.txt
├── frontend/
│   ├── src/app/
│   │   ├── page.tsx                   Landing (bento grid, stats bar)
│   │   ├── chat/                      SSE chat + sidebar conversation history
│   │   ├── opportunities/             Semantic internship search
│   │   ├── tracker/                   Kanban application pipeline (5 columns)
│   │   ├── profile/                   Skill radar + resume upload
│   │   ├── onboarding/                PDF dropzone + processing stages
│   │   ├── auth/                      Sign in / Register
│   │   ├── about/                     Project overview + agent docs
│   │   └── components/                Nav.tsx, Footer.tsx
│   └── src/lib/                       API client, auth helpers, types
├── ml/
│   ├── generate_synthetic_data.py     500-pair training set generation
│   ├── train_skill_gap_classifier.py  QLoRA fine-tuning (Colab T4)
│   ├── train_kaggle.py                Unsloth variant (Kaggle T4×2)
│   └── distill_intent.py             Adapter loader + inference
├── COVERAGE.md                        Detailed technical coverage (read this)
├── SRS.md                             Software Requirements Specification
├── CLAUDE.md                          AI assistant context file
└── README.md                          This file
```

---

## Deployment

### Backend: Render

1. Create a new **Web Service** from the `backend/` directory.
2. Set environment: Python 3.12, build command `pip install -r requirements.txt`, start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Add all required environment variables in Render's dashboard.

**Free tier note:** the sentence-transformers model (`all-MiniLM-L6-v2`, ~90 MB) loads at startup. Render free tier has 512 MB RAM — the model fits, but the first request after a cold start still pays a ~5-second embedding load cost. The `fast_complete()` Haiku path eliminates the intent-routing API latency.

### Frontend: Vercel

```bash
cd frontend
npx vercel --prod
```

Set `NEXT_PUBLIC_API_URL` to your Render backend URL in Vercel environment variables.

---

## Roadmap

- [x] Multi-agent LangGraph orchestration with parallel entry nodes
- [x] Hybrid-scored pgvector episodic memory (semantic + recency + importance)
- [x] Resume upload → PDF parsing → section-aware RAG chunking
- [x] 4-stage skill matching with tier-weighted scoring and skill taxonomy
- [x] Semantic opportunity search + live on-demand fetch for "latest" queries
- [x] Application tracker with natural-language create-from-chat
- [x] Interview coach: question generation + answer evaluation
- [x] ML fine-tuning pipeline (QLoRA knowledge distillation from Claude)
- [x] Dual-model tier: Haiku for routing, Sonnet for agent tasks
- [x] JWT auth + bcrypt, rate limiting, health check, scheduler status API
- [x] Next.js 14 frontend: SSE chat, kanban tracker, skill radar, bento landing
- [ ] True token streaming in responder (currently word-split after full generation)
- [ ] Multi-intent parsing (single intent per request today)
- [ ] Conversation history injection into agent state
- [ ] Explainable opportunity matching (per-listing match score + skill breakdown)
- [ ] Resume diff on re-upload (skill progress tracking)
- [ ] Duplicate memory suppression
- [ ] Roadmap → GapAnalysis DB linkage (foreign key exists, not yet populated)
- [ ] LangSmith observability
