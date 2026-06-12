"""
QLoRA fine-tuning of Qwen2.5-3B-Instruct for Skill Gap Classification.

Teacher: Claude (data generation in generate_synthetic_data.py)
Student: Qwen2.5-3B-Instruct
Method: QLoRA via PEFT + TRL SFTTrainer

For fastest training, run in Google Colab with T4 GPU.
Optional: install Unsloth for 2x speedup.

Usage:
    python train_skill_gap_classifier.py
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

MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"
DATA_PATH = Path(__file__).parent / "data" / "skill_gap_dataset.jsonl"
OUTPUT_DIR = Path(__file__).parent / "checkpoints" / "skill-gap-classifier"

SYSTEM_PROMPT = """You are a skill gap analyzer. Given a student background and a job description,
output a JSON with missing_skills (prioritized), present_skills, match_score, and reasoning."""


def load_dataset() -> Dataset:
    records = []
    with open(DATA_PATH) as f:
        for line in f:
            record = json.loads(line)
            text = (
                f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"
                f"<|im_start|>user\n{record['input']}<|im_end|>\n"
                f"<|im_start|>assistant\n{json.dumps(record['output'], indent=2)}<|im_end|>"
            )
            records.append({"text": text})
    ds = Dataset.from_list(records)
    return ds.train_test_split(test_size=0.1, seed=42)


def setup_model_and_tokenizer():
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
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

    return model, tokenizer


def train():
    dataset = load_dataset()
    model, tokenizer = setup_model_and_tokenizer()

    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=3,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        fp16=False,
        bf16=True,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        logging_steps=10,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["test"],
        tokenizer=tokenizer,
        dataset_text_field="text",
        max_seq_length=2048,
        packing=False,
    )

    trainer.train()
    trainer.save_model(str(OUTPUT_DIR / "final"))
    print(f"\nModel saved to {OUTPUT_DIR / 'final'}")


if __name__ == "__main__":
    train()
