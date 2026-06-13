# Mitra — Technical Coverage Document

> Written from source code, not from intent. Every claim here is traceable to a specific file and function.
> Last updated against the current implementation as of June 2026.

---

## 1. What Mitra Actually Is

Mitra is a **multi-agent career intelligence system** built as a portfolio project for ML/AI students in India. It helps users find internships, map skill gaps, build learning roadmaps, track applications, and prepare for interviews — delivered through a streaming chat interface.

### Is it truly agentic?

**Honest answer: it is an agentic workflow, not a fully autonomous agent.**

Here is the distinction, applied to the actual code:

| Agentic capability | Mitra's reality |
|---|---|
| Multiple specialized LLM-powered components | Yes — 6 distinct agent nodes, each with a focused purpose |
| Shared typed state that persists across nodes | Yes — `AgentState` TypedDict passed through the LangGraph graph |
| Conditional routing based on content | Yes — `classify_intent()` selects one of 7 intent branches |
| Memory that persists across sessions | Yes — hybrid-scored pgvector episodic memory |
| RAG over user's own resume | Yes — section-aware chunking + cosine retrieval |
| Autonomous next-action selection (ReAct-style) | **No** — graph edges are pre-wired at compile time |
| Retry or reflection loops | **No** — if an agent fails or finds nothing, it returns an error string; it does not re-plan |
| Multi-intent handling in one message | **No** — a single intent is chosen; "find internships AND gaps" collapses to one path |
| True token-level streaming from LLM | **No** — `responder_node` buffers the full response then word-splits it: `text.split(" ")` — this is simulated streaming |
| Goal-directed multi-turn planning | **No** — each request is a fresh graph invocation; the conversation history exists in DB but is not injected into the agent state |

**The correct term for this architecture:** an **agentic pipeline** — specifically LangGraph's recommended "workflow" pattern. Multiple LLM-powered specialists collaborate in a structured graph with conditional edges, memory injection, and real-time streaming. This is genuinely impressive for a portfolio project; it is just not a fully autonomous, self-directing agent.

---

## 2. System Architecture — As Built

### Request flow (current, post-optimization)

```
POST /api/chat/stream  (rate-limited: 10 req/user/minute)
        │
        ▼
  chat_stream()           ← FastAPI SSE endpoint
        │
        ▼
   build_graph(db)        ← fresh LangGraph compile per request
        │
        ├──────────────────────────────────────────────┐
        │                                              │
  memory_retriever_node                      intent_router_node
  (DB: pgvector cosine search                (LLM: Haiku classify_intent,
   over MemoryEpisode + ResumeChunk)          returns one of 7 intent labels)
        │                                              │
        └──────────────┬───────────────────────────────┘
                       │  (fan-in — both must complete)
                  router_node
                  (no-op; triggers conditional routing)
                       │
          ┌────────────┼────────────────────────────────────┐
          │            │            │            │           │
  opportunity_  resume_     gap_      roadmap_  application_ interview_
  hunter_node   analyzer_   detector_ planner_  tracker_    coach_node
                node        node      node      node
          │            │            │            │           │
          │            │            │            │           │
          └────────────┴────────────┴────────────┴───────────┘
                                    │
                               responder_node
                               (Sonnet synthesis)
                                    │
                           memory_writer_node
                           (stores episode to pgvector)
                                    │
                                   END
```

**Note on the `opportunity_hunter → gap_detector` chain:** this was previously hardwired. As of current implementation, `opportunity_hunter` routes directly to `responder`. Gap analysis and roadmap generation are only triggered when the user explicitly asks for them (intent `"gaps"` or `"roadmap"`). This cuts 2–3 unnecessary Sonnet calls from the most common query path.

### Parallel entry nodes

`memory_retriever_node` (DB vector search) and `intent_router_node` (Haiku LLM call) now run in the same LangGraph superstep — they execute concurrently. Both must complete before `router_node` fires. This saves approximately 2–3 seconds per request by overlapping a network-bound operation (vector DB query) with a different network-bound operation (Haiku API call).

---

## 3. Agent Node Inventory

### `memory_retriever_node` (`graph.py`)
- Runs `memory_service.retrieve()` — hybrid pgvector query: `importance × (0.7 × semantic_sim + 0.3 × recency_decay)`
- Also runs `resume_service.retrieve_chunks()` — cosine search over `ResumeChunk` rows
- Threshold-filtered: episodes with cosine distance ≥ 0.75 (memories) or 0.85 (resume chunks) are discarded
- Both run concurrently with `intent_router_node`

### `intent_router_node` (`graph.py`)
- Calls `llm_client.classify_intent()` → `fast_complete()` → **Haiku** (not Sonnet)
- 7 valid labels: `opportunities | resume | gaps | roadmap | track | interview | general`
- Falls back to `"general"` if the returned token is not in the valid set
- Optional: replaced by `distill_intent.classify_intent()` when `USE_LOCAL_CLASSIFIER=true` (Qwen2.5-3B QLoRA adapter)

### `opportunity_hunter_node` (`agents/opportunity_hunter.py`)
- Detects "live search" keywords: `latest, recent, new, newest, fresh, today, just posted, live, current openings, new openings`
- If detected: calls `quick_fetch(limit_per_source=3)` + `ingest_jobs()` with an 8-second timeout, then falls through to semantic search. Live fetch failure is non-fatal.
- Builds query text: `user_message + top 10 skill names from profile`
- Embeds query with `sentence-transformers/all-MiniLM-L6-v2` (384-dim)
- Cosine search over `opportunities` table via `pgvector <=>` operator, `LIMIT 8`
- Fallback: if no embeddings present yet, returns most-recently-fetched 8 active opportunities
- Returns: dict with `opportunities` list (includes `source` and `fetched_at` fields)

### `resume_analyzer_node` (`agents/resume_analyzer.py`)
- Reads stored `SkillProfile.resume_text` from DB
- Re-runs `skill_graph.extract_from_text()` → Sonnet call, returns `{skills, projects, experience_summary}`
- Normalizes extracted skill names through `SKILL_TAXONOMY` (80+ entries covering abbreviations, aliases, packaging names)
- Recomputes profile embedding (`skills + project descriptions`) and persists it
- Commits updated `SkillProfile` to DB

### `gap_detector_node` (`agents/gap_detector.py`)
- Uses `state["user_profile"]` or falls back to reading `SkillProfile` from DB
- Aggregates `required_skills` from the first opportunity in state (if any); falls back to generic ML/AI role requirements
- `skill_graph.compute_match()`: taxonomy normalize → exact → substring → fuzzy (SequenceMatcher ≥ 0.82) — four-stage matching pipeline
- Tier-weighted scoring: Tier 1 skills (Python, PyTorch, SQL, Git, etc.) weight 2.0×; Tier 2 (scikit-learn, FastAPI, Docker, etc.) weight 1.5×; all others 1.0×
- If missing skills found: Sonnet call to rank them by priority with hours estimates
- Persists `GapAnalysis` row to DB
- Returns: `{match_score, missing_skills, present_skills, summary}`

### `roadmap_planner_node` (`agents/roadmap_planner.py`)
- Requires `gap_analysis` in state — returns error if absent (caller must run `gap_detector` first)
- If no missing skills: returns early with a "you're ready, apply now" message
- Sonnet `complete_json()` call to generate structured roadmap: `{steps: [{step, resource, hours, priority, skill}], total_hours, summary}`
- Resources are real and specific (Coursera, GitHub repos, Kaggle, papers) — generated by Sonnet, not hardcoded
- Persists `Roadmap` row to DB. Note: `gap_analysis_id` is not linked (left as `None` in current code — see improvement #11 below)
- Returns: `{roadmap}`

### `application_tracker_node` (`agents/application_tracker.py`)
- Fetches all applications for `user_id`, ordered by `created_at DESC`
- Keyword detection: if message contains `"applied to"`, `"applied for"`, `"add application"`, or `"track application"` → runs Sonnet `complete_json()` to extract company/role/status/dates from the message
- If extracted and `company` is non-empty: creates `Application` row in DB and stores a memory episode
- Returns all applications (newly created one inserted at position 0 if added)

### `interview_coach_node` (`agents/interview_coach.py`)
- Detects if user is answering a previous question via keywords: `"my answer"`, `"i would"`, `"i think"`, `"the answer"`
- **Answering path:** Sonnet call to evaluate on 3 dimensions (technical accuracy, depth, clarity), gives feedback + model answer
- **Question path:** Sonnet call to generate 5 role-specific questions (2 technical, 1 system design, 1 project, 1 behavioral)
- Sets `final_response` directly — bypasses `responder_node` (graph edge: `interview_coach → responder`, but `responder_node` checks `if state.get("final_response"): return {}`)

### `responder_node` (`graph.py`)
- Aggregates all state data: memory context, resume chunks, profile skills, opportunities, gap analysis, roadmap, tracked applications
- Builds a contextual system prompt + user prompt and calls `llm_client.complete()` (Sonnet, `max_tokens=1000`)
- Returns `{final_response, messages: [AIMessage]}`
- **Important limitation:** the chat SSE endpoint then word-splits this response (`text.split(" ")`) and re-emits it as `type: token` events. The full response is computed synchronously before any tokens are streamed to the client.

### `memory_writer_node` (`graph.py`)
- Calls `memory_service.build_episode(state)` to construct a structured text representation of the interaction
- Importance scaling: base 1.0, +0.5 if gap analysis, +0.5 if roadmap with steps, +0.3 if opportunities — capped at 3.0
- Stores with the classified `intent` as `episode_type`

---

## 4. Services

### `embedding_service.py`
- Singleton `SentenceTransformer("all-MiniLM-L6-v2")` via `@lru_cache(maxsize=1)`
- Pre-warmed at startup in `main.py` lifespan: `run_in_executor(None, embedding_service._get_model)`
- 2-worker `ThreadPoolExecutor` — sync inference runs off the async event loop
- `embed(text)` → single embedding; `embed_batch(texts)` → batched, `batch_size=64`
- 384-dimensional output, L2-normalized

### `llm_client.py`
- Two model tiers:
  - `complete()` / `complete_json()` → `settings.claude_model` (Sonnet 4.6) — used for agent tasks
  - `fast_complete()` / `fast_complete_json()` → `settings.fast_model` (Haiku 4.5) — used for intent routing and classification
- `stream_complete()` exists but is **not used** by any current agent — the responder calls `complete()` (blocking), not `stream_complete()`
- `classify_intent()`: uses `fast_complete(max_tokens=10)` or the local Qwen2.5-3B adapter

### `memory_service.py`
- `store()`: embeds content, creates `MemoryEpisode` row
- `retrieve()`: hybrid SQL query — cosine threshold filter + `importance × (0.7 × semantic + 0.3 × recency)` ORDER BY. Vector literal is inlined (not bound parameter) to avoid psycopg3/pgvector conflict with `$N` placeholder syntax — safe because values are model-generated floats
- `build_episode()`: packs intent, query, top opportunities, gap score, roadmap summary, and first 400 chars of response into a structured string
- `get_recent()`: plain recency-ordered fetch (not used by agents currently)

### `skill_graph.py`
- `SKILL_TAXONOMY`: 80+ entries mapping aliases → canonical names (e.g., `"qlora" → "QLoRA"`, `"sklearn" → "scikit-learn"`)
- `_TIER_1` / `_TIER_2`: frozensets for weighted scoring
- `_find_match()`: 3-stage: exact → substring (bidirectional) → fuzzy (SequenceMatcher ratio ≥ 0.82)
- `extract_from_text()`: Sonnet + `complete_json()`, normalizes extracted skills through taxonomy
- `compute_match()`: taxonomy-normalizes both sides, runs `_find_match()` per required skill, calls Sonnet to rank missing skills by priority with hours estimates

### `resume_chunker.py`
- Pure function — no DB, no embeddings
- Detects section headers from a list of 28 patterns (Experience, Projects, Education, Skills, etc.)
- Sub-splits sections > 500 chars into overlapping windows (overlap = 80 chars) breaking on sentence/newline/semicolon/space boundaries
- Returns `[{content, section, chunk_index}]`

### `resume_service.py`
- `store_chunks()`: deletes old chunks (idempotent re-upload), batch-embeds new chunks, inserts `ResumeChunk` rows
- `retrieve_chunks()`: cosine search with `threshold=0.85`, returns `"[Section] content"` strings

### `job_fetcher/` (5 fetchers + orchestrator)
- **Internshala** (`internshala.py`): HTTP scraper with BeautifulSoup, 6 ML/AI category pages, 1.5s polite delay between pages, dedup by `external_id`
- **Adzuna** (`adzuna.py`): REST API (requires `ADZUNA_APP_ID` + `ADZUNA_APP_KEY`)
- **Himalayas** (`himalayas.py`), **Remotive** (`remotive.py`), **Unstop** (`unstop.py`): each has its own fetch strategy
- `run()`: concurrent gather of all 5, upsert keyed on `(source, external_id)`, prune stale (30 days) and past-deadline listings, return stats including `source_counts`
- `quick_fetch(limit_per_source=3)`: same concurrent gather with 8-second `asyncio.wait_for` hard timeout — used for live search
- `ingest_jobs(jobs)`: creates its own `AsyncSessionLocal` session, calls `_upsert_all()`
- Seeded/manual listings (`source IS NULL`) are never pruned

---

## 5. Data Model (9 tables)

| Table | Purpose | Key columns |
|---|---|---|
| `users` | User accounts | `id`, `name`, `email`, `hashed_password`, `goal`, `target_role` |
| `skill_profiles` | Extracted resume data | `skills` (JSON `{name: 0.0-1.0}`), `projects` (JSON), `embedding` (vector(384)) |
| `opportunities` | Job listings | `embedding` (vector(384)), `source`, `external_id` (upsert key), `is_active`, `fetched_at` |
| `gap_analyses` | Skill gap records | `match_score`, `missing_skills` (JSON), `present_skills` (JSON) |
| `roadmaps` | Learning roadmaps | `steps` (JSON), `total_hours`, `gap_analysis_id` (nullable — not linked currently) |
| `applications` | User job applications | `status` (5 valid values), `applied_date`, `deadline`, `notes` |
| `memory_episodes` | Episodic memory | `embedding` (vector(384)), `importance` (float), `episode_type` |
| `conversations` | Chat sessions | `title`, `updated_at` (bumped on new message) |
| `chat_history_messages` | Message turns | `role` (user/assistant), `content`, `conversation_id` FK |

**Vectors:** all `vector(384)` columns use pgvector's `<=>` cosine distance operator. The pgvector extension is enabled at startup via `CREATE EXTENSION IF NOT EXISTS vector`.

**Note:** `conversations` and `chat_history_messages` are persisted by the `history` router, but the agent graph does **not** read chat history — it only reads `memory_episodes`. The two systems are parallel and not integrated.

---

## 6. API Surface (complete)

### Auth
```
POST  /api/auth/register   → {access_token, user}  (201)
POST  /api/auth/login      → {access_token, user}
GET   /api/auth/me         → user  (Bearer token)
```

### Users
```
POST   /api/users          → user  (201)
GET    /api/users/{id}     → user
PATCH  /api/users/{id}     → user
```

### Profile
```
POST  /api/profile/upload  multipart: user_id + file (PDF or text)
                           → {skills, projects, experience_text, chunk_count}  (201)
GET   /api/profile/{user_id} → skill profile
```

### Chat
```
POST  /api/chat            JSON body: {user_id, message} → {response, intent, data}
POST  /api/chat/stream     JSON body: {user_id, message} → text/event-stream
GET   /api/chat/health     → {"status": "ok"}
```
Rate limit on `/api/chat/stream`: 10 requests per `user_id` per 60 seconds.

SSE event types from `/api/chat/stream`:
```
{"type": "progress", "node": "<node_name>", "detail": "<human label>"}
{"type": "data",     "key": "opportunities",  "value": [<opportunity>, ...]}
{"type": "data",     "key": "gap_score",      "value": <int 0-100>}
{"type": "token",    "chunk": "<word> "}
{"type": "error",    "message": "<error>"}
{"type": "done"}
```

### Opportunities
```
GET   /api/opportunities               → list (filter: ?type=internship, ?limit=20)
POST  /api/opportunities/search        {query, user_id?, limit?} → list (semantic)
POST  /api/opportunities               {title, company, ...} → opportunity  (201)
```

### Tracker
```
GET    /api/tracker/{user_id}          → list of applications
POST   /api/tracker                    JSON body: {user_id, company, role, status?, ...}  (201)
PATCH  /api/tracker/{app_id}           {status?, notes?, deadline?} → application
DELETE /api/tracker/{app_id}           (204)
```
Valid statuses: `applied | interview | offered | rejected | withdrawn`

### History
```
GET    /api/history/conversations/{user_id}       → list with message_count
POST   /api/history/conversations                 {user_id, title?}  (201)
GET    /api/history/conversations/{conv_id}/messages → conversation + messages
PATCH  /api/history/conversations/{conv_id}       {title}
DELETE /api/history/conversations/{conv_id}       (204)
POST   /api/history/messages                      {conversation_id, role, content}  (201)
```

### Admin (Bearer token required)
```
POST  /api/admin/refresh-jobs          → full stats dict {fetched, upserted, pruned, source_counts, errors}
GET   /api/admin/scheduler-status      → {running: bool, jobs: [{id, name, next_run_time, trigger}]}
```

### System
```
GET   /                    → {name, version, agents[]}
GET   /api/health          → {status, db, opportunity_count, embedding_model}  (503 if DB down)
```

---

## 7. Scheduler

`APScheduler AsyncIOScheduler` registered in `main.py` lifespan. One job:
- ID: `refresh_jobs`
- Trigger: `CronTrigger(hour="6,18", minute=0, timezone="Asia/Kolkata")` → 6:00 and 18:00 IST
- `misfire_grace_time=300` → fires within 5 minutes if server was down at trigger time
- Calls `job_fetcher.run()` which fetches all 5 sources, upserts, prunes, logs `source_counts`

---

## 8. Security

- **Auth:** JWT (HS256, 30-day expiry) via `python-jose`, bcrypt password hashing (72-byte limit respected)
- **Rate limiting:** in-memory `deque(maxlen=10)` per `user_id` on `/api/chat/stream`, 60-second sliding window
- **Admin endpoints:** Bearer token required, decoded via same JWT logic
- **SQL injection:** all DB queries use SQLAlchemy ORM or parameterized `text()` with named binds. The one exception is the `vec_literal` inline in memory and resume retrieval — this is model-generated floats only (documented with a comment explaining why)
- **CORS:** `allow_origins=["*"]` — intentionally open for portfolio demo; should be restricted in production

---

## 9. ML Fine-tuning Pipeline

This is a **real, complete pipeline** — not aspirational.

**Goal:** replace the Haiku API call in `classify_intent()` with a local Qwen2.5-3B adapter, eliminating a network round-trip entirely.

**Pipeline:**
1. `ml/generate_synthetic_data.py`: calls Claude to generate 500 labeled `(message, intent)` pairs across 7 intents, saves to `ml/data/training_pairs.jsonl`
2. `ml/train_skill_gap_classifier.py`: QLoRA fine-tuning (NF4 4-bit quantization, rank-16 LoRA, Paged AdamW 8-bit) on Colab T4 GPU (~25 minutes). Also `ml/train_kaggle.py` using Unsloth for T4×2.
3. `ml/distill_intent.py`: inference module — loads the adapter at cold start, exposes `classify_intent(message) -> str`

**Activation:** set `USE_LOCAL_CLASSIFIER=true` + `LOCAL_CLASSIFIER_PATH=/path/to/adapter` in `.env`. The backend imports `distill_intent` lazily on first call and runs inference in a thread pool executor.

**Tradeoffs:**
- Pro: eliminates one API call (~0.3s), fully local, no cost per request
- Con: requires 3B model weights on the server (~6 GB RAM), makes Render free tier infeasible; suitable for GPU-enabled deployments or local dev

---

## 10. Edge Cases Handled

| Scenario | Where handled |
|---|---|
| No resume uploaded when agent tries to analyze it | `resume_analyzer_node` returns graceful error dict |
| Scanned/corrupt PDF upload | `pdfplumber` wrapped in try/except → 422 with clear message |
| Empty resume text after extraction | `profile.py` returns 422 "Could not extract any text" |
| Job fetcher source fails or times out | `_safe()` wrapper catches all exceptions; errors appended to stats |
| `quick_fetch` times out (8s) | Returns `[]` with a warning log; semantic search proceeds on cached data |
| Opportunity upsert collision | Checks `(source, external_id)` pair, updates existing record |
| Manual/seeded listings (`source IS NULL`) | Excluded from stale pruning and deadline pruning |
| Past-deadline listings | Pruned via regex-guarded SQL: `deadline ~ '^\d{4}-\d{2}-\d{2}$' AND deadline < :today` |
| Embedding model not loaded on first request | Pre-warmed in lifespan startup via `run_in_executor` |
| DB down at health check | Returns `{"status": "error", "db": "error"}` with HTTP 503 |
| Rate limit exceeded on chat stream | HTTP 429 with `{"detail": "Rate limit: 10 requests/minute"}` |
| Invalid JWT | `_decode_token()` raises HTTP 401 |
| Duplicate email registration | Returns HTTP 409 |
| Re-upload of resume | `store_chunks()` deletes old chunks first (idempotent) |
| `gap_analysis` missing when roadmap is requested | `roadmap_planner_node` returns error: "Gap analysis required first" |
| Zero missing skills in gap analysis | Roadmap returns "you're ready, apply now" without an LLM call |
| Application tracker NLP extraction fails | Falls through to just returning existing applications |
| Tracker `status` not in valid set | HTTP 422 with list of valid values |
| Windows asyncio event loop (psycopg3 requirement) | `WindowsSelectorEventLoopPolicy` set before FastAPI imports |

---

## 11. Known Limitations and Honest Gaps

These are real gaps in the current implementation — not features "coming soon," but actual limitations an interviewer or reviewer should know about.

1. **Simulated token streaming:** `responder_node` calls `llm_client.complete()` (blocking, returns full text), then the SSE endpoint word-splits it. `llm_client.stream_complete()` exists but is unused. Real streaming would start sending tokens within ~200ms of the LLM response starting.

2. **No conversation history injection:** `ChatHistoryMessage` rows are stored but never read by the agent graph. Each request starts from scratch (only episodic memory provides continuity, which is a coarser grain).

3. **Single-intent per request:** a message like "find internships in ML and also check my skill gaps" is classified as one intent and only partially answered.

4. **`roadmap_planner_node` has no fallback when gap is missing:** if the user directly asks "build me a roadmap" without prior gap analysis in state, the node returns an error string instead of running gap analysis first.

5. **No retry or reflection:** if `opportunity_hunter` returns 0 results, it doesn't retry with a broader query.

6. **`gap_analysis_id` not linked in Roadmap:** `db.add(Roadmap(user_id=..., gap_analysis_id=None, ...))` — the foreign key exists in the schema but is never populated.

7. **`User.goal` field is stored but never used:** the `goal` column on `User` (e.g., "ML internships in India") is saved at registration but never injected into the agent graph as context.

8. **No duplicate memory prevention:** `memory_service.store()` always inserts a new episode. Near-identical queries from the same user accumulate near-duplicate episodes over time.

9. **In-memory rate limiting:** `_rate_limit` dict in `chat.py` is lost on server restart and is not shared across multiple instances/workers. Redis would be needed for production.

10. **`interview_coach_node` is stateless:** there is no mechanism to carry a Q&A session across multiple messages. Each message starts a fresh coaching cycle.

---

## 12. Creative Upgrade Opportunities

These are specific, implementable improvements that would substantially differentiate this project. Each is grounded in the actual code.

### Tier 1 — High impact, moderate effort

**A. True token streaming in `responder_node`**
Replace `llm_client.complete()` in `responder_node` with `llm_client.stream_complete()`. The responder would `yield` chunks directly into the event generator. The SSE client already handles `type: token` events — this is a pure backend change that would make responses feel dramatically faster.

**B. Multi-intent parsing**
Before routing, add a `multi_intent_detector_node` that calls `fast_complete_json()` to extract a list of intents from the message. If multiple are found, use LangGraph `Send` to fan out to each agent in parallel and merge results in a dedicated join node. Makes the chat feel much more capable.

**C. Reflection edge on empty results**
In `opportunity_hunter_node`, if the semantic search returns 0 results and the message had skill filters, re-run with a broader query (just the job category, no skill terms). This is a one-line addition: retry with `query_text = last_message` stripped of skill names. Add a `retry_count` field to state to prevent infinite loops.

**D. Inject `User.goal` into agent context**
In `_build_initial_state()` in `chat.py`, read `user.goal` and `user.target_role` from the DB and include them in the initial state. Pass them to `responder_node` as implicit context. Costs one extra DB query per request but significantly personalizes responses.

### Tier 2 — Strong differentiation, more effort

**E. Explainable opportunity matching**
After the cosine search in `opportunity_hunter`, for each returned opportunity run `skill_graph.compute_match(user_skills, opportunity.required_skills)` to generate a per-listing match score and skill breakdown. Return this as `{opportunity, match_score, matched_skills, missing_skills}` in the `type: data` SSE event. The frontend can then render "82% match — you have Python/PyTorch, missing Docker."

**F. Conversation-scoped memory retrieval**
Add `conversation_id: Optional[str]` to `AgentState`. If present, filter `memory_service.retrieve()` to only episodes from that conversation's time window. Prevents memories from a previous job search contaminating a current interview prep session.

**G. Resume diff on re-upload**
In `profile.py`, before overwriting the profile, compute the skill diff: `new_skills - old_skills`. If non-empty, store a `"skill_progress"` memory episode: `"Added Docker, Kubernetes since last upload (2025-03-15)"`. This creates a longitudinal skill timeline visible through the memory system.

**H. Deadline urgency in application tracker**
In `application_tracker_node`, after fetching applications, sort them by `deadline` and flag any where `deadline` is within 7 days (today + 7). Emit a separate `type: data` SSE event with `key: "urgent_deadlines"` so the frontend can display a banner. Uses only existing data — no new DB columns needed.

**I. Duplicate memory suppression**
Before `memory_service.store()`, run a fast cosine query: if any existing episode for this user has distance < 0.15 to the new content's embedding, skip insertion. This keeps the episodic memory compact and relevant over many sessions.

### Tier 3 — Notable but complex

**J. Link Roadmap → GapAnalysis**
In `roadmap_planner_node`, after running `gap_detector`, the `gap_analysis_id` is available in state via `db.execute(select(GapAnalysis)...)`. Linking them enables tracking: "You completed the PyTorch step from your March roadmap — your match score went from 42% to 71%."

**K. Skill confidence decay**
Add a `skill_assessed_at` timestamp to `SkillProfile`. In `compute_match()`, weight the candidate's proficiency score by a recency factor: `proficiency × (1 / (1 + months_since_upload / 6))`. A skill from a 1-year-old resume counts at roughly 75% of face value. More honest matching.

**L. Cross-user skill-gap aggregation (admin insight)**
Add an admin endpoint `GET /api/admin/gap-insights` that aggregates `GapAnalysis.missing_skills` across all users grouped by skill name. Returns: `"Top 5 gaps across all users: Docker (67 users), Kubernetes (43 users), LangGraph (38 users)."` Demonstrates real population-level insight — impressive for a recruiter or product demo.

**M. GitHub profile ingestion**
Add a `POST /api/profile/github` endpoint that accepts a GitHub username, calls the GitHub API to fetch repo names/descriptions/languages, and runs `skill_graph.extract_from_text()` on the combined text. Merges extracted skills with the existing profile. Removes the dependency on PDF upload for users without a polished resume.
