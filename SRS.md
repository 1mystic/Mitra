# Software Requirements Specification
# Mitra — Career Intelligence OS
**Version:** 1.0  
**Date:** 2026-06-12  
**Author:** Athar  
**Status:** Active Development

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Overall Description](#2-overall-description)
3. [System Architecture](#3-system-architecture)
4. [Functional Requirements](#4-functional-requirements)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [Database Design](#6-database-design)
7. [API Specification](#7-api-specification)
8. [Agent Specifications](#8-agent-specifications)
9. [ML Pipeline Specification](#9-ml-pipeline-specification)
10. [Development Phases](#10-development-phases)
11. [Out of Scope](#11-out-of-scope)

---

## 1. Introduction

### 1.1 Purpose

Mitra is a domain-specific, multi-agent AI system built to solve a concrete problem: **Indian CS/AI/DS students applying for ML and AI internships do not know what skills they lack, which companies to target, or how to prioritise their learning.** Existing tools (LinkedIn, Internshala, Naukri) surface listings but provide zero intelligence.

Mitra acts as a persistent career decision engine — not a chatbot, not a research agent — that combines semantic search, skill graph analysis, recommendation algorithms, long-term memory, and a fine-tuned classifier to give actionable, specific guidance.

### 1.2 Scope

The system consists of:

- **Backend API** — FastAPI, Python 3.12, deployed on Railway
- **Multi-agent graph** — LangGraph with 6 specialised agents
- **Database** — PostgreSQL + pgvector on Neon (free tier)
- **Embeddings** — sentence-transformers (`all-MiniLM-L6-v2`, 384-dim)
- **LLM** — Anthropic Claude (Sonnet 4.6 for agents, Haiku for data generation)
- **Fine-tuned model** — Qwen2.5-3B-Instruct via QLoRA for skill gap classification
- **Frontend** — Next.js (Phase 2)

### 1.3 Definitions

| Term | Meaning |
|---|---|
| Skill Profile | Structured `{skill: proficiency}` dict extracted from a user's resume |
| Skill Gap | Set of skills required by a target role that the user does not have |
| Opportunity | Internship, hackathon, fellowship, or research opening |
| Episodic Memory | Per-user conversation events stored with pgvector embeddings |
| Intent | Classified category of a user message: one of 6 routing labels |
| QLoRA | Quantised Low-Rank Adaptation — efficient LLM fine-tuning method |

---

## 2. Overall Description

### 2.1 Product Perspective

Mitra is a standalone backend system with a REST + SSE API. It integrates with:
- **Neon** (managed PostgreSQL + pgvector)
- **Anthropic API** (Claude Sonnet 4.6)
- **HuggingFace Hub** (sentence-transformers model download)
- **Railway** (backend deployment)
- **Vercel** (frontend deployment, Phase 2)

### 2.2 User Classes

| User | Description |
|---|---|
| Student | Primary user. Uploads resume, asks questions, tracks applications. |
| Admin (future) | Manages opportunity database, views analytics. |

### 2.3 Assumptions

- Users are Indian CS/DS/AI students, primarily in 2nd–final year of B.Tech/M.Tech/MCA.
- The opportunity database is seeded manually and periodically updated; live scraping is out of scope for v1.
- Users interact via a chat interface (natural language), not forms.
- One user session = one `user_id` (no authentication in v1; auth is Phase 3).

### 2.4 Constraints

- Database: Must be free-tier compatible. Neon selected (no inactivity pause, pgvector support).
- GPU: Fine-tuning runs on external GPU (Google Colab T4 or similar). Inference is CPU-compatible.
- Budget: Zero operating cost for primary features. LLM API calls are the only variable cost.

---

## 3. System Architecture

### 3.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Client (Browser / CLI)                  │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP / SSE
┌────────────────────────────▼────────────────────────────────┐
│                    FastAPI Application                        │
│  ┌─────────┐  ┌─────────┐  ┌──────────────┐  ┌──────────┐  │
│  │ /users  │  │/profile │  │/opportunities│  │/tracker  │  │
│  └─────────┘  └─────────┘  └──────────────┘  └──────────┘  │
│                    ┌────────────────┐                         │
│                    │  /chat/stream  │  ← SSE streaming        │
│                    └───────┬────────┘                         │
└────────────────────────────│────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                  LangGraph StateGraph                         │
│                                                               │
│  START → memory_retriever → intent_router                     │
│                                    │                          │
│               ┌────────────────────┼──────────────────┐      │
│               ▼                    ▼                   ▼      │
│     opportunity_hunter      resume_analyzer    application_   │
│               │                    │            tracker       │
│               ▼                    │                │         │
│         gap_detector               │                │         │
│               │                    │                │         │
│               ▼                    │                │         │
│       roadmap_planner              │          interview_coach │
│               │                    │                │         │
│               └────────────────────┴────────────────┘         │
│                                    │                          │
│                               responder                       │
│                                    │                          │
│                                   END                         │
└────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                   Services Layer                              │
│  llm_client  │  embedding_service  │  memory_service  │ skill_graph │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              PostgreSQL + pgvector (Neon)                     │
│  users │ skill_profiles │ opportunities │ gap_analyses        │
│  roadmaps │ applications │ memory_episodes                   │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Data Flow for a Chat Request

1. `POST /api/chat/stream` with `{user_id, message}`
2. FastAPI retrieves user's `SkillProfile` from DB
3. Initial `AgentState` is constructed with profile + empty fields
4. LangGraph graph is built with the request-scoped DB session
5. `memory_retriever` → cosine search in `memory_episodes` → injects top-5 relevant memories
6. `intent_router` → Claude classifies message → returns one of 6 intent labels
7. Conditional routing to appropriate sub-agent chain
8. Each agent updates state and persists results to DB
9. `responder` synthesises a final answer from the full state
10. Response is streamed as SSE tokens back to the client
11. Conversation is stored as a new `MemoryEpisode`

---

## 4. Functional Requirements

### FR-01: User Management

| ID | Requirement |
|---|---|
| FR-01-1 | System shall create a user record with optional name, email, goal, and target role |
| FR-01-2 | System shall retrieve a user by ID |
| FR-01-3 | System shall update a user's goal and target role |

### FR-02: Resume Analysis

| ID | Requirement |
|---|---|
| FR-02-1 | System shall accept PDF and plain-text resume uploads via multipart form |
| FR-02-2 | System shall extract text from PDFs using pdfplumber |
| FR-02-3 | System shall use Claude to extract `{skill: proficiency}` pairs from resume text |
| FR-02-4 | System shall extract project summaries (name, description, skills used) from resume text |
| FR-02-5 | System shall generate a 384-dim embedding of the skill profile and store it in pgvector |
| FR-02-6 | System shall upsert the skill profile (one per user; re-upload replaces the previous) |

### FR-03: Opportunity Discovery

| ID | Requirement |
|---|---|
| FR-03-1 | System shall store at least 20 curated ML/AI opportunities with embeddings |
| FR-03-2 | System shall support semantic search over opportunities via cosine distance on pgvector |
| FR-03-3 | System shall filter opportunities by type (internship / hackathon / fellowship / research) |
| FR-03-4 | System shall return the top-N most relevant opportunities for a given user message |
| FR-03-5 | System shall support adding new opportunities via API |

### FR-04: Skill Gap Detection

| ID | Requirement |
|---|---|
| FR-04-1 | System shall compare candidate skills against a target opportunity's required skills |
| FR-04-2 | System shall compute a match score (0.0 – 1.0) as `present / required` |
| FR-04-3 | System shall use Claude to prioritise missing skills and estimate learning hours |
| FR-04-4 | System shall persist gap analysis results to `gap_analyses` table |
| FR-04-5 | System shall generate a 3–4 sentence plain-English summary of the gap analysis |

### FR-05: Roadmap Planning

| ID | Requirement |
|---|---|
| FR-05-1 | System shall generate a step-by-step learning roadmap from a gap analysis |
| FR-05-2 | Each roadmap step shall include: skill, specific action, best free resource, estimated hours, priority |
| FR-05-3 | System shall compute total estimated hours across all steps |
| FR-05-4 | System shall persist roadmaps to the `roadmaps` table |
| FR-05-5 | When the user has no skill gaps, roadmap shall indicate readiness to apply |

### FR-06: Application Tracking

| ID | Requirement |
|---|---|
| FR-06-1 | System shall support CRUD for application records |
| FR-06-2 | Application status shall be one of: `applied`, `interview`, `offered`, `rejected`, `withdrawn` |
| FR-06-3 | Application Tracker agent shall auto-extract application details from natural language (e.g. "I applied to Razorpay for ML intern") |
| FR-06-4 | System shall store extracted applications as `MemoryEpisode` entries |

### FR-07: Interview Coaching

| ID | Requirement |
|---|---|
| FR-07-1 | System shall generate 5 role-specific interview questions (2 technical, 1 design, 1 project, 1 behavioral) |
| FR-07-2 | System shall evaluate user answers on technical accuracy, depth, and communication (1–5 scale) |
| FR-07-3 | Evaluation shall include a model answer the user can learn from |

### FR-08: Episodic Memory

| ID | Requirement |
|---|---|
| FR-08-1 | System shall store conversation events as `MemoryEpisode` records with pgvector embeddings |
| FR-08-2 | System shall retrieve the top-5 most semantically relevant memories before each agent run |
| FR-08-3 | Memory shall be filterable by episode type: `goal`, `skill`, `application`, `insight`, `general` |
| FR-08-4 | Memory shall persist across sessions (not in-memory cache) |

### FR-09: Streaming Chat

| ID | Requirement |
|---|---|
| FR-09-1 | System shall expose a non-streaming `POST /api/chat` endpoint returning complete JSON |
| FR-09-2 | System shall expose a streaming `POST /api/chat/stream` endpoint returning SSE |
| FR-09-3 | SSE stream shall emit `progress` events as each agent node completes |
| FR-09-4 | SSE stream shall emit `token` events for the final response text |
| FR-09-5 | SSE stream shall emit a `done` event when the graph finishes |
| FR-09-6 | SSE stream shall emit an `error` event with a message on exception |

---

## 5. Non-Functional Requirements

### 5.1 Performance

| ID | Requirement |
|---|---|
| NFR-P-1 | Non-streaming chat response shall complete within 15 seconds for a cold request |
| NFR-P-2 | Embedding model shall be loaded once at startup (singleton); subsequent calls < 100ms |
| NFR-P-3 | pgvector semantic search over 10,000 rows shall complete < 200ms |
| NFR-P-4 | Neon cold-start reconnect (after inactivity) shall not error — handled by `pool_pre_ping=True` |

### 5.2 Reliability

| ID | Requirement |
|---|---|
| NFR-R-1 | If Claude returns invalid JSON, `complete_json()` shall return `{}` rather than raise |
| NFR-R-2 | If no opportunities are found via semantic search, system shall fall back to recency sort |
| NFR-R-3 | Database tables shall be created idempotently via `metadata.create_all` on startup |
| NFR-R-4 | SSE stream shall always emit `done` in a `finally` block, even on exceptions |

### 5.3 Security

| ID | Requirement |
|---|---|
| NFR-S-1 | API keys (ANTHROPIC_API_KEY, DATABASE_URL) shall be read from environment variables only |
| NFR-S-2 | `.env` file shall be in `.gitignore` |
| NFR-S-3 | CORS shall be configured — `allow_origins=["*"]` in dev; restrict to frontend domain in production |
| NFR-S-4 | User authentication is deferred to Phase 3 — system is single-tenant by `user_id` in v1 |

### 5.4 Maintainability

| ID | Requirement |
|---|---|
| NFR-M-1 | Each agent shall be in its own file under `agents/` with a single async node function |
| NFR-M-2 | All LLM calls shall go through `services/llm_client.py` (no direct `anthropic` imports in agents) |
| NFR-M-3 | All embedding operations shall go through `services/embedding_service.py` |
| NFR-M-4 | Database session shall be injected via FastAPI `Depends(get_db)` or passed explicitly to agents |

### 5.5 Portability

| ID | Requirement |
|---|---|
| NFR-PO-1 | Backend shall run on any Linux/macOS/Windows environment with Python 3.12+ and a PostgreSQL connection |
| NFR-PO-2 | `DATABASE_URL` shall support any psycopg3-compatible PostgreSQL host (Neon, Supabase, local) |

---

## 6. Database Design

### 6.1 Entity-Relationship Summary

```
users ──< skill_profiles        (1:1)
users ──< applications          (1:N)
users ──< memory_episodes       (1:N)
users ──< gap_analyses          (1:N)
users ──< roadmaps              (1:N)
opportunities ──< gap_analyses  (1:N, nullable)
gap_analyses ──< roadmaps       (1:N, nullable)
```

### 6.2 Table Definitions

#### `users`
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR PK | UUID |
| name | VARCHAR | nullable |
| email | VARCHAR UNIQUE | nullable |
| goal | VARCHAR | e.g. "ML internships in India" |
| target_role | VARCHAR | e.g. "ML Engineer" |
| created_at | DATETIME | UTC |

#### `skill_profiles`
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR PK | UUID |
| user_id | VARCHAR FK → users | UNIQUE, CASCADE |
| skills | JSON | `{"Python": 0.9, "PyTorch": 0.7}` |
| projects | JSON | `[{"name": "...", "description": "...", "skills": [...]}]` |
| experience_text | TEXT | Claude-generated summary |
| resume_text | TEXT | raw extracted text |
| embedding | VECTOR(384) | all-MiniLM-L6-v2 |
| updated_at | DATETIME | auto-update |

#### `opportunities`
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR PK | UUID |
| title | VARCHAR | |
| company | VARCHAR | |
| location | VARCHAR | nullable |
| description | TEXT | nullable |
| required_skills | JSON | `["Python", "PyTorch"]` |
| url | VARCHAR | nullable |
| deadline | VARCHAR | ISO date string |
| type | VARCHAR | internship / hackathon / fellowship / research |
| stipend | VARCHAR | nullable, display string |
| embedding | VECTOR(384) | semantic search |
| is_active | BOOLEAN | default true |
| fetched_at | DATETIME | |

#### `gap_analyses`
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR PK | UUID |
| user_id | VARCHAR FK → users | CASCADE |
| opportunity_id | VARCHAR FK → opportunities | SET NULL on delete |
| match_score | FLOAT | 0.0 – 1.0 |
| missing_skills | JSON | `[{"skill": "...", "priority": 1, "hours": 30}]` |
| present_skills | JSON | `["Python", "SQL"]` |
| summary | TEXT | |
| created_at | DATETIME | |

#### `roadmaps`
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR PK | UUID |
| user_id | VARCHAR FK → users | CASCADE |
| gap_analysis_id | VARCHAR FK → gap_analyses | nullable |
| steps | JSON | `[{"step": "...", "resource": "...", "hours": 10, "priority": 1, "skill": "..."}]` |
| total_hours | FLOAT | |
| summary | TEXT | |
| created_at | DATETIME | |

#### `applications`
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR PK | UUID |
| user_id | VARCHAR FK → users | CASCADE |
| company | VARCHAR | |
| role | VARCHAR | |
| status | VARCHAR | applied / interview / offered / rejected / withdrawn |
| applied_date | VARCHAR | nullable |
| deadline | VARCHAR | nullable |
| notes | TEXT | nullable |
| url | VARCHAR | nullable |
| created_at | DATETIME | |
| updated_at | DATETIME | auto-update |

#### `memory_episodes`
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR PK | UUID |
| user_id | VARCHAR FK → users | CASCADE |
| content | TEXT | |
| episode_type | VARCHAR | goal / skill / application / insight / general |
| embedding | VECTOR(384) | cosine distance retrieval |
| importance | FLOAT | 0.0 – 1.0, default 1.0 |
| created_at | DATETIME | |

---

## 7. API Specification

### Base URL
`http://localhost:8000` (dev) · `https://mitra.up.railway.app` (prod)

### Endpoints

#### `POST /api/users`
Create a user.
```json
Body:  { "name": "Athar", "goal": "ML internships in India", "target_role": "ML Engineer" }
200:   { "id": "uuid", "name": "Athar", ... }
```

#### `POST /api/profile/upload`
Upload a resume (multipart form).
```
Form: user_id (string), file (PDF or .txt)
200:  SkillProfileRead — { id, user_id, skills: {...}, projects: [...], ... }
```

#### `POST /api/chat`
Full synchronous chat.
```json
Body:  { "user_id": "uuid", "message": "Find me ML internships and show skill gaps" }
200:   { "user_id": "...", "response": "...", "intent": "opportunities", "data": { ... } }
```

#### `POST /api/chat/stream`
Streaming SSE chat.
```
Content-Type: text/event-stream

data: {"type": "progress", "node": "memory_retriever"}
data: {"type": "progress", "node": "intent_router"}
data: {"type": "progress", "node": "opportunity_hunter"}
data: {"type": "progress", "node": "gap_detector"}
data: {"type": "progress", "node": "roadmap_planner"}
data: {"type": "progress", "node": "responder"}
data: {"type": "token", "chunk": "Based on your profile, "}
data: {"type": "token", "chunk": "here are the top opportunities:"}
...
data: {"type": "done"}
```

#### `GET /api/opportunities?type=internship`
List active opportunities, optionally filtered by type.

#### `POST /api/opportunities/search`
Body: `{ "query": "LLM fine-tuning Bangalore" }` → semantic search.

#### `GET /api/tracker/{user_id}`
List all tracked applications for a user.

#### `PATCH /api/tracker/{app_id}`
Update application status: `{ "status": "interview", "notes": "..." }`

---

## 8. Agent Specifications

### 8.1 Memory Retriever

**Trigger:** Every request (first node)  
**Input:** `user_id`, last user message  
**Process:** pgvector cosine distance search over `memory_episodes` for `user_id`  
**Output:** `memory_context: list[str]` — top 5 most relevant past episodes  
**Side effects:** None (read-only)

### 8.2 Intent Router

**Trigger:** After memory retriever  
**Input:** Last user message  
**Process:** Claude classifies into one of: `opportunities | resume | gaps | roadmap | track | interview | general`  
**Output:** `intent: str`  
**Model:** Claude Sonnet 4.6, max_tokens=20  
**Side effects:** None

### 8.3 Opportunity Hunter

**Trigger:** `intent == "opportunities"`  
**Input:** User message, skill profile skills  
**Process:** 
1. Builds query embedding from message + top-10 skills
2. cosine distance search over `opportunities` with pgvector
3. Falls back to recency sort if no embeddings found  
**Output:** `opportunities: list[dict]` — top 8 matches  
**Side effects:** None (read-only)

### 8.4 Resume Analyzer

**Trigger:** `intent == "resume"`  
**Input:** `user_id`  
**Process:**
1. Loads `resume_text` from `skill_profiles`
2. Sends to `skill_graph.extract_from_text()`
3. Claude extracts skills + projects + experience summary
4. Generates new profile embedding
5. Persists updated profile  
**Output:** `user_profile: dict`  
**Side effects:** Updates `skill_profiles` row

### 8.5 Gap Detector

**Trigger:** `intent == "gaps"` OR after Opportunity Hunter  
**Input:** `user_profile`, `opportunities` (uses first opportunity as target)  
**Process:**
1. Loads skills from state or DB
2. Calls `skill_graph.compute_match()` — reciprocal skill matching
3. Claude prioritises missing skills and estimates hours
4. Claude generates plain-English summary  
**Output:** `gap_analysis: dict` — `{match_score, missing_skills, present_skills, summary}`  
**Side effects:** Inserts into `gap_analyses`

### 8.6 Roadmap Planner

**Trigger:** `intent == "roadmap"` OR after Gap Detector  
**Input:** `gap_analysis`, `user_profile`, `opportunities`  
**Process:**
1. If no missing skills → returns readiness message
2. Otherwise: Claude generates ordered steps with specific resources and hour estimates
3. Returns structured roadmap  
**Output:** `roadmap: dict` — `{steps, total_hours, summary}`  
**Side effects:** Inserts into `roadmaps`

### 8.7 Application Tracker

**Trigger:** `intent == "track"`  
**Input:** `user_id`, last user message  
**Process:**
1. Fetches all applications from DB
2. Checks if message contains application-logging keywords
3. If yes: Claude extracts company/role/date from natural language and inserts new `Application`
4. Stores in `memory_episodes`  
**Output:** `tracked_applications: list[dict]`  
**Side effects:** May insert `Application` and `MemoryEpisode`

### 8.8 Interview Coach

**Trigger:** `intent == "interview"`  
**Input:** `opportunities`, skill profile, last user message  
**Process:**
1. Detects whether user is asking for questions or submitting an answer
2. If asking → Claude generates 5 role-specific questions
3. If answering → Claude evaluates answer on 3 dimensions + provides model answer  
**Output:** Sets `final_response` directly (bypasses generic responder)  
**Side effects:** None

### 8.9 Responder

**Trigger:** All paths except when `final_response` already set  
**Input:** Full accumulated state (profile, opportunities, gap, roadmap, applications, memories)  
**Process:** Claude synthesises a focused, data-grounded response using all available context  
**Output:** `final_response: str`, appends `AIMessage` to messages  
**Model:** Claude Sonnet 4.6, max_tokens=1000

---

## 9. ML Pipeline Specification

### 9.1 Task: Skill Gap Classification

**Problem statement:** Given a student's background summary and a job description, predict the prioritised list of missing skills, present skills, and a match score.

**Why fine-tune:**  
- Claude calls are expensive at inference time for a production system
- A 3B model can achieve 80%+ of Claude's accuracy on this narrow task at 10x lower cost
- Demonstrates knowledge distillation, QLoRA, and evaluation — all key interview topics

### 9.2 Data Generation

**Script:** `ml/generate_synthetic_data.py`  
**Teacher:** Claude Haiku (`claude-haiku-4-5-20251001`) — cheaper, still high quality for structured output  
**Volume:** 500 `(input, output)` pairs  
**Format:**
```json
{
  "input": "STUDENT BACKGROUND:\n...\n\nJOB DESCRIPTION:\n...",
  "output": {
    "missing_skills": [{"skill": "PyTorch", "priority": 1, "hours": 40}],
    "present_skills": ["Python", "SQL"],
    "match_score": 0.45,
    "reasoning": "..."
  }
}
```
**Diversity:** 7 student profiles × 10 target roles = 70 unique pairs, randomly sampled to 500

### 9.3 Training

**Script:** `ml/train_skill_gap_classifier.py`  
**Base model:** `Qwen/Qwen2.5-3B-Instruct`  
**Method:** QLoRA (4-bit NF4 quantisation + LoRA r=16, α=32)  
**Target modules:** `q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`  
**Training:** 3 epochs, batch size 4, gradient accumulation 4, lr 2e-4, cosine schedule  
**Hardware:** Single T4 GPU (Google Colab free tier is sufficient)  
**Prompt format:** ChatML (`<|im_start|>system/user/assistant<|im_end|>`)

### 9.4 Evaluation Metrics

| Metric | Description |
|---|---|
| Skill overlap F1 | Exact match between predicted and true missing skills |
| Priority rank correlation | Spearman correlation between predicted and Claude priority ordering |
| Match score MAE | Mean absolute error on the 0–1 match score |
| JSON validity rate | % of outputs that parse as valid JSON |

### 9.5 Serving (Future)

After training, the fine-tuned adapter can be:
1. Merged into the base model and pushed to HuggingFace Hub
2. Served via a separate `/ml/predict` FastAPI endpoint
3. Used as a replacement for the `gap_detector` agent's Claude call

---

## 10. Development Phases

### Phase 1 — Core Backend (Current)

- [x] Project scaffold (`config`, `database`, models, services)
- [x] 6 LangGraph agents
- [x] FastAPI routers (users, profile, opportunities, tracker, chat)
- [x] SSE streaming chat
- [x] Seed data (20 opportunities)
- [x] pgvector episodic memory
- [x] Skill gap + roadmap logic
- [x] ML data generation + QLoRA training scripts

### Phase 2 — Frontend (Next.js)

- [ ] Chat interface with SSE streaming display and progress indicators
- [ ] Dashboard: skill profile radar chart, match scores, application pipeline
- [ ] Opportunities board with filters
- [ ] Roadmap view with progress tracking
- [ ] Resume upload page

### Phase 3 — Research Component

- [ ] Fine-tuned Qwen2.5-3B serving endpoint
- [ ] RAGAS evaluation pipeline for RAG quality
- [ ] Neo4j knowledge graph for skill relationships (prerequisite chains)
- [ ] Adaptive skill gap recommendation using reciprocal ranking (paper-worthy)

### Phase 4 — Production

- [ ] JWT-based authentication
- [ ] Railway deployment with GitHub Actions CI/CD
- [ ] GitHub profile analysis (extract skills from public repos)
- [ ] LangSmith observability
- [ ] Deadline reminder cron jobs

---

## 11. Out of Scope

The following are explicitly excluded from v1 to keep scope controlled:

- **Live job scraping** — LinkedIn, Internshala, Naukri scraping is legally and technically complex; seeded data is sufficient for portfolio demonstration
- **User authentication** — any `user_id` can query any endpoint; authentication is Phase 3
- **Real-time notifications** — email or push reminders for deadlines
- **Mobile app** — web only
- **Payment / premium tier** — open access
- **Multi-language support** — English only in v1 (ironic given the Sarvam/Krutrim context, but pragmatic)
- **GitHub OAuth** — profile analysis from repos is Phase 4
