# Mitra — Career Intelligence OS

A production-grade multi-agent AI system that helps ML/AI students find internships, identify skill gaps, build learning roadmaps, and track applications — purpose-built for the Indian ML/AI job market.

## Architecture

```
User message
     │
     ▼
FastAPI (SSE streaming)
     │
     ▼
LangGraph Multi-Agent Graph
     ├─ Memory Retriever      → pgvector semantic search over episodic memory
     ├─ Intent Router         → Qwen2.5-3B (local) OR Claude — classifies into 7 intents
     │
     ├─ opportunity_hunter    → semantic search over curated opportunities
     ├─ resume_analyzer       → Claude extracts structured skill profile from PDF
     ├─ gap_detector          → reciprocal skill matching + priority estimation
     ├─ roadmap_planner       → optimised learning plan with real resources
     ├─ application_tracker   → CRUD + auto-extraction from natural language
     ├─ interview_coach       → role-specific questions + answer evaluation
     │
     └─ Responder             → synthesis node, generates final response
     │
     ▼
PostgreSQL + pgvector (Neon)
```

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.12 |
| Agents | LangGraph 0.2 |
| LLM | Anthropic Claude (claude-sonnet-4-6) |
| Intent routing (optional) | Qwen2.5-3B-Instruct (QLoRA fine-tuned, local) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Database | PostgreSQL + pgvector (Neon) |
| ORM | SQLAlchemy 2.0 async + psycopg3 |
| PDF Parsing | pdfplumber |
| Fine-tuning | QLoRA via PEFT + TRL, Qwen2.5-3B |
| Deployment | Fly.io (backend) + Vercel (frontend) |

---

## Quick Start

### 1. Database — Neon (free tier)

1. [neon.tech](https://neon.tech) → New Project → copy the **Connection String** (psycopg format)
2. pgvector is enabled automatically on Neon — nothing else needed

### 2. Backend

```bash
cd backend

# Create and activate virtualenv
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Fill in DATABASE_URL and ANTHROPIC_API_KEY
```

### 3. Run

```bash
uvicorn app.main:app --reload --port 8000
```

Tables are created automatically on first startup. Visit `http://localhost:8000/docs` for the Swagger UI.

### 4. Seed opportunity data (run once)

```bash
python -m db.seed_opportunities
```

Seeds 20 realistic Indian ML/AI internship opportunities with embeddings.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | psycopg3-format PostgreSQL URL |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `LANGSMITH_API_KEY` | No | LangSmith tracing |
| `LANGSMITH_TRACING` | No | `true` to enable tracing |
| `CLAUDE_MODEL` | No | defaults to `claude-sonnet-4-6` |
| `EMBEDDING_MODEL` | No | defaults to `all-MiniLM-L6-v2` |
| `USE_LOCAL_CLASSIFIER` | No | `true` to use fine-tuned Qwen for intent routing |
| `LOCAL_CLASSIFIER_PATH` | No | Absolute path to the LoRA adapter directory |

---

## API Reference

### Users
```
POST   /api/users              Create user
GET    /api/users/{id}         Get user
PATCH  /api/users/{id}         Update goal/name
```

### Profile
```
POST   /api/profile/upload     Upload resume (PDF or plain text)
GET    /api/profile/{user_id}  Get extracted skill profile
```

### Chat (multi-agent)
```
POST   /api/chat               Full JSON response
POST   /api/chat/stream        Server-Sent Events stream
```

#### Example
```json
POST /api/chat
{
  "user_id": "abc123",
  "message": "Find me ML internships and show my skill gaps"
}
```

#### SSE stream events
```
data: {"type": "progress", "node": "opportunity_hunter"}
data: {"type": "progress", "node": "gap_detector"}
data: {"type": "progress", "node": "roadmap_planner"}
data: {"type": "token", "chunk": "Based on your profile..."}
data: {"type": "done"}
```

### Opportunities
```
GET    /api/opportunities              List all (filter: ?type=internship)
POST   /api/opportunities/search       Semantic search by query string
POST   /api/opportunities              Add new opportunity
```

### Application Tracker
```
GET    /api/tracker/{user_id}          List all applications
POST   /api/tracker?user_id=...        Add application
PATCH  /api/tracker/{app_id}           Update status / notes
DELETE /api/tracker/{app_id}           Delete
```

---

## ML Fine-tuning Pipeline

The `ml/` directory contains a knowledge distillation pipeline: Claude acts as teacher model to generate training data; a small Qwen2.5-3B model is fine-tuned via QLoRA to handle intent classification cheaply at inference time.

### Pipeline overview

```
Claude (teacher)
    │  generates 500 labeled career queries
    ▼
ml/data/training_pairs.jsonl
    │  QLoRA fine-tuning on Colab T4 (free)
    ▼
ml/checkpoints/intent-classifier/final/  ← LoRA adapter (~30 MB)
    │  loaded by distill_intent.py
    ▼
classify_intent() in llm_client.py        ← replaces Claude API call for routing
```

### Step 1 — Generate training data

Requires `ANTHROPIC_API_KEY` in `backend/.env`.

```bash
cd mitra

# Intent classification data (default) — 500 career queries × 7 intents
python ml/generate_synthetic_data.py

# Rich skill-gap analysis data (separate use case)
python ml/generate_synthetic_data.py --mode skillgap
```

Output: `ml/data/training_pairs.jsonl`
Format: `{"input": "<user query>", "output": "<intent_label>", "intent": "<intent_label>"}`

### Step 2 — Fine-tune on Colab T4

Open a Colab notebook, paste and run:

```python
# Cell 1 — install
!pip install -q "transformers>=4.45" "peft>=0.13" "trl>=0.12" \
    "bitsandbytes>=0.43" "datasets>=2.19" "accelerate>=0.34"

# Cell 2 — upload training_pairs.jsonl to Colab Files, then run
# (copy contents of ml/train_skill_gap_classifier.py)
```

Training takes ~25 min on T4. The adapter is saved to `OUTPUT_DIR/final/` (~30 MB).

### Step 3 — Enable in the backend

```bash
# Download the adapter from Colab output panel, then set in backend/.env:
USE_LOCAL_CLASSIFIER=true
LOCAL_CLASSIFIER_PATH=/absolute/path/to/intent-classifier/final
```

`classify_intent()` in `llm_client.py` will now use the local model instead of Claude for routing, saving ~1 API call per message.

### Standalone classifier

```bash
python ml/distill_intent.py "Find me ML internships in Bangalore"
# → [opportunities  ]  Find me ML internships in Bangalore

python ml/distill_intent.py --batch < queries.txt
```

### Key ML talking points (for interviews)

- Knowledge distillation: Claude (3.5 Sonnet) → Qwen2.5-3B via synthetic data
- QLoRA: 4-bit NF4 quantisation + rank-16 LoRA = fine-tune 3B model on 15 GB T4 VRAM
- Paged AdamW 8-bit: further reduces optimizer VRAM by ~300 MB
- Intent classification replaces a full Claude API call — ~10× cheaper at scale
- Thread-pool executor pattern: sync model inference called from async FastAPI without blocking

---

## Project Structure

```
mitra/
├── backend/
│   ├── app/
│   │   ├── main.py                    FastAPI entry point
│   │   ├── config.py                  pydantic-settings (reads .env)
│   │   ├── database.py                async SQLAlchemy + pgvector init
│   │   ├── agents/
│   │   │   ├── state.py               LangGraph AgentState TypedDict
│   │   │   ├── graph.py               StateGraph orchestration
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
│   │       ├── llm_client.py          Anthropic SDK wrapper + local classifier toggle
│   │       ├── embedding_service.py   sentence-transformers singleton
│   │       ├── memory_service.py      pgvector episodic memory
│   │       └── skill_graph.py         skill extraction + matching
│   ├── db/
│   │   └── seed_opportunities.py      20 curated ML/AI opportunities
│   └── requirements.txt
├── ml/
│   ├── generate_synthetic_data.py     Generates training_pairs.jsonl (intent) or skill_gap_dataset.jsonl
│   ├── train_skill_gap_classifier.py  QLoRA fine-tuning (run on Colab T4)
│   ├── train_kaggle.py                Unsloth-optimised variant for Kaggle T4×2
│   ├── distill_intent.py              Inference module — loads adapter, classifies intent
│   └── requirements.txt
├── SRS.md
├── CLAUDE.md
├── USERGUIDE.md
└── README.md
```

---

## Deployment

### Backend → Fly.io

```bash
curl -L https://fly.io/install.sh | sh

cd backend
fly launch --no-deploy

fly secrets set ANTHROPIC_API_KEY=sk-ant-...
fly secrets set DATABASE_URL=postgresql+psycopg://...

fly deploy
```

`fly.toml` (create in `backend/`):
```toml
app = "mitra-backend"
primary_region = "sin"   # Singapore — lowest latency from India

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

`Dockerfile` (create in `backend/`):
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Roadmap

- [x] Multi-agent LangGraph orchestration
- [x] Episodic memory with pgvector
- [x] Resume upload + skill extraction
- [x] Semantic opportunity matching
- [x] Application tracker with NL updates
- [x] Interview coach with question generation
- [x] ML fine-tuning pipeline (QLoRA + knowledge distillation)
- [x] Local intent classifier with USE_LOCAL_CLASSIFIER toggle
- [ ] Next.js frontend with real-time SSE chat UI
- [ ] LangSmith observability integration
- [ ] RAGAS evaluation for RAG quality
- [ ] GitHub profile analysis (extract projects from repos)
- [ ] Deadline reminders via cron + email notifications
