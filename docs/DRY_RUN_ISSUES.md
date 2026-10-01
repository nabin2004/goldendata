# Dry-Run Rendering Issues

## Run

- **Command:** `uv run python -m manim_aos_data.cli render --dry-run-only --workers 5`
- **Backend:** local
- **Samples attempted:** 149
- **Successful attempts:** 142
- **Failed attempts:** 7
- **Unique failing sample IDs:** 3
- **Concurrency:** 5 workers
- **Manim:** 0.19.2
- **Run status:** completed

The counts above are attempt counts. The input contains repeated sample IDs, so one unique ID can appear more than once in the run.

## Failure Summary

| Sample ID | Attempts | Failures | Reason | Error |
|---|---:|---:|---|---|
| `r00009` | 3 | 3 | `TIMEOUT` | `Dry run timed out` |
| `r00068` | 2 | 2 | `DRY_RUN_FAIL` | `TypeError: Code.__init__() got an unexpected keyword argument 'font_size'` |
| `r00094` | 2 | 2 | `DRY_RUN_FAIL` | `TypeError: Code.__init__() got an unexpected keyword argument 'font_size'` |

## Root Causes

### `r00009`: dry-run timeout

The scene contains several voiceover sections and animation waits. The dry-run path was still doing work that is unnecessary for construction validation, particularly voiceover generation and timing setup. This exceeded the renderer timeout.

**Classification:** performance/validation-path issue, not a Python or Manim API error.

### `r00068` and `r00094`: invalid `Code` keyword

Both scenes construct Manim's `Code` mobject with `font_size=18`. Manim CE 0.19.2 does not accept `font_size` in `Code.__init__`.

The installed signature accepts `code_string`, `formatter_style`, `language`, and related parameters. It does not accept `font_size` or the legacy `style` spelling.

**Classification:** dataset API incompatibility.

## Repairs Applied After This Run

- Added the `manim-voiceover[transcribe]` dependency so the configured transcription stack is reproducible.
- Added five-worker rendering with duplicate-ID serialization in `src/manim_aos_data/cli.py`.
- Added deterministic dry-run behavior that skips TTS/transcription work and bookmark timing waits.
- Added a compatibility normalization for legacy `Code` kwargs in `src/manim_aos_data/render.py`.
- Added `scripts/repair_validated_code_api.py` and ran it against `data/canonical/validated.jsonl`.
- The canonical repair reported **4 records repaired**, covering the repeated `r00068` and `r00094` records. A backup was written to `data/canonical/validated.jsonl.bak`.

## Required Verification

Rerun the full command after the canonical repair:

```bash
env RENDER_BACKEND=local uv run python -m manim_aos_data.cli render \
  --dry-run-only --workers 5
```

Expected result: no `DRY_RUN_FAIL` entries for `r00068` or `r00094`, and no timeout for `r00009` under the dry-run-only path.

## Scope Note

This report covers the 149-sample validated render run shown in the terminal output. It does not certify the separate `data/qwen_manimator_master_with_skill.jsonl` dataset, which has a different chat-message schema and requires its own extraction/verification run.

## Chat Dataset Run

The separate chat-schema dataset was subsequently tested with:

```bash
uv run python -u scripts/dry_run_samples.py \
  --input data/qwen_manimator_master_with_skill.jsonl \
  --out-dir data/rendered/qwen_master_with_skill \
  --workers 5 --timeout 180
```

Results:

- **Samples loaded:** 785
- **Passed:** 291
- **Failed:** 494
- **Pass rate:** 37.1%
- **Concurrency:** 5 workers

### Observed Failure Families

| Failure family | Representative error | Impact |
|---|---|---|
| Missing `text=` in voiceover calls | `self.voiceover(text("...") as tracker:` followed by `SyntaxError` | Large group of records cannot be parsed as Python |
| Legacy speech service import | `ModuleNotFoundError: No module named 'tools'` for `tools.aos_speech_service` | Legacy records cannot import the scene |
| Legacy speech service symbol | `NameError: name 'AOSSpeechService' is not defined` | Related legacy records fail during `construct()` |
| Missing scene class | `NO_SCENE_CLASS` | Tail records did not contain a parseable class definition |
| Unicode punctuation in Python | `SyntaxError: invalid character '“' (U+201C)` | At least one record contains non-ASCII quote syntax |
| Other syntax corruption | Examples include `title.to_edge( is UP)` and malformed voiceover parentheses | Individual records require syntax repair or rejection |

The full run output establishes the scale of the problem but does not preserve a machine-readable per-record error log. The next repair pass should write each result to JSONL as it runs, then group failures by normalized error type before modifying the dataset.

## Targeted Repair Plan

The repair pass for the chat dataset uses this order:

1. Extract the assistant's Python block from each `messages` record.
2. Repair deterministic syntax patterns: malformed `voiceover(text(...))`, mismatched voiceover parentheses, curly quotes, string-valued `self.wait`, malformed `.to_edge(...)`, and unescaped LaTeX strings.
3. Replace the unavailable legacy `tools.aos_speech_service.AOSSpeechService` with the repository-standard `GTTSService(transcription_model="base")`.
4. Restore the canonical eight-key Plan, required scene structure, and bookmark parity.
5. Preserve records without an extractable scene as explicit unfixable/rejection records rather than inventing code.
6. Run Manim dry-run validation with five workers and a per-sample timeout.
7. Promote only records that pass syntax, API, bookmark, and dry-run checks.

Repair command used:

```bash
uv run python diagnose_and_repair.py \
  --input data/qwen_manimator_master_with_skill.jsonl \
  --output data/qwen_manimator_master_with_skill_repaired.jsonl
```

The repaired output is separate from the source dataset. The initial repair pass reported 785 syntactically valid/repaired records, 785 canonicalized records, and 0 unfixable records. A 10-record smoke dry-run reported 9 passes and one timeout for `sample_0006`; that sample is structurally valid and is being treated as a slow-scene threshold issue, not silently marked as valid.