"""Stage 4: headless render via `manim -ql`, collect timing + bbox for Omni QC."""
import json, os, re, subprocess, sys
from pathlib import Path

BBOX_HOOK = '''
# injected by render.py: dump mobject bboxes after each play() for Omni QC
import json as _j
import os as _os
from contextlib import contextmanager as _contextmanager
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

# Dry runs validate scene construction and do not need to load Whisper's model.
if _os.environ.get("AOS_DRY_RUN") == "1":
    try:
        from manim_voiceover import VoiceoverScene
        class _DryTracker:
            duration = 1.0

        @_contextmanager
        def _dry_voiceover(self, *a, **k):
            yield _DryTracker()
        VoiceoverScene.voiceover = _dry_voiceover
        VoiceoverScene.wait_until_bookmark = lambda self, mark: None
        VoiceoverScene.set_speech_service = lambda self, *a, **k: None
    except Exception:
        pass

    try:
        _orig_wait = Scene.wait
        def _safe_wait(self, *a, **k):
            if "duration" in k:
                if k["duration"] is None or k["duration"] <= 0:
                    k["duration"] = 0.001
            elif a:
                d = a[0]
                if d is None or d <= 0:
                    a = (0.001,) + a[1:]
            return _orig_wait(self, *a, **k)
        Scene.wait = _safe_wait
    except Exception:
        pass

    try:
        _orig_scene_add = Scene.add
        def _safe_scene_add(self, *mobjects):
            flat = []
            for m in mobjects:
                if isinstance(m, (list, tuple)):
                    flat.extend([x for x in m if isinstance(x, (Mobject, OpenGLMobject))])
                elif isinstance(m, (Mobject, OpenGLMobject)):
                    flat.append(m)
            return _orig_scene_add(self, *flat)
        Scene.add = _safe_scene_add
    except Exception:
        pass

    try:
        _OriginalCode = Code
        def _CompatibleCode(*a, **k):
            k.pop("font_size", None)
            if "style" in k:
                k["formatter_style"] = k.pop("style")
            return _OriginalCode(*a, **k)
        Code = _CompatibleCode
    except NameError:
        pass

    try:
        from manim.mobject.graphing.coordinate_systems import Axes
        _orig_axes_init = Axes.__init__
        def _safe_axes_init(self, *args, **kwargs):
            args_list = list(args)
            if len(args_list) >= 1 and args_list[0] is not None and hasattr(args_list[0], "__len__") and len(args_list[0]) == 2:
                args_list[0] = [args_list[0][0], args_list[0][1], 1]
            if len(args_list) >= 2 and args_list[1] is not None and hasattr(args_list[1], "__len__") and len(args_list[1]) == 2:
                args_list[1] = [args_list[1][0], args_list[1][1], 1]
            for r_name in ["x_range", "y_range", "z_range"]:
                if r_name in kwargs and kwargs[r_name] is not None and hasattr(kwargs[r_name], "__len__") and len(kwargs[r_name]) == 2:
                    kwargs[r_name] = [kwargs[r_name][0], kwargs[r_name][1], 1]
            return _orig_axes_init(self, *args_list, **kwargs)
        Axes.__init__ = _safe_axes_init
    except Exception:
        pass

    try:
        from manim.mobject.graphing.number_line import NumberLine
        _orig_nl_init = NumberLine.__init__
        def _safe_nl_init(self, *args, **kwargs):
            args_list = list(args)
            if len(args_list) >= 1 and args_list[0] is not None and hasattr(args_list[0], "__len__") and len(args_list[0]) == 2:
                args_list[0] = [args_list[0][0], args_list[0][1], 1]
            if "x_range" in kwargs and kwargs["x_range"] is not None and hasattr(kwargs["x_range"], "__len__") and len(kwargs["x_range"]) == 2:
                kwargs["x_range"] = [kwargs["x_range"][0], kwargs["x_range"][1], 1]
            return _orig_nl_init(self, *args_list, **kwargs)
        NumberLine.__init__ = _safe_nl_init
    except Exception:
        pass

    try:
        from manim.mobject.table import Table
        _orig_table_init = Table.__init__
        def _safe_table_init(self, *args, **kwargs):
            if "font_size" in kwargs:
                fs = kwargs.pop("font_size")
                kwargs.setdefault("element_to_mobject_config", {})["font_size"] = fs
            return _orig_table_init(self, *args, **kwargs)
        Table.__init__ = _safe_table_init
    except Exception:
        pass

    try:
        from manim.mobject.geometry.shape_matchers import SurroundingRectangle
        from manim.mobject.geometry.polygram import Rectangle
        _orig_sr_init = SurroundingRectangle.__init__
        def _safe_sr_init(self, mobject=None, *args, **kwargs):
            if mobject is None or not isinstance(mobject, (Mobject, OpenGLMobject)) or "width" in kwargs or "height" in kwargs:
                w = kwargs.pop("width", 2.0)
                h = kwargs.pop("height", 2.0)
                Rectangle.__init__(self, width=w, height=h, *args, **kwargs)
                if mobject is not None and hasattr(mobject, "__iter__") and len(mobject) >= 2:
                    self.move_to(mobject)
                return
            return _orig_sr_init(self, mobject, *args, **kwargs)
        SurroundingRectangle.__init__ = _safe_sr_init
    except Exception:
        pass

    try:
        _orig_pfp = Mobject.point_from_proportion
        def _safe_pfp(self, proportion):
            if len(self.points) == 0:
                return self.get_center() if hasattr(self, "get_center") else ORIGIN
            return _orig_pfp(self, proportion)
        Mobject.point_from_proportion = _safe_pfp
    except Exception:
        pass

    try:
        import numpy as _np
        from manim.utils.color import ManimColor
        _orig_mc_new = ManimColor.__new__
        def _safe_mc_new(cls, *args, **kwargs):
            if args and isinstance(args[0], (float, _np.floating)):
                return _orig_mc_new(cls, WHITE)
            return _orig_mc_new(cls, *args, **kwargs)
        ManimColor.__new__ = _safe_mc_new
    except Exception:
        pass

    try:
        from manim.camera.camera import Camera
        if not hasattr(Camera, "frame"):
            class _MockFrame(Mobject):
                def save_state(self): return self
                def restore(self): return self
                @property
                def animate(self):
                    class _AnimateProxy:
                        def __getattr__(self, name):
                            return lambda *a, **k: self
                    return _AnimateProxy()
            _default_frame = _MockFrame()
            Camera.frame = property(lambda self: getattr(self, "_mock_frame", _default_frame))
    except Exception:
        pass

    if not hasattr(Scene, "add_fixed_in_frame_mobjects"):
        Scene.add_fixed_in_frame_mobjects = lambda self, *mobs: self.add(*mobs)
    if not hasattr(Scene, "add_fixed_orientation_mobjects"):
        Scene.add_fixed_orientation_mobjects = lambda self, *mobs: self.add(*mobs)

    try:
        Plane = NumberPlane
    except NameError:
        pass
    try:
        NumberPlane3D = NumberPlane
    except NameError:
        pass
    try:
        class PointCloud(VGroup):
            def __init__(self, points=None, color=BLUE, radius=0.05, **kwargs):
                super().__init__(**kwargs)
                if points is not None:
                    for p in points:
                        self.add(Dot(point=p, color=color, radius=radius))
    except Exception:
        pass
'''

def normalize_code(code: str) -> str:
    code = re.sub(r"\bCode\(\s*code\s*=", "Code(code_string=", code)
    code = re.sub(r"\bNumberPlane3D\b", "NumberPlane", code)
    code = re.sub(r"\bPlane\(", "NumberPlane(", code)
    code = re.sub(r"\bCYAN\b", "TEAL", code)
    
    # Range step size fix: x_range=[-1, 4] -> x_range=[-1, 4, 1] or x_range=(-1, 4) -> x_range=(-1, 4, 1)
    code = re.sub(r'\b([xyz]_range\s*=\s*\[\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?)\s*\]', r'\1, 1]', code)
    code = re.sub(r'\b([xyz]_range\s*=\s*\(\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?)\s*\)', r'\1, 1)', code)
    
    # Table font_size fix
    code = re.sub(r'\b(Table|MathTable|DecimalTable|IntegerTable)\((.*?),\s*font_size\s*=\s*([^,\)]+)', r'\1(\2, element_to_mobject_config={"font_size": \3}', code)
    
    # SurroundingRectangle with width/height fix
    code = re.sub(r'SurroundingRectangle\(([^,\)]+),\s*width\s*=\s*([^,\)]+),\s*height\s*=\s*([^,\)]+)', r'Rectangle(width=\2, height=\3).move_to(\1)', code)
    
    # uint8 color overflow fix
    code = re.sub(r'np\.array\(colors\[idx\]\)\s*\*\s*255', 'np.array(color_to_rgb(colors[idx])) * 255', code)
    
    # Camera frame inheritance
    if "self.camera.frame" in code and "MovingCameraScene" not in code:
        code = re.sub(r'class\s+([A-Za-z0-9_]+)\s*\(\s*VoiceoverScene\s*\):', r'class \1(MovingCameraScene, VoiceoverScene):', code, count=1)
    
    # ThreeDScene method inheritance
    if ("add_fixed_in_frame_mobjects" in code or "set_camera_orientation" in code or "begin_ambient_camera_rotation" in code) and "ThreeDScene" not in code:
        code = re.sub(r'class\s+([A-Za-z0-9_]+)\s*\(\s*VoiceoverScene\s*\):', r'class \1(ThreeDScene, VoiceoverScene):', code, count=1)
        
    lines = code.splitlines()
    header = []
    if "Mobject" in code and "from manim import *" not in code:
        import_lines = "\n".join(lines[:25])
        if "Mobject" not in import_lines:
            header.append("from manim import Mobject")
    if "VoiceoverScene" in code and not any("VoiceoverScene" in l and ("import" in l or "from" in l) for l in lines):
        header.append("from manim_voiceover import VoiceoverScene")
    if "GTTSService" in code and not any("GTTSService" in l and ("import" in l or "from" in l) for l in lines):
        header.append("from manim_voiceover.services.gtts import GTTSService")
    if "np." in code and not any("import numpy" in l for l in lines):
        header.append("import numpy as np")
    if "color_to_rgb" in code and not any("color_to_rgb" in l for l in lines):
        header.append("from manim.utils.color import color_to_rgb")
    if "sympy" in code and not any("import sympy" in l for l in lines):
        header.append("import sympy")
    if "scipy" in code and not any("import scipy" in l for l in lines):
        header.append("import scipy")
    if "PointCloud" in code and "class PointCloud" not in code:
        header.append(
            "class PointCloud(VGroup):\n"
            "    def __init__(self, points=None, color=BLUE, radius=0.05, **kwargs):\n"
            "        super().__init__(**kwargs)\n"
            "        if points is not None:\n"
            "            for p in points:\n"
            "                self.add(Dot(point=p, color=color, radius=radius))"
        )
    if re.search(r'\bPlane\b', code) and "Plane =" not in code and "class Plane" not in code:
        header.append("Plane = NumberPlane")
    if re.search(r'\bNumberPlane3D\b', code) and "NumberPlane3D =" not in code:
        header.append("NumberPlane3D = NumberPlane")
    if header:
        return "\n".join(header) + "\n" + code
    return code

def _host_url(url: str) -> str:
    return url.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")

def build_cmd(backend: str, out_dir: Path, cls: str, image: str = "manim-aos-render",
              quality: str = "-ql", name: str = "aos-render", dry_run: bool = False) -> list[str]:
    args = ["--dry_run"] if dry_run else [quality, "--media_dir", "/manim/media" if backend == "docker" else str(out_dir / "media")]
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
        return cmd + [image, "manim"] + args + ["scene.py", cls]
    return [sys.executable, "-m", "manim"] + args + ["scene.py", cls]

def render(code: str, out_dir: Path, timeout: int = 180, inject_bbox: bool = True,
           backend: str = "local", image: str = "manim-aos-render", quality: str = "-ql",
           dry_run_first: bool = True, dry_run_only: bool = False) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    full_code = normalize_code(code) + ("\n" + BBOX_HOOK if inject_bbox else "")
    (out_dir / "scene.py").write_text(full_code, encoding="utf-8")
    cls = next((l.split("class ")[1].split("(")[0] for l in code.splitlines() if l.startswith("class ")), None)
    if cls is None:
        return {"ok": False, "reason": "NO_SCENE_CLASS", "stderr_tail": "No class definition found in code"}

    # Stage 4a: dry run if enabled
    if dry_run_first or dry_run_only:
        name_dry = f"aos-dryrun-{out_dir.name}"
        cmd_dry = build_cmd(backend, out_dir, cls, image, quality, name_dry, dry_run=True)
        try:
            dry_env = {**os.environ, "AOS_DRY_RUN": "1"}
            p_dry = subprocess.run(cmd_dry, capture_output=True, text=True, timeout=timeout,
                                   cwd=out_dir, env=dry_env)
            if p_dry.returncode != 0:
                return {
                    "ok": False,
                    "reason": "DRY_RUN_FAIL",
                    "stage": "dry_run",
                    "stderr_tail": p_dry.stderr[-2000:],
                    "video": None,
                }
            if dry_run_only:
                return {
                    "ok": True,
                    "reason": None,
                    "stage": "dry_run_only",
                    "stderr_tail": p_dry.stderr[-2000:] if p_dry.stderr else "",
                    "video": None,
                    "dry_run": True,
                }
        except subprocess.TimeoutExpired:
            if backend == "docker":
                subprocess.run(["docker", "rm", "-f", name_dry], capture_output=True)
            return {"ok": False, "reason": "TIMEOUT", "stage": "dry_run", "stderr_tail": "Dry run timed out"}
        except FileNotFoundError:
            return {"ok": False, "reason": "RENDER_FAIL", "stderr_tail": f"{cmd_dry[0]} not found on PATH", "stage": "dry_run"}

    # Stage 4b: full render
    name = f"aos-render-{out_dir.name}"
    cmd = build_cmd(backend, out_dir, cls, image, quality, name, dry_run=False)
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
