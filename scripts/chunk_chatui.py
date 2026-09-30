#!/usr/bin/env python3
"""Create compact, ChatUI-ready JSONL batches from a JSONL dataset.

Usage:
    python scripts/chunk_chatui.py data/raw/raw.jsonl data/chatui

The input is never modified. Each output batch contains at most 10 source
records. Source ``messages`` and ``metadata`` fields are intentionally omitted
because they duplicate context and make prompting more expensive.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path


SYSTEM_PROMPT = """You are an expert Manim Community Edition v0.19+ engineer creating robust canonical Manim-AOS training data.

INPUT: The user message is JSONL with exactly {BATCH_SIZE} source items. Each line has this shape:
{"id":"...","instruction":"...","code":"..."}
Process all 10 lines exactly once and in order. The id is tracking metadata: never copy it into the answer. If code is empty, implement the instruction directly. If code is present, repair or transform it while preserving the requested behavior. Do not invent missing requirements or silently drop an item.

OUTPUT: Return exactly 10 canonical samples, in the same order as the input. Each sample must contain exactly one <Plan>...</Plan> block, one ```python block, and one closing block in this order:
<End>
    <WhatWasBuilt>...</WhatWasBuilt>
    <WhatWasDemonstrated>...</WhatWasDemonstrated>
    <AnimationAndNarration>...</AnimationAndNarration>
    <ExpectedChecks>...</ExpectedChecks>
</End>
Separate samples with one line containing exactly:
--- SAMPLE END ---
Output nothing else: no introduction, headings, IDs, JSON, numbering, or text outside the three required blocks. The End fields must be concise, factual, and in the exact order shown. If the context limit is reached, stop only after a complete End block and wait for Continue; then resume at the next uncompleted item without repeating or renumbering anything.

PLAN: Use exactly these eight keys, in this order, one line each: goal, skills, layout, camera, dynamics, math, narration, validate. The narration line contains the full spoken script and inline tags such as <bookmark mark='b1'/>.

PYTHON: Use exactly these imports:
from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService
The scene inherits VoiceoverScene, defines MARGIN = 0.5 and defines and uses fit_in_frame(mob, w_frac=0.9, h_frac=0.9). The first statement in construct() is self.set_speech_service(GTTSService(transcription_model="base")). Use frame-relative layout, raw LaTeX strings, and [SETUP], [LAYOUT], [UPDATER], [BEAT n | sync: label] comments. Use documented Manim CE v0.19+ APIs only.

BOOKMARKS: Every narration bookmark must have exactly one matching self.wait_until_bookmark("...") call inside the same with self.voiceover(...) block. Before camera movement call self.camera.frame.save_state() and restore with Restore(self.camera.frame). Use one ValueTracker with always_redraw or DecimalNumber for changing values; never rebuild MathTex every frame. Do not use banned or deprecated kwargs/APIs.

FINAL CHECK: Before answering, verify there are 10 outputs for 10 inputs, source order is preserved, every sample has exactly one Plan block, Python block, and End block, all eight Plan keys are ordered, End tags are complete and ordered, bookmarks have exact parity, fit_in_frame is used, and no prose appears outside the samples."""


SLIDE10_SYSTEM_PROMPT = """You are an expert Manim Community Edition v0.19+ engineer creating 10-slide Manim-AOS fine-tuning data.

INPUT: The user message is JSONL with exactly 10 source items. Each line has this shape:
{"id":"...","instruction":"...","code":"..."}
Process all 10 lines exactly once and in order. The id is tracking metadata: never copy it into the answer.

OUTPUT: Return exactly {BATCH_SIZE} completions in source order. Separate completions with one line containing exactly:
--- SAMPLE END ---
Output nothing else. Every completion must contain exactly one <Plan> block, one ```python block, and one <End> block.

PLAN: Use YAML inside <Plan>...</Plan> with these keys in order: topic, audience, learning_goal, voice, slide_count, slides.
Set voice to alba and slide_count to 10. The slides list must contain exactly these classes and roles in order:
Slide01_Title (hook and title), Slide02_Motivation (why it matters), Slide03_Prerequisites (definitions and notation),
Slide04_CoreIdea (main concept and visual intuition), Slide05_Construction (step-by-step build),
Slide06_Formal (MathTex or formal statement), Slide07_Example (worked example),
Slide08_Camera (zoom or pan on a detail), Slide09_Pitfalls (common mistake or edge case),
Slide10_Recap (summary and takeaway).
Each slide entry has id, class, title, narration_goal, visuals, bookmarks, and camera.

PYTHON: Use from manim import *, from manim_voiceover import VoiceoverScene, and
from tools.aos_speech_service import AOSSpeechService. Define SlideBase(VoiceoverScene), VOICE = "alba",
setup() with AOSSpeechService(voice=self.VOICE, cache_dir="voiceover_cache"), slide_title(), and clear_slide().
Define exactly 10 slide classes named exactly as the Plan classes, each inheriting SlideBase. Slide08_Camera
also inherits MovingCameraScene. Every slide has at least one with self.voiceover(...) block and ends with
self.clear_slide(). Every self.play inside a voiceover block uses run_time=tracker.duration or
tracker.get_remaining_duration(). Every wait_until_bookmark("X") is inside the matching voiceover block and
has exactly one <bookmark mark='X'/> in that block's narration. Use documented Manim CE v0.19+ APIs only.

END: Use YAML inside <End>...</End> with slide_order, slide_count, render_cmd, concat, and checks.
slide_order must exactly match the 10 class names. render_cmd must render the 10 classes in that order.
checks must include 10_classes, all_voiceover, no_deprecated_api, bookmarks_resolved, and each_slide_clears.

FINAL CHECK: Verify 10 inputs produce 10 outputs, the order is preserved, each completion has exactly one
Plan/Python/End block, the Plan and End class orders match, there are exactly 10 slide classes, bookmarks resolve,
and no prose appears outside the completion blocks."""

SKILL_RELATIVE_PATH = Path(".claude/skills/manim-aos-master/SKILL.md")
COMPOSER_SKILL_RELATIVE_PATH = Path(".claude/skills/manim-composer/SKILL.md")


def load_records(input_path: Path) -> list[dict]:
    records = []
    with input_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on line {line_number}: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"line {line_number} is not a JSON object")
            records.append(record)
    return records


def render_record(record: dict, position: int) -> dict:
    sample_id = str(record.get("id") or f"sample_{position:05d}")
    instruction = str(record.get("instruction") or "").strip()
    code = str(record.get("code") or "").strip()
    return {"id": sample_id, "instruction": instruction, "code": code}


def write_combined_markdown(
    bundle_dir: Path,
    batch_name: str,
    batch_text: str,
    system_text: str,
    skill_text: str,
    composer_text: str,
) -> None:
    combined = (
        f"# ChatUI Batch {batch_name}\n\n"
        "## 1. SYSTEM.md\n\n"
        "````text\n"
        f"{system_text.rstrip()}\n"
        "````\n\n"
        "## 2. JSONL input\n\n"
        "````jsonl\n"
        f"{batch_text.rstrip()}\n"
        "````\n\n"
        "## 3. SKILL.md\n\n"
        "````markdown\n"
        f"{skill_text.rstrip()}\n"
        "````\n\n"
        "## 4. MANIM_COMPOSER.md\n\n"
        "````markdown\n"
        f"{composer_text.rstrip()}\n"
        "````\n"
    )
    (bundle_dir / f"{batch_name}.md").write_text(combined, encoding="utf-8")


def write_batches(records: list[dict], output_dir: Path, chunk_size: int, mode: str = "legacy") -> int:
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")
    output_dir.mkdir(parents=True, exist_ok=True)
    batch_count = math.ceil(len(records) / chunk_size) if records else 0
    repository_root = Path(__file__).resolve().parents[1]
    skill_path = repository_root / SKILL_RELATIVE_PATH
    if not skill_path.is_file():
        raise FileNotFoundError(f"master skill not found: {skill_path}")
    composer_skill_path = repository_root / COMPOSER_SKILL_RELATIVE_PATH
    if not composer_skill_path.is_file():
        raise FileNotFoundError(f"composer skill not found: {composer_skill_path}")

    if mode not in {"legacy", "slide10"}:
        raise ValueError("mode must be 'legacy' or 'slide10'")
    system_path = output_dir / "SYSTEM.md"
    if mode == "slide10":
        system_text = SLIDE10_SYSTEM_PROMPT.replace("{BATCH_SIZE}", str(chunk_size)) + "\n"
    else:
        system_text = system_path.read_text(encoding="utf-8") if system_path.exists() else SYSTEM_PROMPT + "\n"
    skill_text = skill_path.read_text(encoding="utf-8")
    composer_text = composer_skill_path.read_text(encoding="utf-8")
    system_path.write_text(system_text, encoding="utf-8")
    shutil.copyfile(skill_path, output_dir / "SKILL.md")
    shutil.copyfile(composer_skill_path, output_dir / "MANIM_COMPOSER.md")
    if mode == "slide10":
        shutil.copyfile(repository_root / "configs/slide_roles.yaml", output_dir / "slide_roles.yaml")

    for batch_index in range(batch_count):
        start = batch_index * chunk_size
        batch = records[start : start + chunk_size]
        items = [render_record(record, start + offset + 1) for offset, record in enumerate(batch)]
        batch_path = output_dir / f"batch_{batch_index + 1:03d}.jsonl"
        with batch_path.open("w", encoding="utf-8") as handle:
            for item in items:
                handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
        bundle_dir = output_dir / f"batch_{batch_index + 1:03d}"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(batch_path, bundle_dir / batch_path.name)
        (bundle_dir / "SYSTEM.md").write_text(system_text, encoding="utf-8")
        shutil.copyfile(skill_path, bundle_dir / "SKILL.md")
        shutil.copyfile(composer_skill_path, bundle_dir / "MANIM_COMPOSER.md")
        if mode == "slide10":
            shutil.copyfile(repository_root / "configs/slide_roles.yaml", bundle_dir / "slide_roles.yaml")
        write_combined_markdown(
            bundle_dir,
            batch_path.stem,
            batch_path.read_text(encoding="utf-8"),
            system_text,
            skill_text,
            composer_text,
        )

    manifest = {
        "input_records": len(records),
        "chunk_size": chunk_size,
        "mode": mode,
        "batch_count": batch_count,
        "batches": [
            {
                "file": f"batch_{index + 1:03d}.jsonl",
                "bundle": f"batch_{index + 1:03d}/",
                "start": index * chunk_size + 1,
                "end": min((index + 1) * chunk_size, len(records)),
                "count": len(records[index * chunk_size : (index + 1) * chunk_size]),
            }
            for index in range(batch_count)
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return batch_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="source JSONL file")
    parser.add_argument("output_dir", type=Path, help="directory for ChatUI files")
    parser.add_argument("--chunk-size", type=int, default=10, help="items per JSONL file (default: 10)")
    parser.add_argument("--mode", choices=("legacy", "slide10"), default="legacy")
    parser.add_argument("--limit", type=int, help="only prepare the first N source records")
    args = parser.parse_args()

    records = load_records(args.input)
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("limit must be at least 1")
        records = records[: args.limit]
    batch_count = write_batches(records, args.output_dir, args.chunk_size, mode=args.mode)
    print(f"Wrote {batch_count} ChatUI batches from {len(records)} records to {args.output_dir}")


if __name__ == "__main__":
    main()