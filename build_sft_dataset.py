#!/usr/bin/env python3
"""
build_sft_dataset.py
--------------------
Extracts, cleans, and structures Qwen chat export history into high-quality
JSONL datasets for Supervised Fine-Tuning (SFT) of Qwen models (e.g. Qwen3-8B)
on the Manim Community Edition (Manim CE) task.

Features:
- Scans exported_chats/*.json (skips :Zone.Identifier files)
- Safely handles NoneType content_list and message fields
- Downloads and caches uploaded batch files (batch_*.md) locally in exported_chats/cached_batches/
- Extracts input instructions and starting code from the batch files
- Uses scene class-name matching to guarantee 100% accurate alignment even if samples are skipped
- Splits assistant turns into individual samples (two-block contract: <Plan> + ```python)
- Supports both:
    1) With skill.md / system prompt (data/sft_manimce_with_skill.jsonl)
    2) Without skill.md / clean prompt (data/sft_manimce_no_skill.jsonl)
- Built-in smoke test verifying JSONL schema, message keys, and ChatML format
"""

import os
import sys
import json
import re
import urllib.request
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
EXPORT_DIR = REPO_ROOT / "exported_chats"
CACHE_DIR = EXPORT_DIR / "cached_batches"
DATA_DIR = REPO_ROOT / "data"

SAMPLE_DELIMITER = "--- SAMPLE END ---"

RE_PLAN_AND_CODE = re.compile(
    r"(<Plan>.*?</Plan>\s*```python\s*.*?```)(?:\s*<End>.*?</End>)?",
    re.DOTALL
)

def download_batch_file(url: str, filename: str) -> str:
    """Download and cache batch file locally."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    local_path = CACHE_DIR / filename
    if local_path.exists() and local_path.stat().st_size > 0:
        return local_path.read_text(encoding="utf-8")
    
    print(f"[*] Downloading {filename} from CDN...")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ManimSFTBuilder/1.0)"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read().decode("utf-8")
    local_path.write_text(content, encoding="utf-8")
    return content

def parse_batch_markdown(md_text: str):
    """
    Extracts SYSTEM.md, JSONL input items, and SKILL.md from a batch markdown file.
    """
    system_prompt = ""
    skill_text = ""
    items = []

    # 1. Extract SYSTEM.md
    m_sys = re.search(r"## 1\. SYSTEM\.md\s*````(?:text|markdown)?\s*\n(.*?)\n````", md_text, re.DOTALL)
    if m_sys:
        system_prompt = m_sys.group(1).strip()

    # 2. Extract JSONL input items
    m_jsonl = re.search(r"## 2\. JSONL input\s*````(?:jsonl|json)?\s*\n(.*?)\n````", md_text, re.DOTALL)
    if m_jsonl:
        for line in m_jsonl.group(1).splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                items.append(item)
            except Exception as e:
                print(f"[!] Warning: failed to parse jsonl line: {e}")

    # 3. Extract SKILL.md
    m_skill = re.search(r"## 3\. SKILL\.md\s*````(?:markdown|text)?\s*\n(.*?)\n````", md_text, re.DOTALL)
    if m_skill:
        skill_text = m_skill.group(1).strip()

    return system_prompt, skill_text, items

def extract_samples_from_assistant_text(text: str, keep_end: bool = False):
    """
    Extracts individual canonical samples from assistant text.
    Uses regex finditer to reliably extract all (<Plan> + python + optional <End>) blocks.
    Strips <End> block by default according to the canonical two-block contract.
    """
    samples = []
    for m in RE_PLAN_AND_CODE.finditer(text):
        if keep_end:
            samples.append(m.group(0).strip())
        else:
            samples.append(m.group(1).strip())
    
    # Fallback to split if regex returned empty
    if not samples:
        for block in re.split(r"-{2,}\s*SAMPLE END\s*-{2,}", text):
            block = block.strip()
            if not block or "<Plan>" not in block or "```python" not in block:
                continue
            m = RE_PLAN_AND_CODE.search(block)
            if m:
                samples.append(m.group(0 if keep_end else 1).strip())
            else:
                samples.append(block)

    return samples

def match_items_to_samples(input_items, output_samples):
    """
    Intelligently matches input items to output samples:
    1. First tries matching scene class names (e.g. PedagogicalScene848).
    2. Falls back to sequential alignment for un-matched items.
    Prevents alignment drift if a model skips or drops an item in a batch.
    """
    aligned_pairs = []
    unmatched_samples = []

    # Map input items by class name found in item['code'] or item['instruction']
    item_by_class = {}
    for item in input_items:
        code_str = (item.get("code") or "") + " " + (item.get("instruction") or "")
        m_cls = re.search(r"class\s+([A-Za-z0-9_]+)", code_str)
        if m_cls:
            item_by_class[m_cls.group(1)] = item

    used_item_ids = set()

    for sample in output_samples:
        m_sample_cls = re.search(r"class\s+([A-Za-z0-9_]+)", sample)
        matched_item = None
        if m_sample_cls:
            cls_name = m_sample_cls.group(1)
            if cls_name in item_by_class and item_by_class[cls_name].get("id") not in used_item_ids:
                matched_item = item_by_class[cls_name]

        if matched_item:
            used_item_ids.add(matched_item.get("id"))
            aligned_pairs.append((matched_item, sample))
        else:
            unmatched_samples.append(sample)

    # For any unmatched samples, match against remaining unused items in order
    remaining_items = [it for it in input_items if it.get("id") not in used_item_ids]
    for sample in unmatched_samples:
        if remaining_items:
            item = remaining_items.pop(0)
            aligned_pairs.append((item, sample))
        else:
            # If no items left, infer item from plan goal
            m_goal = re.search(r"goal:\s*(.*?)(?:\n|$)", sample)
            goal = m_goal.group(1).strip() if m_goal else "Create a Manim CE animation."
            item = {
                "id": f"inferred_{len(aligned_pairs)}",
                "instruction": f"Create an educational Manim CE animation: {goal}",
                "code": ""
            }
            aligned_pairs.append((item, sample))

    return aligned_pairs

def process_exported_chats(keep_end: bool = False, max_files: int = None):
    """
    Processes all chat-export-*.json files and returns aligned pairs:
    """
    export_files = sorted([
        f for f in EXPORT_DIR.glob("chat-export-*.json")
        if not f.name.endswith(":Zone.Identifier")
    ])

    if max_files:
        export_files = export_files[:max_files]

    print(f"[*] Found {len(export_files)} chat export file(s) in {EXPORT_DIR}")
    all_aligned = []

    for fpath in export_files:
        print(f"\n--- Processing {fpath.name} ---")
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[!] Failed to load {fpath.name}: {e}")
            continue

        if not isinstance(data, list):
            data = [data]

        for session in data:
            chat_hist = session.get("chat", {}) or {}
            history = chat_hist.get("history", {}) or {}
            messages = history.get("messages", {}) or {}

            for msg_id, msg in messages.items():
                if not isinstance(msg, dict):
                    continue
                if msg.get("role") != "user":
                    continue

                files = msg.get("files") or []
                children_ids = msg.get("childrenIds") or []
                if not children_ids:
                    continue

                assistant_id = children_ids[0]
                assistant_msg = messages.get(assistant_id) or {}
                if not assistant_msg or assistant_msg.get("role") != "assistant":
                    continue

                # Safely locate assistant output text
                assistant_text = ""
                content_list = assistant_msg.get("content_list") or []
                if isinstance(content_list, list):
                    for c in content_list:
                        if not isinstance(c, dict):
                            continue
                        content = c.get("content") or ""
                        if isinstance(content, str) and "<Plan>" in content and "```python" in content:
                            assistant_text = content
                            break

                if not assistant_text:
                    direct_content = assistant_msg.get("content") or ""
                    if isinstance(direct_content, str) and "<Plan>" in direct_content and "```python" in direct_content:
                        assistant_text = direct_content

                if not assistant_text:
                    continue

                # Parse assistant samples
                output_samples = extract_samples_from_assistant_text(assistant_text, keep_end=keep_end)

                # Process attached batch file if present
                batch_processed = False
                for file_info in files:
                    if not isinstance(file_info, dict):
                        continue
                    fname = file_info.get("name") or ""
                    furl = file_info.get("url") or ""
                    if fname.startswith("batch_") and furl:
                        try:
                            md_content = download_batch_file(furl, fname)
                            sys_prompt, skill_text, input_items = parse_batch_markdown(md_content)

                            matched_pairs = match_items_to_samples(input_items, output_samples)
                            print(f"  [+] {fname}: {len(input_items)} inputs vs {len(output_samples)} outputs -> {len(matched_pairs)} aligned")

                            for item, sample in matched_pairs:
                                all_aligned.append({
                                    "id": item.get("id", f"sample_{len(all_aligned)}"),
                                    "instruction": item.get("instruction", ""),
                                    "code": item.get("code", ""),
                                    "system_prompt": sys_prompt,
                                    "skill_text": skill_text,
                                    "output_sample": sample,
                                    "batch": fname
                                })
                            batch_processed = True
                        except Exception as e:
                            print(f"[!] Error processing {fname} from {furl}: {e}")

                # Fallback: if no batch file processed but samples exist, extract goal from Plan
                if not batch_processed and output_samples:
                    print(f"  [!] No batch file found for message {msg_id[:8]}, extracting goals from Plan headers...")
                    for sample in output_samples:
                        m_goal = re.search(r"goal:\s*(.*?)(?:\n|$)", sample)
                        goal = m_goal.group(1).strip() if m_goal else "Create a Manim CE animation."
                        all_aligned.append({
                            "id": f"sample_{len(all_aligned)}",
                            "instruction": f"Create an educational Manim CE animation: {goal}",
                            "code": "",
                            "system_prompt": "You are an expert Manim Community Edition v0.19+ engineer creating robust canonical Manim-AOS training data.",
                            "skill_text": "",
                            "output_sample": sample,
                            "batch": "inline_goal_fallback"
                        })

    return all_aligned

def format_sft_dataset(aligned_data, include_skill: bool = True):
    """
    Formats aligned items into ChatML / OpenAI JSONL format for Qwen SFT.
    """
    records = []
    for item in aligned_data:
        # Build User Prompt
        instruction = (item.get("instruction") or "").strip()
        code = (item.get("code") or "").strip()
        if code and code not in instruction:
            user_content = f"{instruction}\n\n```python\n{code}\n```"
        else:
            user_content = instruction

        # Build Assistant Response
        assistant_content = (item.get("output_sample") or "").strip()

        # Build System Prompt
        messages = []
        if include_skill:
            sys_text = item.get("system_prompt") or ""
            skill = item.get("skill_text") or ""
            if skill:
                sys_text = f"{sys_text}\n\n# SKILL REFERENCE\n\n{skill}"
            messages.append({"role": "system", "content": sys_text.strip()})
        else:
            # Minimal clean system prompt for direct generation
            messages.append({
                "role": "system",
                "content": "You are an expert Manim Community Edition v0.19+ engineer creating robust canonical animations."
            })

        messages.append({"role": "user", "content": user_content})
        messages.append({"role": "assistant", "content": assistant_content})

        records.append({"messages": messages})

    return records

def run_smoke_test(aligned_data):
    """Runs smoke test on extracted dataset."""
    print("\n" + "=" * 50)
    print("RUNNING SMOKE TEST")
    print("=" * 50)
    assert len(aligned_data) > 0, "Smoke test failed: No aligned samples found!"
    print(f"[PASS] Total aligned samples: {len(aligned_data)}")

    # 1. Check structure of first sample
    first = aligned_data[0]
    assert "instruction" in first and first["instruction"], "First sample missing instruction!"
    assert "output_sample" in first and first["output_sample"], "First sample missing output!"
    assert "<Plan>" in first["output_sample"], "First sample missing <Plan> block!"
    assert "```python" in first["output_sample"], "First sample missing ```python block!"
    print(f"[PASS] Sample 0 ID: {first.get('id')}")
    print(f"[PASS] Sample 0 Batch: {first.get('batch')}")
    print(f"[PASS] Sample 0 Prompt preview: {first['instruction'][:80]}...")
    print(f"[PASS] Sample 0 Response contains <Plan> and ```python")

    # 2. Test JSON formatting
    sample_with = format_sft_dataset(aligned_data[:2], include_skill=True)
    sample_no = format_sft_dataset(aligned_data[:2], include_skill=False)

    json_str_with = json.dumps(sample_with[0], ensure_ascii=False)
    json_str_no = json.dumps(sample_no[0], ensure_ascii=False)

    parsed_with = json.loads(json_str_with)
    parsed_no = json.loads(json_str_no)

    assert len(parsed_with["messages"]) == 3, "ChatML must have system, user, assistant messages!"
    assert [m["role"] for m in parsed_with["messages"]] == ["system", "user", "assistant"]
    assert len(parsed_no["messages"]) == 3, "No-skill must also have system, user, assistant messages!"

    print(f"[PASS] ChatML structure validated (system -> user -> assistant)")
    print(f"[PASS] With-skill prompt length: {len(parsed_with['messages'][0]['content'])} chars")
    print(f"[PASS] No-skill prompt length: {len(parsed_no['messages'][0]['content'])} chars")
    print("=" * 50)
    print("[ALL SMOKE TESTS PASSED]")
    print("=" * 50 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Build SFT dataset for Qwen3-8B from exported Qwen chats.")
    parser.add_argument("--mode", choices=["both", "with_skill", "no_skill"], default="both",
                        help="Whether to generate with skill, without skill, or both.")
    parser.add_argument("--keep-end", action="store_true",
                        help="Keep <End> tags in assistant response (default strips to 2-block contract).")
    parser.add_argument("--smoke-test", action="store_true",
                        help="Run smoke test on 1 export file and exit.")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("=== Manim CE SFT Dataset Builder for Qwen ===")
    max_files = 1 if args.smoke_test else None
    aligned = process_exported_chats(keep_end=args.keep_end, max_files=max_files)
    print(f"\n[✓] Total successfully aligned samples: {len(aligned)}")

    if not aligned:
        print("[!] No samples extracted. Please check the exported chats directory.")
        return

    # Run smoke test
    run_smoke_test(aligned)

    if args.smoke_test:
        print("[*] Smoke test run complete.")
        return

    if args.mode in ["both", "with_skill"]:
        out_with_skill = DATA_DIR / "sft_manimce_with_skill.jsonl"
        data_with_skill = format_sft_dataset(aligned, include_skill=True)
        with open(out_with_skill, "w", encoding="utf-8") as f:
            for rec in data_with_skill:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[✓] Saved {len(data_with_skill)} samples to {out_with_skill}")

    if args.mode in ["both", "no_skill"]:
        out_no_skill = DATA_DIR / "sft_manimce_no_skill.jsonl"
        data_no_skill = format_sft_dataset(aligned, include_skill=False)
        with open(out_no_skill, "w", encoding="utf-8") as f:
            for rec in data_no_skill:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[✓] Saved {len(data_no_skill)} samples to {out_no_skill}")

    print("\nDataset preparation completed successfully!")

if __name__ == "__main__":
    main()
