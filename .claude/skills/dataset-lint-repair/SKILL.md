---
name: dataset-lint-repair
description: Run the deterministic linter on dataset samples, interpret rule codes, and produce minimal-diff repairs and V1->diagnosis->V2 repair traces. Use when a sample fails lint, render or Omni QC, or when building DPO/repair data.
---
# Lint and repair

Run: `python -m manim_aos_data.cli lint path/to/response.txt` (add `--no-manim` if Manim is not importable).
Rules: `docs/LINTER_RULES.md`. Rejections go to `logs/rejections.jsonl` with a reason code; never drop silently.

Repair procedure
1. Read the diagnosis (lint issue, render stderr tail, or Omni flags).
2. Prefer a deterministic auto-fix (raw prefix, unicode math, ShowCreation, banned kwarg). Use the LLM only for bookmark mismatches and layout.
3. Smallest possible diff; do not restyle working code or change narration unless a bookmark requires it.
4. Re-run lint, then render. Save the trace to `data/repairs/` as `{signal, v1_code, diagnosis, fix_summary, v2_code, diff_lines}`.
5. DPO pair: chosen = verified V2, rejected = failing V1.
