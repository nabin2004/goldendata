# Manim-AOS → Qwen ChatUI Manual Generation Workflow

> **Goal:** Generate canonical Manim-AOS samples 100 at a time using Qwen ChatUI (or any ChatUI-compatible UI), save them locally, render each one, and queue failed renders for coding-agent repair.

---

## Table of Contents
1. [What This Repo Does](#1-what-this-repo-does)
2. [Two-Block Contract (Never Break This)](#2-two-block-contract-never-break-this)
3. [The Qwen ChatUI System Prompt](#3-the-qwen-chatui-system-prompt)
4. [100-at-a-Time User Prompt Template](#4-100-at-a-time-user-prompt-template)
5. [Copy & Save Workflow](#5-copy--save-workflow)
6. [Render Each Sample Locally](#6-render-each-sample-locally)
7. [Failure Triage & Coding-Agent Repair](#7-failure-triage--coding-agent-repair)
8. [Folder Layout](#8-folder-layout)
9. [Checklist Before Pushing to `data/canonical/`](#9-checklist-before-pushing-to-datacanonical)
10. [Skills & Prompt References](#10-skills--prompt-references)

---

## 1. What This Repo Does

This repo refines **`nabin2004/manim-aos-5k400`** (5 000+ Manim animation scripts) into a gold
supervised fine-tuning (SFT) + DPO repair dataset.

| Stage | What happens |
|-------|-------------|
| **Ingest / AST triage** | Read raw scripts, reject `SYNTAX_ERROR`, `NO_SCENE`, `MANIMLIB` |
| **Transform** | LLM rewrites legacy script → canonical two-block sample |
| **Lint** | Deterministic checks (bookmarks, kwargs, deprecated API, frame bounds…) |
| **Render** | `manim -ql` + GTTSService → mp4 + audio |
| **Omni QC** | Vision check for overlap, clipping, A/V drift |
| **Package** | Passing samples → `data/packaged/sft.jsonl`; failing V1 + fixed V2 → `data/packaged/dpo.jsonl` |

In this manual workflow **you replace the LLM transform stage** with Qwen ChatUI, generating
100 samples per session, saving them locally, and feeding failures to a coding agent.

---

## 2. Completion Modes

The legacy workflow below remains available for existing batches. The new 10-slide workflow is prepared with:

```bash
python scripts/chunk_chatui.py data/raw/raw.jsonl data/chatui_slide10 --mode slide10 --limit 1000 --chunk-size 10
```

This creates 100 ten-prompt bundles in `data/chatui_slide10/`. Each returned completion must use the
`<Plan>` + Python + `<End>` contract described in the new `SYSTEM.md`, with the fixed roles in
`configs/slide_roles.yaml`. Validate a returned completion before moving it to canonical data:

```bash
python scripts/validate_slide10.py path/to/completion.txt
```

## 3. Legacy Two-Block Contract (Never Break This)

Every sample you save **must** look exactly like this — one `<Plan>` block, then one Python block, nothing else:

```
<Plan>
goal: <one line describing what the scene teaches>
skills: VoiceoverScene, GTTSService, ValueTracker, always_redraw, ...
layout: <where elements sit, e.g. "title top, axes centre, label right">
camera: Static | MovingCameraScene + key frames described
dynamics: ValueTracker + always_redraw / DecimalNumber updater
math: r"\frac{d}{dx}f(x)", r"\lim_{h\to 0}", ...
narration: Beat 1 text <bookmark mark='b1'/> Beat 2 text <bookmark mark='b2'/>
validate: render passes manim -ql, bookmarks b1 b2 fire in order
</Plan>

```python
from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService

MARGIN = 0.5

class MyScene(VoiceoverScene):
    def fit_in_frame(self, mob: Mobject, w_frac=0.9, h_frac=0.9) -> Mobject:
        max_w = config.frame_width * w_frac
        max_h = config.frame_height * h_frac
        if mob.width > max_w: mob.width = max_w
        if mob.height > max_h: mob.height = max_h
        return mob

    def construct(self):
        self.set_speech_service(GTTSService(transcription_model="base"))
        # [SETUP]
        ...
        # [LAYOUT]
        ...
        # [BEAT 1 | sync: b1]
        with self.voiceover(text="Beat 1 <bookmark mark='b1'/>") as t:
            self.wait_until_bookmark("b1")
            ...
```
```

> **Rule:** `set(bookmark names in narration)` must exactly equal `set(wait_until_bookmark args)`.

---

## 4. The Qwen ChatUI System Prompt

Paste this as the **System** message when starting a new Qwen ChatUI conversation.
Keep it pinned for the entire 100-sample session.

---

```
You are an expert Manim Community Edition (v0.19+) engineer generating canonical Manim-AOS
training samples for a supervised fine-tuning dataset.

### HARD RULES — never violate these:

1. Output EXACTLY: one <Plan>…</Plan> block immediately followed by one ```python block.
   Nothing before, between, or after. No prose, no markdown headings outside the two blocks.

2. Plan block — 8 keys in FIXED ORDER, one line each:
   goal | skills | layout | camera | dynamics | math | narration | validate

3. narration line carries the full script with inline bookmark tags:
   <bookmark mark='b1'/>, <bookmark mark='b2'/>, …

4. Every bookmark mark='X' in narration MUST appear as self.wait_until_bookmark("X") inside
   the matching `with self.voiceover(...)` block. Set equality is enforced by the linter.

5. Imports (exactly these three):
   from manim import *
   from manim_voiceover import VoiceoverScene
   from manim_voiceover.services.gtts import GTTSService

6. Class MUST inherit VoiceoverScene. Add MovingCameraScene ONLY if camera moves.

7. First statement in construct(): self.set_speech_service(GTTSService(transcription_model="base"))

8. Always define and use:
   MARGIN = 0.5
   def fit_in_frame(self, mob, w_frac=0.9, h_frac=0.9) -> Mobject

9. Section comments required: # [SETUP]  # [LAYOUT]  # [UPDATER]  # [BEAT n | sync: label]

10. Dynamics: ONE ValueTracker + always_redraw / DecimalNumber. NEVER rebuild MathTex per frame.

11. Camera moves: self.camera.frame.save_state() before move, Restore(self.camera.frame) after.

12. LaTeX: raw strings (r"…"), NO unicode sub/superscripts.

13. Positioning: next_to / to_edge / to_corner / arrange / align_to — frame-relative only.
    No hard-coded pixel values. Use config.frame_width / config.frame_height.

14. Banned API / deprecated: ShowCreation → Create, from manimlib → from manim,
    no .intersect() / .union() on Mobjects (use manim.Intersection / manim.Union).

15. Banned kwargs:
    global: element_color, max_magnitude, font_size_px, center_point
    DecimalNumber: max_value | Text / MathTex / Dot: size

### SKILLS TO APPLY:
- manimce-best-practices: Create() not ShowCreation, MathTex() not Tex(), always frame-relative layout
- manim-voiceover-aos: wait_until_bookmark inside with self.voiceover block, GTTSService, bookmark parity
- manim-aos-canonical-sample: two-block contract, Plan schema, section comments

### OUTPUT FORMAT:
Return ONLY the two blocks. No numbering, no explanation, no markdown outside the blocks.
```

---

## 5. 100-at-a-Time User Prompt Template

After setting the system prompt, send this as your first user message.
Replace `{TOPIC_LIST}` with 100 math/physics/CS topics (one per line).

```
Generate 100 canonical Manim-AOS samples. For each one output the two-block format
(Plan then python) separated by a blank line, then a line with exactly:
--- SAMPLE END ---

Topics (one scene per topic):
{TOPIC_LIST}
```

### Example topic list (copy-paste 100 of these):
```
1. Derivative definition as limit of secant slope
2. Riemann sum convergence to integral
3. Fourier series partial sums of square wave
4. Gradient descent on a 2D loss surface
5. Matrix multiplication step-by-step
6. Eigenvalue power iteration
7. Bayes theorem with visual probability boxes
8. Central limit theorem coin-flip simulation
9. Pythagorean theorem geometric proof
10. Unit circle and trig functions
... (continue to 100)
```

> **Tip:** If Qwen stops mid-generation, send: `"Continue from sample N"` and it will resume.

---

## 6. Copy & Save Workflow

### 5a. Folder structure for manual saves
```
data/
  canonical_manual/        ← paste completed samples here as .py files
    sample_001.py
    sample_002.py
    ...
  canonical_manual_jsonl/  ← after validation, converted to .jsonl
  render_pass/             ← rendered mp4 + timing json for passing samples
  render_fail/             ← failed renders with error logs
  repairs/                 ← coding-agent fixes (v1_code + v2_code diffs)
logs/
  rejections.jsonl         ← every rejection with reason code (never delete)
```

### 5b. Splitting the Qwen output into individual files

Copy the entire ChatUI response, paste into a text file called `raw_batch_001.txt`, then run:

```bash
python scripts/split_batch.py raw_batch_001.txt data/canonical_manual/
```

> If `scripts/split_batch.py` doesn't exist yet, create it (see skeleton below):

```python
# scripts/split_batch.py
"""Split a raw Qwen batch output into individual .py files."""
import sys, pathlib, re

raw = pathlib.Path(sys.argv[1]).read_text()
out_dir = pathlib.Path(sys.argv[2])
out_dir.mkdir(parents=True, exist_ok=True)

samples = re.split(r"^--- SAMPLE END ---$", raw, flags=re.MULTILINE)
for i, s in enumerate(samples, 1):
    s = s.strip()
    if not s:
        continue
    # Extract the python block
    m = re.search(r"```python\n(.*?)```", s, re.DOTALL)
    if not m:
        print(f"[WARN] sample {i}: no python block found — skipping")
        continue
    (out_dir / f"sample_{i:03d}.py").write_text(s)   # save full two-block text
    print(f"Saved sample_{i:03d}.py")
```

### 5c. Manual copy without the script
1. In Qwen ChatUI, select all text in the response (Ctrl+A in the message box won't work — scroll to top, click before first `<Plan>`, Shift+click after last `--- SAMPLE END ---`).
2. Paste into VS Code or any editor.
3. Save as `data/canonical_manual/sample_NNN.py` using the two-block format.

---

## 6. Render Each Sample Locally

### 6a. Prerequisites
```bash
make setup          # installs venv, deps, docs index
make docker-build   # build render image (optional, for Docker backend)
```

### 6b. Render a single sample
```bash
# Extract the python block from sample_001.py (everything inside ```python ... ```)
# save it as /tmp/scene_001.py, then:

manim -ql /tmp/scene_001.py MyScene
```

Or use the pipeline render script (renders all files in the folder):
```bash
python -m manim_aos_data.render --input data/canonical_manual/ --output data/render_pass/ \
       --fail-dir data/render_fail/ --workers 4
```

Or with Docker (more reproducible):
```bash
RENDER_BACKEND=docker make docker-render
```

### 6c. What a passing render produces
```
media/videos/scene_001/480p15/MyScene.mp4
media/videos/scene_001/480p15/MyScene_ManimVoiceover/
```
Copy these to `data/render_pass/sample_001/`.

### 6d. Logging failures
Every render failure must be logged to `logs/rejections.jsonl`:
```json
{"id": "sample_001", "stage": "render", "reason_code": "RENDER_FAIL", "error": "...traceback..."}
```

---

## 7. Failure Triage & Coding-Agent Repair

### 7a. Failure types and reason codes
| Reason code | Cause | Fix approach |
|-------------|-------|-------------|
| `SYNTAX_ERROR` | Invalid Python | Agent fixes syntax |
| `RENDER_FAIL` | Manim crash | Agent reads traceback, patches code |
| `TTS_FAIL` | GTTSService error | Check internet / bookmark mismatch |
| `BOOKMARK_SET_EQUALITY` | Narration ↔ wait_until_bookmark mismatch | Agent aligns sets |
| `KWARG_SIGNATURE_CHECK` | Hallucinated kwarg | Agent strips banned kwarg |
| `FRAME_BOUNDS_CHECK` | Mobject out of frame | Wrap in `fit_in_frame` |
| `DEPRECATED_API_BAN` | ShowCreation, manimlib | Agent applies deprecated_map.yaml |

### 7b. Coding-agent repair prompt (paste into your coding agent)

````
You are a Manim CE repair agent. Fix the following failed sample with the SMALLEST possible diff.

Failure signal: {REASON_CODE}
Error / diagnosis:
```
{PASTE_FULL_ERROR_TRACEBACK_HERE}
```

V1 code (full two-block sample):
```
{PASTE_FULL_SAMPLE_HERE}
```

Rules:
- Keep the <Plan>…</Plan> block unchanged unless a bookmark mismatch forces a narration edit.
- Do NOT restyle working code. Fix only what caused the failure.
- After the fix, confirm: set(bookmark names in narration) == set(wait_until_bookmark args).
- Output JSON only:
  {"diagnosis": "...", "fix_summary": "...", "v2_code": "...full fixed python..."}
````

### 7c. Saving repair traces (for DPO dataset)
```
data/repairs/sample_001.jsonl  ← one JSON line:
{"id":"sample_001","v1_code":"...","diagnosis":"...","fix_summary":"...","v2_code":"...","diff_lines":N,"signal":"render"}
```

---

## 8. Folder Layout

```
THEGOLDENDATASET/
├── configs/
│   ├── pipeline.yaml          ← manim version, render workers, LLM retries
│   ├── banned_kwargs.yaml     ← hallucinated kwargs per class
│   └── deprecated_map.yaml   ← ShowCreation→Create, manimlib→manim
├── docs/
│   ├── SPEC.md                ← canonical sample contract
│   ├── ARCHITECTURE.md        ← 6-stage pipeline
│   ├── LINTER_RULES.md        ← all lint checks
│   └── QWEN_CHATUI_MANUAL_WORKFLOW.md   ← THIS FILE
├── prompts/
│   ├── transform.md           ← full LLM transform prompt (basis for system prompt above)
│   ├── repair.md              ← repair prompt template
│   └── omni_qc.md             ← vision QC prompt
├── data/
│   ├── raw/                   ← READ-ONLY source dataset
│   ├── triage/
│   ├── canonical/             ← pipeline-verified samples only
│   ├── canonical_manual/      ← YOUR manual Qwen saves go here
│   ├── render_pass/
│   ├── render_fail/
│   ├── repairs/
│   └── packaged/
│       ├── sft.jsonl
│       └── dpo.jsonl
├── logs/
│   └── rejections.jsonl       ← NEVER delete; append-only
├── scripts/
│   └── split_batch.py         ← splits Qwen batch output into files
└── src/manim_aos_data/
    └── linter/                ← deterministic lint checks
```

---

## 9. Checklist Before Pushing to `data/canonical/`

Run through this for every sample before it leaves `canonical_manual/`:

- [ ] Two-block contract holds: exactly one `<Plan>…</Plan>` then one ` ```python ` block
- [ ] Plan has exactly 8 keys in fixed order: `goal, skills, layout, camera, dynamics, math, narration, validate`
- [ ] `set(bookmark marks in narration)` == `set(wait_until_bookmark args)` and all calls are inside `with self.voiceover`
- [ ] All kwargs valid — none in `configs/banned_kwargs.yaml`
- [ ] No deprecated API (`ShowCreation`, `from manimlib`, `.intersect()`, `.union()`)
- [ ] LaTeX uses raw strings (`r"..."`) — no unicode `₁ ² ³ α β`
- [ ] `fit_in_frame` defined and called on all major mobjects
- [ ] `MARGIN = 0.5` defined; layout uses `to_edge / next_to / align_to`
- [ ] Camera moves paired: `save_state()` before, `Restore(self.camera.frame)` after
- [ ] `manim -ql` render succeeds (mp4 produced)
- [ ] Audio generated (no `TTS_FAIL`)
- [ ] Omni QC: no overlap / clipping flags

---

## 10. Skills & Prompt References

| Asset | Path | Purpose |
|-------|------|---------|
| Transform prompt | [`prompts/transform.md`](file:///home/nabin/THEGOLDENDATASET/prompts/transform.md) | Full LLM transform template (basis of system prompt) |
| Repair prompt | [`prompts/repair.md`](file:///home/nabin/THEGOLDENDATASET/prompts/repair.md) | Coding-agent repair template |
| Omni QC prompt | [`prompts/omni_qc.md`](file:///home/nabin/THEGOLDENDATASET/prompts/omni_qc.md) | Vision QC JSON schema |
| Spec | [`docs/SPEC.md`](file:///home/nabin/THEGOLDENDATASET/docs/SPEC.md) | Canonical sample contract |
| Architecture | [`docs/ARCHITECTURE.md`](file:///home/nabin/THEGOLDENDATASET/docs/ARCHITECTURE.md) | 6-stage pipeline overview |
| Linter rules | [`docs/LINTER_RULES.md`](file:///home/nabin/THEGOLDENDATASET/docs/LINTER_RULES.md) | All deterministic lint checks |
| Pipeline config | [`configs/pipeline.yaml`](file:///home/nabin/THEGOLDENDATASET/configs/pipeline.yaml) | Manim version, workers, thresholds |
| Banned kwargs | [`configs/banned_kwargs.yaml`](file:///home/nabin/THEGOLDENDATASET/configs/banned_kwargs.yaml) | Hallucinated kwargs by class |
| Deprecated map | [`configs/deprecated_map.yaml`](file:///home/nabin/THEGOLDENDATASET/configs/deprecated_map.yaml) | API rewrites |
| AGENTS.md | [`AGENTS.md`](file:///home/nabin/THEGOLDENDATASET/AGENTS.md) | Operating manual for all coding agents |

---

## Quick-Start TL;DR

```
1. Open Qwen ChatUI → New Conversation
2. Paste Section 3 (System Prompt) as the System message
3. Send Section 4 (User Prompt) with 100 topics filled in
4. Copy response → paste into raw_batch_NNN.txt
5. python scripts/split_batch.py raw_batch_NNN.txt data/canonical_manual/
6. python -m manim_aos_data.render --input data/canonical_manual/ --fail-dir data/render_fail/
7. For each file in data/render_fail/ → paste coding-agent repair prompt (Section 7b)
8. Save repair trace to data/repairs/
9. Re-render fixed v2 → if passes, move to data/canonical/
10. Repeat from step 2 with the next 100 topics
```
