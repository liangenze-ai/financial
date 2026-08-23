# Project Instructions

## Project Overview

This repository contains a WeChat Mini Program frontend and a Django backend for a finance and quantitative stock diagnosis project.

- Frontend: WeChat Mini Program files in the repository root and `pages/`
- Backend: Django project in `backend/`
- Database: PostgreSQL
- Cache and task broker: Redis
- Async tasks: Celery
- Market data provider: TuShare
- Quantitative analysis and model artifacts: `backend/api/services/`, `backend/api/management/commands/`, and `backend/artifacts/`

## Repository Structure

- `app.js`, `app.json`, `app.wxss`: Mini Program entry point and global configuration
- `pages/`: Mini Program pages
- `backend/manage.py`: Django command entry point
- `backend/config/`: Django and Celery configuration
- `backend/api/`: Models, views, URLs, services, tasks, tests, and management commands
- `backend/api/migrations/`: Django database migrations
- `docs/`: Data standards, API contracts, model plans, and development notes
- `scripts/`: Windows and Linux setup, service startup, and data pipeline scripts
- `docker-compose.yml`: Local PostgreSQL and Redis services

## Development Workflow

1. Inspect the relevant existing files and tests before editing.
2. Keep changes focused on the requested behavior.
3. Preserve unrelated user changes in the working tree. Do not reset, discard, or rewrite them.
4. Update relevant documentation when changing an API, data schema, command, pipeline, or operational workflow.
5. Prefer existing project patterns and helpers over introducing new abstractions.

## Backend Commands

Run Django commands from `backend/`.

Windows:

```powershell
..\.venv\Scripts\python.exe manage.py check
..\.venv\Scripts\python.exe manage.py test api
..\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
..\.venv\Scripts\python.exe manage.py migrate
..\.venv\Scripts\python.exe manage.py runserver
```

Linux or macOS:

```bash
../.venv/bin/python manage.py check
../.venv/bin/python manage.py test api
../.venv/bin/python manage.py makemigrations --check --dry-run
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py runserver
```

Start local infrastructure with:

```powershell
docker compose up -d
```

The Celery worker is started from `backend/`:

```powershell
..\.venv\Scripts\python.exe -m celery -A config worker -l info
```

Use the existing scripts in `scripts/` for project-specific PostgreSQL, Redis, installation, and quantitative data pipeline workflows. Read a script's parameters before running it.

## Configuration and Secrets

- Use `backend/.env.example` as the template for local backend configuration.
- Keep actual `.env` files, TuShare tokens, database passwords, API keys, and production settings out of version control.
- Never print or commit secrets in source code, logs, test fixtures, documentation, or generated artifacts.
- Treat downloaded market data and generated model artifacts as potentially large and sensitive; avoid committing them unless explicitly required.

## Database and Data Rules

- Use Django models and migrations for schema changes.
- Do not edit an existing migration after it has been applied or shared; create a new migration instead.
- Preserve the existing TuShare table naming and metadata conventions documented in `docs/tushare-table-standard.md`.
- Prefer explicit field lists when calling TuShare APIs.
- Preserve idempotency and resume behavior in synchronization commands.
- Validate date ranges, trading dates, stock codes, missing values, and duplicate records in data pipelines.
- Avoid look-ahead bias and data leakage in feature generation, model training, evaluation, and diagnosis.
- Use decimal-safe arithmetic for user-facing monetary calculations. Be explicit about units, percentages, shares, and dates.

## API and Frontend Rules

- Keep API URL patterns, request parameters, response fields, and error formats consistent with existing code and documentation.
- When changing an API contract, update the corresponding documentation and tests.
- Keep WeChat Mini Program page logic in `pages/<page>/index.js`, markup in `index.wxml`, styles in `index.wxss`, and page configuration in `index.json`.
- Do not put backend secrets or database connection details in Mini Program code.
- Keep loading, empty, error, and retry states usable when changing frontend data flows.

## Testing and Verification

For backend changes, run at least:

```powershell
..\.venv\Scripts\python.exe manage.py check
..\.venv\Scripts\python.exe manage.py test api
```

For model, feature, synchronization, or migration changes, also run the narrowest relevant management command in check or dry-run mode when available.

For frontend changes, inspect the affected page in WeChat Developer Tools and verify normal, loading, empty, and error states.

Before finishing, review the diff and confirm that no secrets, debug output, large generated files, or unrelated formatting changes were introduced.

## Documentation References

- `README.md`: project setup and local services
- `docs/tushare-table-standard.md`: TuShare table and synchronization conventions
- `docs/quant-stock-diagnosis-api-contract.md`: quantitative diagnosis API contract
- `docs/model-sample-v1-design.md`: model sample construction
- `docs/quant-stock-diagnosis-model-plan.md`: quantitative model plan

## Current Quant Baseline State

As of 2026-08-23:

- `model_sample_v1` is built and enriched through `20260428`.
- Baseline training and diagnosis commands are implemented.
- Calibration and paper-trading tracking are implemented.
- Default diagnosis now uses calibrated primary and fallback artifacts.
- Fallback is intentionally narrow and only switches on `202604`.

Useful artifacts:

- `backend/artifacts/quant_baseline_medium_quality_value_ablate_calibrated`
- `backend/artifacts/quant_baseline_medium_no_momentum_quality_value_calibrated`
- `backend/artifacts/quant_baseline_medium_no_momentum_quality_value_v2_calibrated`
- `backend/artifacts/quant_baseline_regime_blend_calibrated_old_202604`
- `backend/artifacts/quant_baseline_regime_blend_v2_202604`
- `backend/artifacts/quant_paper_trading_calibrated_top10`

Working conclusion:

- Primary calibrated model is usable.
- Fallback calibrated model is weaker globally, so keep the switch window narrow.
- Paper-trading summaries are positive overall, but they are overlapping 20-day label summaries, not a live NAV backtest.

Fallback retraining comparison on the same 50,000-row-per-split sample:

- The v2 no-momentum fallback was retrained and calibrated, but it was not promoted.
- `up` regime blend rolling AUC/top excess: old `0.563 / 0.0079`, v2 `0.551 / -0.0010`.
- `outperform` regime blend rolling AUC/top excess: old `0.506 / 0.0109`, v2 `0.503 / 0.0065`.
- The v2 fallback was also weak in the active `202604` switch month for `up`.

Decision:

- Keep the current calibrated fallback as the default.
- Keep the switch window limited to `202604`.
- Retain v2 artifacts for research only; do not use them in diagnosis defaults.

Recommended next step:

- Continue paper-trading tracking; only retrain fallback again after adding a materially different feature or label design.
