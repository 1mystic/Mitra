# Mitra 2.0 — Progress Log

## Status: Phase 3 in progress

---

## Completed ✅

### Phase 1 — Core backend
- FastAPI + SQLAlchemy + pgvector setup
- 7 DB tables: users, skill_profiles, opportunities, gap_analyses, roadmaps, applications, memory_episodes
- LangGraph multi-agent graph: memory_retriever → intent_router → [7 sub-agents] → responder → memory_writer
- SSE streaming chat endpoint (`/api/chat/stream`)
- Resume upload + chunk embedding (`/api/profile/upload`)
- Semantic memory store/retrieve (episodic, pgvector cosine)
- bcrypt auth (JWT bearer tokens)

### Phase 2 — UI v1
- Next.js 14 app router frontend
- Landing, auth, onboarding, chat, opportunities, tracker pages
- Chat SSE streaming with agent pipeline sidebar
- Opportunity cards with skill tags on `/opportunities`
- Application kanban tracker with column colour stripes

### Phase 3 — In progress
- [x] psycopg3 `::vector` cast syntax fix (memory_service + resume_service)
- [x] Resume upload speed: batch embedding (batch_size=64), rotating tips, elapsed timer
- [x] Live job fetcher: Adzuna API + Internshala scraper + Unstop API
- [x] APScheduler (twice daily, 06:00 + 18:00 IST)
- [x] Admin endpoints: `POST /api/admin/refresh-jobs` and `.../sync`
- [x] Stale listing pruner (30 days, respects manual seeds source IS NULL)
- [x] UI/UX: gradient hero title, card hover glows, opp left-accent strip, user text pill, kanban column stripe, nav depth shadow
- [x] Chat history: Conversation + ChatHistoryMessage DB models + migrations
- [x] Chat history router (`/api/history/...`)
- [x] Chat history frontend: sidebar list, load, delete, rename
- [x] Auto-save conversation turns to DB (user + assistant messages)
- [x] Profile page: Account Settings section (edit name + goal)
- [x] Fix `memory_writer_node` LangGraph empty-dict error → returns `{"error": None}`
- [x] Opportunity cards in chat: inline after agent runs, with clickable follow-up action pills
- [x] SSE `data` event: backend emits opportunities after `opportunity_hunter` runs
- [x] Fix field name mismatch: `required_skills` → consistent across backend schema + frontend types

---

## Pending / Next

- [ ] Seed the opportunities DB: `python -m db.seed_opportunities`
- [ ] Trigger admin refresh to fetch live listings (avoid cold start):
  ```
  curl.exe -X POST http://localhost:8000/api/admin/refresh-jobs/sync -H "Authorization: Bearer <token>"
  ```
- [ ] Fine-tuning pipeline: `ml/generate_synthetic_data.py` + `train_skill_gap_classifier.py`
- [ ] Alembic migrations (Phase 4)
- [ ] Analytics dashboard
- [ ] Mobile-responsive improvements
- [ ] Rate limiting on chat endpoint

---

## Known issues / watchlist

- Internshala scraper may be blocked by anti-bot; has polite 1.5s delay + browser headers
- Adzuna requires `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` env vars (silently returns [] if missing)
- Unstop API endpoint is unofficial; monitor for breaking changes
- `memory_writer_node` was crashing with `{}` return — fixed to return `{"error": None}`
- If opportunities DB is empty, agent falls back to recency order; result may be generic

---

## Architecture quick-reference

```
frontend (Next.js 14, port 3000)
  ↕ fetch / SSE
backend (FastAPI, port 8000)
  ├── /api/chat/stream  → LangGraph graph (per-request, binds DB session)
  ├── /api/history/...  → Conversation CRUD
  ├── /api/profile/...  → Resume upload + skill profile
  ├── /api/opportunities → Opportunity CRUD + search
  ├── /api/tracker      → Application tracker
  ├── /api/admin        → Job refresh trigger (requires auth)
  └── APScheduler       → Runs at 06:00 + 18:00 IST
DB (Neon PostgreSQL + pgvector)
```
