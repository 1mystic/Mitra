"""
QLoRA fine-tuning of Qwen2.5-3B-Instruct for intent classification.

Teacher: Claude (data generation via generate_synthetic_data.py)
Student: Qwen/Qwen2.5-3B-Instruct fine-tuned to classify 7 career intents
Method: QLoRA via PEFT + TRL SFTTrainer

Designed for Google Colab T4 (free tier). Copy-paste into a Colab cell and run.

──────────────────────────────────────────────────────────────
COLAB SETUP (run in the first cell):
  !pip install -q "transformers>=4.45" "peft>=0.13" "trl>=0.12" \
      "bitsandbytes>=0.43" "datasets>=2.19" "accelerate>=0.30"
  # Then upload ml/data/training_pairs.jsonl to Colab Files and adjust DATA_PATH
──────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import json
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from trl import SFTTrainer

# ── Config ────────────────────────────────────────────────────────────────────

MODEL_ID   = "Qwen/Qwen2.5-3B-Instruct"
DATA_PATH  = Path(__file__).parent / "data" / "training_pairs.jsonl"
OUTPUT_DIR = Path(__file__).parent / "checkpoints" / "intent-classifier"

# When running on Colab, override these paths:
# DATA_PATH  = Path("/content/training_pairs.jsonl")
# OUTPUT_DIR = Path("/content/mitra-intent-classifier")

INTENTS = ["opportunities", "resume", "gaps", "roadmap", "track", "interview", "general"]

SYSTEM_PROMPT = (
    "You are an intent classifier for a career assistant. "
    "Given a user message, respond with exactly one intent label from: "
    + ", ".join(INTENTS)
    + ". Output only the label — no explanation, no punctuation."
)

# ── Dataset ───────────────────────────────────────────────────────────────────


def load_dataset() -> dict[str, Dataset]:
    """Load training_pairs.jsonl and format as chat-template text for SFT."""
    records = []
    with open(DATA_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            # Qwen2.5 ChatML format
            text = (
                f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"
                f"<|im_start|>user\n{rec['input']}<|im_end|>\n"
                f"<|im_start|>assistant\n{rec['output']}<|im_end|>"
            )
            records.append({"text": text})

    if not records:
        raise RuntimeError(f"No records found in {DATA_PATH}. Run generate_synthetic_data.py first.")

    ds = Dataset.from_list(records)
    split = ds.train_test_split(test_size=0.1, seed=42)
    print(f"Dataset: {len(split['train'])} train | {len(split['test'])} eval")
    return split


# ── Model + tokenizer ─────────────────────────────────────────────────────────


def setup_model_and_tokenizer():
    # T4 supports fp16 but not bf16; A100/H100 support bf16
    use_bf16 = torch.cuda.is_bf16_supported() if torch.cuda.is_available() else False

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16 if use_bf16 else torch.float16,
    )

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    return model, tokenizer, use_bf16


# ── Training ──────────────────────────────────────────────────────────────────


def train() -> None:
    dataset = load_dataset()
    model, tokenizer, use_bf16 = setup_model_and_tokenizer()

    # eval_strategy is the current name (evaluation_strategy deprecated in transformers ≥4.45)
    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=3,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        fp16=not use_bf16,
        bf16=use_bf16,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        logging_steps=10,
        eval_strategy="epoch",       # replaces deprecated evaluation_strategy
        save_strategy="epoch",
        load_best_model_at_end=True,
        optim="paged_adamw_8bit",    # saves ~300 MB VRAM vs adamw
        weight_decay=0.01,
        report_to="none",
        seed=42,
    )

    # trl ≥0.9 uses processing_class; older trl uses tokenizer — handle both
    try:
        trainer = SFTTrainer(
            model=model,
            args=training_args,
            train_dataset=dataset["train"],
            eval_dataset=dataset["test"],
            processing_class=tokenizer,
            dataset_text_field="text",
            max_seq_length=256,   # intent labels are short — 256 is sufficient
            packing=False,
        )
    except TypeError:
        # Fallback for trl <0.9
        trainer = SFTTrainer(
            model=model,
            args=training_args,
            train_dataset=dataset["train"],
            eval_dataset=dataset["test"],
            tokenizer=tokenizer,
            dataset_text_field="text",
            max_seq_length=256,
            packing=False,
        )

    trainer.train()

    final_dir = OUTPUT_DIR / "final"
    trainer.save_model(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))
    print(f"\nAdapter saved to {final_dir}")
    print("Upload this directory to Google Drive or HuggingFace Hub for use with distill_intent.py")


# ── Quick sanity check (run after training) ───────────────────────────────────


def test_inference(checkpoint_dir: str | None = None) -> None:
    """Smoke-test the saved adapter against a few known queries."""
    from peft import PeftModel

    ckpt = checkpoint_dir or str(OUTPUT_DIR / "final")
    tokenizer = AutoTokenizer.from_pretrained(ckpt, trust_remote_code=True)

    base = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, device_map="auto", trust_remote_code=True,
        torch_dtype=torch.float16,
    )
    model = PeftModel.from_pretrained(base, ckpt)
    model.eval()

    test_cases = [
        ("Find me ML internships in Bangalore", "opportunities"),
        ("What skills am I missing for this role?", "gaps"),
        ("Give me a 3-month learning roadmap for NLP", "roadmap"),
        ("I want to practice coding interview questions", "interview"),
        ("Track my application to Google STEP", "track"),
    ]

    print("\n─── Inference smoke-test ───")
    for query, expected in test_cases:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=8, do_sample=False)
        label = tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        status = "✓" if label == expected else "✗"
        print(f"  {status} [{expected:12s}] got='{label}'  query='{query[:50]}'")


if __name__ == "__main__":
    train()
