# Sports Facilities Monitoring System

> <sub>Система мониторинга состояния спортивных сооружений с поддержкой web, desktop и mobile клиентов.</sub>

Система мониторинга состояния спортивных сооружений — это программный комплекс для контроля технического состояния объектов, обработки пользовательских заявок, мониторинга инженерного оборудования и работы с отчётами.

---

# 1. Назначение проекта

> <sub>Раздел описывает основную цель разработки системы и её бизнес-задачи.</sub>

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

> <sub>Проект построен по клиент-серверной архитектуре с единым backend API.</sub>

```text
Web Site        \
Desktop Client  ---> Backend API ---> PostgreSQL
Mobile Client  /
```

## Используемые технологии

> <sub>В проекте используются современные backend, frontend и infrastructure технологии.</sub>

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

> <sub>Проект состоит из backend API и трёх клиентских приложений.</sub>

## Backend API

> <sub>Backend является центральной частью системы и обслуживает все клиенты.</sub>

Backend отвечает за:

- авторизацию пользователей;
- обработку JWT токенов;
- проверку ролей;
- обработку заявок;
- работу с датчиками;
- работу с задачами инженеров;
- генерацию отчётов;
- обработку очередей;
- взаимодействие с базой данных.

---

## Web Site

> <sub>Web-сайт используется обычным пользователем системы.</sub>

Пользователь может:

- зарегистрироваться;
- авторизоваться;
- создать заявку;
- просмотреть свои заявки;
- отслеживать статус заявки.

---

## Desktop Client

> <sub>Desktop-приложение используется оператором и инженером по эксплуатации.</sub>

Desktop-клиент разработан на PySide6.

### Функции оператора

- просмотр заявок;
- назначение инженеров;
- просмотр сотрудников;
- просмотр журнала действий.

### Функции инженера по эксплуатации

- просмотр объектов;
- просмотр датчиков;
- анализ оборудования;
- создание инженерных задач;
- работа с журналом.

---

## Mobile Client

> <sub>Mobile-приложение предназначено для технического инженера.</sub>

Основные возможности:

- просмотр задач;
- выполнение задач;
- загрузка отчётов;
- работа с объектами на выезде.

---

# 4. Ролевая модель

> <sub>Каждая роль имеет ограниченный набор возможностей согласно RBAC.</sub>

| Роль | Клиент | Возможности |
|---|---|---|
| USER | Web | Создание и просмотр заявок |
| OPERATOR | Desktop | Работа с заявками |
| ENGINEER | Desktop | Работа с датчиками и оборудованием |
| ENGINEER | Mobile | Выполнение задач и загрузка отчётов |

## Ограничения доступа

> <sub>RBAC ограничивает доступ к функциональности в зависимости от роли пользователя.</sub>

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

> <sub>Backend API обслуживает web, desktop и mobile клиентов.</sub>

## Основные endpoint-ы

> <sub>Все клиенты взаимодействуют с системой через REST API.</sub>

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

> <sub>В проекте используется разделение операций чтения и изменения данных.</sub>

CQRS (Command Query Responsibility Segregation) разделяет:

- Query — операции чтения;
- Command — операции изменения данных.

## Query

> <sub>Query endpoint-ы только читают данные и не изменяют состояние системы.</sub>

```text
GET /bff/desktop/dashboard
GET /bff/mobile/tasks
GET /reports/jobs/{job_id}
GET /bff/desktop/requests/all
```

## Command

> <sub>Command endpoint-ы изменяют данные и состояние системы.</sub>

```text
POST /auth/register
POST /auth/login
POST /engineer-tasks
POST /reports/upload
POST /bff/desktop/requests/{id}/assign
```

## Структура backend

> <sub>Команды и запросы разделены на уровне сервисов backend.</sub>

```text
app/services/commands/
app/services/queries/
```

---

# 7. Очереди и фоновые задачи

> <sub>Для асинхронной обработки используются очереди и background workers.</sub>

Для обработки фоновых задач используется:

```text
Celery + Redis/Valkey
```

Очередь применяется для:

- delayed report generation;
- background jobs;
- eventual consistency.

## Поток обработки

> <sub>Команда превращается в событие, помещается в очередь и обрабатывается worker-процессом.</sub>

```text
command -> domain event -> queue -> worker
```

---

# 8. Безопасность

> <sub>В проекте реализованы механизмы защиты API и пользовательских данных.</sub>

В системе используются:

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

> <sub>Каждая роль имеет доступ только к разрешённым endpoint-ам.</sub>

## Ownership

> <sub>Пользователь может видеть только свои данные и задачи.</sub>

---

# 9. Desktop-приложение

> <sub>Desktop-клиент реализован на PySide6 и работает через polling.</sub>

## Основные модули

### LoginDialog

> <sub>Модуль авторизации сотрудников.</sub>

- авторизация сотрудников;
- получение JWT токена;
- определение роли.

### OperatorWindow

> <sub>Главное окно оператора.</sub>

- работа с заявками;
- просмотр сотрудников;
- журнал действий.

### EngineerWindow

> <sub>Главное окно инженера по эксплуатации.</sub>

- работа с объектами;
- просмотр датчиков;
- создание инженерных задач.

### styles.py

> <sub>Модуль стилей и визуального оформления интерфейса.</sub>

- стили интерфейса;
- цвета;
- шрифты;
- локализация.

---

## Polling

> <sub>Desktop-клиент периодически обновляет данные через QTimer.</sub>

```python
self.poll_timer.start(10000)
```

Каждые 10 секунд выполняется обновление данных.

---

# 10. Mobile-приложение

> <sub>Mobile-клиент предназначен для работы технического инженера на объекте.</sub>

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

> <sub>Web-сайт предоставляет интерфейс обычному пользователю системы.</sub>

## Основной функционал

- регистрация;
- авторизация;
- создание заявки;
- просмотр статусов;
- работа с личным кабинетом.

---

# 12. База данных

> <sub>Система использует PostgreSQL для хранения всех данных.</sub>

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

> <sub>Для управления схемой базы данных используется Alembic.</sub>

```text
Alembic
```

---

# 13. Тестирование

> <sub>Проект покрыт автоматизированными backend тестами на pytest.</sub>

## Используемые виды тестирования

- unit tests;
- integration tests;
- RBAC tests;
- ownership tests;
- security tests;
- API tests;
- CQRS wiring tests.

## Запуск тестов

> <sub>Все backend тесты запускаются через pytest.</sub>

```bash
pytest -q
```

## Проверка компиляции

> <sub>Дополнительно выполняется compile check backend модулей.</sub>

```bash
python -m compileall app tests
```

---

# 14. CI/CD

> <sub>GitHub Actions автоматически проверяет backend после push и pull request.</sub>

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

---

# 15. Deployment

> <sub>Backend и web-сайт размещаются на платформе Render.</sub>

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

> <sub>Mobile-приложение собирается через EAS Build.</sub>

```text
EAS Build (APK)
```

---

# 16. Production URLs

> <sub>Production окружение проекта доступно через Render.</sub>

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

> <sub>Монорепозиторий содержит backend, frontend, mobile, desktop и документацию.</sub>

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

> <sub>Дополнительные документы расположены в папке docs.</sub>

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

> <sub>Проект можно запускать локально для разработки и тестирования.</sub>

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

> <sub>Проект разработан командой студентов.</sub>

- Григорьева А.Е.
- Додонова М.С.
- Жамнова М.А.
- Терещенко В.В.

---

# 21. Основные преимущества проекта

> <sub>Проект объединяет несколько клиентов вокруг единого backend API.</sub>

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

> <sub>Проект демонстрирует современный подход к построению многоклиентской системы мониторинга.</sub>

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
