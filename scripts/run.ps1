# Windows replacement for the Makefile. Usage: .\scripts\run.ps1 <task> [args]
param([Parameter(Mandatory=$true)][string]$Task, [string]$F)
$py = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
switch ($Task) {
  "setup"        { python -m venv .venv; & .\.venv\Scripts\python.exe -m pip install -e ".[dev]"; & .\.venv\Scripts\python.exe scripts\docs\build_docs_index.py }
  "docs-index"   { & $py scripts\docs\build_docs_index.py }
  "lint-sample"  { & $py -m manim_aos_data.cli lint $F }
  "triage"       { & $py -m manim_aos_data.cli triage }
  "transform"    { & $py -m manim_aos_data.cli transform }
  "validate"     { & $py -m manim_aos_data.cli validate }
  "render"       { & $py -m manim_aos_data.cli render }
  "omni"         { & $py -m manim_aos_data.cli omni }
  "package"      { & $py -m manim_aos_data.cli package }
  "test"         { $env:PYTHONPATH = "src"; & $py -m pytest -q }
  "docker-build" { docker compose build render }
  "docker-render"{ $env:RENDER_BACKEND = "docker"; & $py -m manim_aos_data.cli render }
  default        { Write-Error "Unknown task: $Task" }
}
