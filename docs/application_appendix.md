# Приложение к документу

## 1. Состав системы
- Backend API: FastAPI (`app/`), единый API для всех клиентов.
- Web client: `site` (Node.js BFF + static UI для роли USER).
- Mobile client: `EngineerMobile финал/EngineerMobile` (Expo, роль ENGINEER).
- Desktop client: `desctop11/desctop11/desctop` (PySide6, роли OPERATOR/CHIEF_ENGINEER).
- Data layer: Supabase PostgreSQL.
- Queue layer: Celery + Redis/Valkey (best-effort, без падения API при недоступности брокера).

## 2. RBAC
- `USER`: web-сценарии (`/bff/web/*`, свои заявки).
- `ENGINEER`: mobile-сценарии (`/bff/mobile/*`, свои задачи/отчеты).
- `OPERATOR`, `CHIEF_ENGINEER`: desktop-сценарии (`/bff/desktop/*`, назначение и мониторинг).
- Desktop WebSocket (`/ws/tasks`, `/ws/sensors`) не предназначен для ENGINEER.

## 3. Ownership
- `user_id`, `engineer_id`, `owner_id` берутся на сервере из JWT.
- Клиент не передает owner-поля как источник истины.
- Доступ к чужим данным блокируется ответами `403/404`.

## 4. API-контракт
- Политика методов: только `GET` и `POST`.
- API-контракт сохранен backward-compatible.
- Формат полей: `snake_case`.
- Upload отчета: `POST /reports/upload`, ключ файла строго `report_file`.

## 5. BFF
- Web BFF: `/bff/web/dashboard`, `/bff/web/user-requests/my`, `/bff/web/facilities-map`.
- Mobile BFF: `/bff/mobile/tasks`, `/bff/mobile/events/stream`.
- Desktop BFF: `/bff/desktop/dashboard`, `/bff/desktop/requests*`, `/bff/desktop/reports*`, `/bff/desktop/logs`, `/bff/desktop/employees`.

## 6. CQRS
- Команды (write): создание/назначение/смена статусов/загрузка отчетов/обновление профиля.
- Запросы (read): dashboard, списки задач/заявок/отчетов, map DTO, логи.
- Реализация: `app/services/commands/` и `app/services/queries/`.

## 7. Domain events и очередь
- Слой событий: `app/domain/events/`.
- Dispatcher: `app/services/events/event_dispatcher.py`.
- Поток: `command -> domain_event -> queue -> worker`.
- События: `request_created`, `request_assigned`, `task_completed`, `report_uploaded`, `report_generation_started`, `report_generated`.

## 8. Eventual consistency
- Тяжелые операции (генерация отчетов) выполняются фоном.
- Клиент получает `job_id`, затем опрашивает `GET /reports/jobs/{job_id}`.
- Read-модель может обновляться с небольшой задержкой.

## 9. Безопасность
- JWT access/refresh, refresh rotation, logout invalidation.
- RBAC + ownership на каждом защищенном endpoint.
- Rate limiting на auth endpoint'ах.
- DTO-валидация и защита от mass assignment.
- CORS whitelist в production (без wildcard).
- CSP и security headers.
- Санитизация пользовательского текста (XSS hardening).
- В логах скрываются токены и чувствительные данные.

## 10. Логирование и горячие точки
- Логируются: `method`, `path`, `status_code`, `duration_ms`, `user_id`, `role`, ошибки.
- Горячие точки: auth, desktop requests, mobile tasks, reports upload/generation, realtime каналы.

## 11. Deployment
- Backend: Render Web Service (`uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
- Site: Render Web Service (`site`, `npm install`, `npm start`).
- Mobile: EAS build APK.
- Desktop: локальный запуск/пакетирование.

## 12. Тестирование
- Автотесты: `pytest`.
- CI: GitHub Actions (`.github/workflows/ci.yml`).
- Security smoke checks: `docs/security_checklist.md`.
