#!/usr/bin/env python3
"""
scripts/fix_dataset_targeted.py
-------------------------------
Performs targeted, deterministic repairs on data/qwen3_8b_manimator_master_sft.jsonl:
1. Fixes NameError: name 'VoiceoverScene' is not defined & 'GTTSService' is not defined
   by injecting:
     from manim_voiceover import VoiceoverScene
     from manim_voiceover.services.gtts import GTTSService
2. Fixes EOFError: EOF when reading a line (Whisper stdin prompt in headless Docker)
   by removing `transcription_model="base"` from GTTSService calls.
3. Preserves a backup of the original dataset at .jsonl.bak before patching.
"""

import sys
import json
import shutil
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = REPO_ROOT / "data" / "qwen3_8b_manimator_master_sft.jsonl"

def apply_targeted_fixes(code: str) -> tuple[str, bool, list[str]]:
    """Applies import and Whisper prompt fixes. Returns (new_code, was_modified, reasons)."""
    if not code:
        return code, False, []

    reasons = []
    new_code = code

    # 1. Strip transcription_model kwarg from GTTSService
    stripped_code = re.sub(
        r'GTTSService\(\s*transcription_model\s*=\s*["\'][^"\']*["\']\s*,?\s*',
        'GTTSService(',
        new_code
    )
    stripped_code = re.sub(r'GTTSService\(\s*,\s*', 'GTTSService(', stripped_code)
    if stripped_code != new_code:
        reasons.append("removed transcription_model kwarg")
        new_code = stripped_code

    # 2. Check and inject missing imports
    lines = new_code.splitlines()
    has_vo_import = any(
        ("from manim_voiceover import" in l and "VoiceoverScene" in l) or
        ("import manim_voiceover" in l)
        for l in lines
    )
    has_gtts_import = any(
        ("from manim_voiceover.services.gtts import" in l and "GTTSService" in l) or
        ("import manim_voiceover.services.gtts" in l)
        for l in lines
    )

    needed_imports = []
    if "VoiceoverScene" in new_code and not has_vo_import:
        needed_imports.append("from manim_voiceover import VoiceoverScene")
        reasons.append("added VoiceoverScene import")
    if "GTTSService" in new_code and not has_gtts_import:
        needed_imports.append("from manim_voiceover.services.gtts import GTTSService")
        reasons.append("added GTTSService import")

    if needed_imports:
        insert_idx = 0
        for i, l in enumerate(lines):
            if l.startswith("from manim import") or l.startswith("import manim"):
                insert_idx = i + 1
        for imp in reversed(needed_imports):
            lines.insert(insert_idx, imp)
        new_code = "\n".join(lines)

    return new_code, bool(reasons), reasons

def main():
    target_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATASET
    if not target_path.exists():
        print(f"[!] Error: Dataset file not found at {target_path}")
        sys.exit(1)

    backup_path = target_path.with_suffix(".jsonl.bak")
    print(f"[*] Creating safety backup at: {backup_path}")
    shutil.copy2(target_path, backup_path)

    total_samples = 0
    modified_samples = 0
    reason_stats = {}
    new_records = []

    print(f"[*] Scanning and repairing samples in: {target_path}...")
    with open(target_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line_str = line.strip()
            if not line_str:
                continue
            total_samples += 1
            rec = json.loads(line_str)
            sample_modified = False

            for m in rec.get("messages", []):
                if m.get("role") == "assistant":
                    content = m.get("content", "")
                    m_code = re.search(r"```python\s*(.*?)\s*```", content, re.DOTALL)
                    if m_code:
                        old_code = m_code.group(1).strip()
                        new_code, was_mod, reasons = apply_targeted_fixes(old_code)
                        if was_mod:
                            m["content"] = content[:m_code.start(1)] + "\n" + new_code + "\n" + content[m_code.end(1):]
                            sample_modified = True
                            for r in reasons:
                                reason_stats[r] = reason_stats.get(r, 0) + 1

            if sample_modified:
                modified_samples += 1

            new_records.append(json.dumps(rec, ensure_ascii=False) + "\n")

    with open(target_path, "w", encoding="utf-8") as f:
        f.writelines(new_records)

    print("\n" + "=" * 65)
    print("✓ TARGETED REPAIRS COMPLETE")
    print("=" * 65)
    print(f"Total Samples Scanned:   {total_samples}")
    print(f"Samples Fixed:           {modified_samples} ({round(modified_samples / max(1, total_samples) * 100, 1)}%)")
    print("Fix Breakdown:")
    for r, count in sorted(reason_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {r}: {count} scene(s)")
    print(f"\nSafety backup saved to:  {backup_path}")
    print(f"Patched dataset:         {target_path}")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    main()
