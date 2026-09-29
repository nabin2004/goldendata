PY=python
setup:
	$(PY) -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]" && $(MAKE) docs-index
docs-index:
	$(PY) scripts/docs/build_docs_index.py
lint-sample:
	$(PY) -m manim_aos_data.cli lint $(F)
triage:
	$(PY) -m manim_aos_data.cli triage
transform:
	$(PY) -m manim_aos_data.cli transform
validate:
	$(PY) -m manim_aos_data.cli validate
render:
	$(PY) -m manim_aos_data.cli render
omni:
	$(PY) -m manim_aos_data.cli omni
package:
	$(PY) -m manim_aos_data.cli package
test:
	$(PY) -m pytest -q
docker-build:
	docker compose build render
docker-render:
	RENDER_BACKEND=docker $(PY) -m manim_aos_data.cli render
