# Dataset Verification & Targeted Fixes Report

## 1. Summary of Issues Identified (732 / 733 Failures)

When executing `verify_dataset_docker.py` across the 733 samples, 732 scenes failed during stage-4 rendering with `RENDER_FAIL`.
Detailed log analysis of the failed scenes in `data/verification_run/failed/<sample_id>/render.log` revealed two primary deterministic root causes:

### Issue A: `NameError: name 'VoiceoverScene' is not defined`
* **Root Cause**: The assistant response generated code defining `class SceneName(VoiceoverScene):` or referencing `GTTSService` without importing them. Only `from manim import *` was included.
* **Impact**: Manim failed at module import time inside Docker before scene initialization could even begin.

### Issue B: `EOFError: EOF when reading a line` (Whisper Interactive Prompt)
* **Root Cause**: When scenes called `self.set_speech_service(GTTSService(transcription_model="base"))`, `manim_voiceover` triggered its transcription setup module. Because Whisper was not installed in the Docker container (which only requires cloud Google TTS), `prompt_ask_missing_extras` in `manim_voiceover/helper.py` attempted to prompt user input on stdin (`Shall I install them for you? [Y/n]`). In a non-interactive headless Docker runner, `input()` raised `EOFError`.
* **Correction**: Per `docs/SPEC.md` and `devnote.md` §4, `GTTSService()` generates segment audio via Google Translate and calculates exact bookmark offsets via SoX without needing local Whisper speech recognition. Calling `GTTSService()` without `transcription_model` eliminates the prompt and runs cleanly.

---

## 2. Targeted Fixes Applied

1. **Auto-Detection & In-flight Repair in [`verify_dataset_docker.py`](../verify_dataset_docker.py)**:
   - Added `apply_targeted_fixes(code)`:
     - Automatically injects `from manim_voiceover import VoiceoverScene` and `from manim_voiceover.services.gtts import GTTSService` whenever referenced.
     - Strips `transcription_model="..."` from `GTTSService` invocations.
   - Applied automatically during sample loading before scenes are rendered.

2. **Permanent In-Place Dataset Patching**:
   - Added `--fix-dataset-in-place` flag to `verify_dataset_docker.py`.
   - Created standalone utility [`scripts/fix_dataset_targeted.py`](../scripts/fix_dataset_targeted.py) to patch `data/qwen3_8b_manimator_master_sft.jsonl` in-place while keeping a safety backup (`.jsonl.bak`).

3. **High-Throughput Concurrency (100 at a time)**:
   - Upgraded default concurrency from 10 workers to 100 workers.
   - Added staggered container launch throttling (10–20ms) to prevent Docker daemon socket exhaustion during thundering-herd startups.

---

## 3. How to Run the Updated 100-at-a-time Verification

### Step 1 (Optional but Recommended): Permanently Patch Dataset In-Place
```bash
uv run python3 verify_dataset_docker.py --fix-dataset-in-place
```

### Step 2: Launch Verification Daemon (100 at a time)
```bash
# Clean previous failure cache and run with 100 concurrent workers
uv run python3 verify_dataset_docker.py --daemon --clean
```

### Step 3: Monitor Live Progress & Pass Rate
```bash
uv run python3 verify_dataset_docker.py --status
```
Or view the live Markdown report at `data/verification_run/summary_report.md`.
