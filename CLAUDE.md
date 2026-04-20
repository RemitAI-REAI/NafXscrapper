# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Senior Dev Mentor Mode

**Read `docs/senior-dev-ai-instructions.md` before any non-trivial task.** It is the behavioral contract for this project. Key obligations:

- **Phase 0 before coding**: restate the problem, identify ambiguities, map system impact, propose approach with trade-offs, wait for confirmation
- **Challenge requirements** that smell wrong — unnecessary features are the most expensive technical debt
- **Rule of Three**: no abstraction until the 3rd repetition
- **Layered architecture**: Controller (thin) → Service (business logic) → Repository (data access) → Domain (entities/errors)
- **Dependency injection** always — no hardcoded `new ConcreteClass()` inside services
- **Validate at boundaries** with Pydantic/Zod — never trust raw input
- **Structured logging** with context (`requestId`, `userId`, amounts) — never bare `print()` or `console.log()`
- **Systematic debugging** only: Reproduce → Isolate → Hypothesize → Verify → Fix → Prove with a test
- **Conventional commits**: `feat(scope): description`, `fix(scope): description`, etc.
- **Prefer stdlib** over external packages unless the stdlib genuinely cannot do it

---

## Project Overview

RemitAI is a remittance comparison platform that scrapes real-time exchange rates, fees, and transfer times from 7 providers (Wise, Xoom, Remitly, Western Union, MoneyGram, Taptap Send, Monito) and exposes them via a Django REST backend for user notifications and rate alerts. The USD→BDT corridor is the primary focus.

## Repo Structure

```
RemitAI/
  scrapers/      # Selenium-based provider spiders + orchestration
  backend/       # Django REST API (HopeFlow API) — cloned from RemitAI-REAI/server
  docs/          # Product research PDFs
```

The `backend/` folder is a **separate git repo** (subproject). Run git commands for it from inside `backend/`.

---

## Scrapers

### Running

```bash
# Run all spiders
python scrapers/main.py

# Manual testing
jupyter notebook scrapers/testing.ipynb
```

### Dependencies

```bash
pip install -r requirements.txt
```

### Architecture

- **`scrapers/main.py`** — CLI entry point; validates corridor args, sets up logging, delegates to `run_all()`
- **`scrapers/core/orchestrator.py`** — `run_all()` runs corridors sequentially; `run_corridor()` fans out to enabled providers via `ThreadPoolExecutor(max_workers=5)`
- **`scrapers/core/output.py`** — saves each `ScrapeRun` to `output/<timestamp>_<corridor>.json`
- **`scrapers/config/corridors.py`** / **`scrapers/config/providers.py`** — config-only; `PRIORITY` corridor list and `PROVIDERS` registry
- **`scrapers/models/data_model.py`** — `ProviderResult` dataclass (`exchange_rate`, `fees: dict[str, Decimal]`, `transfer_time: dict[str, str]`) and `ScrapeRun` wrapper
- **`scrapers/core/base_spider.py`** — `BaseScraper` ABC; providers implement `scrape(send_currency, recv_currency, send_amount) → ProviderResult`
- **`scrapers/models/base_page.py`** — `BasePage` Selenium helper mixin (waits, clicks, text extraction) shared by all spiders
- **`scrapers/utils/utils.py`** — `setup_driver()` creates headless Chrome with anti-detection flags; all spiders must use this

When adding a new provider: create `scrapers/providers/<name>.py` implementing `BaseScraper`, then register it in `scrapers/config/providers.py`.

---

## Backend (Django — `backend/`)

### Package Manager

The backend uses **`uv`** (not pip). Always prefix Python/Django commands with `uv run`.

### Running

```bash
cd backend

# Start dev server
uv run python manage.py runserver

# Celery worker
uv run celery -A config.celery_app worker -l info

# Celery beat scheduler
uv run celery -A config.celery_app beat
```

Requires PostgreSQL (`DATABASE_URL`) and Redis running locally.

### Testing

```bash
cd backend
uv run pytest                      # all tests
uv run pytest hopeflow_api/users/  # single app
uv run coverage run -m pytest && uv run coverage html
```

Test settings: `config.settings.test`. Uses factory-boy for fixtures.

### Linting & Formatting

```bash
cd backend
uv run ruff check hopeflow_api     # lint
uv run ruff format hopeflow_api    # format
uv run mypy hopeflow_api           # type checking
uv run djlint hopeflow_api --check # template linting
```

Pre-commit hooks enforce all of the above automatically on `git commit`.

### Architecture

- **Settings** split: `config/settings/base.py` → `local.py` / `production.py` / `test.py`
- **Auth**: Custom `AbstractUser` with email as primary identifier (no username), phone number (E.164), soft-delete, email/phone verification flags; allauth + token auth
- **API**: DRF with `drf-spectacular` (OpenAPI); routes registered in `config/api_router.py`; currently only `UserViewSet`
- **Async**: Celery + Redis for background tasks and scheduled scraper runs
- **Email**: Mailgun via django-anymail
- **Storage**: S3 via django-storages in production

### Scraper ↔ Backend Integration

Scrapers currently output JSON to stdout. The intended integration is:
1. Celery Beat triggers periodic scraper runs
2. Scraper data is POSTed to a backend API endpoint (not yet implemented)
3. Backend compares rates, triggers user notifications

When building this integration, the data contract is `ProviderResult` / `ScrapeRun` from `scrapers/models/data_model.py`.
