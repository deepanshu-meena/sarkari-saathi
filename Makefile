.PHONY: install test run demo
install:
	pip install -e ".[dev]"
test:
	pytest -q
run:
	uvicorn saathi.api:app --reload
demo:
	python -m saathi.cli --demo
