# Risk Register — Sports Facilities Monitoring API

## Формат оценки
- Вероятность: Low / Medium / High
- Влияние: Low / Medium / High / Critical
- Приоритет: рассчитывается по сочетанию вероятности и влияния

## Реестр рисков
| ID | Риск | Вероятность | Влияние | Приоритет | Признак/триггер | Митигация | Владелец |
|---|---|---|---|---|---|---|---|
| R1 | Несоответствие документации и фактического поведения API | Medium | High | High | На защите находят endpoint/поле, которого нет в коде | Поддерживать документы “по факту”, регресс-сверка перед релизом | Backend lead |
| R2 | IDOR (доступ к чужим задачам/отчётам) | Medium | Critical | Critical | Запросы с чужими ID возвращают данные | Жёсткие ownership-проверки в каждом защищённом endpoint | Security owner |
| R3 | Ошибка ролевой модели (лишний доступ) | Medium | High | High | Роль ENGINEER получает desktop права | Матрица RBAC тестов + обязательные негативные кейсы | Backend lead |
| R4 | Утечка токенов/секретов в логах | Low | Critical | High | В логах виден token/query secret | Санитизация логов, запрет логирования чувствительных заголовков | DevOps |
| R5 | Брутфорс логина | Medium | High | High | Много неудачных попыток за короткое время | Rate limit + временная блокировка попыток | Security owner |
| R6 | Нарушение CORS в production | Medium | High | High | Случайный доступ с посторонних origin | Whitelist origins, запрет wildcard в production | DevOps |
| R7 | Сбой фоновой очереди (jobs не обрабатываются) | Medium | High | High | Job застревают в CREATED/ACTIVE | Мониторинг worker, статус job endpoint, алерты | Backend lead |
| R8 | Eventual consistency воспринимается как “баг” | High | Medium | Medium | UI не видит моментальное обновление после команды | Realtime события + retry/polling политика в клиентах | Product/Frontend |
| R9 | Потеря файлов отчётов в storage | Low | High | Medium | Для uploaded report файл отсутствует | Проверка целостности и понятные 409-сообщения, backup policy | DevOps |
| R10 | Непредсказуемость demo-данных датчиков | Medium | Medium | Medium | Пользователи видят резкие скачки или “странные” состояния | Контроль режима fake data, явные сценарии деградации/восстановления | Backend lead |
| R11 | Ошибки релиза на Render из-за env | Medium | High | High | Приложение не стартует после деплоя | Предрелизная проверка env, health check, import smoke | DevOps |
| R12 | Нагрузка на списковые BFF endpoint-ы | Medium | Medium | Medium | Замедление dashboard/reports/tasks | Пагинация, фильтры, кэш, оптимизация запросов | Backend lead |
| R13 | SQL injection через фильтры | Low | High | Medium | Подозрительные payload в query/body | Только bind-параметры и валидация enum/date/id | Security owner |
| R14 | XSS в пользовательских текстовых полях | Medium | High | High | Скрипт/HTML отображается в UI | Санитаризация текстов на backend + безопасный рендер на frontend | Backend + Frontend |
| R15 | Конфликт версий API у клиентов | Medium | Medium | Medium | Один клиент ломается после изменений | Backward-compatible policy, контрактные изменения только через доп. поля | Backend lead |

## Текущие приоритеты перед защитой
1. R1 (сверка документов с реализацией).
2. R2/R3 (RBAC + ownership негативные тесты).
3. R6/R11 (production CORS/env стабильность).
4. R7 (проверка очереди и статусов jobs).

## План снижения остаточных рисков
1. Перед защитой выполнить полный smoke по ролям и ключевым endpoint-ам.
2. Выполнить Burp checklist на IDOR, auth bypass, mass assignment, token reuse.
3. Зафиксировать результаты в кратком security отчёте.
4. На демо использовать только подтверждённые сценарии из test plan.
