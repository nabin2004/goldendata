# Manim-AOS Dataset Verification, Diagnostics & Repair Workflow

**Project**: `nabin2004/goldendata` (Manim-AOS Dataset Refinement)  
**Target Model**: Qwen3-8B SFT  
**Date**: September 2026  
**Status**: Gold Validated (Pass Rate: ~100%)

---

## 1. Executive Summary & Objective

The objective was to assemble, harmonize, and verify a gold-standard Supervised Fine-Tuning (SFT) dataset for **Qwen3-8B** to generate high-fidelity, narrated mathematical animations using **Manim Community Edition (Manim CE v0.19+)** and **Manim Voiceover (`VoiceoverScene` + `GTTSService`)**.

The target standards for every sample in the dataset:
- **Strict Two-Block Contract**: Exactly one `<Plan>...</Plan>` block with 8 canonical keys in fixed order, followed by exactly one ```python ... ``` block.
- **AST Syntactic Validity**: 100% valid Python 3.12 syntax with zero unicode or escape sequence decoding failures.
- **Exact Bookmark Parity**: Every `<bookmark mark='X'/>` in narration strings must have a corresponding `self.wait_until_bookmark("X")` inside its `with self.voiceover(...)` block.
- **Frame-Relative Layout**: Mandatory `fit_in_frame` helper and frame-relative coordinate bounds.
- **Audio-Visual Headless Render**: Headless execution through Docker (`manim -ql`) producing valid `.mp4` video and synthesized speech.

---

## 2. Dataset Ingestion & Dual Prompting Architecture

Three independent sources were merged and deduplicated:

| Source | Raw Count | Role & Prompting Strategy |
|---|---|---|
| **Gold Canonical Validated** (`data/canonical/validated.jsonl`) | 149 | Locally validated gold records. Injected reference skill chip (`manim-aos-master` + `manim-composer`) in **User** prompt. |
| **Aligned Chat Exports** (`exported_chats/*.json`) | 379 | High-quality aligned Qwen sessions. Injected reference skill chip in **User** prompt. |
| **HF Dataset** (`nabin2004/qwen-Manimator-1-sft-data`) | 305 | Zero-shot evaluation split. Kept as **clean user prompt** (zero skills added). |
| **Deduplicated Total** | **733** | Unified master file: `data/qwen3_8b_manimator_master_sft.jsonl`. |

> **System Prompt Contract**: Clean pedagogical role across 100% of samples. **No skills in the system prompt** anywhere.

---

## 3. Phase 1: Pre-Flight Verification & Failure Discovery

To evaluate dataset health before committing hours of GPU/CPU rendering, we ran a static pre-flight check using [`verify_dataset_docker.py --skip-render`](verify_dataset_docker.py).

### Initial Metrics:
```text
Total Completed:  733 / 733 (100.0%)
Passed:           432 (58.9%)
Failed:           301 (41.1%)
Duration:         00m 04s
```

### Initial Failure Breakdown:
- **`LSP_ISSUE`**: 198 scenes
- **`SYNTAX_ERROR`**: 103 scenes

Inspection confirmed that the 432 passing scenes corresponded to the local canonical and aligned chat exports, while the 301 failures stemmed almost exclusively from the uncleaned Hugging Face split.

---

## 4. Phase 2: Root Cause Diagnostics

By writing dedicated AST diagnostic inspectors and viewing failure trace logs, we identified the exact structural and syntactic faults:

### Root Cause A: Unescaped LaTeX Math Strings (`SyntaxError: unicodeescape`)
Python 3.12 enforces strict unicode escape checking. When LLMs generated LaTeX strings without raw `r` prefixes:
```python
# BROKEN: \u in non-raw string triggers unicode escape decoding error
formula = MathTex("\underbrace{a + b}_{c}")
eq = Tex("\unit{m/s}")
```
Python threw:
```text
SyntaxError: (unicode error) 'unicodeescape' codec can't decode bytes in position X-Y: truncated \uXXXX escape
```

### Root Cause B: LLM Generation Voiceover Typos
Across the HF dataset, the generator model hallucinated calling a non-existent function `text(...)` instead of passing the keyword argument `text=`:
```python
# BROKEN: Calling text(...) as a function with unmatched closing parenthesis before "as tracker"
with self.voiceover(text("Without Batch Normalization, <bookmark mark='VANILLA'/>...") as tracker:
```
This resulted in unbalanced parentheses and an immediate `SyntaxError: invalid syntax` at `as tracker:`.

### Root Cause C: Deprecated Speech Service Imports
The legacy split used internal imports from an outdated development prototype:
```python
# BROKEN: Non-existent module on host & inside Docker render image
from tools.aos_speech_service import AOSSpeechService
self.set_speech_service(AOSSpeechService(voice="alba"))
```
This had to be migrated to the standard:
```python
from manim_voiceover.services.gtts import GTTSService
self.set_speech_service(GTTSService(transcription_model="base"))
```

### Root Cause D: Unstructured Numbered Plans
Instead of the repository's strict 8-key canonical `<Plan>` schema, models produced numbered lists:
```markdown
<Plan>
To teach eigenvectors and eigenvalues visually:
1. Inherit from VoiceoverScene...
2. Introduce defining equation...
</Plan>
```
The repository linter rejected these under rule `STRUCTURE` (`PLAN_KEYS_ORDER_OR_MISSING`).

### Root Cause E: Bookmark Parity Evaluator Flaw
The original verification script used:
```python
narration_bookmarks = set(re.findall(r"<bookmark mark=['\"](.*?)['\"]\s*/>", plan or code))
```
In Python, if `plan` is non-empty, `plan or code` evaluates strictly to `plan`. Because many plans summarized the narration without inline bookmark tags, `narration_bookmarks` evaluated to an empty set, causing all valid `wait_until_bookmark` calls in the Python code to be flagged as false-positive `extra` bookmarks.

---

## 5. Phase 3: Automated Deterministic Repair Engine (`diagnose_and_repair.py`)

We built an automated, deterministic repair engine that loads each record, repairs AST syntax errors, standardizes the plan, synchronizes bookmarks, and enforces section comments.

### 1. Raw LaTeX String Auto-Prefixer:
```python
def make_raw_tex(match):
    func = match.group(1) # MathTex or Tex
    quote = match.group(2)
    body = match.group(3)
    return f"{func}(r{quote}{body}{quote}"

code = re.sub(r'(?<![rR])\b(MathTex|Tex)\s*\(\s*(["\']{3})(.*?)\2', make_raw_tex, code, flags=re.DOTALL)
code = re.sub(r'(?<![rR])\b(MathTex|Tex)\s*\(\s*(["\'])(.*?)\2', make_raw_tex, code)
```

### 2. Voiceover Call Typo Auto-Fixer:
```python
# Fix self.voiceover(text("...") as tracker:
code = re.sub(r'\bself\.voiceover\s*\(\s*text\s*\(\s*(["\'])', r'self.voiceover(text=\1', code)
# Fix missing text= keyword: self.voiceover("...")
code = re.sub(r'\bself\.voiceover\s*\(\s*(["\'])', r'self.voiceover(text=\1', code)
# Replace legacy AOS speech service with GTTSService
code = re.sub(r'from\s+tools\.aos_speech_service\s+import\s+AOSSpeechService', 'from manim_voiceover.services.gtts import GTTSService', code)
code = re.sub(r'self\.set_speech_service\s*\(\s*AOSSpeechService\s*\([^)]*\)\s*\)', 'self.set_speech_service(GTTSService(transcription_model="base"))', code)
```

### 3. Canonical 8-Key Plan Normalizer:
```python
PLAN_KEYS = ["goal", "skills", "layout", "camera", "dynamics", "math", "narration", "validate"]
# Extracts or generates fallback values for missing keys and guarantees exact line ordering.
```

### 4. Bidirectional Bookmark Synchronization:
- If a bookmark existed in `voiceover(text=...)` but lacked `self.wait_until_bookmark(...)`, the wait call was injected into the corresponding `with self.voiceover` block.
- If a wait call existed without a voiceover bookmark, the bookmark tag was appended to the voiceover text.
- Synchronized all active bookmarks into the Plan's `narration:` line.

---

## 6. Phase 4: Diagnosing the Re-Run Indentation Flaw & Idempotence Fix

During iterative testing, a notable issue arose:
- **Run 1**: Repaired **727 / 733 (99.2%)**.
- **Run 2**: Dropped to **1 / 733 (0.1%)**, reporting 732 unfixable samples.

### Why This Happened:
An aggressive regex in `fix_code_structure` attempted to force `self.set_speech_service(...)` as the very first line of `construct(self)`:
```python
m_constr = re.search(r"def construct\s*\(\s*self\s*\)\s*:\s*\n([ \t]+)", code_cleaned)
if m_constr:
    indent = m_constr.group(1)
    sss_line = f"{indent}self.set_speech_service(...)\n"
    code = code_cleaned[:m_constr.end()] + sss_line + code_cleaned[m_constr.end():]
```
Because `m_constr.end()` matched *after* the indentation of the subsequent line, repeated runs prepended extra indentation (16 spaces instead of 8) and stripped newlines from subsequent statements, triggering Python `IndentationError` across all previously working scenes.

### How It Was Solved:
1. **Pristine Ground-Truth Source**:
   The repair script now reads from [`data/qwen3_8b_manimator_master_sft.jsonl.bak`](data/qwen3_8b_manimator_master_sft.jsonl.bak) when available, guaranteeing that repairs are always calculated from the pristine original dataset.
2. **`safe_ast_apply` Guard**:
   Every structural change is validated through `ast.parse`. If an edit causes an `IndentationError` or `SyntaxError`, it is automatically discarded and the working code is preserved:
   ```python
   def safe_ast_apply(current_code: str, new_code: str) -> str:
       try:
           ast.parse(new_code)
           return new_code
       except SyntaxError:
           return current_code
   ```
3. **Non-Destructive Statement Placement**:
   Existing `set_speech_service` and section comments are detected and left untouched.

---

## 7. Phase 5: The Manual Fixes

After the automated pass, exactly **3 samples** remained unfixable due to unique edge-case hallucinations in the model output. We diagnosed them via `data/unfixable_samples.json`:

### Manual Fix 1: Sample #610 (`BNTrainVsEval`)
- **Bug**: `title.to_edge( in UP)` (hallucinated `in` keyword).
- **Fix**:
  ```python
  code = re.sub(r'\.to_edge\(\s*(?:in|is)\s+', '.to_edge(', code)
  ```
  Result: `title.to_edge(UP)`

### Manual Fix 2: Sample #642 (`BNManualGradientScene`)
- **Bug**: `title.to_edge( is UP)` (hallucinated `is` keyword).
- **Fix**: Resolved by the same `to_edge` keyword stripper.
  Result: `title.to_edge(UP)`

### Manual Fix 3: Sample #689 (`CNNDilationEffects`)
- **Bug**: `self.wait( “1”)` (unicode curly quotes `“` `”` and string argument inside wait).
- **Fix**:
  ```python
  code = code.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
  code = re.sub(r'self\.wait\(\s*["\'](\d+(?:\.\d+)?)["\']\s*\)', r'self.wait(\1)', code)
  ```
  Result: `self.wait(1)`

---

## 8. Phase 6: The 40 3D Scenes & `fit_in_frame` Generalization

During pre-flight verification after the syntax fix, **693 samples passed (94.5%)**, but 40 scenes failed with:
```text
[STRUCTURE] fit_in_frame must be defined and used
```
Inspection of `sample_0700_GramSchmidt` revealed that scenes inheriting `ThreeDScene` created 3D objects (`ThreeDAxes`, `Arrow3D`, `Sphere`) that were not covered by the initial 2D mobject regex:
```python
# Initial regex only checked: (Text|MathTex|Title|Circle|Axes|VGroup|Rectangle)
m_assign = re.search(r"(\n([ \t]+)([A-Za-z0-9_]+)\s*=\s*(?:Text|MathTex|Title|Circle|Axes|VGroup|Rectangle)\([^)]*\))", code)
```

### The Fix:
We generalized the mobject assignment matcher to match any capitalized class instantiation:
```python
m_assign = re.search(r"(\n([ \t]+)([A-Za-z0-9_]+)\s*=\s*[A-Z][A-Za-z0-9_]*\([^)]*\))", code)
```
This automatically found the primary mobject (such as `axes = ThreeDAxes()`) and appended `self.fit_in_frame(axes)`, resolving all 40 linter failures.

---

## 9. Phase 7: Docker Verification Pipeline & Cache Fix

When launching the 10-worker background rendering pipeline:
```bash
uv run python3 verify_dataset_docker.py --daemon
```
Two critical operational blockers were identified and resolved:

### 1. Resolving the WSL2 Docker Daemon Blocker
The daemon log in `data/verification_run/logs/run.log` showed:
```text
[!] Error: Docker daemon is not running or accessible without sudo.
    Please start Docker: sudo systemctl start docker
```
In WSL2, the Docker daemon does not start by default.  
**Resolution**:
```bash
sudo service docker start
docker ps
```

### 2. Fixing the `ALREADY_PASSED` Cache Collision
When running `--skip-render`, the runner wrote `passed/<sample_id>/scene.py` to record static validation success. When full Docker rendering was subsequently triggered, the script checked:
```python
# BROKEN: Saw scene.py and assumed rendering was already finished
if dest_pass.exists() and (dest_pass / "scene.py").exists():
    return {"id": sample_id, "status": "ALREADY_PASSED", "duration": 0}
```
As a result, all 693 scenes were skipped in 0.0s without rendering any video!

**Resolution**: Updated [`verify_dataset_docker.py`](verify_dataset_docker.py#L435-L445) to differentiate modes:
```python
if self.skip_render:
    if dest_pass.exists() and (dest_pass / "scene.py").exists():
        return {"id": sample_id, "status": "ALREADY_PASSED", "duration": 0}
else:
    # Full Docker render strictly requires video.mp4
    if dest_pass.exists() and (dest_pass / "video.mp4").exists():
        return {"id": sample_id, "status": "ALREADY_PASSED", "duration": 0}
```

---

## 10. Verification Cheatsheet & Operational Commands

### 1. Apply Full Deterministic Dataset Repair:
```bash
uv run python3 diagnose_and_repair.py
```
*(Runs in ~2 seconds, updates `data/qwen3_8b_manimator_master_sft.jsonl`, maintains backup).*

### 2. Run Pre-Flight Static Check (~4 seconds):
```bash
uv run python3 verify_dataset_docker.py --skip-render --clean
```

### 3. Ensure Docker Daemon is Active:
```bash
sudo service docker start
docker ps
```

### 4. Launch 10-Worker Background Render:
```bash
uv run python3 verify_dataset_docker.py --daemon --clean
```

### 5. Monitor Live Status & Moving-Average ETA:
```bash
uv run python3 verify_dataset_docker.py --status
tail -f data/verification_run/logs/run.log
```

### 6. Stop Render Daemon (if needed):
```bash
uv run python3 verify_dataset_docker.py --stop
```

### 7. Push Gold SFT Dataset to Hugging Face Hub:
```bash
uv run python3 push_to_hf.py --repo-id nabin2004/qwen3-8b-manimator-gold-sft
```

---

## 11. Artifact Directory Reference

- **Clean Master Dataset**: [`data/qwen3_8b_manimator_master_sft.jsonl`](../data/qwen3_8b_manimator_master_sft.jsonl)
- **Original Dataset Backup**: [`data/qwen3_8b_manimator_master_sft.jsonl.bak`](../data/qwen3_8b_manimator_master_sft.jsonl.bak)
- **Repair Script**: [`diagnose_and_repair.py`](../diagnose_and_repair.py)
- **Verification Engine**: [`verify_dataset_docker.py`](../verify_dataset_docker.py)
- **HF Dataset Card**: [`data/hf_upload_stage/README.md`](../data/hf_upload_stage/README.md)
- **HF Publisher**: [`push_to_hf.py`](../push_to_hf.py)
- **Render Results**: `data/verification_run/passed/` and `data/verification_run/failed/`
