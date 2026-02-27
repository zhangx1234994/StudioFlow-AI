.PHONY: run test lint frontend-build frontend-install

run:
	python3 -m uvicorn app.main:app --reload --port 12222

test:
	python3 -m pytest

lint:
	python3 -m ruff check app tests

frontend-install:
	npm --prefix frontend install

frontend-build:
	npm --prefix frontend run build
