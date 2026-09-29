from pathlib import Path
from manim_aos_data.render import build_cmd

def test_local_cmd():
    c = build_cmd("local", Path("x"), "S")
    assert c[1:3] == ["-m", "manim"] and c[-2:] == ["scene.py", "S"]

def test_docker_cmd(monkeypatch):
    monkeypatch.setenv("AOS_TTS_URL", "http://localhost:8000")
    monkeypatch.delenv("AOS_REPO", raising=False)
    c = build_cmd("docker", Path("x"), "S", image="img")
    assert c[:3] == ["docker", "run", "--rm"]
    assert "AOS_TTS_URL=http://host.docker.internal:8000" in c
    assert "-p" not in c and "-f" not in c
    assert c[-6:] == ["manim", "-ql", "--media_dir", "/manim/media", "scene.py", "S"] and "img" in c

def test_docker_mounts_aos(monkeypatch):
    monkeypatch.setenv("AOS_REPO", "/host/aos")
    c = build_cmd("docker", Path("x"), "S")
    assert "/host/aos:/aos:ro" in c
