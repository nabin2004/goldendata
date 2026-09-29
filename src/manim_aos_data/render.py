"""Stage 4: headless render via `manim -ql`, collect timing + bbox for Omni QC."""
import json, os, subprocess, sys
from pathlib import Path

BBOX_HOOK = '''
# injected by render.py: dump mobject bboxes after each play() for Omni QC
import json as _j
_orig_play = Scene.play
_LOG = []
def _play(self, *a, **k):
    r = _orig_play(self, *a, **k)
    _LOG.append({"t": float(self.renderer.time), "boxes": [
        {"name": type(m).__name__, "x": float(m.get_center()[0]), "y": float(m.get_center()[1]),
         "w": float(m.width), "h": float(m.height)} for m in self.mobjects if hasattr(m, "width")]})
    return r
Scene.play = _play
import atexit; atexit.register(lambda: open("bbox.json", "w").write(_j.dumps(_LOG)))
'''

def _host_url(url: str) -> str:
    return url.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")

def build_cmd(backend: str, out_dir: Path, cls: str, image: str = "manim-aos-render",
              quality: str = "-ql", name: str = "aos-render") -> list[str]:
    if backend == "docker":
        cmd = ["docker", "run", "--rm", "--name", name, "-v", f"{out_dir.resolve()}:/manim", "-w", "/manim",
               "--add-host=host.docker.internal:host-gateway"]
        if os.environ.get("AOS_TTS_URL"):
            cmd += ["-e", f"AOS_TTS_URL={_host_url(os.environ['AOS_TTS_URL'])}"]
        if os.environ.get("AOS_TTS_SPEECH"):
            cmd += ["-e", f"AOS_TTS_SPEECH={os.environ['AOS_TTS_SPEECH']}"]
        if os.environ.get("AOS_REPO"):
            cmd += ["-v", f"{os.environ['AOS_REPO']}:/aos:ro", "-e", f"PYTHONPATH={os.environ.get('AOS_PYTHONPATH', '/aos')}"]
        # -p / -f are unsupported inside Docker, so they are never passed.
        return cmd + [image, "manim", quality, "--media_dir", "/manim/media", "scene.py", cls]
    return [sys.executable, "-m", "manim", quality, "--media_dir", str(out_dir / "media"), "scene.py", cls]

def render(code: str, out_dir: Path, timeout: int = 180, inject_bbox: bool = True,
           backend: str = "local", image: str = "manim-aos-render", quality: str = "-ql") -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "scene.py").write_text(code + ("\n" + BBOX_HOOK if inject_bbox else ""), encoding="utf-8")
    cls = next((l.split("class ")[1].split("(")[0] for l in code.splitlines() if l.startswith("class ")), None)
    name = f"aos-render-{out_dir.name}"
    cmd = build_cmd(backend, out_dir, cls, image, quality, name)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=out_dir)
    except subprocess.TimeoutExpired:
        if backend == "docker":
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        return {"ok": False, "reason": "TIMEOUT"}
    except FileNotFoundError:
        return {"ok": False, "reason": "RENDER_FAIL", "stderr_tail": f"{cmd[0]} not found on PATH"}
    ok = p.returncode == 0
    vids = list((out_dir / "media").rglob("*.mp4"))
    return {"ok": ok, "reason": None if ok else "RENDER_FAIL", "stderr_tail": p.stderr[-2000:],
            "video": str(vids[0]) if vids else None}
