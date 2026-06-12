"""
Synthetic data generator for the Skill Gap Classifier fine-tuning dataset.

Uses Claude as the teacher model to generate (resume, JD) → skill_gaps pairs.

Output: ml/data/skill_gap_dataset.jsonl

Each record:
{
  "input": "<resume_summary>\n<job_description>",
  "output": {
    "missing_skills": [{"skill": "...", "priority": 1, "hours": 30}],
    "match_score": 0.62,
    "reasoning": "..."
  }
}
"""
from __future__ import annotations

import asyncio
import json
import os
import random
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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


async def generate_one(student: str, role: str) -> dict | None:
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
            "input": f"STUDENT BACKGROUND:\n{data['resume_summary']}\n\nJOB DESCRIPTION:\n{data['job_description']}",
            "output": {
                "missing_skills": data["missing_skills"],
                "present_skills": data["present_skills"],
                "match_score": data["match_score"],
                "reasoning": data["reasoning"],
            },
        }
    except Exception as e:
        print(f"Failed: {e}")
        return None


async def main(n_samples: int = 500):
    output_path = Path(__file__).parent / "data" / "skill_gap_dataset.jsonl"
    output_path.parent.mkdir(exist_ok=True)

    pairs = [
        (random.choice(STUDENT_PROFILES), random.choice(ROLES))
        for _ in range(n_samples)
    ]

    results = []
    batch_size = 10
    for i in range(0, len(pairs), batch_size):
        batch = pairs[i : i + batch_size]
        tasks = [generate_one(s, r) for s, r in batch]
        outputs = await asyncio.gather(*tasks)
        valid = [o for o in outputs if o is not None]
        results.extend(valid)
        print(f"Progress: {len(results)}/{n_samples}")
        await asyncio.sleep(1)  # Rate limit buffer

    with open(output_path, "w") as f:
        for record in results:
            f.write(json.dumps(record) + "\n")

    print(f"\nDone. Saved {len(results)} records to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
