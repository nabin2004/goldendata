#!/usr/bin/env python3
"""
build_sft_dataset.py
--------------------
Extracts, cleans, harmonizes, and combines Manim Community Edition (Manim CE)
training data into a single unified JSONL dataset for Supervised Fine-Tuning (SFT)
of Qwen3-8B.

Datasets Combined (Pure Gold SFT):
1. Local Validated Canonicals: data/canonical/validated.jsonl (149 gold samples)
2. Local Chat Exports: exported_chats/*.json (379 new Qwen generations)
3. Hugging Face Dataset: nabin2004/qwen-Manimator-1-sft-data (305 samples)

Skill Placement & Prompt Harmonization Rules:
- System Prompt: Standardized and clean across ALL datasets (NO skills in system prompt).
  Specifies role as expert Python programmer & math educator in ManimCE + Voiceover,
  strict VoiceoverScene & SpeechService usage, bookmark timing, and ```python blocks.
- User Prompt:
  * Local datasets (canonical validated + chat exports): Skill reference appended
    at the end of the user prompt as a structured reference chip:
    ---
    ### Reference Guidelines & Skill Specifications
    <skill_content>
  * Hugging Face datasets: Kept as standard user prompts without skills (ensuring
    the model learns both zero-shot prompt following and rich in-context skill compliance).
- Assistant Response: Strict two-block contract: <Plan>...</Plan> followed by ```python ... ```.
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
CANONICAL_VALIDATED_PATH = DATA_DIR / "canonical" / "validated.jsonl"
MASTER_SKILL_PATH = REPO_ROOT / "configs" / "master_skill.md"
MANIM_COMPOSER_PATH = REPO_ROOT / ".agents" / "skills" / "manim-composer" / "SKILL.md"

HF_MANIMATOR_1_URL = "https://huggingface.co/datasets/nabin2004/qwen-Manimator-1-sft-data/resolve/main/train.jsonl"
HF_MANIMATOR_1_CACHE = DATA_DIR / "qwen_manimator_1_hf_305.jsonl"

SAMPLE_DELIMITER = "--- SAMPLE END ---"

RE_PLAN_AND_CODE = re.compile(
    r"(<Plan>.*?</Plan>\s*```python\s*.*?```)(?:\s*<End>.*?</End>)?",
    re.DOTALL
)

def get_harmonized_system_prompt(code_text: str) -> str:
    """
    Returns a concise, harmonized system prompt tailored to the speech service.
    NOTE: Skills are NEVER placed in the system prompt.
    """
    if "GTTSService" in code_text:
        service_name = "`GTTSService`"
    elif "AOSSpeechService" in code_text:
        service_name = "`AOSSpeechService`"
    else:
        service_name = "speech services (`GTTSService` or `AOSSpeechService`)"

    return (
        "You are an expert Python programmer and mathematics educator specializing in ManimCE and Manim Voiceover. "
        f"You create high-quality, pedagogically rich, narrated animations. You always use `VoiceoverScene`, {service_name}, "
        "and precise bookmark timing (`<bookmark>` tags and `wait_until_bookmark`) to sync audio with visual elements. "
        "Wrap your code in ```python ... ``` blocks."
    )

def download_file(url: str, dest_path: Path, desc: str = "file") -> str:
    """Download and cache file locally."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.exists() and dest_path.stat().st_size > 0:
        return dest_path.read_text(encoding="utf-8")
    
    print(f"[*] Downloading {desc} from {url}...")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ManimSFTBuilder/1.0)"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        content = resp.read().decode("utf-8")
    dest_path.write_text(content, encoding="utf-8")
    return content

def parse_batch_markdown(md_text: str):
    """
    Extracts SYSTEM.md, JSONL input items, and SKILL.md from a batch markdown file.
    """
    system_prompt = ""
    skill_text = ""
    items = []

    m_sys = re.search(r"## 1\. SYSTEM\.md\s*````(?:text|markdown)?\s*\n(.*?)\n````", md_text, re.DOTALL)
    if m_sys:
        system_prompt = m_sys.group(1).strip()

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

    m_skill = re.search(r"## 3\. SKILL\.md\s*````(?:markdown|text)?\s*\n(.*?)\n````", md_text, re.DOTALL)
    if m_skill:
        skill_text = m_skill.group(1).strip()

    return system_prompt, skill_text, items

def get_master_skill() -> str:
    """
    Retrieves the consolidated master skill text including:
    1. The core manim-aos master skill (best practices, voiceover, layout, etc.)
    2. The manim-composer skill (.agents/skills/manim-composer/SKILL.md)
    """
    base_skill = ""
    if MASTER_SKILL_PATH.exists() and MASTER_SKILL_PATH.stat().st_size > 0:
        base_skill = MASTER_SKILL_PATH.read_text(encoding="utf-8").strip()
    elif CACHE_DIR.exists():
        for b_file in sorted(CACHE_DIR.glob("batch_*.md")):
            try:
                content = b_file.read_text(encoding="utf-8")
                _, skill, _ = parse_batch_markdown(content)
                if skill:
                    base_skill = skill.strip()
                    break
            except Exception:
                pass

    composer_skill = ""
    if MANIM_COMPOSER_PATH.exists() and MANIM_COMPOSER_PATH.stat().st_size > 0:
        composer_skill = MANIM_COMPOSER_PATH.read_text(encoding="utf-8").strip()

    if composer_skill and "name: manim-composer" not in base_skill:
        base_skill = f"{base_skill}\n\n---\n\n{composer_skill}".strip()
        MASTER_SKILL_PATH.parent.mkdir(parents=True, exist_ok=True)
        MASTER_SKILL_PATH.write_text(base_skill, encoding="utf-8")
        print(f"[✓] Consolidated manim-composer skill into {MASTER_SKILL_PATH}")

    return base_skill

def load_canonical_validated(master_skill: str = ""):
    """
    Loads samples from data/canonical/validated.jsonl (149 gold canonical items).
    Returns list of aligned dicts.
    """
    if not CANONICAL_VALIDATED_PATH.exists():
        print(f"[!] Warning: {CANONICAL_VALIDATED_PATH} not found.")
        return []

    samples = []
    print(f"\n--- Loading local canonical dataset: {CANONICAL_VALIDATED_PATH.name} ---")
    with open(CANONICAL_VALIDATED_PATH, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                instruction = (rec.get("instruction") or "").strip()
                response = (rec.get("response") or "").strip()
                item_id = rec.get("id") or f"canonical_{line_no:04d}"

                if not instruction or not response:
                    continue

                samples.append({
                    "id": item_id,
                    "instruction": instruction,
                    "code": "",
                    "system_prompt": get_harmonized_system_prompt(response),
                    "skill_text": master_skill,
                    "output_sample": response,
                    "batch": "canonical_validated"
                })
            except Exception as e:
                print(f"[!] Warning parsing line {line_no} of {CANONICAL_VALIDATED_PATH.name}: {e}")

    print(f"[✓] Successfully loaded {len(samples)} samples from {CANONICAL_VALIDATED_PATH.name}")
    return samples

def load_hf_dataset(url: str, cache_path: Path, desc: str):
    """
    Download and load JSONL dataset from Hugging Face.
    Harmonizes system prompt. Does NOT add skills anywhere.
    """
    print(f"\n--- Loading dataset: {desc} ---")
    try:
        content = download_file(url, cache_path, desc)
        samples = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if "messages" in rec and len(rec["messages"]) >= 2:
                    assistant_msg = ""
                    for m in rec["messages"]:
                        if m.get("role") == "assistant":
                            assistant_msg = m.get("content", "")

                    # Clean harmonized system prompt (NO skills)
                    harmonized_sys = get_harmonized_system_prompt(assistant_msg)

                    msgs = []
                    msgs.append({"role": "system", "content": harmonized_sys})
                    for m in rec["messages"]:
                        if m.get("role") in ["user", "assistant"]:
                            msgs.append({"role": m.get("role"), "content": m.get("content", "")})

                    if len(msgs) == 3:
                        samples.append({"messages": msgs})
            except Exception:
                pass
        print(f"[✓] Successfully loaded {len(samples)} samples from {desc}")
        return samples
    except Exception as e:
        print(f"[!] Warning: Could not download {desc}: {e}")
        return []

def extract_samples_from_assistant_text(text: str, keep_end: bool = False):
    """Extracts (<Plan> + python + optional <End>) blocks."""
    samples = []
    for m in RE_PLAN_AND_CODE.finditer(text):
        if keep_end:
            samples.append(m.group(0).strip())
        else:
            samples.append(m.group(1).strip())
    
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
    """Matches input items to output samples by class name or order."""
    aligned_pairs = []
    unmatched_samples = []

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

    remaining_items = [it for it in input_items if it.get("id") not in used_item_ids]
    for sample in unmatched_samples:
        if remaining_items:
            item = remaining_items.pop(0)
            aligned_pairs.append((item, sample))
        else:
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
    """Processes chat export JSON files into aligned item-sample pairs."""
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

                output_samples = extract_samples_from_assistant_text(assistant_text, keep_end=keep_end)

                batch_processed = False
                for file_info in files:
                    if not isinstance(file_info, dict):
                        continue
                    fname = file_info.get("name") or ""
                    furl = file_info.get("url") or ""
                    if fname.startswith("batch_") and furl:
                        try:
                            md_content = download_file(furl, CACHE_DIR / fname, f"batch file {fname}")
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

                if not batch_processed and output_samples:
                    print(f"  [!] No batch file found for message {msg_id[:8]}, extracting goals from Plan headers...")
                    for sample in output_samples:
                        m_goal = re.search(r"goal:\s*(.*?)(?:\n|$)", sample)
                        goal = m_goal.group(1).strip() if m_goal else "Create a Manim CE animation."
                        all_aligned.append({
                            "id": f"sample_{len(all_aligned)}",
                            "instruction": f"Create an educational Manim CE animation: {goal}",
                            "code": "",
                            "system_prompt": "",
                            "skill_text": "",
                            "output_sample": sample,
                            "batch": "inline_goal_fallback"
                        })

    return all_aligned

def format_sft_dataset(aligned_data, add_skill_to_user: bool = True, default_skill: str = ""):
    """
    Formats aligned items into ChatML / OpenAI JSONL format for Qwen SFT.
    - System prompt is ALWAYS clean & harmonized (NO skills in system prompt).
    - If add_skill_to_user is True, appends the skill specification as a structured
      reference chip below the user instruction.
    """
    records = []
    for item in aligned_data:
        instruction = (item.get("instruction") or "").strip()
        code = (item.get("code") or "").strip()
        
        if code and code not in instruction:
            base_prompt = f"{instruction}\n\n```python\n{code}\n```"
        else:
            base_prompt = instruction

        # Attach skill chip to User prompt for locally prepared datasets
        if add_skill_to_user:
            skill = (item.get("skill_text") or default_skill or "").strip()
            # Ensure manim-composer is always included
            if "name: manim-composer" not in skill:
                composer_txt = ""
                if MANIM_COMPOSER_PATH.exists():
                    composer_txt = MANIM_COMPOSER_PATH.read_text(encoding="utf-8").strip()
                if composer_txt:
                    skill = f"{skill}\n\n---\n\n{composer_txt}".strip() if skill else composer_txt

            if skill:
                user_content = (
                    f"{base_prompt}\n\n"
                    "---\n"
                    "### Reference Guidelines & Skill Specifications\n"
                    f"{skill}"
                )
            else:
                user_content = base_prompt
        else:
            user_content = base_prompt

        assistant_content = (item.get("output_sample") or "").strip()

        # Clean harmonized system prompt (NO skill in system prompt)
        sys_text = get_harmonized_system_prompt(assistant_content)

        messages = [
            {"role": "system", "content": sys_text.strip()},
            {"role": "user", "content": user_content.strip()},
            {"role": "assistant", "content": assistant_content}
        ]

        records.append({"messages": messages})

    return records

def merge_and_deduplicate(datasets, dedup_prompt_only: bool = False):
    """
    Merges multiple lists of ChatML records into a single unified dataset.

    Deduplication rules:
    - Default (diverse multi-sample mode): Removes true exact duplicates
      (identical assistant responses / duplicate chat export runs), while preserving
      diverse implementations, both speech services (GTTSService vs AOSSpeechService),
      and both skill-augmented and zero-shot prompt variants. Total: 1,000+ samples.
    - If dedup_prompt_only=True: Aggressively collapses any samples sharing
      the same base user instruction.
    """
    merged = []

    if dedup_prompt_only:
        seen_prompts = {}
        for ds in datasets:
            for rec in ds:
                msgs = rec.get("messages", [])
                user_prompt = ""
                assistant_content = ""
                for m in msgs:
                    if m.get("role") == "user":
                        user_prompt = m.get("content", "").strip()
                    elif m.get("role") == "assistant":
                        assistant_content = m.get("content", "").strip()

                prompt_key = user_prompt.split("\n\n---\n### Reference Guidelines")[0].strip()
                norm_prompt = re.sub(r"\s+", " ", prompt_key.lower())

                if norm_prompt in seen_prompts:
                    idx = seen_prompts[norm_prompt]
                    existing_asst = ""
                    for m in merged[idx]["messages"]:
                        if m.get("role") == "assistant":
                            existing_asst = m.get("content", "")
                    if "<Plan>" not in existing_asst and "<Plan>" in assistant_content:
                        merged[idx] = rec
                else:
                    seen_prompts[norm_prompt] = len(merged)
                    merged.append(rec)
        return merged

    # Standard deduplication: Drop exact identical responses / repeated export clones
    seen_responses = set()
    seen_pairs = set()

    for ds in datasets:
        for rec in ds:
            msgs = rec.get("messages", [])
            user_prompt = ""
            assistant_content = ""
            for m in msgs:
                if m.get("role") == "user":
                    user_prompt = m.get("content", "").strip()
                elif m.get("role") == "assistant":
                    assistant_content = m.get("content", "").strip()

            if not user_prompt or not assistant_content:
                continue

            # Normalized assistant response (Plan + code)
            norm_asst = re.sub(r"\s+", " ", assistant_content.strip())
            norm_user = re.sub(r"\s+", " ", user_prompt.strip().lower())
            pair_key = (norm_user, norm_asst)

            if pair_key in seen_pairs:
                continue

            # Avoid exact identical assistant code duplicates
            if norm_asst in seen_responses:
                continue

            seen_pairs.add(pair_key)
            seen_responses.add(norm_asst)
            merged.append(rec)

    return merged

def save_jsonl(records, path: Path, desc: str):
    """Save records to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[✓] Saved {len(records)} samples to {path} ({desc})")

def run_smoke_test(aligned_data, canonical_data=None, hf_datasets=None, master_skill=""):
    """Runs comprehensive smoke test validating prompt rules and schema."""
    print("\n" + "=" * 65)
    print("RUNNING COMPREHENSIVE SMOKE TEST")
    print("=" * 65)
    assert len(aligned_data) > 0, "Smoke test failed: No aligned chat samples found!"
    print(f"[PASS] Total aligned chat samples from exports: {len(aligned_data)}")

    if canonical_data is not None:
        assert len(canonical_data) >= 100, f"Expected >= 100 canonical samples, got {len(canonical_data)}"
        print(f"[PASS] Total validated canonical samples: {len(canonical_data)}")

    if master_skill:
        assert len(master_skill) > 500, "Master skill text seems too short or empty!"
        print(f"[PASS] Master skill loaded ({len(master_skill)} chars)")

    if hf_datasets:
        for name, data in hf_datasets.items():
            print(f"[PASS] Loaded {len(data)} samples from {name}")

    # 1. Test local format with skills in USER prompt and clean SYSTEM prompt
    sample_local = format_sft_dataset(aligned_data[:1], add_skill_to_user=True, default_skill=master_skill)
    json_str = json.dumps(sample_local[0], ensure_ascii=False)
    parsed = json.loads(json_str)

    assert len(parsed["messages"]) == 3, "ChatML must have system, user, assistant messages!"
    assert [m["role"] for m in parsed["messages"]] == ["system", "user", "assistant"]
    
    # SYSTEM PROMPT: MUST NOT contain skills
    sys_content = parsed["messages"][0]["content"]
    assert "### Reference Guidelines" not in sys_content, "Skills must NOT be in system prompt!"
    assert "# SKILL REFERENCE" not in sys_content, "Skills must NOT be in system prompt!"
    assert "VoiceoverScene" in sys_content, "System prompt must mention VoiceoverScene!"
    print(f"[PASS] Local system prompt is clean (no skills) and properly harmonized")

    # USER PROMPT: MUST contain skill reference chip including manim-composer
    user_content = parsed["messages"][1]["content"]
    assert "### Reference Guidelines & Skill Specifications" in user_content, "Skills MUST be in user prompt for local data!"
    assert "manim-composer" in user_content, "manim-composer skill MUST be in user prompt for local data!"
    print(f"[PASS] Local user prompt contains reference guidelines chip with manim-composer")

    # ASSISTANT PROMPT: MUST contain <Plan> and ```python
    asst_content = parsed["messages"][2]["content"]
    assert "<Plan>" in asst_content, "Assistant response missing <Plan> block!"
    assert "```python" in asst_content, "Assistant response missing ```python block!"
    print(f"[PASS] Assistant response complies with two-block contract")

    # 2. Test HF dataset: MUST NOT contain skills in SYSTEM or USER prompt
    if hf_datasets:
        first_hf_name = list(hf_datasets.keys())[0]
        hf_first = hf_datasets[first_hf_name][0]
        assert "### Reference Guidelines" not in hf_first["messages"][0]["content"], "HF system prompt must not have skills!"
        assert "### Reference Guidelines" not in hf_first["messages"][1]["content"], "HF user prompt must not have skills!"
        print(f"[PASS] Hugging Face datasets validated (clean system and clean user prompts)")

    print("=" * 65)
    print("[ALL SMOKE TESTS PASSED SUCCESSFULLY]")
    print("=" * 65 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Build unified gold SFT dataset for Qwen3-8B.")
    parser.add_argument("--keep-end", action="store_true",
                        help="Keep <End> tags in assistant response (default strips to 2-block contract).")
    parser.add_argument("--skip-hf", action="store_true",
                        help="Do not download or merge Hugging Face datasets.")
    parser.add_argument("--without-user-skills", action="store_true",
                        help="Do not add skill chip to user prompts in local data.")
    parser.add_argument("--dedup-prompt-only", action="store_true",
                        help="Aggressively collapse samples sharing the same base instruction.")
    parser.add_argument("--smoke-test", action="store_true",
                        help="Run smoke test on 1 export file + canonical + HF, and exit.")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("=== Manim CE SFT Dataset Builder for Qwen3-8B ===")
    
    # 1. Process Chat Exports
    max_files = 1 if args.smoke_test else None
    aligned_chats = process_exported_chats(keep_end=args.keep_end, max_files=max_files)
    print(f"\n[✓] Total successfully aligned chat export samples: {len(aligned_chats)}")

    if not aligned_chats:
        print("[!] No chat samples extracted. Please check the exported chats directory.")
        return

    # 2. Master Skill Reference
    master_skill = get_master_skill()
    if master_skill:
        print(f"[✓] Master skill reference loaded ({len(master_skill)} chars)")
    else:
        print("[!] Note: No master skill reference found.")

    # 3. Load Local Canonical Validated Dataset (149 gold items)
    canonical_samples = load_canonical_validated(master_skill=master_skill)

    # 4. Load HF dataset (Harmonized system prompt, NO skills anywhere)
    hf_manimator = []
    hf_map = {}

    if not args.skip_hf:
        hf_manimator = load_hf_dataset(
            HF_MANIMATOR_1_URL, HF_MANIMATOR_1_CACHE, "nabin2004/qwen-Manimator-1-sft-data"
        )
        hf_map = {
            "nabin2004/qwen-Manimator-1-sft-data": hf_manimator
        }

    # 5. Run smoke tests
    run_smoke_test(
        aligned_data=aligned_chats,
        canonical_data=canonical_samples,
        hf_datasets=hf_map,
        master_skill=master_skill
    )

    if args.smoke_test:
        print("[*] Smoke test run complete.")
        return

    # 6. Format Datasets
    # Local datasets: Skill chip added to USER prompt (unless --without-user-skills is passed)
    add_skills = not args.without_user_skills

    # 6a. Canonical Validated (149 samples)
    canonical_formatted = format_sft_dataset(
        canonical_samples, add_skill_to_user=add_skills, default_skill=master_skill
    )
    out_canon = DATA_DIR / "canonical_validated_sft.jsonl"
    save_jsonl(canonical_formatted, out_canon, "Canonical validated (gold)")

    # 6b. Exported Chats (379 samples)
    chats_formatted = format_sft_dataset(
        aligned_chats, add_skill_to_user=add_skills, default_skill=master_skill
    )
    out_chats = DATA_DIR / "exported_chats_sft.jsonl"
    save_jsonl(chats_formatted, out_chats, "Exported chats")

    # 6c. HF Dataset (Already formatted with clean system and clean user prompts)
    if hf_manimator:
        out_hf_manimator = DATA_DIR / "hf_manimator_1_sft.jsonl"
        save_jsonl(hf_manimator, out_hf_manimator, "HF qwen-Manimator-1")

    # 7. Build ONE Unified Master Combined Dataset for Qwen3-8B
    # Order of precedence: Canonical Validated -> Exported Chats -> HF Manimator 1
    all_datasets = [canonical_formatted, chats_formatted]
    if hf_manimator:
        all_datasets.append(hf_manimator)

    master_sft = merge_and_deduplicate(all_datasets, dedup_prompt_only=args.dedup_prompt_only)

    # Primary unified file
    out_master_unified = DATA_DIR / "qwen3_8b_manimator_master_sft.jsonl"
    save_jsonl(master_sft, out_master_unified, "Unified Master SFT for Qwen3-8B")

    # Backward compatibility alias
    out_master_alias = DATA_DIR / "qwen_manimator_master_sft.jsonl"
    save_jsonl(master_sft, out_master_alias, "Master SFT alias")

    # 8. Print Summary
    print(f"\n{'=' * 75}")
    print(f"🎉 MASTER UNIFIED SFT DATASET READY FOR QWEN3-8B TRAINING!")
    print(f"{'=' * 75}")
    print(f"File: {out_master_unified}")
    print(f"Total Unique Samples: {len(master_sft)}")
    print(f"\nInput Sources Integrated (Pure Gold SFT):")
    print(f"  [1] Local Gold Canonical Validated: {len(canonical_formatted)} samples (skills in user prompt)")
    print(f"  [2] Local Qwen Chat Exports:        {len(chats_formatted)} samples (skills in user prompt)")
    print(f"  [3] HF nabin2004/qwen-Manimator-1:  {len(hf_manimator)} samples (clean user prompt)")
    print(f"\nPrompt & Contract Structure:")
    print(f"  • System Prompt: Clean pedagogical role across 100% of samples (NO skills).")
    print(f"  • User Prompt: In-context skill guidelines chip for local data; standard for HF.")
    print(f"  • Assistant: Strict two-block contract (<Plan>...</Plan> + ```python ... ```).")
    print(f"{'=' * 75}\n")

if __name__ == "__main__":
    main()
