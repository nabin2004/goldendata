import json, os, sys
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from pathlib import Path
import typer
from dotenv import load_dotenv
from .linter import lint_sample
from .ast_triage import triage as _triage

app = typer.Typer(no_args_is_help=True)
ROOT = Path(__file__).resolve().parents[2]

# Load environment variables from .env file
load_dotenv(ROOT / ".env")

@app.command()
def ingest(repo: str = "nabin2004/manim-aos-5k400"):
    from .ingest import ingest as run
    print(run(repo, ROOT / "data/raw"), "rows")

@app.command()
def lint(path: Path, no_manim: bool = typer.Option(False, "--no-manim", help="skip signature checks that import manim")):
    """Lint a file containing a full <Plan>+python response."""
    issues = lint_sample(path.read_text(encoding="utf-8"), use_manim=not no_manim)
    for i in issues:
        print(f"{i.rule}: {i.msg}{' [auto-fixable]' if i.fixable else ''}")
    raise typer.Exit(1 if issues else 0)

@app.command()
def triage():
    """Stage 1. Adjust the field name below to your dataset column holding code."""
    src, dst = ROOT / "data/raw/raw.jsonl", ROOT / "data/triage/triage.jsonl"
    rej = ROOT / "logs/rejections.jsonl"
    with open(src) as f, open(dst, "w") as o, open(rej, "a") as r:
        for line in f:
            row = json.loads(line)
            code = row.get("code") or row.get("output") or ""
            t = _triage(code)
            (o if t["ok"] else r).write(json.dumps({"id": row["id"], "stage": 1, **t, "row": row if t["ok"] else None}) + "\n")

def _read(p):
    return [json.loads(l) for l in open(p)] if Path(p).exists() else []

def _append(p, rec):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as f:
        f.write(json.dumps(rec, default=str) + "\n")

@app.command()
def transform(limit: int = typer.Option(None, "--limit", "-l", help="Limit number of samples to process")):
    """Stage 2: triage -> canonical candidates (needs LLM_* / TRANSFORM_MODEL in .env)."""
    from .transform import transform as run
    tpl = (ROOT / "prompts/transform.md").read_text()
    samples = _read(ROOT / "data/triage/triage.jsonl")
    if limit:
        samples = samples[:limit]
        print(f"Processing {limit} samples (limited mode)")
    else:
        print(f"Processing all {len(samples)} samples")
    
    for i, t in enumerate(samples):
        # Support both triage format (with "row" key) and direct format (first_100.jsonl)
        row = t.get("row", t)
        text = run(row.get("instruction") or row.get("prompt") or "", row.get("code") or row.get("output") or "", tpl)
        if (i + 1) % 10 == 0:
            print(f"Processed {i + 1}/{len(samples)} samples...")
        _append(ROOT / ("data/canonical/candidates.jsonl" if text else "logs/rejections.jsonl"),
                {"id": t["id"], "instruction": row.get("instruction") or row.get("prompt"), "response": text} if text
                else {"id": t["id"], "stage": 2, "reason": "TRANSFORM_FAILED"})

@app.command()
def validate():
    """Stage 3: lint candidates; passes -> canonical/validated.jsonl."""
    for c in _read(ROOT / "data/canonical/candidates.jsonl"):
        issues = lint_sample(c["response"])
        if issues:
            _append(ROOT / "logs/rejections.jsonl", {"id": c["id"], "stage": 3, "issues": [i.__dict__ for i in issues]})
        else:
            _append(ROOT / "data/canonical/validated.jsonl", c)

@app.command()
def render(
    limit: int = typer.Option(None, "--limit", "-l", help="Limit number of samples to process (e.g. 10)"),
    dry_run_first: bool = typer.Option(True, "--dry-run-first/--no-dry-run-first", help="Run manim --dry_run before full render"),
    dry_run_only: bool = typer.Option(False, "--dry-run-only", help="Only run manim --dry_run without video render"),
    workers: int = typer.Option(None, "--workers", min=1, help="Maximum concurrent renders (default: pipeline config)"),
):
    """Stage 4: headless render of validated samples."""
    import os, yaml
    from .render import render as run
    from .sample import parse_response
    cfg = yaml.safe_load((ROOT / "configs/pipeline.yaml").read_text())["render"]
    backend = os.environ.get("RENDER_BACKEND") or cfg.get("backend", "local")
    worker_count = workers or int(cfg.get("workers", 1))
    samples = _read(ROOT / "data/canonical/validated.jsonl")
    if limit:
        samples = samples[:limit]
        print(f"Processing {len(samples)} samples (dry_run_first={dry_run_first}, dry_run_only={dry_run_only})")
    sample_locks = {sample_id: Lock() for sample_id in {c["id"] for c in samples}}

    def render_one(item):
        i, c = item
        with sample_locks[c["id"]]:
            res = run(parse_response(c["response"]).code, ROOT / "data/rendered" / c["id"], timeout=cfg["timeout_s"],
                      backend=backend, image=cfg["docker_image"], quality=cfg["quality_flag"],
                      dry_run_first=dry_run_first, dry_run_only=dry_run_only)
        return i, c, res

    print(f"Rendering with {worker_count} concurrent worker(s)")
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        results = executor.map(render_one, enumerate(samples))
        for i, c, res in results:
            print(f"[{i+1}/{len(samples)}] Rendering sample {c['id']}...")
            status = "OK" if res["ok"] else f"FAIL ({res.get('reason')})"
            print(f"  -> {status}")
            if not res["ok"] and res.get("stderr_tail"):
                tail = res["stderr_tail"].strip().splitlines()[-4:]
                print("     " + "\n     ".join(tail))
            _append(ROOT / ("data/rendered/ok.jsonl" if res["ok"] else "logs/rejections.jsonl"), {**c, "stage": 4, **res})

@app.command()
def omni():
    """Stage 5: geometric + VLM QC; failures are sent to repair."""
    import os, yaml
    from .omni_qc import geometric_flags, sample_frames, vlm_verdict
    cfg = yaml.safe_load((ROOT / "configs/pipeline.yaml").read_text())["omni"]
    for c in _read(ROOT / "data/rendered/ok.jsonl"):
        d = ROOT / "data/rendered" / c["id"]
        flags = geometric_flags(json.loads((d / "bbox.json").read_text()) if (d / "bbox.json").exists() else [],
                                iou_thr=cfg["overlap_iou_threshold"])
        verdict = {"verdict": "pass"}
        # Only use VLM if OMNI_VISION_MODEL is configured and working
        if c.get("video") and os.environ.get("OMNI_VISION_MODEL"):
            try:
                frames = sample_frames(c["video"], cfg["frames_per_scene"], d / "frames")
                verdict = vlm_verdict(frames, json.dumps(flags[:20]), ROOT / "prompts/omni_qc.md")
            except Exception as e:
                print(f"VLM call failed for {c['id']}: {e}, using geometric QC only")
        ok = not flags and verdict.get("verdict") == "pass"
        _append(ROOT / ("data/canonical/final.jsonl" if ok else "data/repairs/todo.jsonl"),
                {**c, "omni": {"flags": flags, "vlm": verdict}})

@app.command()
def package():
    """Stage 6: SFT + DPO jsonl."""
    import json as _j
    from .package import build
    from .sample import parse_response
    final = []
    for c in _read(ROOT / "data/canonical/final.jsonl"):
        s = parse_response(c["response"])
        plan_text = "\n".join(f"{k}: {v}" for k, v in s.plan.items())
        final.append({"instruction": c["instruction"], "plan_text": plan_text, "code": s.code})
    build(final, _read(ROOT / "data/repairs/traces.jsonl"), ROOT / "data/packaged")
    print(len(final), "SFT rows")

if __name__ == "__main__":
    app()
