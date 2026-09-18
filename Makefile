.PHONY: help install run worker beat test lint fmt migrate revision clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Install the package + dev extras (editable)
	pip install -e ".[dev]"

run:  ## Run the FastAPI server
	uvicorn smauto.api.main:app --reload --port 8000

worker:  ## Run a celery worker
	celery -A smauto.workers.queue.celery_app worker -l info

beat:  ## Run celery beat (metrics pulls)
	celery -A smauto.workers.queue.celery_app beat -l info

test:  ## Run the test suite
	pytest -q

lint:  ## Ruff check
	ruff check src tests

fmt:  ## Ruff format + import sort
	ruff check --fix src tests
	ruff format src tests

migrate:  ## Apply alembic migrations
	alembic -c src/smauto/storage/db/migrations/alembic.ini upgrade head

revision:  ## Autogenerate a migration: make revision m="add x"
	alembic -c src/smauto/storage/db/migrations/alembic.ini revision --autogenerate -m "$(m)"

clean:  ## Remove caches and run output
	rm -rf .pytest_cache .ruff_cache .mypy_cache runs/ __pycache__