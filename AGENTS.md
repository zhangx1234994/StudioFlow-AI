# Repository Guidelines

## Project Structure & Module Organization
- `app/main.py` hosts the FastAPI app, routes, and static mount points.
- `app/services/` contains pipeline logic and provider integrations (`volc_service.py`, `sora_service.py`, `reference_image_service.py`, `assembly_service.py`).
- `app/schemas.py` defines shared Pydantic models; `app/store.py` is the in-memory state/log store.
- `app/utils/` holds reusable helpers (JSON repair, ffmpeg/image tools, logging setup).
- `frontend/` is the Next.js App Router frontend; build output is served from `frontend/out` via `/app/*`.
- `tests/` includes API/service/frontend smoke tests; `data/` stores uploads, render outputs, and runtime logs.

## Build, Test, and Development Commands
- `python3 -m venv .venv && source .venv/bin/activate` — create local Python env.
- `pip install -e .` — install app dependencies in editable mode.
- `make run` (or `uvicorn app.main:app --reload --port 12222`) — start local server.
- `make test` (or `pytest -q`) — run the test suite.
- `make lint` (or `ruff check app tests`) — run lint checks.

Example health check: `curl http://127.0.0.1:12222/healthz`.

## Coding Style & Naming Conventions
- Python 3.10+ with 4-space indentation; keep line length near Ruff limit (`100`).
- Use `snake_case` for files/functions/variables, `PascalCase` for classes, and explicit type hints for public methods.
- Keep service methods focused: parse/validate first, then call external provider, then normalize output.
- Prefer small utility helpers over duplicated inline logic.

## Testing Guidelines
- Test framework: `pytest` with tests under `tests/test_*.py`.
- Add unit tests for new parsing/validation branches and API tests for route-level behavior.
- When changing prompt-to-JSON logic, include failure-path tests.
- Keep tests deterministic: use mock providers (`MVP_USE_MOCK_PROVIDERS=true`) unless intentionally validating live integrations.

## Commit & Pull Request Guidelines
- Follow Conventional Commits (e.g., `feat: add project log endpoint`, `fix: escape script text in frontend`).
- PRs should include: purpose, key files changed, test evidence (`pytest`, `ruff`), and screenshots/GIFs.
- Note env/config changes (`.env.example`, provider keys, ffmpeg) in the PR description.

## Security & Configuration Tips
- Never commit real API keys; keep secrets in `.env` and maintain placeholders in `.env.example`.
- Default to mock mode for development unless live provider testing is required.
- Check `data/logs/app.log` and `/api/v1/projects/{id}/logs` for pipeline debugging.

## Product & UX Guardrails (MUST)
- Tool forms must be scenario-specific: image tools must not display video-only fields (e.g., duration, frame count), and video tools must not display image-only controls.
- Primary CTA must be singular per step; non-primary actions go to secondary/advanced actions.
- Every async action must show explicit state: `submitting` → `running` → `success/failed` with retry entry.
- Distinguish clearly between public studio showcase and private user assets: homepage is for showcase/conversion, while `我的素材库` is personal/private.
- The tools homepage must include an operational showcase block (grouped sample sets) to support commercial conversion, not just functional forms.
- Before handoff, run a visual walkthrough for each tool page: create form, state transitions, and navigation return path to `/app/tools`.
- Use owner mindset: proactively identify UX/product risks and propose at least one better alternative before implementation.
- For homepage and funnel changes, include “运营目标” checks: first-screen value proposition, sample-driven conversion entry (`拍同款`), and commercial blocks (套图销售/二次编辑).

## Delivery Rule (MUST)
- Before handoff, run `python3 -m ruff check app tests`, `python3 -m pytest -q`, and a local API smoke flow.
- Do not ask the product owner to do first-round debugging for issues the team can reproduce locally.
- If live third-party APIs are unreachable, state that explicitly and provide logs plus fallback validation evidence.
- UX acceptance is part of delivery: verify no blocking overlay, no dead CTA, and no scenario-field leakage.
