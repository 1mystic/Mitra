"""
Mitra Skill Gap Classifier — Kaggle/Unsloth Training Script

Optimised for Kaggle T4 GPU (free, 30h/week).
Unsloth is 2x faster than vanilla PEFT and uses 40% less VRAM.

Setup in Kaggle notebook:
    1. Settings → Accelerator → GPU T4 x2
    2. Settings → Internet → On
    3. Settings → Secrets → add ANTHROPIC_API_KEY and HF_TOKEN

Install in first cell:
    !pip install unsloth
    !pip install datasets trl

Run order:
    Option A: Upload ml/data/skill_gap_dataset.jsonl as a Kaggle Dataset,
              then set DATA_PATH below.
    Option B: Run generate_synthetic_data.py first (needs ANTHROPIC_API_KEY secret).

After training, model is saved to /kaggle/working/ and optionally pushed to HuggingFace Hub.
"""

import json
import os
from pathlib import Path

from datasets import Dataset
from trl import SFTTrainer, TrainingArguments
from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template

# ── Config ────────────────────────────────────────────────────────────────────

MODEL_ID    = "unsloth/Qwen2.5-3B-Instruct-bnb-4bit"   # pre-quantised — no download overhead
MAX_SEQ_LEN = 2048
DATA_PATH   = "/kaggle/input/mitra-skill-gap-data/skill_gap_dataset.jsonl"  # adjust to your dataset path
OUTPUT_DIR  = "/kaggle/working/mitra-skill-gap-classifier"
HF_REPO     = "your-hf-username/mitra-skill-gap-classifier"  # set this to push to Hub

SYSTEM_PROMPT = (
    "You are a skill gap analyzer. Given a student background and a job description, "
    "output JSON with missing_skills (prioritized), present_skills, match_score, and reasoning."
)

# ── Load model with Unsloth ───────────────────────────────────────────────────

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_ID,
    max_seq_length=MAX_SEQ_LEN,
    dtype=None,           # auto-detect: bf16 on A100/H100, fp16 on T4
    load_in_4bit=True,    # QLoRA
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=32,
    lora_dropout=0.05,
    bias="none",
    use_gradient_checkpointing="unsloth",   # 30% less VRAM vs standard checkpointing
    random_state=42,
)

tokenizer = get_chat_template(tokenizer, chat_template="chatml")

print(f"Trainable params: {model.print_trainable_parameters()}")

# ── Dataset ───────────────────────────────────────────────────────────────────

def format_record(record: dict) -> dict:
    messages = [
        {"role": "system",    "content": SYSTEM_PROMPT},
        {"role": "user",      "content": record["input"]},
        {"role": "assistant", "content": json.dumps(record["output"], indent=2)},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    return {"text": text}


raw = []
with open(DATA_PATH) as f:
    for line in f:
        raw.append(json.loads(line))

ds = Dataset.from_list([format_record(r) for r in raw])
split = ds.train_test_split(test_size=0.1, seed=42)
print(f"Train: {len(split['train'])}  |  Eval: {len(split['test'])}")

# ── Training ──────────────────────────────────────────────────────────────────

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=split["train"],
    eval_dataset=split["test"],
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LEN,
    dataset_num_proc=2,
    packing=False,
    args=TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=3,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        warmup_ratio=0.03,
        learning_rate=2e-4,
        fp16=True,          # T4 does not support bf16
        logging_steps=10,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        optim="adamw_8bit",  # Unsloth's 8-bit AdamW — saves ~300MB VRAM
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        report_to="none",
        seed=42,
    ),
)

trainer_stats = trainer.train()
print(f"\nTraining complete. Time: {trainer_stats.metrics['train_runtime']:.0f}s")

# ── Save ──────────────────────────────────────────────────────────────────────

# Save LoRA adapter only (small — ~30MB)
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print(f"Adapter saved to {OUTPUT_DIR}")

# Merge adapter into base model and save (larger — ~6GB, needed for standalone serving)
model.save_pretrained_merged(
    OUTPUT_DIR + "-merged",
    tokenizer,
    save_method="merged_16bit",
)
print(f"Merged model saved to {OUTPUT_DIR}-merged")

# ── Push to HuggingFace Hub (optional) ───────────────────────────────────────
# Requires HF_TOKEN Kaggle secret

hf_token = os.environ.get("HF_TOKEN", "")
if hf_token:
    model.push_to_hub_merged(
        HF_REPO,
        tokenizer,
        save_method="lora",   # push adapter only
        token=hf_token,
    )
    print(f"Pushed to HuggingFace Hub: {HF_REPO}")
else:
    print("HF_TOKEN not set — skipping Hub push. Download from Kaggle output panel.")

# ── Quick inference test ──────────────────────────────────────────────────────

FastLanguageModel.for_inference(model)

test_input = """STUDENT BACKGROUND:
Final year B.Tech CSE at NIT. Knows Python well, built a sentiment classifier with scikit-learn. No experience with deep learning or LLMs.

JOB DESCRIPTION:
ML Intern at Sarvam AI. Will work on fine-tuning LLMs for Indian languages. Requires PyTorch, HuggingFace transformers, and experience with training pipelines."""

messages = [
    {"role": "system",  "content": SYSTEM_PROMPT},
    {"role": "user",    "content": test_input},
]
inputs = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt").to("cuda")

outputs = model.generate(input_ids=inputs, max_new_tokens=512, temperature=0.1, do_sample=True)
response = tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True)
print("\n─── Test inference ───")
print(response)
