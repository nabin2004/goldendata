# Manim-AOS Gold SFT Dataset for Qwen3-8B

Unified dataset and pipeline for Supervised Fine-Tuning (SFT) of **Qwen3-8B** to achieve state-of-the-art generation of narrated, pedagogically structured mathematical animations using **Manim Community Edition (v0.19+)** and **Manim Voiceover**.

---

## 1. Dataset Overview

The master dataset compiles high-quality, verified Manim CE animations paired with synchronized voiceovers, precise narration bookmarks, and frame-relative visual layouts.

- **Primary SFT Artifact**: [`data/qwen3_8b_manimator_master_sft.jsonl`](file:///home/nabin/THEGOLDENDATASET/data/qwen3_8b_manimator_master_sft.jsonl)
- **Comprehensive Workflow & Repair Guide**: [`docs/DATASET_VERIFICATION_AND_REPAIR_WORKFLOW.md`](file:///home/nabin/THEGOLDENDATASET/docs/DATASET_VERIFICATION_AND_REPAIR_WORKFLOW.md)
- **Target Model**: Qwen3-8B (also compatible with Qwen 2.5 7B/14B/32B, LLaMA 3.1/3.3, and DeepSeek)
- **Format**: Standard OpenAI / ChatML 3-turn message format:
  ```json
  {"messages": [{"role": "system", "..."}, {"role": "user", "..."}, {"role": "assistant", "..."}]}
  ```

---

## 2. Integrated Data Sources (Pure Gold SFT)

The master dataset aggregates three pure gold data sources, completely filtering out noisy legacy sets:

| Source | Type | Samples | Skill Placement | Description |
|---|---|---|---|---|
| **Local Canonical Validated** | Local JSONL | 149 | User Prompt | Human-reviewed, linter-validated gold canonicals (`data/canonical/validated.jsonl`) |
| **Qwen Chat Exports** | Local Chat Logs | 379 | User Prompt | High-quality generations aligned from Qwen web chats (`exported_chats/*.json`) |
| **`nabin2004/qwen-Manimator-1-sft-data`** | Hugging Face | 305 | None (Clean) | Base Manimator SFT dataset with verified `<Plan>` blocks and voiceover bookmarks |

> **Note on Excluded Datasets**: `nabin2004/AOS-Narrated-Manim-400` was deliberately excluded from this SFT set. Inspection revealed that it completely lacked `<Plan>` blocks, lacked `<bookmark>` audio synchronization tags, and used unresolvable internal imports (`tools.aos_speech_service`). Excluding it protects the strict two-block contract and audio-visual synchronization of the fine-tuned model.

### Total Size
- **Total Integrated Samples**: **833 pure gold SFT samples**
- **Contract Adherence**: 100% of samples follow the `<Plan>` + ````python```` two-block contract with exact bookmark synchronization.


---

## 3. Prompt Architecture & Design Decisions

### A. Clean, Harmonized System Prompt (Zero Skills in System Message)
To ensure consistent conditioning and prevent context bloat in the system role, **skills are NEVER placed in the system prompt** across any sample in any dataset.

The system prompt is unified to:
```text
You are an expert Python programmer and mathematics educator specializing in ManimCE and Manim Voiceover. You create high-quality, pedagogically rich, narrated animations. You always use `VoiceoverScene`, {`GTTSService`|`AOSSpeechService`}, and precise bookmark timing (`<bookmark>` tags and `wait_until_bookmark`) to sync audio with visual elements. Wrap your code in ```python ... ``` blocks.
```
*(The speech service is dynamically tagged based on whether the code utilizes `GTTSService` or `AOSSpeechService`).*

### B. User Prompt Augmentation Strategy
- **Locally Prepared Data** (Canonicals & Chat Exports):
  The user request is followed by a structured **Reference Guidelines & Skill Specifications** chip:
  ```markdown
  {User Instruction / Math Concept / Code Repair Request}

  ---
  ### Reference Guidelines & Skill Specifications
  {manim_aos_master_skill + manim_composer_skill}
  ```
- **Hugging Face Dataset** (`nabin2004/qwen-Manimator-1-sft-data`):
  Kept as direct, clean user requests without skill chips.

### Why This Dual-Mode User Strategy?
1. **In-Context Skill Adherence**: When a user or system injects a skill sheet or API constraints into the prompt, the model learns to strictly follow them.
2. **Zero-Shot Generalization**: When a user provides a brief instruction without any skill documentation, the model still generates complete `<Plan>` blocks and valid ManimCE voiceover code.

### C. Assistant Response Contract (Strict Two-Block Format)
Every assistant response adheres to the strict two-block contract:
1. **`<Plan>...</Plan>` Block**: Exactly 8 ordered lines:
   - `goal`: Clear objective of the animation.
   - `skills`: Key Manim classes and functions used.
   - `layout`: Spatial arrangement of components with margins.
   - `camera`: Camera behavior (e.g., static, `MovingCameraScene`, zoom).
   - `dynamics`: Updaters and `ValueTracker` specifications.
   - `math`: LaTeX equations and mathematical concepts.
   - `narration`: Spoken transcript containing inline `<bookmark mark='...'/>` tags.
   - `validate`: Verification checklist (bookmark parity, frame bounds).
2. **` ```python ... ``` ` Block**:
   - Inherits `VoiceoverScene` (or `VoiceoverScene, MovingCameraScene`).
   - Sets speech service in `construct()`: `self.set_speech_service(GTTSService(...))` or `AOSSpeechService`.
   - Defines and uses `fit_in_frame(mob, w_frac=0.9, h_frac=0.9)` and `MARGIN = 0.5`.
   - Exact parity: Every narration bookmark has a corresponding `self.wait_until_bookmark(...)` inside the same `with self.voiceover(...)` context.

---

## 4. Building the Dataset

### Prerequisites
The build script is self-contained and uses standard Python (Python 3.10+):
```bash
# Recommended environment runner
uv run python3 build_sft_dataset.py
```

### Options & Flags
- `--smoke-test`: Quick verification testing 1 chat export, canonicals, and HF datasets, validating the message schema.
- `--skip-hf`: Build solely using local chat exports and local canonicals (offline mode).
- `--without-user-skills`: Build local data without appending the skill chip to user prompts.
- `--dedup-prompt-only`: Aggressively collapse distinct implementations sharing the same base instruction (reduces dataset size).
- `--keep-end`: Preserves legacy `<End>...</End>` blocks if present.

---

## 5. File Structure

```
THEGOLDENDATASET/
├── build_sft_dataset.py                       # Master dataset extraction & build pipeline
├── README.md                                  # Dataset documentation & SFT guide
├── configs/
│   ├── master_skill.md                        # Consolidated Manim-AOS master skill reference
│   └── pipeline.yaml                          # Core pipeline configuration
├── exported_chats/                            # Exported Qwen chat logs (*.json)
│   └── cached_batches/                        # Downloaded batch inputs & skills
└── data/
    ├── canonical/
    │   └── validated.jsonl                    # 149 gold canonical validated items
    ├── canonical_validated_sft.jsonl          # Canonical validated formatted for SFT
    ├── exported_chats_sft.jsonl               # Exported chats formatted for SFT
    ├── hf_manimator_1_sft.jsonl               # HF Qwen-Manimator-1 dataset
    └── qwen3_8b_manimator_master_sft.jsonl    # ⭐ UNIFIED MASTER SFT DATASET
```

---

## 6. Fine-Tuning Qwen3-8B

### Recommended Hyperparameters
- **Base Model**: `Qwen/Qwen2.5-7B-Instruct` or `Qwen3-8B`
- **Context Length**: `8192` (or `16384` to accommodate full-skill in-context prompts)
- **Training Epochs**: `3`
- **Learning Rate**: `1e-5` (Full SFT) or `1e-4` (LoRA / QLoRA)
- **LR Scheduler**: `cosine` with 3% warmup
- **LoRA Configuration** (if using PEFT/LoRA):
  - `r`: `64`
  - `lora_alpha`: `128`
  - `lora_dropout`: `0.05`
  - `target_modules`: `["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]`
- **Packing**: `true` (Multipack samples for higher throughput)

### Example with Unsloth / Hugging Face TRL:
```python
from datasets import load_dataset
from trl import SFTTrainer, SFTConfig

dataset = load_dataset("json", data_files="data/qwen3_8b_manimator_master_sft.jsonl")

training_args = SFTConfig(
    output_dir="./qwen3-8b-manimator",
    max_seq_length=8192,
    num_train_epochs=3,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,
    learning_rate=1e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.03,
    logging_steps=10,
    save_strategy="epoch",
    fp16=False,
    bf16=True,
    dataset_text_field="messages",
)
```
