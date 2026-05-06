# Sports Facilities Monitoring

Монорепозиторий финальной версии проекта для защиты.

## 1. Architecture Overview
- **Backend API**: FastAPI (`app/`) — единый источник данных для всех клиентов.
- **Web Site**: `site/` — Node.js BFF + static frontend (роль `USER`).
- **Mobile**: `EngineerMobile финал/EngineerMobile` — Expo app (роль `ENGINEER`).
- **Desktop**: `desctop11/desctop11/desctop` — PySide6 desktop client (роли `OPERATOR`, `CHIEF_ENGINEER`).
- **Database**: Supabase PostgreSQL.
- **Queue**: Celery + Redis/Valkey (best-effort; API не должен падать при недоступной очереди).

## 2. Production URLs
- Backend API: `https://sports-facility-api.onrender.com`
- Frontend site: `https://site-zw5j.onrender.com`
- Mobile distribution: APK через EAS build
- Desktop: локальный запуск (или локальная сборка exe)

## 3. Roles
- `USER` -> web site
- `ENGINEER` -> mobile
- `OPERATOR`, `CHIEF_ENGINEER` -> desktop

## 4. API Policy
- Для текущего API используется только `GET` и `POST`.
- JWT Bearer auth.
- RBAC + ownership проверки обязательны.
- Все API-поля — `snake_case`.
- API-контракт сохранен backward-compatible.

## 5. Backend (FastAPI)
### Run locally
1. `py -3.11 -m venv .venv`
2. `\.venv\Scripts\Activate.ps1`
3. `pip install -r requirements.txt`
4. `alembic upgrade head`
5. `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

### Important endpoints
- Auth: `/auth/register`, `/auth/login`, `/auth/employee-login`, `/auth/refresh`, `/auth/logout`, `/auth/me`
- Web BFF: `/bff/web/*`
- Mobile BFF: `/bff/mobile/tasks`
- Desktop BFF: `/bff/desktop/*`
- Reports: `/reports/upload`, `/reports/generate-delayed`, `/reports/jobs/{job_id}`

## 6. Site (Node.js BFF + static)
### Run locally
1. `cd site`
2. `npm install`
3. `npm start`

### Required env (Render/production)
- `APP_ENV=production`
- `API_BASE_URL=https://sports-facility-api.onrender.com`
- `PUBLIC_API_BASE_URL=/bff/web`
- `CORS_ORIGINS=https://<your-site-domain>`

## 7. Desktop client
См. подробности в:
- [desctop11 README](/c:/Users/viktoria/Desktop/API/desctop11/README.md)

Quick start:
1. `pip install PySide6 requests`
2. `python desctop11/desctop11/desctop/main.py`

## 8. Mobile client
См. подробности в:
- [EngineerMobile README](/c:/Users/viktoria/Desktop/API/EngineerMobile финал/EngineerMobile/README.md)

Quick start:
1. `cd "EngineerMobile финал/EngineerMobile"`
2. `npm install`
3. `npm start`

APK build:
1. `npx eas-cli login`
2. `npx eas-cli build --platform android --profile production`

## 9. CQRS
- Command services: `app/services/commands/`
- Query services: `app/services/queries/`
- Commands меняют состояние, queries только читают.

## 10. Domain Events + Queue
- Event models: `app/domain/events/`
- Dispatcher: `app/services/events/event_dispatcher.py`
- Поток: `command -> event -> queue -> worker`
- Eventual consistency: `POST /reports/generate-delayed` + `GET /reports/jobs/{job_id}`

## 11. Security
- RBAC по ролям
- Ownership (id владельца только из JWT)
- Rate limit/bruteforce protection
- JWT refresh rotation + logout invalidation
- CORS whitelist only in production
- CSP/security headers
- XSS hardening (sanitize + escaping)
- SQL injection protection (ORM/param queries)
- No secrets in repository

## 12. Tests and CI
- Local tests: `pytest`
- Compile check: `python -m compileall app tests`
- CI workflow: `.github/workflows/ci.yml` (`push`, `pull_request`)

## 13. Deploy
### Backend on Render
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Site on Render
- Root Directory: `site`
- Build: `npm install`
- Start: `npm start`

### Mobile
- EAS cloud build (APK)

## 14. Security checklist for defense
- [Security checklist](/c:/Users/viktoria/Desktop/API/docs/security_checklist.md)

## 15. Additional docs
- [Manual](/c:/Users/viktoria/Desktop/API/docs/readme_manual.md)
- [Test plan](/c:/Users/viktoria/Desktop/API/docs/test_plan.md)
- [SAD](/c:/Users/viktoria/Desktop/API/docs/sad.md)
- [Risk register](/c:/Users/viktoria/Desktop/API/docs/risk_register.md)
- [Application appendix](/c:/Users/viktoria/Desktop/API/docs/application_appendix.md)
