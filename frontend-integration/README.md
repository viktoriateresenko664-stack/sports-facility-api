# Frontend Integration Kit

Единый набор примеров подключения для frontend-команды (desktop/web/mobile).

## Для всех фронтендеров

- Использовать `VITE_API_URL=https://current-ngrok-or-deployed-backend-url`
- Для ngrok добавлять заголовок `ngrok-skip-browser-warning: true`
- Не добавлять `/api/v1` в URL: backend использует endpoint вида `/auth/login`, `/engineer-tasks`, `/bff/...`

## Что найдено в desktop frontend (анализ 3 папок)

Проверены:
- `desctop/desctop_polling/main.py`
- `desctop/desctop_websocket/main.py`
- `desctop/desctop_to/main.py`

Наблюдения:
- `BASE_URL` захардкожен: `https://current-ngrok-or-deployed-backend-url`
- В websocket-вариантах `WS_URL` захардкожен: `wss://current-ngrok-or-deployed-backend-url/ws/tasks`
- Логин: `POST /auth/employee-login`
- Токен передаётся в `Authorization: Bearer <token>` для HTTP
- `localStorage/sessionStorage` не используются (в desktop-реализациях токен хранится в глобальной переменной процесса)

Найденные ошибочные endpoint (backend сейчас их не поддерживает):
- `GET /bff/desktop/requests/my`
- `GET /bff/desktop/requests/all`
- `GET /bff/desktop/employees`
- `GET /bff/desktop/logs`
- `GET /bff/desktop/dashboard`
- `POST /bff/desktop/requests/{id}/assign`
- `WS /ws/desktop`

Использовать вместо них:
- `GET /bff/desktop/monitoring`
- `GET /engineer-tasks`
- `GET /engineer-tasks/raw`
- `WS /ws/sensors?token=<JWT>`
- При необходимости деталей задач: `GET /engineer-tasks/{task_id}`

## Desktop frontend

Использовать:
- `GET /bff/desktop/monitoring`
- `GET /engineer-tasks`
- `GET /engineer-tasks/raw`
- `WS /ws/sensors` для live датчиков

Не использовать несуществующие:
- `/bff/desktop/requests/my`
- `/bff/desktop/requests/all`
- `/bff/desktop/employees`
- `/bff/desktop/logs`
- `/bff/desktop/dashboard` (если endpoint не реализован)

## Web frontend

Использовать:
- `POST /auth/login`
- `POST /auth/register`
- `GET /auth/me`
- `POST /user-requests`
- `GET /user-requests/my`
- `GET /bff/web/dashboard`
- `GET /bff/web/facilities-map?only_with_coordinates=true`

## Mobile frontend

Использовать:
- `POST /auth/employee-login`
- `GET /auth/me`
- `GET /bff/mobile/tasks`
- `GET /engineer-tasks`
- `POST /engineer-tasks/{id}/start`
- `POST /engineer-tasks/{id}/finish`
- `POST /engineer-tasks/{id}/cancel`

Поля объекта задачи в `GET /bff/mobile/tasks`:
- `facility_name` — название объекта
- `facility_address` — адрес объекта
- `facility_id` — технический fallback (не показывать пользователю как основной текст)

## Файлы в этом наборе

- `apiClient.ts` - единый API client
- `wsClient.ts` - websocket client для `/ws/sensors`
- `polling.ts` - helper для polling и `jobs`
- `roles.ts` - роль-ориентированная маршрутизация по `roles`
- `examples.ts` - готовые примеры использования


## Report file flow (mobile)

- Download template: `GET /reports/template`
- Upload filled report file: `POST /reports/upload` (multipart: `task_id`, `report_file`, `notes?`) + header `Idempotency-Key: <uuid>`
- List reports: `GET /reports/my`
- Download uploaded report file: `GET /reports/{report_id}/download`
- Generate sample reports quickly: `POST /reports/seed-samples`
- Change current account password: `POST /auth/change-password`

## Report registry flow (desktop)

- Registry list: `GET /bff/desktop/reports` (filters: `facility_id`, `engineer_id`, `source`, `created_from`, `created_to`, `page`, `limit`)
- Report card: `GET /bff/desktop/reports/{report_id}`
- Inline preview: `GET /reports/{report_id}/preview`
- Download: `GET /reports/{report_id}/download`
- Update own web user profile: `PATCH /auth/me`

## Requests separation (desktop)

- Unified endpoint for UI: `GET /bff/desktop/requests`
- Role behavior:
  - `OPERATOR` / `CHIEF_ENGINEER` / `ADMIN`: all requests
  - `ENGINEER`: only own assigned requests
- Legacy endpoints remain:
  - `GET /bff/desktop/requests/all` (privileged roles only)
  - `GET /bff/desktop/requests/my` (engineer only)


## 2026-05-03 backend contract update

### Realtime task updates
- WebSocket endpoint: `WS /ws/tasks?token=<JWT>`
- Server events:
  - `TASK_CREATED`
  - `TASK_ASSIGNED`
  - `TASK_STARTED`
  - `TASK_COMPLETED`
  - `REPORT_READY`
- Ping/Pong keepalive:
  - client -> `{"type":"ping"}`
  - server -> `{"type":"pong"}`

### Pagination (backward compatible)
- Endpoints now support `page` and `limit` query params:
  - `GET /bff/desktop/requests`
  - `GET /bff/desktop/logs`
  - `GET /reports/my`
  - `GET /engineer-tasks`
- If pagination params are passed, response shape:
```json
{
  "items": [],
  "page": 1,
  "limit": 20,
  "total": 135
}
```
- If pagination params are not passed, legacy list response is preserved.

### Filters (query params)
- `GET /bff/desktop/requests`: `status`, `facility_id`, `assigned_engineer`, `date_from`, `date_to`
- `GET /bff/desktop/logs`: `status`, `date_from`, `date_to`
- `GET /reports/my`: `status`, `facility_id`, `assigned_engineer`, `engineer_id`, `date_from`, `date_to`
- `GET /engineer-tasks`: `status`, `facility_id`, `assigned_engineer`, `date_from`, `date_to`

### Enum normalization
- Unified alert/status values in API responses:
  - `NORMAL`, `WARNING`, `CRITICAL`
  - `ACTIVE`, `INACTIVE`
- Backward-compatible input aliases are still accepted on backend.

### Mobile realtime stream (SSE)

- Endpoint: `GET /bff/mobile/events/stream`
- Auth: either `Authorization: Bearer <employee access token>` or query `?token=<JWT>` (for EventSource without custom headers)
- Content-Type: `text/event-stream`
- Keep-alive comments are sent periodically.
- Initial event after connect:

```json
{"type":"STREAM_READY","timestamp":"2026-05-03T20:30:15.639Z"}
```

- Task/report events:
  - `TASK_CREATED`
  - `TASK_ASSIGNED`
  - `TASK_STARTED`
  - `TASK_COMPLETED`
  - `TASK_CANCELLED`
  - `TASK_UPDATED`
  - `REPORT_READY`

Example payload:

```json
{"type":"TASK_UPDATED","task_id":26,"status":"COMPLETED","timestamp":"2026-05-03T20:30:15.639Z"}
```

Notes:
- `TASK_UPDATED` is generic and emitted on status changes.
- Existing websocket `WS /ws/tasks` remains supported for backward compatibility.

- `sseClient.ts` - SSE client for `/bff/mobile/events/stream`
