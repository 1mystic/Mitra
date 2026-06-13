"""
Synthetic data generator for Mitra's fine-tuning pipeline.

Two modes:
  python generate_synthetic_data.py                → ml/data/training_pairs.jsonl
  python generate_synthetic_data.py --mode skillgap → ml/data/skill_gap_dataset.jsonl

training_pairs.jsonl format (used by train_skill_gap_classifier.py + distill_intent.py):
  {"input": "<user query>", "output": "<intent_label>", "intent": "<intent_label>"}

skill_gap_dataset.jsonl format (used for rich skill-gap analysis training):
  {"input": "<student_bg + jd>", "output": {missing_skills, match_score, ...}}
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
from pathlib import Path

import anthropic
from dotenv import load_dotenv

# Support running from both ml/ and project root
_backend_env = Path(__file__).parent.parent / "backend" / ".env"
load_dotenv(_backend_env if _backend_env.exists() else Path(".env"))

client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ── Intent classification data ────────────────────────────────────────────────

# Labels must match graph.py conditional edges exactly
INTENTS: dict[str, str] = {
    "opportunities": (
        "finding internships, jobs, hackathons, research fellowships, open positions — "
        "user wants to discover or search for career opportunities"
    ),
    "resume": (
        "uploading, analyzing, or improving a resume/CV — extracting skills from it, "
        "asking what the resume says or getting feedback on it"
    ),
    "gaps": (
        "identifying skill gaps, comparing current skills to job requirements, "
        "asking what skills are missing for a target role"
    ),
    "roadmap": (
        "asking for a learning plan, study roadmap, what courses to take, "
        "how to prepare over weeks/months for a role or skill area"
    ),
    "track": (
        "tracking, updating, or reviewing job/internship applications — "
        "application status, history, follow-ups"
    ),
    "interview": (
        "interview preparation, practice questions, mock interviews, "
        "tips for specific companies or roles"
    ),
    "general": (
        "general career advice, questions about the field, salary, PhDs, "
        "comparisons between options — does not clearly fit any other intent"
    ),
}

N_PER_INTENT = 75  # 7 intents × 75 ≈ 525 → trim to 500


async def generate_intent_queries(intent: str, description: str, n: int) -> list[dict]:
    prompt = f"""Generate exactly {n} diverse, realistic messages that an ML/AI student in India would send to a career AI assistant.

These messages must clearly belong to the intent: "{intent}"
Intent description: {description}

Requirements:
- Vary phrasing, length (3-25 words), and specificity
- Mix question forms: questions ("Can you..."), commands ("Find me..."), statements ("I want to...")
- Include Indian context naturally: IITs, NITs, Bangalore, Hyderabad, Flipkart, Sarvam AI, Krutrim, etc.
- Some messages should mention specific technologies: PyTorch, LangChain, RAG, fine-tuning, etc.
- Keep them grounded — these are real things students would actually type

Return a JSON array of exactly {n} strings. No markdown, no explanation, just the array:
["message 1", "message 2", ...]"""

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        queries = json.loads(text)
        if not isinstance(queries, list):
            return []
        return [
            {"input": q.strip(), "output": intent, "intent": intent}
            for q in queries
            if isinstance(q, str) and q.strip()
        ]
    except Exception as e:
        print(f"  ✗ intent={intent}: {e}")
        return []


async def main_intent(n_samples: int = 500) -> None:
    output_path = Path(__file__).parent / "data" / "training_pairs.jsonl"
    output_path.parent.mkdir(exist_ok=True)

    print(f"Generating intent classification training data ({n_samples} examples)…")
    tasks = [
        generate_intent_queries(intent, desc, N_PER_INTENT)
        for intent, desc in INTENTS.items()
    ]
    results = await asyncio.gather(*tasks)

    all_records: list[dict] = []
    for records in results:
        all_records.extend(records)

    random.shuffle(all_records)
    all_records = all_records[:n_samples]

    with open(output_path, "w", encoding="utf-8") as f:
        for record in all_records:
            f.write(json.dumps(record) + "\n")

    print(f"\nSaved {len(all_records)} records → {output_path}")
    from collections import Counter
    dist = Counter(r["intent"] for r in all_records)
    for intent in INTENTS:
        print(f"  {intent:20s}: {dist.get(intent, 0)}")


# ── Skill-gap analysis data ───────────────────────────────────────────────────

ROLES = [
    "Machine Learning Intern at Sarvam AI",
    "MLOps Engineer Intern at Fractal",
    "NLP Research Intern at IIT Madras",
    "Computer Vision Intern at Ather Energy",
    "Data Science Intern at Tiger Analytics",
    "Agentic AI Intern at yellow.ai",
    "Recommender Systems Intern at Meesho",
    "AI Research Intern at Krutrim",
    "Generative AI Intern at Quantiphi",
    "ML Platform Intern at Flipkart",
]

STUDENT_PROFILES = [
    "3rd year B.Tech CSE student at BITS Pilani. Knows Python, NumPy, basic sklearn. Built a sentiment analysis model for Twitter. No production ML experience.",
    "2nd year M.Tech Data Science at IIT Bombay. Strong in statistics and R. Limited Python. Has done 2 Kaggle competitions. No LLM experience.",
    "Final year B.Tech at VIT. Built a RAG chatbot with LangChain. Knows FastAPI, pgvector, sentence-transformers. Limited MLOps knowledge.",
    "3rd year BSc Statistics at Delhi University. Excellent math. Python intermediate. No deep learning experience. Strong SQL.",
    "Final year B.Tech AI at IITM. Experience with PyTorch, transformers, fine-tuning LLaMA. Good CUDA knowledge. Limited frontend/deployment.",
    "2nd year MCA. Knows Python and scikit-learn. Built a movie recommendation system with collaborative filtering. No cloud or MLOps experience.",
    "1st year MS CS at IIIT Hyderabad. Research background in NLP. Good with HuggingFace. Published one workshop paper. No industry experience.",
]


async def generate_skill_gap_pair(student: str, role: str) -> dict | None:
    prompt = f"""You are a senior ML engineer evaluating a student's fit for a role.

Student background:
{student}

Target role: {role}

Analyze the skill gap and return JSON only (no markdown):
{{
  "resume_summary": "2-3 sentence summary of the student",
  "job_description": "3-4 sentence description of the role and its requirements",
  "missing_skills": [
    {{"skill": "PyTorch", "priority": 1, "hours": 40, "reason": "core framework not mentioned"}},
    {{"skill": "Docker", "priority": 2, "hours": 8, "reason": "needed for deployment"}}
  ],
  "present_skills": ["Python", "Scikit-learn"],
  "match_score": 0.45,
  "reasoning": "2 sentence explanation of the score"
}}

Be realistic and specific. Missing skills should be actionable."""

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        data = json.loads(text)
        return {
            "input": (
                f"STUDENT BACKGROUND:\n{data['resume_summary']}\n\n"
                f"JOB DESCRIPTION:\n{data['job_description']}"
            ),
            "output": {
                "missing_skills": data["missing_skills"],
                "present_skills": data["present_skills"],
                "match_score": data["match_score"],
                "reasoning": data["reasoning"],
            },
        }
    except Exception as e:
        print(f"  ✗ {e}")
        return None


async def main_skillgap(n_samples: int = 500) -> None:
    output_path = Path(__file__).parent / "data" / "skill_gap_dataset.jsonl"
    output_path.parent.mkdir(exist_ok=True)

    print(f"Generating skill-gap analysis training data ({n_samples} examples)…")
    pairs = [
        (random.choice(STUDENT_PROFILES), random.choice(ROLES))
        for _ in range(n_samples)
    ]

    results: list[dict] = []
    batch_size = 10
    for i in range(0, len(pairs), batch_size):
        batch = pairs[i : i + batch_size]
        tasks = [generate_skill_gap_pair(s, r) for s, r in batch]
        outputs = await asyncio.gather(*tasks)
        valid = [o for o in outputs if o is not None]
        results.extend(valid)
        print(f"  Progress: {len(results)}/{n_samples}")
        await asyncio.sleep(0.5)

    with open(output_path, "w", encoding="utf-8") as f:
        for record in results:
            f.write(json.dumps(record) + "\n")

    print(f"\nSaved {len(results)} records → {output_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Mitra fine-tuning datasets")
    parser.add_argument(
        "--mode",
        choices=["intent", "skillgap"],
        default="intent",
        help="intent → training_pairs.jsonl (default); skillgap → skill_gap_dataset.jsonl",
    )
    parser.add_argument("--n", type=int, default=500, help="Number of samples to generate")
    args = parser.parse_args()

    if args.mode == "intent":
        asyncio.run(main_intent(args.n))
    else:
        asyncio.run(main_skillgap(args.n))
