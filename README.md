# Sports Facilities Monitoring System

Система мониторинга состояния спортивных сооружений — это программный комплекс для контроля технического состояния объектов, обработки пользовательских заявок, мониторинга инженерного оборудования и работы с отчётами.

Проект реализован как монорепозиторий и включает backend API, web-сайт, desktop-приложение и mobile-приложение.

---

# 1. Назначение проекта

Проект предназначен для автоматизации контроля состояния спортивных сооружений.

Система позволяет:

- пользователям создавать заявки через web-сайт;
- оператору обрабатывать заявки пользователей;
- инженеру по эксплуатации контролировать оборудование и датчики;
- техническому инженеру выполнять задачи через мобильное приложение;
- хранить данные централизованно;
- разграничивать доступ по ролям;
- формировать отчёты;
- автоматизировать мониторинг объектов.

Основная цель проекта — повышение скорости обнаружения неисправностей и упрощение взаимодействия между пользователями и инженерными службами.

---

# 2. Архитектура проекта

Проект построен по клиент-серверной архитектуре.

```text
Web Site        \
Desktop Client  ---> Backend API ---> PostgreSQL
Mobile Client  /
```

## Используемые технологии

### Backend
- FastAPI
- SQLAlchemy
- PostgreSQL
- Alembic
- JWT
- Celery
- Redis/Valkey

### Desktop
- Python
- PySide6
- Qt

### Mobile
- React Native
- Expo

### Web
- Node.js
- Static frontend

### Infrastructure
- Render
- Supabase
- GitHub Actions

---

# 3. Состав проекта

## Backend API

Backend является центральной частью системы.

Основные задачи backend:

- авторизация пользователей;
- обработка JWT токенов;
- проверка ролей;
- обработка заявок;
- работа с датчиками;
- работа с задачами инженеров;
- генерация отчётов;
- обработка очередей;
- взаимодействие с базой данных.

---

## Web Site

Web-сайт предназначен для обычного пользователя системы.

Пользователь может:

- зарегистрироваться;
- авторизоваться;
- создать заявку;
- просмотреть свои заявки;
- отслеживать статус заявки.

---

## Desktop Client

Desktop-приложение используется:

- оператором;
- инженером по эксплуатации.

Desktop-клиент разработан на PySide6.

Функции оператора:

- просмотр заявок;
- назначение инженеров;
- просмотр сотрудников;
- просмотр журнала действий.

Функции инженера по эксплуатации:

- просмотр объектов;
- просмотр датчиков;
- анализ оборудования;
- создание инженерных задач;
- работа с журналом.

---

## Mobile Client

Mobile-приложение предназначено для технического инженера.

Основные возможности:

- просмотр задач;
- выполнение задач;
- загрузка отчётов;
- работа с объектами на выезде.

---

# 4. Ролевая модель

| Роль | Клиент | Возможности |
|---|---|---|
| USER | Web | Создание и просмотр заявок |
| OPERATOR | Desktop | Работа с заявками |
| ENGINEER | Desktop | Работа с датчиками и оборудованием |
| ENGINEER | Mobile | Выполнение задач и загрузка отчётов |

## Ограничения доступа

### USER
Не имеет доступа:
- к desktop функционалу;
- к мониторингу;
- к датчикам.

### OPERATOR
Не имеет доступа:
- к датчикам;
- к оборудованию;
- к инженерным данным.

### ENGINEER (Desktop)
Не имеет доступа:
- к пользовательским заявкам.

### ENGINEER (Mobile)
Имеет доступ только:
- к своим задачам;
- к своим отчётам.

---

# 5. Backend API

Backend API обслуживает все клиентские приложения.

## Основные endpoint-ы

### Auth

```text
/auth/register
/auth/login
/auth/employee-login
/auth/refresh
/auth/logout
/auth/me
```

### Web BFF

```text
/bff/web/*
```

### Desktop BFF

```text
/bff/desktop/*
```

### Mobile BFF

```text
/bff/mobile/tasks
```

### Reports

```text
/reports/upload
/reports/generate-delayed
/reports/jobs/{job_id}
```

---

# 6. CQRS

В проекте используется CQRS (Command Query Responsibility Segregation).

CQRS разделяет:

- операции чтения (Query);
- операции изменения данных (Command).

## Query

```text
GET /bff/desktop/dashboard
GET /bff/mobile/tasks
GET /reports/jobs/{job_id}
GET /bff/desktop/requests/all
```

## Command

```text
POST /auth/register
POST /auth/login
POST /engineer-tasks
POST /reports/upload
POST /bff/desktop/requests/{id}/assign
```

## Структура backend

```text
app/services/commands/
app/services/queries/
```

CQRS делает архитектуру более понятной и безопасной.

---

# 7. Очереди и фоновые задачи

Для обработки фоновых задач используется:

```text
Celery + Redis/Valkey
```

Очередь применяется для:

- delayed report generation;
- обработки background jobs;
- eventual consistency.

## Поток обработки

```text
command -> domain event -> queue -> worker
```

## Пример

1. Пользователь создаёт задачу генерации отчёта.
2. Backend создаёт background job.
3. Job помещается в очередь.
4. Worker обрабатывает задачу.
5. Клиент получает результат по `job_id`.

---

# 8. Безопасность

В проекте реализованы:

- JWT authentication;
- refresh rotation;
- logout invalidation;
- RBAC;
- ownership checks;
- SQL injection protection;
- XSS protection;
- CSP headers;
- CORS whitelist;
- rate limiting;
- bruteforce protection.

## RBAC

Каждая роль имеет ограниченный набор endpoint-ов.

## Ownership

Пользователь может видеть только свои данные.

Технический инженер может видеть только свои задачи.

---

# 9. Desktop-приложение

Desktop-клиент построен на PySide6.

## Основные модули

### LoginDialog
- авторизация сотрудников;
- получение JWT токена;
- определение роли.

### OperatorWindow
- работа с заявками;
- просмотр сотрудников;
- журнал действий.

### EngineerWindow
- работа с объектами;
- просмотр датчиков;
- создание инженерных задач.

### styles.py
- стили интерфейса;
- цвета;
- шрифты;
- локализация.

---

## Polling

Desktop-приложение использует polling.

```python
self.poll_timer.start(10000)
```

Каждые 10 секунд выполняется обновление данных.

---

## API взаимодействие

Все запросы выполняются через:

```python
api_request()
```

Функция:
- отправляет HTTP запрос;
- добавляет JWT токен;
- обрабатывает ошибки;
- возвращает JSON данные.

---

# 10. Mobile-приложение

Mobile-клиент предназначен для технического инженера.

## Основной функционал

- просмотр задач;
- изменение статуса задач;
- загрузка отчётов;
- работа с объектами.

## Технологии

- React Native
- Expo
- EAS Build

---

# 11. Web-сайт

Web-сайт предназначен для обычного пользователя системы.

## Основной функционал

- регистрация;
- авторизация;
- создание заявки;
- просмотр статусов;
- работа с личным кабинетом.

---

# 12. База данных

Проект использует PostgreSQL.

Основные сущности:

- users;
- employees;
- facilities;
- sensors;
- equipment;
- engineer_tasks;
- reports;
- logs.

## Миграции

Для миграций используется:

```text
Alembic
```

---

# 13. Тестирование

В проекте реализованы автоматизированные тесты.

## Используемые виды тестирования

- unit tests;
- integration tests;
- RBAC tests;
- ownership tests;
- security tests;
- API tests;
- CQRS wiring tests.

## Запуск тестов

```bash
pytest -q
```

## Проверка компиляции

```bash
python -m compileall app tests
```

---

# 14. CI/CD

Используется GitHub Actions.

Pipeline выполняет:

```text
install dependencies
compile check
pytest
```

## Workflow

```text
.github/workflows/ci.yml
```

CI позволяет автоматически проверять backend после каждого push и pull request.

---

# 15. Deployment

## Backend

### Render

```text
Build:
pip install -r requirements.txt

Start:
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

## Site

### Render

```text
Root Directory: site

Build:
npm install

Start:
npm start
```

---

## Mobile

```text
EAS Build (APK)
```

---

# 16. Production URLs

## Backend API

```text
https://sports-facility-api.onrender.com
```

## Frontend Site

```text
https://site-zw5j.onrender.com
```

---

# 17. Структура проекта

```text
sports-facility-api/
├── app/
├── tests/
├── docs/
├── site/
├── desctop11/
├── EngineerMobile финал/
├── alembic/
├── requirements.txt
├── docker-compose.yml
├── render.yaml
└── README.md
```

---

# 18. Документация

Дополнительная документация находится в папке:

```text
docs/
```

Основные документы:

```text
docs/test_plan.md
docs/security_checklist.md
docs/sad.md
docs/risk_register.md
docs/readme_manual.md
docs/application_appendix.md
```

---

# 19. Запуск проекта

## Backend

```bash
py -3.11 -m venv .venv

.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

alembic upgrade head

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Site

```bash
cd site

npm install

npm start
```

---

## Desktop

```bash
pip install PySide6 requests

python desctop11/desctop11/desctop/main.py
```

---

## Mobile

```bash
cd "EngineerMobile финал/EngineerMobile"

npm install

npm start
```

---

# 20. Команда проекта

Проект разработан командой:

- Григорьева А.Е.
- Додонова М.С.
- Жамнова М.А.
- Терещенко В.В.

---

# 21. Основные преимущества проекта

- единый backend для всех клиентов;
- разделение ролей;
- поддержка desktop/mobile/web;
- CQRS архитектура;
- background jobs;
- автоматизированное тестирование;
- CI/CD;
- RBAC безопасность;
- ownership проверки;
- масштабируемость.

---

# 22. Итог

Sports Facilities Monitoring System — это комплексная система мониторинга спортивных объектов, объединяющая web, desktop и mobile клиентов вокруг единого backend API.

Проект демонстрирует:

- клиент-серверную архитектуру;
- REST API;
- RBAC;
- CQRS;
- background jobs;
- очереди;
- автоматизированное тестирование;
- CI/CD;
- многоклиентскую систему мониторинга.
