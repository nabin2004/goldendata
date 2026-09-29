---
description: Rewrite a legacy Manim sample into the canonical Manim-AOS format
mode: subagent
---
Follow AGENTS.md and docs/SPEC.md. Input: a triage record. Output: canonical candidate JSON.
Use prompts/transform.md. Always verify uncertain APIs with `python scripts/docs/api_lookup.py <Name>`.
After writing, run `python -m manim_aos_data.cli lint <file>` and fix failures (max 3 rounds).
