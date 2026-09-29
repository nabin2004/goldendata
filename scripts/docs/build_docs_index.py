"""Download Sphinx objects.inv for each project into docs_cache/<project>.json.
Usage: python scripts/docs/build_docs_index.py [--only manim]
"""
import argparse, json, re, sys, zlib
from pathlib import Path
import httpx

CACHE = Path(__file__).resolve().parents[2] / "docs_cache"
PROJECTS = {
    "manim": "https://docs.manim.community/en/stable/",
    "manim_voiceover": "https://voiceover.manim.community/en/latest/",
    "numpy": "https://numpy.org/doc/stable/",
    "scipy": "https://docs.scipy.org/doc/scipy/",
    "sympy": "https://docs.sympy.org/latest/",
}
LINE = re.compile(r"(?x)^(.+?)\s+(\S+:\S+)\s+(-?\d+)\s+(\S*)\s+(.*)$")

def parse_inv(raw: bytes, base: str) -> list[dict]:
    lines = raw.split(b"\n", 4)          # 4 header lines, then zlib payload
    body = zlib.decompress(lines[4]).decode("utf-8")
    out = []
    for ln in body.splitlines():
        m = LINE.match(ln)
        if not m:
            continue
        name, role, _prio, uri, disp = m.groups()
        if uri.endswith("$"):
            uri = uri[:-1] + name
        out.append({"name": name, "role": role, "url": base + uri, "display": disp})
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    args = ap.parse_args()
    CACHE.mkdir(exist_ok=True)
    for proj, base in PROJECTS.items():
        if args.only and proj != args.only:
            continue
        try:
            r = httpx.get(base + "objects.inv", follow_redirects=True, timeout=60)
            r.raise_for_status()
            entries = parse_inv(r.content, base)
            (CACHE / f"{proj}.json").write_text(json.dumps(entries))
            print(f"{proj}: {len(entries)} objects")
        except Exception as e:  # keep going; report clearly
            print(f"{proj}: FAILED ({e})", file=sys.stderr)

if __name__ == "__main__":
    main()
