# Mitra 2.0 — Phase Roadmap

## Phase 1 — Core (Done)
Backend scaffolding, DB models, LangGraph agents, SSE chat, resume upload, memory service.

## Phase 2 — UI v1 (Done)
Landing page, auth flow, onboarding, chat page, opportunities page, tracker.

## Phase 3 — Live data + polish (Current)
- Live job fetcher (Adzuna, Internshala, Unstop) + APScheduler
- Chat history (persistent conversations)
- Opportunity cards in chat with follow-up action pills
- Profile management (account settings)
- UI micro-interactions: hover glows, gradient text, kanban stripes
- LangGraph bug fixes: memory_writer empty dict

## Phase 4 — Intelligence upgrades
- Alembic migrations
- Fine-tuned skill gap classifier (QLoRA, Qwen2.5-3B, synthetic data)
- Resume parser improvements (section detection, project extraction)
- LangSmith tracing integration
- Rate limiting + request queue

## Phase 5 — Production
- Docker Compose for local dev
- Deploy to Railway / Render
- Environment-based config
- Error monitoring (Sentry)
- Analytics dashboard
- Auth hardening (refresh tokens, email verification)
