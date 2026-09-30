#!/usr/bin/env python3
"""
scripts/split_batch.py
----------------------
Split a raw Qwen ChatUI batch output (100 samples) into individual files.

Usage:
    python scripts/split_batch.py raw_batch_001.txt data/canonical_manual/

The input file must contain samples separated by a line containing exactly:
    --- SAMPLE END ---

Each sample must contain a <Plan>...</Plan> block and a ```python ... ``` block
(the two-block canonical contract from docs/SPEC.md).

Outputs:
    data/canonical_manual/sample_NNN.py   ← full two-block text
    logs/rejections.jsonl                 ← appended for any skipped samples
"""

import sys
import json
import pathlib
import re
import datetime

SEPARATOR = r"^--- SAMPLE END ---$"
PYTHON_BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)
PLAN_BLOCK = re.compile(r"<Plan>(.*?)</Plan>", re.DOTALL)


def log_rejection(log_path: pathlib.Path, sample_id: str, reason: str, detail: str = ""):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "id": sample_id,
        "stage": "manual_split",
        "reason_code": reason,
        "detail": detail,
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }
    with log_path.open("a") as f:
        f.write(json.dumps(record) + "\n")
    print(f"  [REJECT] {sample_id}: {reason} — {detail}")


def split_batch(raw_file: str, out_dir: str, batch_name: str = None) -> None:
    raw_path = pathlib.Path(raw_file)
    out_path = pathlib.Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    log_path = pathlib.Path("logs/rejections.jsonl")
    batch_prefix = batch_name or raw_path.stem

    raw_text = raw_path.read_text(encoding="utf-8")
    samples = re.split(SEPARATOR, raw_text, flags=re.MULTILINE)

    saved = 0
    rejected = 0

    for i, raw_sample in enumerate(samples, 1):
        sample_id = f"{batch_prefix}_sample_{i:03d}"
        text = raw_sample.strip()

        if not text:
            continue  # blank segment between separators — skip silently

        # Check for Plan block
        if not PLAN_BLOCK.search(text):
            log_rejection(log_path, sample_id, "NOT_TWO_BLOCK", "no <Plan>…</Plan> found")
            rejected += 1
            continue

        # Check for python block
        py_match = PYTHON_BLOCK.search(text)
        if not py_match:
            log_rejection(log_path, sample_id, "NOT_TWO_BLOCK", "no ```python block found")
            rejected += 1
            continue

        # Quick bookmark parity check (non-blocking — just warn)
        narration_bookmarks = set(re.findall(r"<bookmark mark='(\w+)'/>", text))
        wait_bookmarks = set(re.findall(r'wait_until_bookmark\("(\w+)"\)', text))
        if narration_bookmarks != wait_bookmarks:
            missing_in_code = narration_bookmarks - wait_bookmarks
            missing_in_narr = wait_bookmarks - narration_bookmarks
            detail = f"narration has {narration_bookmarks}, code has {wait_bookmarks}"
            log_rejection(log_path, sample_id, "BOOKMARK_SET_EQUALITY", detail)
            # Still save — repair agent will fix it
            print(f"  [WARN] {sample_id}: bookmark mismatch — saved anyway for repair")

        out_file = out_path / f"{sample_id}.py"
        out_file.write_text(text, encoding="utf-8")
        print(f"  [OK] saved {out_file.name}")
        saved += 1

    print(f"\nDone. Saved: {saved}  Rejected: {rejected}")
    if rejected:
        print(f"Rejections logged to {log_path}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    raw_file = sys.argv[1]
    out_dir = sys.argv[2]
    batch_name = sys.argv[3] if len(sys.argv) > 3 else None
    split_batch(raw_file, out_dir, batch_name)


if __name__ == "__main__":
    main()
