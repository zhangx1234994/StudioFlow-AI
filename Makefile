.PHONY: run test lint frontend-build frontend-install service-up service-down service-restart service-status service-logs

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

service-up:
	./scripts/dev_service.sh up

service-down:
	./scripts/dev_service.sh down

service-restart:
	./scripts/dev_service.sh restart

service-status:
	./scripts/dev_service.sh status

service-logs:
	./scripts/dev_service.sh logs
