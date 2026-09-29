"""Stage 5: geometric checks (deterministic) + VLM verdict on sampled frames."""
import json, base64, os
from pathlib import Path
import cv2, httpx, yaml

def sample_frames(video: str, n: int, out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(video); total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); paths = []
    for i in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * (i + 0.5) / n))
        ok, fr = cap.read()
        if ok:
            p = out / f"f{i:02d}.png"; cv2.imwrite(str(p), fr); paths.append(p)
    return paths

def geometric_flags(bbox_log: list, frame_w=14.222, frame_h=8.0, margin=0.05, iou_thr=0.05) -> list[dict]:
    flags = []
    for i, snap in enumerate(bbox_log):
        boxes = snap["boxes"]
        for b in boxes:
            if abs(b["x"]) + b["w"] / 2 > frame_w / 2 - margin or abs(b["y"]) + b["h"] / 2 > frame_h / 2 - margin:
                flags.append({"type": "CLIPPED", "snap": i, "mobject": b["name"]})
        texty = [b for b in boxes if b["name"] in {"MathTex", "Tex", "Text", "DecimalNumber"}]
        for a in range(len(texty)):
            for c in range(a + 1, len(texty)):
                A, B = texty[a], texty[c]
                ox = min(A["x"] + A["w"]/2, B["x"] + B["w"]/2) - max(A["x"] - A["w"]/2, B["x"] - B["w"]/2)
                oy = min(A["y"] + A["h"]/2, B["y"] + B["h"]/2) - max(A["y"] - A["h"]/2, B["y"] - B["h"]/2)
                if ox > 0 and oy > 0 and ox * oy / min(A["w"]*A["h"], B["w"]*B["h"]) > iou_thr:
                    flags.append({"type": "OVERLAP", "snap": i, "a": A["name"], "b": B["name"]})
    return flags

def vlm_verdict(frames: list[Path], bbox_summary: str, prompt_path: Path) -> dict:
    content = [{"type": "text", "text": prompt_path.read_text() + "\n\n" + bbox_summary}]
    for f in frames:
        b64 = base64.b64encode(f.read_bytes()).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
    r = httpx.post(os.environ["LLM_BASE_URL"] + "/chat/completions", timeout=300,
                   headers={"Authorization": "Bearer " + os.environ.get("LLM_API_KEY", "")},
                   json={"model": os.environ["OMNI_VISION_MODEL"], "messages": [{"role": "user", "content": content}]})
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])
