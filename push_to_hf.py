#!/usr/bin/env python3
"""
push_to_hf.py
-------------
Prepares and pushes the unified Manim-AOS Gold SFT dataset to Hugging Face Hub.

Pushes:
1. train.jsonl (734 gold SFT samples in ChatML format)
2. README.md (Comprehensive HF Dataset Card with YAML metadata tags)

Usage:
    uv run python3 push_to_hf.py --repo-id nabin2004/qwen3-8b-manimator-gold-sft
"""

import os
import sys
import shutil
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
SOURCE_DATASET = DATA_DIR / "qwen3_8b_manimator_master_sft.jsonl"
STAGING_DIR = DATA_DIR / "hf_upload_stage"

DATASET_CARD_CONTENT = """---
language:
- en
license: apache-2.0
task_categories:
- text-generation
tags:
- manim
- manim-ce
- manim-voiceover
- qwen3
- qwen2.5
- sft
- code-generation
- mathematics
- pedagogy
- 3blue1brown
size_categories:
- n<1K
configs:
- config_name: default
  data_files:
  - split: train
    path: train.jsonl
---

# Qwen3-8B Manimator Gold SFT Dataset

Gold-standard Supervised Fine-Tuning (SFT) dataset for **Qwen3-8B** (also compatible with Qwen 2.5 7B/14B/32B, LLaMA 3.1/3.3, and DeepSeek) designed to produce high-precision, pedagogically structured, narrated mathematical animations using **Manim Community Edition (v0.19+)** and **Manim Voiceover**.

## 📊 Dataset Summary

- **Total Samples**: 734 curated, deduplicated gold samples
- **Format**: OpenAI / ChatML 3-turn format (`system` -> `user` -> `assistant`)
- **Language**: English / Python (Manim CE v0.19+)
- **Primary Split**: `train.jsonl`

```python
from datasets import load_dataset

dataset = load_dataset("nabin2004/qwen3-8b-manimator-gold-sft")
print(dataset["train"][0]["messages"])
```

---

## 🎯 Target Capabilities

This dataset trains language models to:
1. **Plan Before Coding**: Generate an 8-key structured `<Plan>` block before writing any code (`goal`, `skills`, `layout`, `camera`, `dynamics`, `math`, `narration`, `validate`).
2. **Audio-Visual Parity**: Perfectly synchronize speech narration with visual animation using inline `<bookmark mark='...'/>` tags and `self.wait_until_bookmark("...")`.
3. **Frame-Relative Safety**: Enforce `fit_in_frame(mob, w_frac=0.9, h_frac=0.9)` and `MARGIN = 0.5` to eliminate off-screen clipping and visual overlap.
4. **Dual-Mode Prompt Adherence**:
   - Follow detailed in-context skill guides (`manim-aos-master` + `manim-composer`) when provided in the user prompt.
   - Execute zero-shot code generation when given concise user instructions without skills.

---

## 📂 Data Sources & Curation

Every sample in this dataset was vetted to guarantee zero hallucinated APIs and exact contract compliance:

| Source | Samples | Format | Description |
|---|---|---|---|
| **Local Canonical Validated** | 149 | SFT with Skill Chip | Human-reviewed, linter-validated gold canonicals (`data/canonical/validated.jsonl`) |
| **Qwen Chat Exports** | ~280 | SFT with Skill Chip | Fresh multi-batch generations aligned from Qwen chat sessions |
| **`nabin2004/qwen-Manimator-1-sft-data`** | 305 | Zero-Shot Prompts | Core curated SFT examples with verified `<Plan>` and bookmark synchronization |

> **Quality Filter**: Noisy legacy samples lacking `<Plan>` blocks, duration-multiplier audio timing, or unresolvable internal imports (e.g. `AOS-Narrated-Manim-400`) were completely eliminated.

---

## 🏗️ Message Schema

Each line in `train.jsonl` has the standard format:
```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are an expert Python programmer and mathematics educator specializing in ManimCE and Manim Voiceover. You create high-quality, pedagogically rich, narrated animations. You always use `VoiceoverScene`, `GTTSService`, and precise bookmark timing (`<bookmark>` tags and `wait_until_bookmark`) to sync audio with visual elements. Wrap your code in ```python ... ``` blocks."
    },
    {
      "role": "user",
      "content": "Create an interactive Manim CE animation demonstrating: Cycloid Generation with TracedPath and rolling circle...\\n\\n---\\n### Reference Guidelines & Skill Specifications\\n..."
    },
    {
      "role": "assistant",
      "content": "<Plan>\\ngoal: ...\\nskills: ...\\nlayout: ...\\ncamera: ...\\ndynamics: ...\\nmath: ...\\nnarration: ... <bookmark mark='intro'/> ...\\nvalidate: ...\\n</Plan>\\n\\n```python\\nfrom manim import *\\n...\\n```"
    }
  ]
}
```

---

## 🚀 Quickstart: Fine-Tuning Qwen3-8B

### Using Hugging Face TRL (`SFTTrainer`):

```python
import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTTrainer, SFTConfig

model_id = "Qwen/Qwen2.5-7B-Instruct"  # or Qwen3-8B upon release

tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,
    device_map="auto"
)

dataset = load_dataset("nabin2004/qwen3-8b-manimator-gold-sft")

training_args = SFTConfig(
    output_dir="./qwen3-manimator-gold",
    max_seq_length=8192,
    num_train_epochs=3,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,
    learning_rate=1e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.03,
    bf16=True,
    logging_steps=10,
    save_strategy="epoch",
    dataset_text_field="messages",
)

trainer = SFTTrainer(
    model=model,
    args=training_args,
    train_dataset=dataset["train"],
)

trainer.train()
```

### Using Unsloth (Ultra-Fast 2x QLoRA):

```python
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer, SFTConfig

max_seq_length = 8192
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="Qwen/Qwen2.5-7B-Instruct",
    max_seq_length=max_seq_length,
    load_in_4bit=True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=64,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=128,
    lora_dropout=0,
)

dataset = load_dataset("nabin2004/qwen3-8b-manimator-gold-sft")

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset["train"],
    dataset_text_field="messages",
    max_seq_length=max_seq_length,
    dataset_num_proc=2,
    args=SFTConfig(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=10,
        max_steps=250,
        learning_rate=2e-4,
        fp16=False,
        bf16=True,
        logging_steps=1,
        output_dir="outputs",
    ),
)

trainer.train()
```

---

## 📜 License

Apache 2.0. Open for commercial, educational, and research use.
"""

def prepare_staging_directory():
    """Copies primary artifact to train.jsonl and writes README.md."""
    if not SOURCE_DATASET.exists():
        print(f"[!] Error: Source dataset not found at {SOURCE_DATASET}")
        print("    Please run: uv run python3 build_sft_dataset.py first.")
        sys.exit(1)

    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    target_train = STAGING_DIR / "train.jsonl"
    target_readme = STAGING_DIR / "README.md"

    print(f"[*] Copying {SOURCE_DATASET.name} -> {target_train}...")
    shutil.copy2(SOURCE_DATASET, target_train)

    print(f"[*] Writing Dataset Card -> {target_readme}...")
    target_readme.write_text(DATASET_CARD_CONTENT.strip(), encoding="utf-8")

    size_mb = target_train.stat().st_size / (1024 * 1024)
    print(f"[✓] Staging complete: {target_train.name} ({size_mb:.2f} MB), {target_readme.name}")

def push_to_hub(repo_id: str, private: bool = False, token: str = None):
    """Pushes staging directory to Hugging Face Hub using huggingface_hub."""
    try:
        from huggingface_hub import HfApi, create_repo
    except ImportError:
        print("[!] huggingface_hub library not found. Installing via pip/uv...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "huggingface_hub"])
        from huggingface_hub import HfApi, create_repo

    api = HfApi(token=token)

    print(f"\n[*] Creating/verifying Hugging Face dataset repo: {repo_id}...")
    try:
        create_repo(
            repo_id=repo_id,
            repo_type="dataset",
            private=private,
            exist_ok=True,
            token=token
        )
        print(f"[✓] Repo ready: https://huggingface.co/datasets/{repo_id}")
    except Exception as e:
        print(f"[!] Warning while creating repo (might already exist): {e}")

    print(f"\n[*] Uploading folder {STAGING_DIR} to {repo_id}...")
    try:
        api.upload_folder(
            folder_path=str(STAGING_DIR),
            repo_id=repo_id,
            repo_type="dataset",
            commit_message="Add Qwen3-8B Manimator Gold SFT Dataset (734 samples)",
            token=token
        )
        print(f"\n{'=' * 75}")
        print(f"🎉 DATASET SUCCESSFULLY PUBLISHED TO HUGGING FACE!")
        print(f"{'=' * 75}")
        print(f"URL: https://huggingface.co/datasets/{repo_id}")
        print(f"Load with:")
        print(f'    from datasets import load_dataset')
        print(f'    dataset = load_dataset("{repo_id}")')
        print(f"{'=' * 75}\n")
    except Exception as e:
        print(f"\n[!] Upload failed: {e}")
        print("\nTroubleshooting tips:")
        print("1. Login first via CLI:")
        print("   huggingface-cli login")
        print("2. Or pass your Hugging Face write token:")
        print(f"   uv run python3 push_to_hf.py --repo-id {repo_id} --token YOUR_HF_TOKEN")
        print("3. Or upload manually using the huggingface CLI:")
        print(f"   huggingface-cli upload {repo_id} {STAGING_DIR} . --repo-type dataset")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Push gold SFT dataset to Hugging Face Hub.")
    parser.add_argument("--repo-id", type=str, default="nabin2004/qwen3-8b-manimator-gold-sft",
                        help="Target Hugging Face repository ID (e.g. nabin2004/qwen3-8b-manimator-gold-sft)")
    parser.add_argument("--private", action="store_true",
                        help="Create repository as private (default is public).")
    parser.add_argument("--token", type=str, default=None,
                        help="Hugging Face API write token (optional if already logged in).")
    args = parser.parse_args()

    print("=== Hugging Face SFT Dataset Publisher ===")
    prepare_staging_directory()
    push_to_hub(repo_id=args.repo_id, private=args.private, token=args.token)

if __name__ == "__main__":
    main()
