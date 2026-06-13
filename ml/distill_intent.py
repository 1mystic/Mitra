"""
distill_intent.py — Local intent classifier using the fine-tuned Qwen2.5-3B checkpoint.

Replaces Claude's classify_intent() for fast, cheap intent routing.
Enable in backend/.env: USE_LOCAL_CLASSIFIER=true

Integration path (backend imports this module):
    # In backend/app/services/llm_client.py:
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent.parent / "ml"))
    from distill_intent import classify_intent as _local_classify

The model loads lazily on first call (~4 s on CPU, ~0.5 s on GPU) and is
kept in memory as a process-level singleton. Inference is synchronous;
the async wrapper in llm_client.py runs it in a thread-pool executor.

Standalone usage:
    python distill_intent.py "Find me ML internships in Bangalore"
    python distill_intent.py --checkpoint /path/to/adapter "What skills am I missing?"
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────

# Default checkpoint path (relative to this file's directory)
_DEFAULT_CHECKPOINT = Path(__file__).parent / "checkpoints" / "intent-classifier" / "final"

# Env-override: LOCAL_CLASSIFIER_PATH=/absolute/path/to/adapter
_CHECKPOINT_FROM_ENV = os.environ.get("LOCAL_CLASSIFIER_PATH", "")

VALID_INTENTS = frozenset(
    ["opportunities", "resume", "gaps", "roadmap", "track", "interview", "general"]
)

SYSTEM_PROMPT = (
    "You are an intent classifier for a career assistant. "
    "Given a user message, respond with exactly one intent label from: "
    "opportunities, resume, gaps, roadmap, track, interview, general. "
    "Output only the label — no explanation, no punctuation."
)

# ── Lazy singleton ─────────────────────────────────────────────────────────────

_model = None
_tokenizer = None
_device = None
_lock = threading.Lock()


def _load_model(checkpoint: str | Path) -> None:
    global _model, _tokenizer, _device

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    checkpoint = Path(checkpoint)
    if not checkpoint.exists():
        raise FileNotFoundError(
            f"Classifier checkpoint not found: {checkpoint}\n"
            "Run ml/train_skill_gap_classifier.py first, or set "
            "LOCAL_CLASSIFIER_PATH= to the correct path."
        )

    _device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if _device == "cuda" else torch.float32

    # The checkpoint directory contains both the LoRA adapter config
    # and the tokenizer files saved by trainer.save_model().
    # The adapter's base_model_name_or_path tells us the base model id.
    _tokenizer = AutoTokenizer.from_pretrained(str(checkpoint), trust_remote_code=True)
    _tokenizer.pad_token = _tokenizer.eos_token

    base_model_id = _read_base_model_id(checkpoint)
    base = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        device_map="auto" if _device == "cuda" else None,
        torch_dtype=dtype,
        trust_remote_code=True,
    )
    _model = PeftModel.from_pretrained(base, str(checkpoint))
    if _device == "cpu":
        _model = _model.to("cpu")
    _model.eval()


def _read_base_model_id(checkpoint: Path) -> str:
    """Read base_model_name_or_path from adapter_config.json."""
    import json
    adapter_config = checkpoint / "adapter_config.json"
    if adapter_config.exists():
        with open(adapter_config) as f:
            return json.load(f).get("base_model_name_or_path", "Qwen/Qwen2.5-3B-Instruct")
    return "Qwen/Qwen2.5-3B-Instruct"


def _ensure_loaded(checkpoint: str | Path | None = None) -> None:
    global _model
    if _model is not None:
        return
    with _lock:
        if _model is not None:
            return
        ckpt = (
            checkpoint
            or _CHECKPOINT_FROM_ENV
            or _DEFAULT_CHECKPOINT
        )
        _load_model(ckpt)


# ── Inference ─────────────────────────────────────────────────────────────────


def classify_intent(
    query: str,
    checkpoint: str | Path | None = None,
) -> str:
    """
    Classify a user career query into one of 7 intent labels.

    Returns one of: opportunities | resume | gaps | roadmap | track | interview | general

    Falls back to "general" if the model output is not a valid label.
    This function is synchronous; call from async code with run_in_executor.
    """
    import torch

    _ensure_loaded(checkpoint)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query.strip()},
    ]
    text = _tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = _tokenizer(text, return_tensors="pt")
    inputs = {k: v.to(_model.device) for k, v in inputs.items()}

    with torch.no_grad():
        output_ids = _model.generate(
            **inputs,
            max_new_tokens=8,       # intent label is at most 2 tokens
            do_sample=False,        # greedy — classification needs determinism
            pad_token_id=_tokenizer.eos_token_id,
        )

    new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
    label = _tokenizer.decode(new_tokens, skip_special_tokens=True).strip().lower()

    # Normalise: take first word in case model outputs extra text
    label = label.split()[0] if label else "general"
    return label if label in VALID_INTENTS else "general"


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Classify career query intent")
    parser.add_argument("query", nargs="?", help="User message to classify")
    parser.add_argument("--checkpoint", default=None, help="Path to LoRA adapter directory")
    parser.add_argument("--batch", action="store_true", help="Read queries from stdin, one per line")
    args = parser.parse_args()

    if args.batch:
        queries = [line.strip() for line in sys.stdin if line.strip()]
    elif args.query:
        queries = [args.query]
    else:
        # Interactive demo
        queries = [
            "Find me ML internships in Bangalore",
            "What skills am I missing for this NLP role?",
            "Give me a 3-month roadmap to learn PyTorch",
            "I want to practice system design interviews",
            "Update my Google application status to interviewed",
            "Analyze my resume and tell me what stands out",
            "Should I do an MS or go for a startup?",
        ]

    print("Loading model…")
    _ensure_loaded(args.checkpoint)
    print("Model ready.\n")

    for q in queries:
        label = classify_intent(q, checkpoint=args.checkpoint)
        print(f"  [{label:12s}]  {q}")
