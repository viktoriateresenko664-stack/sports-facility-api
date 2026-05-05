# Security

## SQL Injection
- ORM is used for writes.
- Raw SQL read queries use bind parameters (`:param`) only.
- No SQL string concatenation with user input.

## XSS
- Text fields are sanitized on backend (`description`, `operator_comment`, report notes payload).
- Frontend should avoid dangerous HTML render.

## IDOR
- RBAC + ownership checks on task/request reads.
- USER only reads own requests.
- ENGINEER only reads assigned tasks.
- OPERATOR/CHIEF_ENGINEER/ADMIN have broader scope by role.

## CSRF
- API uses Bearer tokens in Authorization header, not cookie auth.
- Risk is mitigated with restricted CORS.
- If HttpOnly cookies are introduced: add CSRF token + SameSite + Origin/Referer checks.

## LFI/RFI and Path Traversal
- Do not open arbitrary paths from request body.
- Use storage whitelist and safe filenames for generated files.
- Allowed extensions should be restricted (`pdf`, `docx`, `png`, `jpg`).

## Burp Suite Checklist (final)

### IDOR
- `/engineer-tasks/{id}`, `/engineer-tasks`, `/reports/my`, `/reports/{id}/download`, `/jobs/{job_id}`:
  owner/role checks are applied.
- Engineer can read only own tasks/reports.
- Desktop roles (`OPERATOR`, `CHIEF_ENGINEER`) have role-based wider access by design.

### Auth bypass / role spoof
- Endpoints require JWT + role checks (`require_roles`).
- JWT roles and account type are taken from signed token payload; body params cannot override role.
- Access token type is enforced for HTTP/SSE/WS checks.

### Mass assignment
- Input DTOs use `extra="forbid"` on auth/tasks/requests/report payloads.
- Owner fields are derived from JWT subject on backend (`user_id`, `employee_id`), not trusted from request body.

### SQL injection
- Filter params (`status`, date ranges, ids) are validated and sent as bind parameters.
- Raw SQL endpoints use `:param` binds only.

### XSS
- User-entered text is sanitized (`bleach.clean` fallback `html.escape`) before persistence where applicable.
- API should return plain data; frontend must avoid unsafe HTML injection.

### File upload attacks
- Upload endpoint accepts whitelisted extensions only.
- Unsafe extensions (`.html`, `.js`, `.svg`, etc.) are blocked.
- Download/preview content type is resolved from safe whitelist logic.
- File path traversal is mitigated by safe filename + storage root checks.

### Refresh/logout token security
- Refresh token rotation implemented: used refresh token is revoked immediately.
- Reuse of revoked refresh token returns `401`.
- Logout revokes refresh token.

### Brute-force / rate limiting
- Auth brute-force protection: per login key/IP attempt counter and temporary block.
- Global/auth endpoint rate limiting middleware enabled.
- TODO: move limiter state from in-memory to Redis for multi-instance production.

### WebSocket/SSE
- Access token required (type=`access`), invalid/missing token rejected.
- Header auth (`Authorization: Bearer ...`) supported; query token remains as backward-compatible fallback.
- Access log sanitizer strips/redacts query token values from logs.
- SSE mobile stream sends only events belonging to current engineer.

## Risk summary

### CRITICAL
- No known unresolved critical issues after current hardening pass.

### MEDIUM
- In-memory rate limit/bruteforce state is per-instance only (not shared across replicas).
- If multiple Render instances are used, move limiter/blocklist to Redis.

### LOW
- Swagger (`/docs`) remains public by design for development/testing; restrict by network/auth in strict production if required.
- Security quality still depends on frontend token storage hygiene and TLS-only deployment.
