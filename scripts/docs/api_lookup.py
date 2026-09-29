"""Authoritative signature lookup from the installed package.
Usage: api_lookup.py Circle | api_lookup.py Circle --methods | api_lookup.py pkg.mod.Class.method
"""
import argparse, importlib, inspect

def resolve(path: str):
    parts = path.split(".")
    if len(parts) == 1:
        import manim
        return getattr(manim, path, None)
    for i in range(len(parts), 0, -1):
        try:
            obj = importlib.import_module(".".join(parts[:i]))
        except ImportError:
            continue
        for p in parts[i:]:
            obj = getattr(obj, p, None)
            if obj is None:
                return None
        return obj
    return None

def accepted_kwargs(cls):
    """Union of explicit params across the MRO (Manim forwards **kwargs up the chain)."""
    names, open_kwargs = set(), False
    for k in inspect.getmro(cls):
        try:
            sig = inspect.signature(k.__init__)
        except (ValueError, TypeError):
            continue
        for n, p in sig.parameters.items():
            if p.kind is p.VAR_KEYWORD: open_kwargs = True
            elif n != "self": names.add(n)
    return sorted(names), open_kwargs

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("name"); ap.add_argument("--methods", action="store_true")
    a = ap.parse_args()
    obj = resolve(a.name)
    if obj is None:
        print(f"NOT FOUND: {a.name} (likely hallucinated)"); raise SystemExit(1)
    try: print(f"{a.name}{inspect.signature(obj)}")
    except (ValueError, TypeError): print(a.name)
    print("\n" + (inspect.getdoc(obj) or "")[:1500])
    if inspect.isclass(obj):
        print("\nMRO:", " > ".join(k.__name__ for k in obj.__mro__[:8]))
        names, open_kw = accepted_kwargs(obj)
        print("Explicit kwargs across MRO:", ", ".join(names), "(+**kwargs forwarded)" if open_kw else "")
        if a.methods:
            print("\nPublic methods:", ", ".join(n for n, _ in inspect.getmembers(obj, callable) if not n.startswith("_")))

if __name__ == "__main__":
    main()
