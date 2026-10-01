"""Run dry_run (manim --dry_run scene.py <SceneClass>) on canonical samples.

Usage:
    python scripts/dry_run_samples.py [--limit 10] [--backend local|docker]
"""
import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from manim_aos_data.sample import parse_response
from manim_aos_data.render import build_cmd, BBOX_HOOK, normalize_code

def main():
    parser = argparse.ArgumentParser(description="Dry run Manim scenes on validated samples")
    parser.add_argument("--limit", "-l", type=int, default=None, help="Number of samples to dry run")
    parser.add_argument("--start", type=int, default=0, help="Zero-based input offset")
    parser.add_argument("--backend", "-b", type=str, default="local", choices=["local", "docker"], help="Render backend")
    parser.add_argument("--input", "-i", type=Path, default=ROOT / "data/canonical/validated.jsonl", help="Input samples file")
    parser.add_argument("--out-dir", "-o", type=Path, default=ROOT / "data/rendered", help="Output directory")
    parser.add_argument("--workers", type=int, default=1, help="Maximum concurrent dry runs")
    parser.add_argument("--timeout", type=int, default=180, help="Per-sample timeout in seconds")
    parser.add_argument("--report", type=Path, default=None, help="Write machine-readable results JSON")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: input file {args.input} does not exist.")
        sys.exit(1)

    with open(args.input, encoding="utf-8") as f:
        samples = [json.loads(line) for line in f if line.strip()]

    samples = samples[args.start:]
    if args.limit is not None:
        samples = samples[:args.limit]

    print(f"Loaded {len(samples)} samples to test with `manim --dry_run`...", flush=True)
    print("=" * 70, flush=True)

    def prepare_sample(i, s):
        if "response" in s:
            sample_id = s.get("id", f"sample_{i + 1:04d}")
            response = s["response"]
        else:
            sample_id = s.get("id", f"sample_{i + 1:04d}")
            response = next((m.get("content", "") for m in s.get("messages", [])
                             if m.get("role") == "assistant"), "")
        return i, sample_id, parse_response(response)

    def dry_run_one(item):
        i, sample_id, parsed = prepare_sample(*item)
        code = parsed.code
        cls = next((l.split("class ")[1].split("(")[0].strip() for l in code.splitlines() if l.startswith("class ")), None)
        if not cls:
            return {"index": i, "id": sample_id, "ok": False, "reason": "NO_SCENE_CLASS"}

        sample_dir = args.out_dir / sample_id
        sample_dir.mkdir(parents=True, exist_ok=True)
        scene_file = sample_dir / "scene.py"
        scene_file.write_text(normalize_code(code) + "\n" + BBOX_HOOK, encoding="utf-8")

        cmd = build_cmd(args.backend, sample_dir, cls, dry_run=True)
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout, cwd=sample_dir,
                               env={**os.environ, "AOS_DRY_RUN": "1"})
            ok = (p.returncode == 0)
            if ok:
                return {"index": i, "id": sample_id, "cls": cls, "ok": True}
            else:
                tail = p.stderr[-500:] if p.stderr else p.stdout[-500:]
                return {"index": i, "id": sample_id, "cls": cls, "ok": False, "stderr": tail}
        except subprocess.TimeoutExpired:
            return {"index": i, "id": sample_id, "cls": cls, "ok": False, "reason": "TIMEOUT"}
        except Exception as e:
            return {"index": i, "id": sample_id, "cls": cls, "ok": False, "reason": str(e)}

    results = []
    indexed_samples = enumerate(samples, start=args.start)
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(dry_run_one, item) for item in indexed_samples]
        for completed, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.append(result)
            status = "PASS" if result["ok"] else result.get("reason", "FAIL")
            print(f"[{completed}/{len(samples)}] {result['id']}: {status}", flush=True)
            if result.get("stderr"):
                print(f"  {result['stderr'].strip()}", flush=True)

    passed = sum(1 for r in results if r["ok"])
    print(f"\nDry Run Summary: {passed}/{len(results)} passed.", flush=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({
            "input": str(args.input),
            "start": args.start,
            "count": len(samples),
            "passed": passed,
            "failed": len(results) - passed,
            "results": results,
        }, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
