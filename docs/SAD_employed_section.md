# SAD employed section

## Architecture
- Single backend API for web/mobile/desktop clients.
- FastAPI + SQLAlchemy (normalized write model) + PostgreSQL (Supabase).
- CQRS style: command endpoints for writes, query/BFF endpoints for reads.
- BFF layer: `/bff/web`, `/bff/mobile`, `/bff/desktop`.

## Security
- JWT access + refresh tokens.
- RBAC and ownership checks on protected endpoints.
- Mass-assignment protection via strict DTO (`extra=forbid`) and explicit model field mapping.
- Rate limiting and security headers middleware.
- CORS restricted to allowed origins (+ ngrok regex).
- XSS mitigation with backend text sanitization (`bleach.clean`).

## Async processing
- Queue: Celery + Redis.
- Background task status in `background_jobs` table.
- Domain events persisted in `domain_events` and processed by queue worker.
- Eventual consistency: command commit is immediate, read projections/cache can update with short delay.
