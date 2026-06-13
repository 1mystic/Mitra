# Mitra User Guide

Practical guide to using Mitra — what you can ask, how each feature works, and how to get the most out of it.

---

## What Mitra does

Mitra is a career assistant built for ML/AI students in India. It runs as a multi-agent system — each message is analysed, routed to specialised agents, and assembled into a coherent response. You talk to it in plain English; it handles the routing internally.

Seven things it can help with:

| What you want | Say something like |
|---|---|
| Find opportunities | "Find me NLP internships in Bangalore" |
| Analyse your resume | "What skills does my resume show?" |
| See skill gaps | "What am I missing for this role?" |
| Get a learning plan | "Give me a 3-month PyTorch roadmap" |
| Track applications | "Add my Google application, status: applied" |
| Prep for interviews | "Give me ML interview questions for IIT grads" |
| General career advice | "Should I do an MS or join a startup?" |

---

## Getting started

### 1. Create your account

```bash
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -d '{"name": "Arjun", "goal": "ML internships in India 2025"}'
```

Save the returned `id` — you'll pass it in every request as `user_id`.

### 2. Upload your resume (optional but recommended)

```bash
curl -X POST http://localhost:8000/api/profile/upload \
  -F "user_id=YOUR_USER_ID" \
  -F "file=@/path/to/resume.pdf"
```

Accepts PDF or plain text. Mitra extracts your skills, experience, and education into a structured profile. Skill gap and roadmap features work much better with a resume loaded.

Check what was extracted:
```bash
curl http://localhost:8000/api/profile/YOUR_USER_ID
```

---

## Chat

All AI features go through chat. Use either the streaming (recommended) or non-streaming endpoint.

### Non-streaming

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "YOUR_USER_ID", "message": "YOUR MESSAGE"}'
```

Returns the full response after all agents finish.

### Streaming (SSE)

```bash
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"user_id": "YOUR_USER_ID", "message": "YOUR MESSAGE"}'
```

Emits events as the agents work:

```
data: {"type": "progress", "node": "opportunity_hunter"}
data: {"type": "progress", "node": "gap_detector"}
data: {"type": "token", "chunk": "Based on your "}
data: {"type": "token", "chunk": "profile..."}
data: {"type": "done"}
```

`progress` events tell you which agent is running. `token` events are streamed response text. Listen for `done` to know the response is complete.

---

## Features in detail

### Finding opportunities

Trigger: messages about internships, jobs, research positions, hackathons.

```
"Find me generative AI internships in Bengaluru"
"Any NLP research openings at IITs?"
"Show me data science internships at Indian product companies"
"Agentic AI roles — what's available?"
```

Mitra does semantic search over its opportunity database. Results include title, company, type, location, and a match score. It runs gap detection and roadmap planning on the top results automatically.

Search the opportunity database directly:
```bash
curl -X POST http://localhost:8000/api/opportunities/search \
  -H "Content-Type: application/json" \
  -d '{"query": "LLM fine-tuning intern", "limit": 5}'
```

### Skill gap analysis

Trigger: messages about gaps, missing skills, fit for a role.

```
"What skills am I missing for this MLOps role?"
"How do I compare to the Sarvam AI internship requirements?"
"Am I ready for a computer vision internship?"
"Show my skill gaps"
```

Mitra compares your extracted skill profile against the target role and returns:
- A match score (0–1)
- Missing skills ranked by priority with estimated learning hours
- Present skills already covered
- 2-sentence reasoning

For best results, upload your resume first and mention the specific role you're targeting.

### Learning roadmap

Trigger: messages about learning plans, what to study, how to prepare.

```
"Give me a 3-month PyTorch learning plan"
"How should I prepare for ML internships over summer?"
"I want to learn RAG from scratch — where do I start?"
"Create a study plan for computer vision"
```

Returns an ordered sequence of steps with:
- Topic / skill to cover
- Estimated hours
- Specific resource recommendation (course, paper, tutorial)
- Summary of the overall plan

### Application tracker

Trigger: messages about tracking, updating, or reviewing applications.

```
"Add my application to Sarvam AI — applied yesterday"
"Update my Meesho status to interviewed"
"Show all my pending applications"
"I got rejected from Fractal. Update the status."
"List everything I've applied to this month"
```

Mitra extracts company name, role, and status from natural language. You don't need to fill a form — just describe the update.

Direct CRUD via API:
```bash
# List applications
curl http://localhost:8000/api/tracker/YOUR_USER_ID

# Add manually
curl -X POST "http://localhost:8000/api/tracker?user_id=YOUR_USER_ID" \
  -H "Content-Type: application/json" \
  -d '{"company": "Krutrim", "role": "ML Intern", "status": "applied"}'

# Update status
curl -X PATCH http://localhost:8000/api/tracker/APP_ID \
  -H "Content-Type: application/json" \
  -d '{"status": "interviewed", "notes": "System design round next week"}'
```

Application statuses: `applied` → `shortlisted` → `interviewed` → `offered` / `rejected`

### Interview preparation

Trigger: messages about interview prep, practice questions, mock interviews.

```
"Give me ML interview questions for a data science role"
"What are common LangGraph questions in agentic AI interviews?"
"I have a Flipkart ML interview tomorrow — what should I review?"
"Ask me a coding question about transformers and evaluate my answer"
"What's typically asked in IIT research lab interviews?"
```

Mitra generates role-specific questions and evaluates answers for technical accuracy and clarity.

### Resume analysis

Trigger: messages about uploading, reviewing, or querying your resume.

```
"Analyse my resume"
"What skills did you extract from my CV?"
"Does my resume match ML internship requirements?"
"What's missing from my resume for this role?"
```

Or upload via the API:
```bash
curl -X POST http://localhost:8000/api/profile/upload \
  -F "user_id=YOUR_USER_ID" \
  -F "file=@resume.pdf"
```

Mitra extracts skills, experience level, education, and builds a structured profile that all other agents use.

---

## Memory

Mitra remembers your previous conversations. Each session is stored as an episodic memory in pgvector. When you ask a follow-up question, relevant memories are retrieved and injected as context — so you don't have to repeat yourself.

```
Session 1:  "I'm targeting Sarvam AI and Krutrim for ML internships"
Session 2:  "How's my preparation going?"
             → Mitra recalls the target companies from session 1
```

Memory context is retrieved by semantic similarity to your current message. It's automatic — nothing to configure.

---

## Tips for best results

**Be specific about the role.** "ML internship" is good. "NLP research intern at a Series B startup in Bengaluru" is better — the opportunity hunter and gap detector use the full detail.

**Upload your resume before asking about gaps or roadmaps.** Without it, Mitra uses your stated goal only, which gives generic results.

**Combine intents in one message.** "Find me ML internships and tell me what I'm missing" triggers opportunity hunter + gap detector + roadmap planner in a single call.

**Use natural language for application tracking.** "I just interviewed at Google and it went okay, status pending" works. You don't need to know the API schema.

**Refer back to earlier context.** Mitra reads episodic memory, so "those internships you found last time" or "the gap analysis from yesterday" will work if the memory is recent.

---

## API quick reference

```
# Users
POST   /api/users
GET    /api/users/{id}
PATCH  /api/users/{id}

# Profile / Resume
POST   /api/profile/upload
GET    /api/profile/{user_id}

# Chat
POST   /api/chat
POST   /api/chat/stream

# Opportunities
GET    /api/opportunities
POST   /api/opportunities/search
POST   /api/opportunities

# Application tracker
GET    /api/tracker/{user_id}
POST   /api/tracker?user_id=...
PATCH  /api/tracker/{app_id}
DELETE /api/tracker/{app_id}
```

Full interactive docs: `http://localhost:8000/docs`

---

## Common problems

**"No skill profile found"** — Upload a resume first with `POST /api/profile/upload`. Gap analysis and roadmap quality depend on it.

**Slow first response** — The embedding model loads on first request (~2–3 s). Subsequent requests are fast.

**Intent routed incorrectly** — Rephrase. "Show me opportunities" is clearer than "What's out there?". If `USE_LOCAL_CLASSIFIER=true`, the fine-tuned model may need retraining if your queries are unusual.

**Empty opportunity results** — Run `python -m db.seed_opportunities` from `backend/`. The database needs seeding on first setup.

**Streaming cuts off** — The SSE connection has a default timeout. For long agent chains (opportunity + gap + roadmap), use the non-streaming endpoint or increase your client timeout.
