# Hotspots / Heat Map

## Most frequent endpoints
- `POST /auth/login`
- `POST /auth/employee-login`
- `GET /bff/mobile/tasks`
- `GET /bff/web/user-requests/my`
- `GET /bff/desktop/monitoring`

## Heavy operations
- BFF aggregation queries for dashboard/monitoring.
- Report generation (`/reports/generate`, `/reports/generate-delayed`).
- Sensor stream write path (`/sensors/data`).

## Queues
- Celery queue for report jobs.
- Domain event queue worker (`process_domain_event_task`).
- `background_jobs` status tracking in DB.

## Logged metrics
- `response_time_ms`
- `status_code`
- `records_count` (for list/query endpoints)
- `errors` (exception and validation failures)
