"""Extract and compare skill graphs from text using Claude.

Matching pipeline (in order):
  1. Taxonomy normalisation — aliases/abbreviations → canonical names
  2. Exact canonical match
  3. Substring containment (bidirectional)
  4. Fuzzy match via difflib.SequenceMatcher (ratio >= 0.82)

Scoring uses tier-weighted arithmetic so must-have skills (Python, PyTorch …)
carry 2x weight and important skills carry 1.5x weight, giving a score that
reflects true job-readiness rather than a naive percentage of skills matched.
"""
from __future__ import annotations

import difflib
from typing import Optional

from . import llm_client


# ── Taxonomy ──────────────────────────────────────────────────────────────────
# Maps lowercased aliases → canonical display names.
# Keys cover abbreviations, regional spellings, package names, and typos.

SKILL_TAXONOMY: dict[str, str] = {
    # Python
    "python3": "Python", "python 3": "Python", "py": "Python",
    # ML frameworks
    "pytorch": "PyTorch", "torch": "PyTorch",
    "tensorflow": "TensorFlow", "tf": "TensorFlow",
    "keras": "Keras",
    "sklearn": "scikit-learn", "scikit learn": "scikit-learn",
    "sk-learn": "scikit-learn", "scikit_learn": "scikit-learn",
    "xgboost": "XGBoost", "lgbm": "LightGBM", "lightgbm": "LightGBM",
    # ML / AI domains
    "ml": "Machine Learning", "machine learning": "Machine Learning",
    "dl": "Deep Learning", "deep learning": "Deep Learning",
    "nlp": "Natural Language Processing",
    "natural language processing": "Natural Language Processing",
    "cv": "Computer Vision", "computer vision": "Computer Vision",
    "rl": "Reinforcement Learning", "reinforcement learning": "Reinforcement Learning",
    "llm": "LLMs", "llms": "LLMs", "large language models": "LLMs",
    "genai": "Generative AI", "generative ai": "Generative AI", "gen ai": "Generative AI",
    "diffusion models": "Diffusion Models",
    "gans": "GANs", "generative adversarial": "GANs",
    "rag": "RAG", "retrieval augmented generation": "RAG",
    "retrieval-augmented generation": "RAG",
    "vector db": "Vector Databases", "vectordb": "Vector Databases",
    "vector database": "Vector Databases",
    # Data
    "pandas": "Pandas", "numpy": "NumPy", "np": "NumPy",
    "matplotlib": "Matplotlib", "seaborn": "Seaborn", "plotly": "Plotly",
    "sql": "SQL", "mysql": "SQL", "postgresql": "SQL", "postgres": "SQL",
    "nosql": "NoSQL", "mongodb": "MongoDB",
    "spark": "Apache Spark", "pyspark": "Apache Spark",
    "hadoop": "Hadoop",
    # Tools & infra
    "git": "Git", "github": "Git", "version control": "Git",
    "docker": "Docker", "containerisation": "Docker", "containerization": "Docker",
    "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "aws": "AWS", "amazon web services": "AWS",
    "gcp": "GCP", "google cloud": "GCP", "google cloud platform": "GCP",
    "azure": "Azure", "microsoft azure": "Azure",
    "ci/cd": "CI/CD", "cicd": "CI/CD", "github actions": "CI/CD",
    # Web / APIs
    "fastapi": "FastAPI", "flask": "Flask", "django": "Django",
    "rest": "REST APIs", "rest api": "REST APIs", "restful": "REST APIs",
    "graphql": "GraphQL",
    # HuggingFace
    "hf": "Hugging Face", "huggingface": "Hugging Face",
    "transformers": "Hugging Face Transformers",
    "hugging face transformers": "Hugging Face Transformers",
    # Orchestration / agents
    "langchain": "LangChain", "langgraph": "LangGraph",
    "llamaindex": "LlamaIndex", "llama index": "LlamaIndex",
    # Fine-tuning
    "lora": "LoRA", "qlora": "QLoRA",
    "peft": "PEFT", "finetuning": "Fine-tuning", "fine tuning": "Fine-tuning",
    # Research
    "arxiv": "Research Papers", "paper reading": "Research Papers",
}


# ── Skill tiers ───────────────────────────────────────────────────────────────
# Tier 1 = must-have (weight 2.0)
# Tier 2 = important (weight 1.5)
# Tier 3 = nice-to-have (weight 1.0)

_TIER_1: frozenset[str] = frozenset({
    "Python", "Machine Learning", "Deep Learning",
    "PyTorch", "TensorFlow", "SQL", "Git",
    "Natural Language Processing", "Computer Vision", "LLMs",
})
_TIER_2: frozenset[str] = frozenset({
    "scikit-learn", "Pandas", "NumPy", "FastAPI", "Flask", "Docker",
    "REST APIs", "Keras", "RAG", "Hugging Face", "Hugging Face Transformers",
    "Generative AI", "LangChain", "LangGraph", "XGBoost", "Apache Spark",
    "Fine-tuning", "PEFT",
})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize(skill: str) -> str:
    """Map a skill alias to its canonical display name."""
    return SKILL_TAXONOMY.get(skill.strip().lower(), skill.strip())


def _tier_weight(canonical: str) -> float:
    if canonical in _TIER_1:
        return 2.0
    if canonical in _TIER_2:
        return 1.5
    return 1.0


def _tier_num(skill: str) -> int:
    canon = _normalize(skill)
    if canon in _TIER_1:
        return 1
    if canon in _TIER_2:
        return 2
    return 3


def _find_match(
    candidate_lower: dict[str, str],
    required_canonical: str,
) -> Optional[str]:
    """Try exact → substring → fuzzy matching.

    candidate_lower: {lowercase_canonical → original_canonical}
    Returns the matched canonical name, or None.
    """
    req_lower = required_canonical.lower()

    # 1. Exact
    if req_lower in candidate_lower:
        return candidate_lower[req_lower]

    # 2. Substring (bidirectional)
    for cand_lower, cand_orig in candidate_lower.items():
        if req_lower in cand_lower or cand_lower in req_lower:
            return cand_orig

    # 3. Fuzzy
    best_ratio, best = 0.0, None
    for cand_lower, cand_orig in candidate_lower.items():
        ratio = difflib.SequenceMatcher(None, req_lower, cand_lower).ratio()
        if ratio > best_ratio:
            best_ratio, best = ratio, cand_orig
    if best_ratio >= 0.82:
        return best

    return None


# ── LLM prompts ───────────────────────────────────────────────────────────────

_EXTRACT_SYSTEM = """You are a technical recruiter AI. Extract skills from text precisely.
Return valid JSON only, no markdown fences."""

_EXTRACT_PROMPT = """Extract all technical skills mentioned in this text.
For each skill, estimate proficiency on a scale 0.0 (mentioned/basic) to 1.0 (expert).

Return JSON in this exact format:
{{
  "skills": {{"Python": 0.9, "PyTorch": 0.7, "SQL": 0.6}},
  "projects": [
    {{"name": "Project Name", "description": "one-line description", "skills": ["Python", "FastAPI"]}}
  ],
  "experience_summary": "2-3 sentence summary of the person's background"
}}

Text to analyze:
{text}"""


# ── Public API ────────────────────────────────────────────────────────────────

async def extract_from_text(text: str) -> dict:
    """Use Claude to extract a structured skill profile from free-form text."""
    prompt = _EXTRACT_PROMPT.format(text=text[:4000])
    result = await llm_client.complete_json(prompt, system=_EXTRACT_SYSTEM)
    # Normalise extracted names through taxonomy
    raw_skills: dict = result.get("skills", {})
    skills = {_normalize(k): v for k, v in raw_skills.items()}
    return {
        "skills": skills,
        "projects": result.get("projects", []),
        "experience_summary": result.get("experience_summary", ""),
    }


async def compute_match(
    candidate_skills: dict[str, float],
    required_skills: list[str],
) -> tuple[float, list[str], list[dict]]:
    """Compare candidate skills against job requirements.

    Matching order: taxonomy normalisation → exact → substring → fuzzy.
    Score is tier-weighted so must-have skills (Python, PyTorch …) count 2x.

    Returns:
        match_score  — 0.0–1.0 weighted score
        present      — canonical names of matched skills
        missing      — [{skill, priority, hours, reason, tier}] sorted by priority
    """
    if not required_skills:
        return 1.0, list(candidate_skills.keys()), []

    # Normalise both sides through taxonomy
    norm_required = [_normalize(s) for s in required_skills]
    norm_candidate = {_normalize(k): v for k, v in candidate_skills.items()}
    candidate_lower = {k.lower(): k for k in norm_candidate}

    present: list[str] = []
    missing_raw: list[str] = []
    total_weight = 0.0
    matched_weight = 0.0

    for req in norm_required:
        w = _tier_weight(req)
        total_weight += w
        if _find_match(candidate_lower, req):
            present.append(req)
            matched_weight += w
        else:
            missing_raw.append(req)

    match_score = round(matched_weight / total_weight, 2) if total_weight > 0 else 1.0

    if missing_raw:
        prompt = f"""Given these missing skills for a job application, rank them by importance and estimate learning hours.

Missing skills: {missing_raw}
Job requires: {norm_required}
Candidate has: {list(norm_candidate.keys())}

Return JSON array (most important first):
[
  {{"skill": "PyTorch", "priority": 1, "hours": 30, "reason": "core ML framework required", "tier": 1}},
  {{"skill": "GCP", "priority": 2, "hours": 10, "reason": "cloud deployment mentioned", "tier": 3}}
]"""
        missing: list[dict] = await llm_client.complete_json(prompt)
        if not isinstance(missing, list):
            missing = [
                {
                    "skill": s,
                    "priority": i + 1,
                    "hours": 20,
                    "reason": "required for role",
                    "tier": _tier_num(s),
                }
                for i, s in enumerate(missing_raw)
            ]
    else:
        missing = []

    return match_score, present, missing
