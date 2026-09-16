# LLM Skill Factory — developer shortcuts.
# All targets are deliberately tiny wrappers around the underlying tools; no magic.

.PHONY: help install dev install-dev lint format test test-cov run docker-build docker-run measured clean

help:  ## Show this help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install:  ## Install runtime deps.
	pip install -r requirements.txt

dev: install-dev  ## Alias for `install-dev`.
	pip install -e .

install-dev:  ## Install runtime + dev deps as an editable package.
	pip install -e ".[dev,pdf]"

lint:  ## Ruff check (lint).
	ruff check .

format:  ## Ruff format in place.
	ruff format .

typecheck:  ## mypy on the core package.
	mypy skill_factory

test:  ## Run the test suite.
	pytest

test-cov:  ## Run tests with coverage.
	pytest --cov --cov-report=term-missing

run:  ## Run the Streamlit app locally.
	streamlit run app.py

docker-build:  ## Build the production Docker image.
	docker build -t skill-factory:latest .

docker-run:  ## Run the production Docker image (set OPENROUTER_API_KEY or others).
	docker run --rm -p 8501:8501 \
		-e LLM_PROVIDER=openrouter \
		-e OPENROUTER_API_KEY=$$OPENROUTER_API_KEY \
		skill-factory:latest

measured:  ## Render the 'Skills that have been measured' README table.
	@python scripts/render_measured_skills.py

clean:  ## Remove caches and build artefacts.
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage build dist *.egg-info
	find . -name __pycache__ -type d -exec rm -rf {} +
