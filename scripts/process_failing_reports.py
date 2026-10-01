#!/usr/bin/env python3
"""
scripts/process_failing_reports.py
----------------------------------
Aggregates and clusters all failed samples ("ok": false) across reports in data/reports/.
Outputs a structured summary to data/reports/failures_summary.json and prints a clean report.
Optionally applies targeted, surgical fixes directly to the dataset when run with --fix.

Usage:
    python scripts/process_failing_reports.py
    python scripts/process_failing_reports.py --fix
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "data" / "reports"
DEFAULT_DATASET = ROOT / "data" / "qwen3_8b_manimator_master_sft.jsonl"

def classify_error(stderr: str, reason: str = "") -> tuple[str, str]:
    """Classifies failure into a deterministic cluster and returns (cluster_name, description)."""
    text = (stderr or "") + " " + (reason or "")
    
    if "Cannot call Mobject.point_from_proportion for a Mobject with no points" in text:
        return "EMPTY_MOBJECT_PROPORTION", "point_from_proportion called on empty Mobject points"
    if "setting an array element with a sequence" in text:
        return "AXES_RANGE_INHOMOGENEOUS", "Axes/NumberPlane range missing step size [min, max] instead of [min, max, step]"
    if "NameError: name 'PointCloud' is not defined" in text:
        return "UNDEFINED_POINTCLOUD", "Missing PointCloud class"
    if "NameError: name 'Plane' is not defined" in text:
        return "UNDEFINED_PLANE", "Missing Plane class (should be NumberPlane)"
    if "NameError: name 'NumberPlane3D' is not defined" in text:
        return "UNDEFINED_NUMBERPLANE3D", "Missing NumberPlane3D class (should be NumberPlane)"
    if "NameError: name 'Tally' is not defined" in text:
        return "UNDEFINED_TALLY", "Unescaped LaTeX or missing Tally variable"
    if "NameError" in text:
        m = re.search(r"NameError: name '(\w+)' is not defined", text)
        sym = m.group(1) if m else "unknown"
        return f"NAME_ERROR_{sym}", f"Missing definition or import for {sym}"
    if "AttributeError: 'Camera' object has no attribute 'frame'" in text:
        return "CAMERA_FRAME_INHERITANCE", "Scene uses self.camera.frame but does not inherit MovingCameraScene"
    if "AttributeError" in text and "add_fixed_in_frame_mobjects" in text:
        return "THREED_FIXED_INHERITANCE", "Scene uses add_fixed_in_frame_mobjects but does not inherit ThreeDScene"
    if "UnboundLocalError: cannot access local variable 'voiceover_tracker'" in text or "name 'voiceover_tracker' is not defined" in text:
        return "VOICEOVER_TRACKER_UNBOUND", "voiceover_tracker used outside or without matching tracker binding"
    if "duration of" in text and "<= 0 seconds" in text:
        return "NEGATIVE_WAIT_DURATION", "wait() called with negative or zero duration"
    if "OverflowError: Python integer" in text and "out of bounds for uint8" in text:
        return "UINT8_COLOR_OVERFLOW", "Hex color integer multiplied by 255 into uint8 array"
    if "Mobject.__init__() got an unexpected keyword argument 'font_size'" in text or "got an unexpected keyword argument 'font_size'" in text:
        return "TABLE_FONT_SIZE", "font_size keyword passed to Table/Mobject constructor"
    if "ManimColor only accepts" in text and "numpy.float64" in text:
        return "MANIM_COLOR_FLOAT", "Float value passed where ManimColor was expected"
    if "Expected all inputs for parameter mobjects to be a Mobject" in text:
        return "NON_MOBJECT_ADD", "List or non-Mobject passed to Scene.add or Group"
    if "latex error converting to dvi" in text or "LaTeX compilation error" in text:
        return "LATEX_ERROR", "LaTeX compilation error in MathTex/Tex"
    if "TIMEOUT" in text:
        return "TIMEOUT", "Execution timed out during dry-run render"
    
    first_err_line = next((l.strip() for l in reversed(text.splitlines()) if l.strip()), "Unknown failure")
    return "OTHER_ERROR", first_err_line[:120]

def apply_targeted_fix(sample_dict: dict, cluster: str) -> bool:
    """Applies minimal, surgical fix to a single sample."""
    changed = False
    messages = sample_dict.get("messages", [])
    asst_idx = next((i for i, m in enumerate(messages) if m.get("role") == "assistant"), None)
    if asst_idx is None:
        return False
    
    content = messages[asst_idx]["content"]
    m_code = re.search(r"```python\s*(.*?)\s*```", content, re.DOTALL)
    if not m_code:
        return False
    
    code = m_code.group(1)
    orig_code = code

    if cluster == "AXES_RANGE_INHOMOGENEOUS":
        # Turn [min, max] into [min, max, 1]
        code = re.sub(r'\b([xyz]_range\s*=\s*\[\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?)\s*\]', r'\1, 1]', code)
    
    elif cluster == "UNDEFINED_PLANE":
        code = re.sub(r'\bPlane\(', 'NumberPlane(', code)
    
    elif cluster == "UNDEFINED_NUMBERPLANE3D":
        code = re.sub(r'\bNumberPlane3D\b', 'NumberPlane', code)
    
    elif cluster == "UNDEFINED_POINTCLOUD":
        if "class PointCloud(" not in code and "PointCloud = " not in code:
            helper = (
                "\nclass PointCloud(VGroup):\n"
                "    def __init__(self, points, **kwargs):\n"
                "        color = kwargs.pop('color', BLUE)\n"
                "        super().__init__(*[Dot(p, color=color, radius=0.03) for p in points], **kwargs)\n"
            )
            # Insert after imports
            code = re.sub(r"(from manim_voiceover[^\n]*\n)", r"\1" + helper, code, count=1)
    
    elif cluster == "CAMERA_FRAME_INHERITANCE":
        if "self.camera.frame" in code and "MovingCameraScene" not in code:
            code = re.sub(r'class\s+([A-Za-z0-9_]+)\s*\(\s*VoiceoverScene\s*\):', r'class \1(MovingCameraScene, VoiceoverScene):', code, count=1)
    
    elif cluster == "THREED_FIXED_INHERITANCE":
        if "add_fixed_in_frame_mobjects" in code and "ThreeDScene" not in code:
            code = re.sub(r'class\s+([A-Za-z0-9_]+)\s*\(\s*VoiceoverScene\s*\):', r'class \1(ThreeDScene, VoiceoverScene):', code, count=1)
    
    elif cluster == "NEGATIVE_WAIT_DURATION":
        code = re.sub(r'self\.wait\(([^)]*duration\s*-\s*[^)]+)\)', r'self.wait(max(0.1, \1))', code)
    
    elif cluster == "UINT8_COLOR_OVERFLOW":
        code = re.sub(r'np\.array\(colors\[idx\]\)\s*\*\s*255', 'np.array(color_to_rgb(colors[idx])) * 255', code)
        if "color_to_rgb" not in code:
            code = "from manim.utils.color import color_to_rgb\n" + code
    
    elif cluster == "TABLE_FONT_SIZE":
        code = re.sub(r'\b(Table|MathTable|DecimalTable|IntegerTable)\((.*?),?\s*font_size\s*=\s*([^,\)]+)', r'\1(\2, element_to_mobject_config={"font_size": \3}', code)
    
    elif cluster == "UNDEFINED_TALLY":
        # Fix f"\text{Tally} = {current_sum:.1f}" where \t is treated as tab or Tally as var
        code = code.replace(r"\text{Tally}", r"\\text{Tally}")
        code = code.replace(r"\text{", r"\\text{")
    
    elif cluster == "VOICEOVER_TRACKER_UNBOUND":
        code = re.sub(r'\brun_time\s*=\s*voiceover_tracker\.duration\b', 'run_time=tracker.duration', code)
        code = re.sub(r'\bvoiceover_tracker\.duration\b', '1.0', code)

    elif cluster == "EMPTY_MOBJECT_PROPORTION":
        # Ensure path has points before MoveAlongPath or proportion sampling
        code = re.sub(r'(path\s*=\s*VMobject\([^)]*\))\s*\n', r'\1\n        path.set_points_as_corners([ORIGIN, RIGHT * 0.01])\n', code)

    if code != orig_code:
        new_content = content[:m_code.start(1)] + code + content[m_code.end(1):]
        messages[asst_idx]["content"] = new_content
        sample_dict["messages"] = messages
        return True

    return False

def main():
    parser = argparse.ArgumentParser(description="Process and cluster failed dry run reports")
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR, help="Directory containing report JSON files")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="Target dataset JSONL to fix")
    parser.add_argument("--fix", action="store_true", help="Apply targeted surgical fixes directly to the dataset")
    args = parser.parse_args()

    if not args.reports_dir.exists():
        print(f"Error: Reports directory {args.reports_dir} does not exist.")
        sys.exit(1)

    report_files = sorted(args.reports_dir.glob("*.json"))
    if not report_files:
        print(f"No JSON report files found in {args.reports_dir}.")
        sys.exit(1)

    print(f"Found {len(report_files)} report file(s) in {args.reports_dir}:")
    for rf in report_files:
        print(f"  - {rf.name}")

    all_failures = []
    total_passed = 0
    total_failed = 0

    for rf in report_files:
        try:
            data = json.loads(rf.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Warning: Failed to parse {rf.name}: {e}")
            continue

        results = data.get("results", [])
        total_passed += sum(1 for r in results if r.get("ok"))
        
        for r in results:
            if not r.get("ok"):
                total_failed += 1
                cluster, desc = classify_error(r.get("stderr", ""), r.get("reason", ""))
                all_failures.append({
                    "id": r.get("id"),
                    "index": r.get("index"),
                    "cluster": cluster,
                    "cluster_desc": desc,
                    "reason": r.get("reason"),
                    "stderr": (r.get("stderr") or "")[-300:],
                    "report_file": rf.name
                })

    print("\n" + "=" * 80)
    print(f"AGGREGATED DRY RUN REPORT: {total_passed} PASSED | {total_failed} FAILED")
    print("=" * 80)

    if not all_failures:
        print("All samples passed! No failures to cluster.")
        return

    # Cluster by cluster_name
    clusters = defaultdict(list)
    for f in all_failures:
        clusters[f["cluster"]].append(f)

    print(f"\n{len(clusters)} FAILURE CLUSTERS IDENTIFIED:\n")
    print(f"{'Cluster':<30} {'Count':<8} {'Description'}")
    print("-" * 80)
    for c_name, items in sorted(clusters.items(), key=lambda kv: len(kv[1]), reverse=True):
        desc = items[0]["cluster_desc"]
        print(f"{c_name:<30} {len(items):<8} {desc}")

    print("\n" + "=" * 80)
    print("SAMPLE BREAKDOWN PER CLUSTER")
    print("=" * 80)
    for c_name, items in sorted(clusters.items(), key=lambda kv: len(kv[1]), reverse=True):
        sample_ids = [it["id"] for it in items]
        print(f"\n[{c_name}] ({len(items)} samples):")
        print("  IDs:", ", ".join(sample_ids))
        print("  Sample Traceback Tail:")
        print("  " + "\n  ".join(items[0]["stderr"].strip().splitlines()[-4:]))

    # Save summary JSON
    summary_path = args.reports_dir / "failures_summary.json"
    summary_data = {
        "total_passed": total_passed,
        "total_failed": total_failed,
        "cluster_counts": {c: len(items) for c, items in clusters.items()},
        "clusters": {c: items for c, items in clusters.items()}
    }
    summary_path.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    print(f"\n[✓] Saved structured failure summary to: {summary_path}")

    # Apply fixes if requested
    if args.fix:
        if not args.dataset.exists():
            print(f"\nError: Dataset {args.dataset} does not exist for applying fixes.")
            sys.exit(1)

        print(f"\nApplying targeted fixes to {args.dataset}...")
        with open(args.dataset, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]

        # Map sample_id to index if index matches
        id_to_failure = {f["id"]: f for f in all_failures}
        fixed_count = 0

        for i, item in enumerate(lines):
            sid = item.get("id", f"sample_{i:04d}")
            if sid in id_to_failure:
                cluster = id_to_failure[sid]["cluster"]
                if apply_targeted_fix(item, cluster):
                    fixed_count += 1
                    print(f"  [FIXED] {sid} (Cluster: {cluster})")

        if fixed_count > 0:
            with open(args.dataset, "w", encoding="utf-8") as f:
                for item in lines:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            print(f"\n[✓] Successfully applied surgical fixes to {fixed_count} sample(s) in {args.dataset}!")
        else:
            print("\n[!] No samples were modified by the automated fix rules.")

if __name__ == "__main__":
    main()
