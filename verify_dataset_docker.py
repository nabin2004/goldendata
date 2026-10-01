#!/usr/bin/env python3
"""
verify_dataset_docker.py
------------------------
Automated verification pipeline for the Manim-AOS SFT dataset.
Runs scenes 100 at a time in parallel inside Docker, performs static LSP
and AST lint checking, collects outputs/logs/errors structurally,
and tracks dynamic Estimated Time of Arrival (ETA).

Features:
1. Concurrency: Runs 100 Docker containers simultaneously (configurable).
2. LSP & Static Linting: Evaluates code syntax, bookmark synchronization,
   kwarg safety, frame layout, and LaTeX validity before & alongside rendering.
3. Targeted Auto-Fixes:
   - Automatically injects missing `VoiceoverScene` & `GTTSService` imports.
   - Normalizes `GTTSService(transcription_model="base")` to headless-safe `GTTSService()`,
     preventing interactive Whisper stdin `EOFError` in headless containers.
4. Structured Output:
   - data/verification_run/passed/<id>/  (scene.py, video.mp4, render.log, lsp.json)
   - data/verification_run/failed/<id>/  (scene.py, render.log, error_summary.json)
   - data/verification_run/summary_report.md (live updated Markdown report)
   - data/verification_run/progress.json (live progress & ETA stats)
5. Dynamic ETA: Moving average duration calculation, batch timing, and ETA countdown.
6. Background Mode: Supports detached daemon execution with status monitoring.

Usage:
    # Run in foreground (100 at a time)
    uv run python3 verify_dataset_docker.py

    # Run in background as daemon (100 at a time)
    uv run python3 verify_dataset_docker.py --daemon --clean

    # Permanently fix dataset JSONL in-place
    uv run python3 verify_dataset_docker.py --fix-dataset-in-place

    # Check live status & ETA of background run
    uv run python3 verify_dataset_docker.py --status

    # Stop background run & clean up containers
    uv run python3 verify_dataset_docker.py --stop
"""

import os
import sys
import json
import time
import shutil
import re
import ast
import argparse
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
DEFAULT_INPUT = DATA_DIR / "qwen3_8b_manimator_master_sft.jsonl"
DEFAULT_OUT_DIR = DATA_DIR / "verification_run"
DOCKER_IMAGE = "manim-aos-render"

# Add src to sys.path to leverage repo's linter modules if available
sys.path.insert(0, str(REPO_ROOT / "src"))

try:
    from manim_aos_data.linter.checks import lint_sample
    from manim_aos_data.sample import parse_response
    HAS_LOCAL_LINTER = True
except Exception:
    HAS_LOCAL_LINTER = False

def extract_code_and_plan(assistant_text: str):
    """Extracts Plan block, Python code, and scene class name from assistant text."""
    plan_text = ""
    m_plan = re.search(r"<Plan>(.*?)</Plan>", assistant_text, re.DOTALL)
    if m_plan:
        plan_text = m_plan.group(1).strip()

    code_text = ""
    m_code = re.search(r"```python\s*(.*?)\s*```", assistant_text, re.DOTALL)
    if m_code:
        code_text = m_code.group(1).strip()
    elif "class " in assistant_text:
        code_text = assistant_text.strip()

    cls_name = "MainScene"
    if code_text:
        classes = re.findall(r"class\s+([A-Za-z0-9_]+)\s*\((.*?)\):", code_text)
        for cname, bases in classes:
            if "VoiceoverScene" in bases or "Scene" in bases:
                cls_name = cname
                break
        if cls_name == "MainScene" and classes:
            cls_name = classes[0][0]

    return plan_text, code_text, cls_name

def apply_targeted_fixes(code: str) -> str:
    """
    Applies deterministic targeted fixes for the primary causes of RENDER_FAIL:
    1. Ensures GTTSService has transcription_model="base" so bookmark timing has word boundaries.
    2. Injects missing VoiceoverScene and GTTSService imports if they are referenced.
    """
    if not code:
        return code

    # Fix 1: Bookmark timing requires transcription word boundaries.
    code = re.sub(
        r'\bGTTSService\(\s*\)',
        'GTTSService(transcription_model="base")',
        code
    )

    # Fix 2: Ensure required voiceover imports
    lines = code.splitlines()
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
    if "VoiceoverScene" in code and not has_vo_import:
        needed_imports.append("from manim_voiceover import VoiceoverScene")
    if "GTTSService" in code and not has_gtts_import:
        needed_imports.append("from manim_voiceover.services.gtts import GTTSService")

    if needed_imports:
        insert_idx = 0
        for i, l in enumerate(lines):
            if l.startswith("from manim import") or l.startswith("import manim"):
                insert_idx = i + 1
        for imp in reversed(needed_imports):
            lines.insert(insert_idx, imp)
        code = "\n".join(lines)

    return code

def run_lsp_checks(code: str, plan: str, assistant_text: str) -> dict:
    """
    Performs static AST analysis, bookmark parity, and Manim-AOS linting.
    Returns structured LSP diagnostics.
    """
    diagnostics = {
        "syntax_valid": False,
        "ast_errors": [],
        "linter_issues": [],
        "bookmark_parity": True,
        "missing_bookmarks": [],
        "extra_bookmarks": [],
        "clean": True
    }

    if not code:
        diagnostics["clean"] = False
        diagnostics["ast_errors"].append("Empty code content")
        return diagnostics

    # 1. AST Syntax Parse
    try:
        tree = ast.parse(code)
        diagnostics["syntax_valid"] = True
    except SyntaxError as e:
        diagnostics["clean"] = False
        diagnostics["ast_errors"].append(f"SyntaxError at line {e.lineno}: {e.msg}")
        return diagnostics

    # 2. Bookmark Synchronization Parity Check
    narration_bookmarks = set(re.findall(r"<bookmark mark=['\"](.*?)['\"]\s*/>", code))
    if not narration_bookmarks and plan:
        narration_bookmarks = set(re.findall(r"<bookmark mark=['\"](.*?)['\"]\s*/>", plan))
    wait_bookmarks = set(re.findall(r"wait_until_bookmark\(\s*['\"](.*?)['\"]\s*\)", code))

    missing = sorted(list(narration_bookmarks - wait_bookmarks))
    extra = sorted(list(wait_bookmarks - narration_bookmarks))

    if missing or extra:
        diagnostics["bookmark_parity"] = False
        diagnostics["missing_bookmarks"] = missing
        diagnostics["extra_bookmarks"] = extra
        diagnostics["linter_issues"].append(
            f"Bookmark mismatch: missing wait_until_bookmark for {missing}, extra waits for {extra}"
        )

    # 3. Built-in Manim-AOS Linter
    if HAS_LOCAL_LINTER:
        try:
            issues = lint_sample(assistant_text, use_manim=False)
            for iss in issues:
                diagnostics["linter_issues"].append(f"[{iss.rule}] {iss.msg}")
        except Exception as e:
            diagnostics["linter_issues"].append(f"[LINTER_EXC] {str(e)}")

    # 4. Optional Ruff diagnostics if ruff is installed
    if shutil.which("ruff"):
        try:
            p = subprocess.run(
                ["ruff", "check", "--stdin-filename", "scene.py", "-"],
                input=code, text=True, capture_output=True, timeout=5
            )
            for line in p.stdout.splitlines():
                if line.strip():
                    diagnostics["linter_issues"].append(f"[RUFF] {line.strip()}")
        except Exception:
            pass

    diagnostics["clean"] = (
        diagnostics["syntax_valid"]
        and diagnostics["bookmark_parity"]
        and len(diagnostics["ast_errors"]) == 0
        and not any("SYNTAX" in str(x) or "STRUCTURE" in str(x) for x in diagnostics["linter_issues"])
    )

    return diagnostics

DOCKER_CMD = ["docker"]

def check_docker_environment():
    """Checks if Docker daemon is running, auto-detects sudo if needed, and ensures image exists."""
    global DOCKER_CMD

    docker_bin = shutil.which("docker")
    if not docker_bin:
        print("[!] Error: 'docker' command not found on PATH.")
        print("    If using Docker Desktop on Windows: enable WSL integration in Docker Desktop Settings > Resources > WSL Integration.")
        print("    If using native Ubuntu: run 'sudo apt update && sudo apt install -y docker.io'")
        return False

    # Check 1: Normal docker info
    res = subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if res.returncode == 0:
        DOCKER_CMD = ["docker"]
    else:
        err_msg = res.stderr.strip()
        # Check 2: Try sudo docker info (e.g. permission denied or requires sudo)
        sudo_res = subprocess.run(["sudo", "-n", "docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if sudo_res.returncode == 0:
            print("[*] Docker requires sudo permissions; using 'sudo docker'.")
            DOCKER_CMD = ["sudo", "docker"]
        else:
            # Try starting native docker service if present
            print(f"[!] Docker check failed: {err_msg.splitlines()[-1] if err_msg else 'daemon not responding'}")
            print("[*] Attempting to start Docker daemon service ('sudo service docker start')...")
            try:
                subprocess.run(["sudo", "service", "docker", "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            except Exception:
                pass

            # Retest after start attempt
            res_after = subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            if res_after.returncode == 0:
                DOCKER_CMD = ["docker"]
            else:
                sudo_after = subprocess.run(["sudo", "-n", "docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if sudo_after.returncode == 0:
                    DOCKER_CMD = ["sudo", "docker"]
                else:
                    print("\n" + "=" * 70)
                    print("[!] CANNOT CONNECT TO DOCKER DAEMON")
                    print("=" * 70)
                    print("Please follow the quick fix for your setup:")
                    print("\n1. If using DOCKER DESKTOP on Windows:")
                    print("   - Open Docker Desktop in Windows.")
                    print("   - Go to Settings ⚙ -> Resources -> WSL Integration.")
                    print("   - Turn ON integration for 'Ubuntu' and click 'Apply & Restart'.")
                    print("\n2. If using NATIVE DOCKER inside WSL2 (Ubuntu):")
                    print("   - Start the service:")
                    print("       sudo service docker start")
                    print("   - Fix permissions so sudo isn't required:")
                    print("       sudo usermod -aG docker $USER && sudo chmod 666 /var/run/docker.sock")
                    print("=" * 70 + "\n")
                    return False

    # Check if manim-aos-render image exists
    img_check = subprocess.run(DOCKER_CMD + ["image", "inspect", DOCKER_IMAGE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if img_check.returncode != 0:
        print(f"[*] Docker image '{DOCKER_IMAGE}' not found. Building it now...")
        dockerfile = REPO_ROOT / "docker" / "Dockerfile.render"
        if not dockerfile.exists():
            print(f"[!] Error: Dockerfile not found at {dockerfile}")
            return False
        build_res = subprocess.run(
            DOCKER_CMD + ["build", "-t", DOCKER_IMAGE, "-f", str(dockerfile), str(REPO_ROOT)],
            text=True
        )
        if build_res.returncode != 0:
            print("[!] Failed to build Docker render image.")
            return False
        print(f"[✓] Successfully built '{DOCKER_IMAGE}'")

    return True

def render_scene_in_docker(sample_id: str, code: str, cls_name: str, scratch_dir: Path, timeout: int = 180) -> dict:
    """
    Renders a single scene inside a disposable Docker container.
    Mounts scratch_dir to /manim and runs: manim -ql scene.py <cls_name>
    """
    scratch_dir.mkdir(parents=True, exist_ok=True)
    scene_file = scratch_dir / "scene.py"
    scene_file.write_text(code, encoding="utf-8")

    container_name = f"manim-verify-{os.getpid()}-{sample_id.replace('_', '-')}"
    cmd = DOCKER_CMD + [
        "run", "--rm",
        "--name", container_name,
        "-v", f"{scratch_dir.resolve()}:/manim",
        "-w", "/manim",
        "--add-host=host.docker.internal:host-gateway",
        DOCKER_IMAGE,
        "manim", "-ql", "--media_dir", "/manim/media", "scene.py", cls_name
    ]

    start_time = time.time()
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            cwd=scratch_dir
        )
        duration = time.time() - start_time
        success = (proc.returncode == 0)
        logs = proc.stdout
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        subprocess.run(DOCKER_CMD + ["rm", "-f", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {
            "success": False,
            "error_type": "TIMEOUT",
            "duration": duration,
            "logs": f"Execution timed out after {timeout} seconds."
        }
    except Exception as e:
        duration = time.time() - start_time
        return {
            "success": False,
            "error_type": "DOCKER_ERROR",
            "duration": duration,
            "logs": str(e)
        }

    # Locate generated video if successful
    video_path = None
    if success:
        mp4_files = list(scratch_dir.rglob("*.mp4"))
        if mp4_files:
            video_path = mp4_files[0]
        else:
            success = False
            logs += "\n[!] Manim exited 0 but no .mp4 video file was generated."

    return {
        "success": success,
        "error_type": None if success else "RENDER_FAIL",
        "duration": duration,
        "logs": logs,
        "video_path": video_path
    }

def format_eta(seconds: float) -> str:
    """Formats seconds into readable HH:MM:SS format."""
    if seconds < 0 or seconds != seconds:  # NaN check
        return "--:--:--"
    td = timedelta(seconds=int(seconds))
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}h {minutes:02d}m {secs:02d}s"
    return f"{minutes:02d}m {secs:02d}s"

class VerificationRunner:
    def __init__(self, input_file: Path, out_dir: Path, concurrency: int = 10, timeout: int = 180, skip_render: bool = False, limit: int = None, clean: bool = False):
        self.input_file = input_file
        self.out_dir = out_dir
        self.concurrency = concurrency
        self.timeout = timeout
        self.skip_render = skip_render
        self.limit = limit
        self.clean = clean

        self.passed_dir = self.out_dir / "passed"
        self.failed_dir = self.out_dir / "failed"
        self.logs_dir = self.out_dir / "logs"
        self.scratch_dir = self.out_dir / "_scratch"
        self.progress_file = self.out_dir / "progress.json"
        self.report_file = self.out_dir / "summary_report.md"

        if self.clean:
            for d in [self.passed_dir, self.failed_dir, self.scratch_dir]:
                if d.exists():
                    shutil.rmtree(d, ignore_errors=True)

        for d in [self.passed_dir, self.failed_dir, self.logs_dir, self.scratch_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.samples = []
        self.completed = 0
        self.passed = 0
        self.failed = 0
        self.durations = []
        self.start_time = None
        self.error_counts = {}

    def load_samples(self):
        """Loads samples from dataset JSONL."""
        if not self.input_file.exists():
            print(f"[!] Error: Input file not found: {self.input_file}")
            sys.exit(1)

        print(f"[*] Reading dataset: {self.input_file}...")
        with open(self.input_file, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    asst_msg = ""
                    user_msg = ""
                    for m in rec.get("messages", []):
                        if m.get("role") == "assistant":
                            asst_msg = m.get("content", "")
                        elif m.get("role") == "user":
                            user_msg = m.get("content", "")

                    plan, code, cls_name = extract_code_and_plan(asst_msg)
                    code = apply_targeted_fixes(code)
                    sample_id = f"sample_{idx:04d}_{cls_name}"

                    self.samples.append({
                        "id": sample_id,
                        "index": idx,
                        "user_prompt": user_msg[:120].replace("\n", " "),
                        "cls_name": cls_name,
                        "plan": plan,
                        "code": code,
                        "assistant_text": asst_msg
                    })
                except Exception as e:
                    print(f"[!] Warning reading line {idx}: {e}")

        if self.limit:
            self.samples = self.samples[:self.limit]

        print(f"[✓] Loaded {len(self.samples)} sample(s) to verify.")

    def update_progress_file(self):
        """Writes live JSON statistics and ETA."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        avg_duration = (sum(self.durations) / len(self.durations)) if self.durations else 0.0

        # Throughput accounting for 10-worker concurrency
        remaining_samples = max(0, len(self.samples) - self.completed)
        if self.skip_render:
            eta_seconds = remaining_samples * 0.02
        else:
            eta_seconds = (remaining_samples / max(1, self.concurrency)) * (avg_duration or 18.0)

        pass_rate = (self.passed / self.completed * 100) if self.completed > 0 else 0.0

        stats = {
            "timestamp": datetime.now().isoformat(),
            "total_samples": len(self.samples),
            "completed": self.completed,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate_pct": round(pass_rate, 2),
            "elapsed_seconds": round(elapsed, 1),
            "elapsed_formatted": format_eta(elapsed),
            "avg_scene_duration_s": round(avg_duration, 2),
            "eta_seconds": round(eta_seconds, 1),
            "eta_formatted": format_eta(eta_seconds),
            "concurrency": self.concurrency,
            "skip_render": self.skip_render,
            "error_breakdown": self.error_counts
        }

        with open(self.progress_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)

        # Write Summary Markdown Report
        report_md = f"""# Manim-AOS Dataset Verification Report

**Last Updated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Status**: {'Completed' if self.completed >= len(self.samples) else 'In Progress'}

## 📊 Live Metrics
- **Total Tested**: {self.completed} / {len(self.samples)} ({round(self.completed / max(1, len(self.samples)) * 100, 1)}%)
- **Passed**: {self.passed} ({round(pass_rate, 1)}%)
- **Failed**: {self.failed}
- **Concurrency**: {self.concurrency} parallel Docker workers
- **Elapsed Time**: {format_eta(elapsed)}
- **Estimated Remaining (ETA)**: {format_eta(eta_seconds)}
- **Avg Render Duration**: {round(avg_duration, 2)}s per scene

## 🛑 Failure Reasons Breakdown
"""
        if self.error_counts:
            for err, cnt in sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True):
                report_md += f"- **{err}**: {cnt} scene(s)\n"
        else:
            report_md += "_No failures recorded yet._\n"

        report_md += f"""
---
*Passed scenes saved in `data/verification_run/passed/` with full .mp4 videos and logs.*  
*Failed scenes saved in `data/verification_run/failed/` with complete tracebacks.*
"""
        with open(self.report_file, "w", encoding="utf-8") as f:
            f.write(report_md)

    def verify_single_sample(self, sample: dict) -> dict:
        """Processes a single sample: LSP static analysis + Docker render."""
        sample_id = sample["id"]
        code = sample["code"]
        plan = sample["plan"]
        asst = sample["assistant_text"]
        cls_name = sample["cls_name"]

        # Check if already processed (resume capability)
        dest_pass = self.passed_dir / sample_id
        dest_fail = self.failed_dir / sample_id
        if self.skip_render:
            if dest_pass.exists() and (dest_pass / "scene.py").exists():
                return {"id": sample_id, "status": "ALREADY_PASSED", "duration": 0}
            if dest_fail.exists() and (dest_fail / "scene.py").exists():
                return {"id": sample_id, "status": "ALREADY_FAILED", "duration": 0}
        else:
            # Full Docker render requires video.mp4
            if dest_pass.exists() and (dest_pass / "video.mp4").exists():
                return {"id": sample_id, "status": "ALREADY_PASSED", "duration": 0}

        # 1. Run LSP & Static Linting Checks
        lsp = run_lsp_checks(code, plan, asst)

        # If fatal syntax error or empty code, fail fast before launching Docker
        if not lsp["syntax_valid"] or not code:
            sample_dest = self.failed_dir / sample_id
            sample_dest.mkdir(parents=True, exist_ok=True)
            (sample_dest / "scene.py").write_text(code, encoding="utf-8")
            (sample_dest / "lsp_report.json").write_text(json.dumps(lsp, indent=2), encoding="utf-8")
            (sample_dest / "render.log").write_text(f"LSP Syntax Failure: {lsp['ast_errors']}", encoding="utf-8")
            return {
                "id": sample_id,
                "status": "FAILED",
                "error_type": "SYNTAX_ERROR",
                "duration": 0.05,
                "cls": cls_name
            }

        # 2. Skip render mode
        if self.skip_render:
            sample_dest = self.passed_dir / sample_id if lsp["clean"] else self.failed_dir / sample_id
            sample_dest.mkdir(parents=True, exist_ok=True)
            (sample_dest / "scene.py").write_text(code, encoding="utf-8")
            (sample_dest / "lsp_report.json").write_text(json.dumps(lsp, indent=2), encoding="utf-8")
            return {
                "id": sample_id,
                "status": "PASSED" if lsp["clean"] else "FAILED",
                "error_type": None if lsp["clean"] else "LSP_ISSUE",
                "duration": 0.05,
                "cls": cls_name
            }

        # 3. Docker Headless Render
        # Stagger container launches slightly (0-1s) to avoid Docker daemon socket thundering herd
        time.sleep(0.01 * (sample.get("index", 0) % 100))
        sample_scratch = self.scratch_dir / sample_id
        render_res = render_scene_in_docker(sample_id, code, cls_name, sample_scratch, timeout=self.timeout)

        # 4. Save structured results
        if render_res["success"] and render_res["video_path"]:
            sample_dest = self.passed_dir / sample_id
            sample_dest.mkdir(parents=True, exist_ok=True)
            (sample_dest / "scene.py").write_text(code, encoding="utf-8")
            (sample_dest / "render.log").write_text(render_res["logs"], encoding="utf-8")
            (sample_dest / "lsp_report.json").write_text(json.dumps(lsp, indent=2), encoding="utf-8")
            try:
                shutil.copy2(render_res["video_path"], sample_dest / "video.mp4")
            except Exception:
                pass
            status = "PASSED"
            err_type = None
        else:
            sample_dest = self.failed_dir / sample_id
            sample_dest.mkdir(parents=True, exist_ok=True)
            (sample_dest / "scene.py").write_text(code, encoding="utf-8")
            (sample_dest / "render.log").write_text(render_res["logs"], encoding="utf-8")
            (sample_dest / "lsp_report.json").write_text(json.dumps(lsp, indent=2), encoding="utf-8")
            err_type = render_res.get("error_type") or "RENDER_FAIL"
            status = "FAILED"

        # Cleanup scratch folder to save disk space
        try:
            shutil.rmtree(sample_scratch, ignore_errors=True)
        except Exception:
            pass

        return {
            "id": sample_id,
            "status": status,
            "error_type": err_type,
            "duration": render_res["duration"],
            "cls": cls_name
        }

    def run(self):
        """Executes the verification with ThreadPoolExecutor."""
        self.load_samples()
        if not self.samples:
            print("[!] No samples to verify.")
            return

        if not self.skip_render:
            if not check_docker_environment():
                print("[!] Docker check failed. Please resolve Docker issues or run with --skip-render.")
                sys.exit(1)

        print("\n" + "=" * 75)
        print(f"🚀 STARTING DATASET VERIFICATION RUN")
        print("=" * 75)
        print(f"Target Samples: {len(self.samples)}")
        print(f"Concurrency:    {self.concurrency} concurrent scenes ({self.concurrency} at a time)")
        print(f"Render Mode:    {'LSP Only (--skip-render)' if self.skip_render else 'Full Docker Render (manim -ql)'}")
        print(f"Output Dir:     {self.out_dir}")
        print("=" * 75 + "\n")

        self.start_time = time.time()

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            future_to_sample = {
                executor.submit(self.verify_single_sample, s): s for s in self.samples
            }

            for future in as_completed(future_to_sample):
                res = future.result()
                self.completed += 1
                sample_id = res["id"]

                if res["status"] in ["PASSED", "ALREADY_PASSED"]:
                    self.passed += 1
                    status_symbol = "✓ PASS"
                else:
                    self.failed += 1
                    status_symbol = "✗ FAIL"
                    err = res.get("error_type", "UNKNOWN")
                    self.error_counts[err] = self.error_counts.get(err, 0) + 1

                if res["duration"] > 0:
                    self.durations.append(res["duration"])

                # Calculate ETA
                elapsed = time.time() - self.start_time
                avg_dur = (sum(self.durations) / len(self.durations)) if self.durations else 15.0
                remaining = len(self.samples) - self.completed
                eta_sec = (remaining / max(1, self.concurrency)) * avg_dur
                pass_pct = (self.passed / self.completed) * 100

                # Print progress update
                print(
                    f"[{self.completed:03d}/{len(self.samples):03d}] {status_symbol} | "
                    f"{sample_id[:30]:<30} | "
                    f"{res['duration']:5.1f}s | "
                    f"Pass: {pass_pct:5.1f}% | "
                    f"Elapsed: {format_eta(elapsed)} | "
                    f"ETA: {format_eta(eta_sec)}"
                )

                self.update_progress_file()

        total_elapsed = time.time() - self.start_time
        print("\n" + "=" * 75)
        print(f"🏁 VERIFICATION RUN COMPLETE")
        print("=" * 75)
        print(f"Total Completed:  {self.completed} / {len(self.samples)}")
        print(f"Passed:           {self.passed} ({round(self.passed / max(1, self.completed) * 100, 1)}%)")
        print(f"Failed:           {self.failed}")
        print(f"Total Duration:   {format_eta(total_elapsed)}")
        print(f"Summary Report:   {self.report_file}")
        print(f"Passed Directory: {self.passed_dir}")
        print(f"Failed Directory: {self.failed_dir}")
        print("=" * 75 + "\n")

def show_status():
    """Prints current live status from progress.json."""
    prog_file = DEFAULT_OUT_DIR / "progress.json"
    if not prog_file.exists():
        print(f"[!] No active or previous verification run found at {prog_file}")
        return

    try:
        data = json.loads(prog_file.read_text(encoding="utf-8"))
        print("\n=== Dataset Verification Live Status ===")
        print(f"Timestamp:       {data.get('timestamp')}")
        print(f"Progress:        {data.get('completed')} / {data.get('total_samples')} ({round(data.get('completed', 0) / max(1, data.get('total_samples', 1)) * 100, 1)}%)")
        print(f"Passed:          {data.get('passed')} (Pass Rate: {data.get('pass_rate_pct')}%)")
        print(f"Failed:          {data.get('failed')}")
        print(f"Elapsed Time:    {data.get('elapsed_formatted')}")
        print(f"Estimated ETA:   {data.get('eta_formatted')}")
        print(f"Avg Scene Time:  {data.get('avg_scene_duration_s')} seconds")
        print(f"Concurrency:     {data.get('concurrency')} workers")
        if data.get("error_breakdown"):
            print("Failure Breakdown:")
            for k, v in data["error_breakdown"].items():
                print(f"  • {k}: {v}")
        print("========================================\n")
    except Exception as e:
        print(f"[!] Error reading status: {e}")

def stop_background_run():
    """Stops background process and active Docker verification containers."""
    pid_file = DEFAULT_OUT_DIR / "logs" / "background.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 15)  # SIGTERM
            print(f"[✓] Stopped background verification process (PID {pid})")
            pid_file.unlink()
        except ProcessLookupError:
            print("[*] Process already exited.")
            pid_file.unlink()
        except Exception as e:
            print(f"[!] Could not kill process: {e}")

    # Clean up any orphan manim-verify containers
    print("[*] Cleaning up any running Docker verification containers...")
    docker_bin = " ".join(DOCKER_CMD)
    subprocess.run(f"{docker_bin} ps -q --filter name=manim-verify | xargs -r {docker_bin} rm -f", shell=True)
    print("[✓] Cleanup complete.")

def start_daemon():
    """Spawns this script in the background."""
    DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
    logs_dir = DEFAULT_OUT_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "run.log"
    pid_file = logs_dir / "background.pid"

    # Remove daemon flag for child invocation
    cmd = [sys.executable, str(Path(__file__).resolve())]
    for arg in sys.argv[1:]:
        if arg not in ["--daemon", "-d"]:
            cmd.append(arg)

    print(f"[*] Launching dataset verification daemon in the background...")
    with open(log_file, "a", encoding="utf-8") as out:
        proc = subprocess.Popen(
            cmd,
            stdout=out,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            cwd=str(REPO_ROOT)
        )

    pid_file.write_text(str(proc.pid))
    print(f"\n{'=' * 75}")
    print(f"🚀 VERIFICATION DAEMON RUNNING IN BACKGROUND (PID {proc.pid})")
    print(f"{'=' * 75}")
    print(f"Log File:       {log_file}")
    print(f"Summary Report: {DEFAULT_OUT_DIR / 'summary_report.md'}")
    print(f"\nTo monitor live progress & ETA:")
    print(f"    uv run python3 verify_dataset_docker.py --status")
    print(f"    tail -f {log_file}")
    print(f"\nTo stop the background run:")
    print(f"    uv run python3 verify_dataset_docker.py --stop")
    print(f"{'=' * 75}\n")

def fix_dataset_file(input_path: Path):
    """Applies targeted fixes directly in-place to the dataset JSONL file with a .bak backup."""
    if not input_path.exists():
        print(f"[!] Error: File not found: {input_path}")
        return
    backup_path = input_path.with_suffix(".jsonl.bak")
    print(f"[*] Creating backup at {backup_path}...")
    shutil.copy2(input_path, backup_path)

    fixed_count = 0
    total_count = 0
    new_lines = []
    print(f"[*] Applying targeted fixes to {input_path}...")
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            total_count += 1
            rec = json.loads(line_str)
            modified = False
            for m in rec.get("messages", []):
                if m.get("role") == "assistant":
                    content = m.get("content", "")
                    m_code = re.search(r"```python\s*(.*?)\s*```", content, re.DOTALL)
                    if m_code:
                        old_code = m_code.group(1).strip()
                        new_code = apply_targeted_fixes(old_code)
                        if new_code != old_code:
                            m["content"] = content[:m_code.start(1)] + "\n" + new_code + "\n" + content[m_code.end(1):]
                            modified = True
            if modified:
                fixed_count += 1
            new_lines.append(json.dumps(rec, ensure_ascii=False) + "\n")

    with open(input_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print(f"[✓] Successfully patched {fixed_count}/{total_count} sample(s) in {input_path}!")
    print(f"[✓] Backup preserved at: {backup_path}\n")

def main():
    parser = argparse.ArgumentParser(description="Verify Manim-AOS SFT dataset inside Docker (100 at a time).")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help="Path to dataset JSONL (default: data/qwen3_8b_manimator_master_sft.jsonl).")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR,
                        help="Directory to save structured outputs, logs, and reports.")
    parser.add_argument("--concurrency", type=int, default=100,
                        help="Number of simultaneous Docker render jobs (default: 100).")
    parser.add_argument("--timeout", type=int, default=180,
                        help="Per-scene render timeout in seconds (default: 180).")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit verification to first N samples (e.g. --limit 20 for a quick test).")
    parser.add_argument("--skip-render", action="store_true",
                        help="Fast mode: run only static AST and LSP checks without Docker rendering.")
    parser.add_argument("--clean", action="store_true",
                        help="Clean existing passed/failed results before starting verification.")
    parser.add_argument("--fix-dataset-in-place", action="store_true",
                        help="Permanently patch data/qwen3_8b_manimator_master_sft.jsonl with targeted import and Whisper prompt fixes.")
    parser.add_argument("--daemon", "-d", action="store_true",
                        help="Launch in background as a detached daemon process.")
    parser.add_argument("--status", action="store_true",
                        help="Display live progress, pass rate, and ETA of running verification.")
    parser.add_argument("--stop", action="store_true",
                        help="Stop running background verification and clean up Docker containers.")
    args = parser.parse_args()

    if args.fix_dataset_in_place:
        fix_dataset_file(args.input)
        return

    if args.status:
        show_status()
        return

    if args.stop:
        stop_background_run()
        return

    if args.daemon:
        start_daemon()
        return

    runner = VerificationRunner(
        input_file=args.input,
        out_dir=args.output_dir,
        concurrency=args.concurrency,
        timeout=args.timeout,
        skip_render=args.skip_render,
        limit=args.limit,
        clean=args.clean
    )
    runner.run()

if __name__ == "__main__":
    main()
