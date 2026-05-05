# Приложение к документу

## RBAC
- `USER`: web (`/bff/web/*`, `user_requests` own only).
- `ENGINEER`: mobile (`/bff/mobile/*`, own tasks/reports only).
- `OPERATOR`, `CHIEF_ENGINEER`: desktop (`/bff/desktop/*`, assignment/monitoring/logs).
- Desktop WebSocket endpoints (`/ws/tasks`, `/ws/sensors`) are restricted to `OPERATOR`, `CHIEF_ENGINEER`.

## Ownership
- `user_id`, `owner_id`, `engineer_id` are derived from JWT on backend.
- `USER` can only access own requests.
- `ENGINEER` can only access assigned tasks and related reports.
- Unauthorized cross-owner access returns `404`/`403` depending on scenario.

## CQRS
- Commands: request/task/report mutations (`POST` endpoints).
- Queries: BFF dashboards/lists/details (`GET` endpoints).
- Write model is normalized (ORM tables), read model is denormalized in BFF DTOs.

## BFF
- Web: `/bff/web/dashboard`, `/bff/web/user-requests/my`, `/bff/web/facilities-map`.
- Mobile: `/bff/mobile/tasks`, `/bff/mobile/events/stream` (SSE).
- Desktop: `/bff/desktop/*` aggregated views for requests/reports/logs/employees.

## Background Jobs
- Queue stack: Celery + Redis.
- Report generation jobs: `POST /reports/generate`, `POST /reports/generate-delayed`.
- Job status endpoints:
  - `GET /jobs/{job_id}` (detailed internal model)
  - `GET /reports/jobs/{job_id}` (report workflow status view)

## Queue
- Flow: command -> enqueue -> worker -> persist result/error.
- API responds immediately with job metadata; heavy work is async.

## Domain Events
- Events are stored in `domain_events`, then processed by background worker.
- Core flow: command -> domain event -> queue -> worker -> read-model/log updates.

## Eventual Consistency
- Commands commit immediately.
- Read models and realtime clients may observe updates with short delay.
- Clients must support brief polling/retry after command execution.

## Logging
- Request metrics include method/path/status/latency/user/role (when enabled).
- Security logging includes auth/report/task lifecycle actions.
- Sensitive token data is redacted from access logs.

## Hot Spots
- Auth endpoints, desktop request lists, mobile task lists, report upload/generation, realtime streams.
- Queue processing and report IO are monitored through action logs and job statuses.

## Cache Invalidation
- Read caches are invalidated after write operations (task/request/report commands).
- BFF cache keys are role/user scoped.

## Security
- Strict DTO validation (`extra=forbid`) and server-side ownership checks.
- Rate limiting and brute-force protection on auth endpoints.
- CORS is explicit in production (`*` forbidden).
- CSP/security headers middleware is enabled.

## API Methods Policy
- API methods policy: only `GET` and `POST` for current and new HTTP endpoints.
- No `PATCH`, `PUT`, `DELETE`, `HEAD` API endpoints are used.
