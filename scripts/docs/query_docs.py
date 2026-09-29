"""Search the local docs index. Usage: query_docs.py "always_redraw" [-p manim] [--fetch] [-n 8]"""
import argparse, json, re
from pathlib import Path
import httpx
from bs4 import BeautifulSoup

CACHE = Path(__file__).resolve().parents[2] / "docs_cache"

def load(project):
    files = [CACHE / f"{project}.json"] if project else sorted(CACHE.glob("*.json"))
    for f in files:
        if f.exists():
            for e in json.loads(f.read_text()):
                e["project"] = f.stem
                yield e

def score(e, q):
    n = e["name"].lower()
    if n == q: return 100
    if n.endswith("." + q): return 90
    if q in n.split(".")[-1]: return 70
    if q in n: return 50
    return 0

def fetch_section(url):
    page, _, frag = url.partition("#")
    html = httpx.get(page, follow_redirects=True, timeout=60).text
    soup = BeautifulSoup(html, "html.parser")
    node = soup.find(id=frag) if frag else soup.find("main") or soup
    node = node.parent if node is not None and node.name == "dt" else node
    text = node.get_text("\n", strip=True) if node else soup.get_text("\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text)[:4000]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query"); ap.add_argument("-p", "--project"); ap.add_argument("-n", type=int, default=8)
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args()
    q = a.query.lower()
    hits = sorted(((score(e, q), e) for e in load(a.project)), key=lambda t: -t[0])
    hits = [e for s, e in hits if s > 0][: a.n]
    if not hits:
        print("NO MATCH. Run build_docs_index.py, or the name may be hallucinated."); return
    for e in hits:
        print(f"[{e['project']}] {e['name']}  ({e['role']})\n  {e['url']}")
    if a.fetch:
        print("\n----- " + hits[0]["name"] + " -----")
        print(fetch_section(hits[0]["url"]))

if __name__ == "__main__":
    main()
