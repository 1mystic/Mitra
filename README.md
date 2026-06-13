# Mitra: Career Intelligence OS

A production-grade multi-agent AI system for ML/AI students. Finds internships, maps skill gaps, builds roadmaps, coaches interviews, and tracks applications — purpose-built for the Indian ML/AI job market.

**Stack:** FastAPI · LangGraph · pgvector · Claude Sonnet 4.6 · Next.js 14 · TypeScript

---

## Architecture

```
User message
     │
     ▼
FastAPI  (SSE streaming)
     │
     ▼
LangGraph  Multi-Agent StateGraph
     │
     ├─ memory_retriever      pgvector semantic search over episodic memory
     ├─ intent_router         Qwen2.5-3B (QLoRA) or Claude: classifies 7 intents
     │
     ├─ opportunity_hunter    cosine similarity over curated ML/AI listings
     ├─ resume_analyzer       Claude extracts structured skill profile from PDF
     ├─ gap_detector          reciprocal skill matching + priority scoring
     ├─ roadmap_planner       time-boxed learning plan with real resources
     ├─ application_tracker   CRUD + natural-language status updates
     ├─ interview_coach       role-aware questions + answer evaluation
     │
     └─ responder             synthesis node, generates final streamed response
     │
     ▼
PostgreSQL + pgvector  (Neon)
```

**Key constraint:** `build_graph(db)` is called per request so each agent node gets a bound `AsyncSession` — no shared state across concurrent requests.

---

## Frontend

Next.js 14 App Router · TypeScript · CSS Modules

```
frontend/src/app/
├── page.tsx              Landing page (bento grid, stats bar, CTA)
├── chat/                 Multi-agent chat with SSE streaming + sidebar history
├── opportunities/        Semantic internship search with skill-gap deep links
├── tracker/              Kanban application pipeline (5 status columns)
├── profile/              Skill radar + resume upload
├── onboarding/           PDF dropzone + processing stages
├── auth/                 Sign in / Register
├── about/                Project overview, agent docs, tech stack
└── components/
    ├── Nav.tsx           Transparent scrolling nav (landing) / fixed (inner pages)
    └── Footer.tsx        Landing-only footer with project links
```

**Design system:** obsidian dark backgrounds (`#07080B`), kinetic mint/sky/iris palette, Plus Jakarta Sans headers, JetBrains Mono labels, glass surfaces with `backdrop-filter: blur`, ambient radial glows, bento grid layouts.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.12 |
| Agent orchestration | LangGraph 0.2 |
| LLM | Claude Sonnet 4.6 (`claude-sonnet-4-6`) |
| Intent routing (optional) | Qwen2.5-3B-Instruct, QLoRA fine-tuned |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) |
| Database | PostgreSQL + pgvector (Neon) |
| ORM | SQLAlchemy 2.0 async + psycopg3 |
| PDF parsing | pdfplumber |
| ML fine-tuning | QLoRA via PEFT + TRL |
| Frontend | Next.js 14, TypeScript, CSS Modules |
| Deployment | Fly.io (backend) + Vercel (frontend) |

---

## Quick Start

### 1. Database

Create a free project at [neon.tech](https://neon.tech) and copy the psycopg connection string. pgvector is pre-enabled on Neon — nothing else required.

### 2. Backend

```bash
cd backend

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env             # fill DATABASE_URL + ANTHROPIC_API_KEY

uvicorn app.main:app --reload --port 8000
```

Tables are created automatically on startup. Swagger UI: `http://localhost:8000/docs`

### 3. Seed opportunity data

```bash
python -m db.seed_opportunities
```

Seeds 50+ curated Indian ML/AI internship listings with pgvector embeddings.

### 4. Frontend

```bash
cd frontend
npm install
npm run dev                      # http://localhost:3000
```

Backend base URL defaults to `http://localhost:8000`. Auth token stored in `localStorage` under `mitra_token`.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | psycopg3-format PostgreSQL URL |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `CLAUDE_MODEL` | No | defaults to `claude-sonnet-4-6` |
| `EMBEDDING_MODEL` | No | defaults to `all-MiniLM-L6-v2` |
| `USE_LOCAL_CLASSIFIER` | No | `true` to use fine-tuned Qwen for intent routing |
| `LOCAL_CLASSIFIER_PATH` | No | Absolute path to the LoRA adapter directory |
| `LANGSMITH_API_KEY` | No | LangSmith tracing |
| `LANGSMITH_TRACING` | No | `true` to enable |

---

## API Reference

### Users
```
POST   /api/users              Create user
GET    /api/users/{id}         Get user
PATCH  /api/users/{id}         Update goal / name
```

### Profile
```
POST   /api/profile/upload     Upload resume (PDF or plain text)
GET    /api/profile/{user_id}  Get extracted skill profile
```

### Chat
```
POST   /api/chat               Full JSON response
POST   /api/chat/stream        Server-Sent Events stream
```

```json
POST /api/chat
{
  "user_id": "abc123",
  "message": "Find me ML internships and show my skill gaps"
}
```

SSE stream events:
```
data: {"type": "progress", "node": "opportunity_hunter"}
data: {"type": "token",    "chunk": "Based on your profile..."}
data: {"type": "done"}
```

### Opportunities
```
GET    /api/opportunities             List all  (filter: ?type=internship)
POST   /api/opportunities/search      Semantic search by query
POST   /api/opportunities             Add listing
```

### Tracker
```
GET    /api/tracker/{user_id}         List all applications
POST   /api/tracker?user_id=...       Add application
PATCH  /api/tracker/{app_id}          Update status / notes
DELETE /api/tracker/{app_id}          Delete
```

---

## ML Fine-tuning Pipeline

Knowledge distillation: Claude acts as teacher to generate labeled training data; Qwen2.5-3B is fine-tuned via QLoRA to handle intent classification cheaply at inference time.

```
Claude  (teacher)
    │  generates 500 labeled career queries
    ▼
ml/data/training_pairs.jsonl
    │  QLoRA fine-tuning on Colab T4 (free, ~25 min)
    ▼
ml/checkpoints/intent-classifier/final/    LoRA adapter (~30 MB)
    │
    ▼
classify_intent() in llm_client.py         replaces Claude API call for routing
```

### Step 1: Generate training data

```bash
# 500 career queries x 7 intents
python ml/generate_synthetic_data.py

# Skill-gap analysis dataset (separate use case)
python ml/generate_synthetic_data.py --mode skillgap
```

Output: `ml/data/training_pairs.jsonl`

### Step 2: Fine-tune on Colab T4

```python
# install
!pip install -q "transformers>=4.45" "peft>=0.13" "trl>=0.12" \
    "bitsandbytes>=0.43" "datasets>=2.19" "accelerate>=0.34"

# upload training_pairs.jsonl, then run ml/train_skill_gap_classifier.py
```

### Step 3: Enable in backend

```bash
# backend/.env
USE_LOCAL_CLASSIFIER=true
LOCAL_CLASSIFIER_PATH=/absolute/path/to/intent-classifier/final
```

### Standalone inference

```bash
python ml/distill_intent.py "Find me ML internships in Bangalore"
# → [opportunities]  Find me ML internships in Bangalore

python ml/distill_intent.py --batch < queries.txt
```

### ML talking points

- Knowledge distillation: Claude Sonnet → Qwen2.5-3B via synthetic data generation
- QLoRA: 4-bit NF4 quantisation + rank-16 LoRA, fine-tunes 3B model on 15 GB T4 VRAM
- Paged AdamW 8-bit: reduces optimizer VRAM by ~300 MB
- Intent classification replaces one Claude API call per message, ~10x cheaper at scale
- Thread-pool executor: sync model inference called from async FastAPI without blocking the event loop

---

## Project Structure

```
mitra/
├── backend/
│   ├── app/
│   │   ├── main.py                    FastAPI entry point
│   │   ├── config.py                  pydantic-settings (.env)
│   │   ├── database.py                async SQLAlchemy + pgvector init
│   │   ├── agents/
│   │   │   ├── state.py               AgentState TypedDict
│   │   │   ├── graph.py               LangGraph StateGraph wiring
│   │   │   ├── opportunity_hunter.py
│   │   │   ├── resume_analyzer.py
│   │   │   ├── gap_detector.py
│   │   │   ├── roadmap_planner.py
│   │   │   ├── application_tracker.py
│   │   │   └── interview_coach.py
│   │   ├── routers/
│   │   │   ├── chat.py                SSE streaming + sync endpoints
│   │   │   ├── profile.py             resume upload
│   │   │   ├── opportunities.py       semantic search
│   │   │   ├── tracker.py             application CRUD
│   │   │   └── users.py
│   │   └── services/
│   │       ├── llm_client.py          Anthropic SDK + local classifier toggle
│   │       ├── embedding_service.py   sentence-transformers singleton
│   │       ├── memory_service.py      pgvector episodic memory
│   │       └── skill_graph.py         skill extraction + matching
│   ├── db/
│   │   └── seed_opportunities.py      curated ML/AI opportunity listings
│   └── requirements.txt
├── frontend/
│   ├── src/app/
│   │   ├── page.tsx                   Landing page
│   │   ├── chat/                      SSE chat UI
│   │   ├── opportunities/             Internship search
│   │   ├── tracker/                   Kanban pipeline
│   │   ├── profile/                   Skill profile
│   │   ├── onboarding/                Resume upload flow
│   │   ├── auth/                      Authentication
│   │   ├── about/                     Project docs page
│   │   └── components/                Nav, Footer
│   ├── src/lib/                       API client, auth helpers, types
│   └── src/app/globals.css            Design system tokens
├── ml/
│   ├── generate_synthetic_data.py     Training data generation
│   ├── train_skill_gap_classifier.py  QLoRA fine-tuning (Colab T4)
│   ├── train_kaggle.py                Unsloth variant for Kaggle T4x2
│   └── distill_intent.py             Inference: load adapter, classify
├── SRS.md
├── CLAUDE.md
└── README.md
```

---

## Deployment

### Backend: Fly.io

```bash
curl -L https://fly.io/install.sh | sh

cd backend
fly launch --no-deploy

fly secrets set ANTHROPIC_API_KEY=sk-ant-...
fly secrets set DATABASE_URL=postgresql+psycopg://...

fly deploy
```

`fly.toml`:
```toml
app = "mitra-backend"
primary_region = "sin"

[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = false
  min_machines_running = 1

[[vm]]
  memory = "512mb"
  cpu_kind = "shared"
  cpus = 1
```

`Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend: Vercel

```bash
cd frontend
npx vercel --prod
```

Set `NEXT_PUBLIC_API_URL` to your Fly.io backend URL in Vercel environment variables.

---

## Roadmap

- [x] Multi-agent LangGraph orchestration
- [x] Episodic memory with pgvector
- [x] Resume upload + skill extraction
- [x] Semantic opportunity matching
- [x] Application tracker with natural-language updates
- [x] Interview coach with question generation
- [x] ML fine-tuning pipeline (QLoRA + knowledge distillation)
- [x] Local intent classifier with toggle
- [x] Next.js 14 frontend with real-time SSE chat
- [x] Kinetic design system (obsidian dark, mint/sky/iris palette)
- [x] Bento grid landing page, kanban tracker, glass UI
- [ ] LangSmith observability integration
- [ ] RAGAS evaluation for RAG quality
- [ ] GitHub profile analysis (extract projects from repos)
- [ ] Deadline reminders via cron + email
