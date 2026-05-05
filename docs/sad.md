# SAD (Software Architecture Document) — Sports Facilities Monitoring API

## 1. Обзор системы
Sports Facilities Monitoring API — единый backend для трёх клиентских приложений:
- Web (конечный пользователь);
- Mobile (инженер);
- Desktop (оператор и инженер по эксплуатации).

Цель архитектуры: централизовать бизнес-логику, безопасность и доступ к данным в одном API, исключив локальную бизнес-логику на клиентах.

## 2. Контекст и границы
Система принимает события от пользователей и сотрудников, управляет жизненным циклом заявок/задач и формирует отчёты.

Внешние границы:
- клиенты (web/mobile/desktop);
- БД PostgreSQL;
- Redis/Celery для фоновых задач;
- публичный HTTP(S) вход через Render.

## 3. Архитектурные требования
## 3.1 Функциональные
1. Авторизация и разграничение ролей.
2. Создание заявок пользователем.
3. Назначение инженеров и управление задачами.
4. Загрузка/генерация/скачивание отчётов.
5. Realtime обновления по задачам и датчикам.
6. BFF-ответы под разные клиенты.

## 3.2 Нефункциональные
1. Безопасность API (RBAC, ownership, валидация, CORS, rate limiting).
2. Масштабируемость операций генерации отчётов через очередь.
3. Наблюдаемость (логи, action log, метрики запросов).
4. Backward compatibility API контрактов.
5. Разделение read/write ответственности (CQRS-стиль).

## 4. Архитектурный стиль и ключевые решения
## 4.1 Единый backend API + BFF
- Один backend обслуживает все клиенты.
- BFF сегменты:
  - `/bff/web/*`
  - `/bff/mobile/*`
  - `/bff/desktop/*`

## 4.2 CQRS-стиль
- Commands (write): `POST` endpoint-ы.
- Queries (read): `GET` endpoint-ы.
- Write model: нормализованные таблицы.
- Read model: денормализованные DTO для UI.

## 4.3 Асинхронность
- Тяжёлые операции запускаются как background jobs.
- API возвращает job metadata сразу.
- Состояние job отслеживается через status endpoint.

## 5. Компоненты и ответственность
## 5.1 API слой
- Роуты по доменам: auth, requests, tasks, reports, bff, realtime.
- Валидация входа через схемы.
- Стандартизированные ошибки 401/403/404/409/422.

## 5.2 Сервисный слой
- Бизнес-правила и transitions.
- Ownership-проверки.
- Логирование доменных действий.
- Инвалидация кэша после команд.

## 5.3 Слой данных
- SQLAlchemy ORM для write-потока.
- Query-oriented SQL/BFF выборки для read-потока.
- Alembic миграции.

## 5.4 Фоновая обработка
- Celery worker.
- Redis брокер.
- Таблица `background_jobs` как источник статуса.

## 5.5 Realtime
- WebSocket: desktop-каналы задач и датчиков.
- SSE: mobile-канал событий задач.

## 6. Модель доступа
## 6.1 RBAC
- USER: только web сценарии и собственные данные.
- ENGINEER: mobile сценарии и только назначенные задачи.
- OPERATOR: desktop сценарии управления.
- CHIEF_ENGINEER: расширенный desktop доступ.

## 6.2 Ownership
- Идентификаторы владельца берутся только из JWT/серверной модели.
- Клиент не передаёт owner/user/engineer как доверенный источник.

## 7. Модель данных (логическая)
Ключевые связи:
- `user_requests.user_id -> users.user_id`
- `engineer_tasks.request_id -> user_requests.request_id`
- `engineer_tasks.assigned_engineer_id -> employees.employee_id`
- `engineer_reports.task_id -> engineer_tasks.task_id`
- `equipment.facility_id -> sports_facilities.facility_id`
- `sensors.equipment_id -> equipment.equipment_id`

## 8. Потоки данных (sequence-level)
## 8.1 Create request
USER -> `POST /user-requests` -> `user_requests` insert -> event/log -> BFF invalidate.

## 8.2 Assign request
OPERATOR/CHIEF_ENGINEER -> `POST /bff/desktop/requests/{id}/assign` -> `engineer_tasks` create -> `user_requests.status=ASSIGNED` -> ws event.

## 8.3 Complete task
ENGINEER -> `POST /engineer-tasks/{id}/finish` -> transition check -> update statuses -> recovery flow -> ws/sse event.

## 8.4 Report upload
ENGINEER -> `POST /reports/upload` -> file validate/store -> report upsert -> event/log -> cache invalidate.

## 8.5 Delayed report generation
Client -> `POST /reports/generate-delayed` -> job created -> worker processing -> job status update -> read by `GET /reports/jobs/{job_id}`.

## 9. Безопасность архитектуры
- JWT access + refresh.
- Refresh rotation + revoke.
- DTO validation (`extra=forbid`).
- SQL bind-params.
- Sanitization text inputs.
- CORS whitelist in production.
- Rate limit/bruteforce protection.
- Security headers middleware.

## 10. CORS в архитектурной цепочке
CORS — это входной сетевой фильтр на уровне HTTP origin.
Дальше выполняются:
1. JWT проверка;
2. role check;
3. ownership check;
4. бизнес-правила endpoint-а.

Именно эта последовательность объясняет, почему “доступ из браузера” и “доступ к данным” контролируются отдельно.

## 11. Eventual consistency
Команда может завершиться раньше, чем обновятся:
- realtime подписчики;
- кэшированные read-модели;
- результаты фоновых задач.

Это проектное решение для снижения задержки API и уменьшения блокирующих операций.

## 12. Компромиссы и ограничения
1. Часть read endpoint-ов использует денормализованные выборки ради UI-производительности.
2. Realtime и фоновые процессы допускают небольшую задержку консистентности.
3. Полная горизонтальная масштабируемость limiter/state требует внешнего хранилища (Redis-first).

## 13. Готовность к защите
Архитектура готова к вопросам “как устроено” при условии:
- документы отражают только фактические endpoint-ы и роли;
- все демонстрационные сценарии выполняются в текущем окружении;
- объяснение идёт по цепочке: клиент -> endpoint -> роль -> ownership -> данные -> ответ.
