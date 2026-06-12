# Mitra — Career Intelligence OS

A production-grade multi-agent AI system that helps ML/AI students find internships, identify skill gaps, build learning roadmaps, and track applications.

## Architecture

```
User
  │
  ▼
FastAPI (SSE streaming)
  │
  ▼
LangGraph Multi-Agent Graph
  ├─ Memory Retriever      → pgvector semantic search over episodic memory
  ├─ Intent Router         → Claude classifies query into 6 intents
  │
  ├─ Opportunity Hunter    → semantic search over 20+ curated opportunities
  ├─ Resume Analyzer       → Claude extracts structured skill profile from PDF
  ├─ Gap Detector          → reciprocal skill matching + priority estimation
  ├─ Roadmap Planner       → optimised learning plan with real resources
  ├─ Application Tracker   → CRUD + auto-extraction from natural language
  ├─ Interview Coach       → role-specific questions + answer evaluation
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
| LLM | Anthropic Claude (Sonnet 4.6) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Database | PostgreSQL + pgvector (Neon) |
| ORM | SQLAlchemy 2.0 async + psycopg3 |
| PDF Parsing | pdfplumber |
| Fine-tuning | QLoRA, Qwen2.5-3B, Unsloth |
| Deployment | Railway (backend) + Vercel (frontend) |

## Setup

### 1. Database (Neon — free, no inactivity pause)

1. Go to [neon.tech](https://neon.tech) → New Project
2. Copy the **Connection String** (psycopg format)
3. Neon auto-enables pgvector — no manual setup needed

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env — set DATABASE_URL and ANTHROPIC_API_KEY
```

### 3. Run the server

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Tables are created automatically on first startup via `init_db()`.

### 4. Seed opportunity data

```bash
cd backend
python -m db.seed_opportunities
```

This seeds 20 realistic Indian ML/AI internship opportunities with embeddings.

### 5. Explore the API

Visit `http://localhost:8000/docs` — full Swagger UI.

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
POST   /api/profile/upload     Upload resume (PDF or text)
GET    /api/profile/{user_id}  Get extracted skill profile
```

### Chat (multi-agent)
```
POST   /api/chat               Full response (JSON)
POST   /api/chat/stream        Streaming SSE (progress + tokens)
```

#### Example chat request
```json
POST /api/chat
{
  "user_id": "abc123",
  "message": "Find me ML internships in India and show my skill gaps"
}
```

#### SSE stream events
```
data: {"type": "progress", "node": "opportunity_hunter"}
data: {"type": "progress", "node": "gap_detector"}
data: {"type": "progress", "node": "roadmap_planner"}
data: {"type": "token", "chunk": "Based on "}
data: {"type": "token", "chunk": "your profile..."}
data: {"type": "done"}
```

### Opportunities
```
GET    /api/opportunities           List all (filter by ?type=internship)
POST   /api/opportunities/search    Semantic search by query string
POST   /api/opportunities           Add new opportunity
```

### Application Tracker
```
GET    /api/tracker/{user_id}       List all applications
POST   /api/tracker?user_id=...     Add application
PATCH  /api/tracker/{app_id}        Update status/notes
DELETE /api/tracker/{app_id}        Delete
```

---

## ML Fine-tuning Pipeline

The `ml/` folder contains a research component: fine-tuning a small model (Qwen2.5-3B) to specialise in skill gap classification, using Claude as the teacher.

### Generate training data
```bash
cd ml
pip install -r requirements.txt
python generate_synthetic_data.py   # generates 500 (resume, JD) → skill_gaps pairs
```

### Train the model
```bash
python train_skill_gap_classifier.py   # requires CUDA GPU
# Or run in Google Colab (T4 free tier is enough)
```

**Key talking points for interviews:**
- Synthetic data generation via knowledge distillation (Claude → Qwen3B)
- QLoRA: 4-bit quantization + low-rank adaptation = fine-tune on T4 GPU
- Evaluation: exact-match skill overlap + priority ranking correlation
- Inference: 10x cheaper than calling Claude API at scale

---

## Project Structure

```
mitra/
├── backend/
│   ├── app/
│   │   ├── main.py                  FastAPI entry point
│   │   ├── config.py                pydantic-settings
│   │   ├── database.py              async SQLAlchemy + pgvector init
│   │   ├── agents/
│   │   │   ├── state.py             LangGraph AgentState TypedDict
│   │   │   ├── graph.py             StateGraph orchestration
│   │   │   ├── opportunity_hunter.py
│   │   │   ├── resume_analyzer.py
│   │   │   ├── gap_detector.py
│   │   │   ├── roadmap_planner.py
│   │   │   ├── application_tracker.py
│   │   │   └── interview_coach.py
│   │   ├── routers/
│   │   │   ├── chat.py              SSE streaming chat
│   │   │   ├── profile.py           resume upload
│   │   │   ├── opportunities.py     semantic search
│   │   │   ├── tracker.py           application CRUD
│   │   │   └── users.py
│   │   ├── services/
│   │   │   ├── llm_client.py        Anthropic SDK wrapper
│   │   │   ├── embedding_service.py sentence-transformers singleton
│   │   │   ├── memory_service.py    pgvector episodic memory
│   │   │   └── skill_graph.py       skill extraction + matching
│   │   └── models/
│   │       ├── db.py                SQLAlchemy ORM
│   │       └── schemas.py           Pydantic request/response
│   ├── db/
│   │   └── seed_opportunities.py    20 curated ML opportunities
│   └── requirements.txt
├── ml/
│   ├── generate_synthetic_data.py   Claude as teacher model
│   ├── train_skill_gap_classifier.py QLoRA fine-tuning
│   └── requirements.txt
└── README.md
```

---

## Deployment

### Backend → Railway
```bash
# In backend/
# Set env vars in Railway dashboard
railway up
```

### Frontend → Vercel (Next.js, Phase 2)
```bash
# Coming next
```

---

## Roadmap (next steps)

- [ ] Next.js frontend with real-time SSE chat UI
- [ ] Neo4j knowledge graph for skill relationships
- [ ] LangSmith observability integration
- [ ] RAGAS evaluation pipeline for RAG quality
- [ ] Fine-tuned Qwen model serving endpoint
- [ ] GitHub profile analysis (extract projects from repos)
- [ ] Deadline reminders via cron + email
