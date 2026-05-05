# Sports Facilities Monitoring API

FastAPI backend for web/mobile/desktop clients with a single API source of truth.

## CI
- GitHub Actions workflow: `.github/workflows/ci.yml`
- Triggers: `push`, `pull_request`
- Checks:
  - dependencies install
  - `python -m compileall app tests`
  - `pytest`

## Defense Documents
- Full product manual (non-code): `docs/readme_manual.md`
- Test plan: `docs/test_plan.md`
- SAD: `docs/sad.md`
- Risk register: `docs/risk_register.md`
- Presentation outline: `docs/presentation_outline.md`

## Architecture
- FastAPI + SQLAlchemy 2.0 + Alembic
- Supabase PostgreSQL
- JWT auth (access 15m, refresh 7d)
- Celery + Redis + Flower
- CQRS-style split: command endpoints and query/BFF endpoints
- Main lifecycle entity: `engineer_tasks`

## API split (CQRS)
- Command endpoints (write):
  - `POST /auth/me`
  - `POST /user-requests`
  - `POST /engineer-tasks`
  - `POST /engineer-tasks/{task_id}/start`
  - `POST /engineer-tasks/{task_id}/finish`
  - `POST /engineer-tasks/{task_id}/cancel`
  - `POST /bff/desktop/requests/{request_id}/assign`
  - `POST /reports/generate`
  - `POST /reports/generate-delayed`
  - `POST /reports/upload`
  - `POST /reports/seed-samples`
- Query endpoints (read):
  - `GET /user-requests/my`
  - `GET /engineer-tasks`
  - `GET /engineer-tasks/raw` (raw SQL + bind params)
  - `GET /bff/web/dashboard`
  - `GET /bff/web/facilities-map`
  - `GET /bff/web/user-requests/my`
  - `GET /bff/mobile/tasks`
  - `GET /bff/desktop/monitoring`
  - `GET /bff/desktop/requests` (role-scoped)
  - `GET /bff/desktop/reports`
  - `GET /bff/desktop/reports/{report_id}`
  - `GET /bff/desktop/requests/all`
  - `GET /bff/desktop/requests/my` (engineer-only)
  - `GET /reports/template`
  - `GET /reports/my`
  - `GET /reports/jobs/{job_id}`
  - `GET /reports/{report_id}/download`
  - `GET /reports/{report_id}/preview`

Write model: normalized ORM tables (`user_requests`, `engineer_tasks`, `background_jobs`, `domain_events`).
Read model: BFF DTOs and aggregated query responses optimized for UI.

## Where CQRS is implemented
- Command services: `app/services/commands/`
  - `auth_commands.py` (`change_password`, `update_profile`)
  - `user_request_commands.py` (`create_request`)
  - `desktop_request_commands.py` (`assign_request`)
  - `report_commands.py` (`upload_report_file`, `generate_report`, `generate_report_delayed`)
- Query services: `app/services/queries/`
  - `web_dashboard_queries.py`
  - `mobile_tasks_queries.py`
  - `desktop_dashboard_queries.py`
  - `desktop_requests_queries.py`
  - `desktop_reports_queries.py`
  - `report_job_queries.py`
- Routers call command/query services and keep URL + request/response contracts unchanged.

## Lifecycle
- Request statuses: `CREATED`, `ACTIVE`, `ASSIGNED`, `IN_WORK`, `COMPLETED`, `CANCELLED`
- Task statuses: `CREATED`, `ACTIVE`, `COMPLETED`, `CANCELLED`
- Allowed transitions:
  - `CREATED -> ACTIVE`
  - `ACTIVE -> COMPLETED`
  - `ACTIVE -> CANCELLED`
- Invalid transitions return `409`.
- Missing task returns `404`.
- Task status syncs linked `user_requests.status`.

## BFF
- Web: `/bff/web/dashboard`, `/bff/web/user-requests/my`
- Web map: `/bff/web/facilities-map`
- Mobile: `/bff/mobile/tasks`
- Desktop: `/bff/desktop/monitoring` (+ legacy desktop endpoints)

## Security
- RBAC + ownership checks (IDOR mitigation)
- Rate limit middleware (`429`)
- Security headers middleware
- CORS from `CORS_ORIGINS` env (no wildcard for release)
- Dev endpoints disabled by default (`ENABLE_DEV_ENDPOINTS=false`)
- Fake-only sensor mode support (`SENSOR_SOURCE_MODE=fake_only`)
- DTO validation (`extra=forbid`, enums, min/max length)
- Mass-assignment prevention: owner ids from JWT only
- XSS sanitation: user text fields sanitized with `bleach.clean`
- Access-log sanitization: query tokens in URL are redacted/stripped in logs

## Queue and Domain Events
Flow: `command -> domain_event -> queue -> worker`
- `domain_events` table stores command events.
- `background_jobs` stores async job status.
- Worker task `process_domain_event_task` updates domain event processing status.

## Cache and Metrics
- `ENABLE_BFF_CACHE=false` by default (demo stability).
- TTL in-memory cache for:
  - `/bff/web/dashboard`
  - `/bff/mobile/tasks`
  - `/bff/desktop/monitoring`
- Cache invalidation after commands:
  - create request/task, task status transitions, report generation
- Request metrics middleware logs:
  - method/path/status/latency/user/role/error

## Setup
1. `py -3.11 -m venv .venv`
2. `.\.venv\Scripts\Activate.ps1`
3. `pip install -r requirements.txt`
4. `alembic upgrade head`
5. `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

## Tests
1. `.\.venv\Scripts\Activate.ps1`
2. `pip install pytest`
3. `pytest -q`

## Render deployment (production)
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check endpoint: `GET /health` (returns `{"status":"ok"}`)
- Root health endpoint: `GET /` (returns `{"status":"ok","service":"sports-facility-api"}`)
- Required env:
  - `APP_ENV=production`
  - `DEBUG=false`
  - `ENABLE_DEV_ENDPOINTS=false`
  - strong `SECRET_KEY` (>=32 chars, non-default)
  - explicit `CORS_ORIGINS` for frontend domains (e.g. Vercel/Netlify)
  - `CORS_ALLOW_ORIGIN_REGEX=` (empty in production)
- Optional: use `render.yaml` from repo root as base config.

## Env example
See `.env.example` (includes `CORS_ORIGINS`, token TTLs).
- Recommended for this project: `SENSOR_SOURCE_MODE=fake_only`, `SENSOR_AUTOGEN_ENABLED=true`.

## Swagger
- `/docs`
- `/openapi.json`

## Migrations and seed
- Alembic migrations in `alembic/versions`.
- Existing DB bootstrap/seed scripts remain project-specific.
- Seed no longer resets passwords for existing users/employees; initial password is set only on first account creation.

## ngrok/mobile connection
- Start backend locally and expose with `ngrok http 8000`.
- Point clients to ngrok URL.

## Dev fake sensor data for Desktop frontend
- Endpoint: `GET /dev/fake-sensor-data`
- Query params:
  - `randomize=true|false` (default `false`)
  - `write_to_db=true|false` (default `false`)
- Protection:
  - In `SENSOR_SOURCE_MODE=fake_only`: available for employee roles `OPERATOR` and `CHIEF_ENGINEER`.
  - Outside fake-only mode: returns `403` when `ENABLE_DEV_ENDPOINTS=false`, `DEBUG=false`, or `APP_ENV=production`.
  - `write_to_db=true` is allowed only for `CHIEF_ENGINEER`.
- Desktop integration:
  - Replace local hardcoded fake data with:
    - `data = api_request("GET", "/dev/fake-sensor-data?randomize=true")`
    - `facilities = data.get("facilities", [])`
  - Map fields directly:
    - object list: `facility["name"]`
    - object info: `facility["address"]`, `facility["type"]`, `facility["description"]`, `facility["status"]`
    - equipment table: `facility["equipment"]`
    - sensors table: `facility["sensors"]`
- Optional seeding script:
  - `python scripts/generate_fake_sensor_data.py`
  - `python scripts/seed_sample_reports.py` (creates sample report files + report rows)

## Manual checks
- Auth: register/login/employee-login/refresh/logout
- Auth: update own user profile (`POST /auth/me`) including phone/email/username
- Auth: change password (`POST /auth/change-password`) with current password check
- Lifecycle transitions + invalid transition
- RBAC and ownership checks
- Rate limit on auth endpoints
- BFF cache invalidation after commands
- Celery/Flower background jobs status flow
- Report template download, report upload, report file download, sample report seeding
- Upload deduplication: `POST /reports/upload` supports `Idempotency-Key` header and content-hash deduplication
- Desktop report registry (filters/pagination), report detail, inline preview
- Facilities map: `/sports-facilities` and `/bff/web/facilities-map` return coordinates (`latitude`, `longitude`)
- WebSocket/SSE auth:
  - supports `Authorization: Bearer <access_token>`
  - query token fallback remains for backward compatibility

## Eventual consistency
Commands complete immediately; read models/cached views may update with short delay.
Clients should re-fetch data or poll job status.
