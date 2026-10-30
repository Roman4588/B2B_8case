Исторический отчёт из чата «Подготовить проект к деплою на Amvera». После указанного снимка опубликован релиз v1.0.0, start.sh получил роли web/worker/beat. Актуальная инструкция: deployment-amvera.md. Доступ к кабинету в другом чате подтверждён; текущий чат по-прежнему получает отказ шлюза до открытия сайта.

# Проверка перед деплоем Amvera — 30 октября 2026

Исходники: `F:\B2B_8case`, локальный commit `58fcada4520f13b798b0cbef70c129ec7bfc1bb4`.
Папка текущего чата не содержит исходников. В другом активном чате продолжается работа с этим репозиторием; исходники здесь не менялись.

## Доступ и состояние облака

В новом чате штатно открылся https://cloud.amvera.ru/projects.
Открылось приложение B2B: статус «Запущено», 1/1 реплик.
В репозитории Amvera отображался commit `262803e346d7ed20b5f187b124554f9fa3489475` (Update README.md).
Это отличается от локального HEAD. Статус приложения не доказывает готовность backend, очереди и индексации.
Конфигурация в UI: Dockerfile.amvera, skip=false, порт 80, постоянный диск /data.
Публикация, перезапуск, изменение переменных и платных ресурсов в этом чате не выполнялись.

## Проверенные файлы

- Dockerfile.amvera: Node 22 собирает frontend через npm ci и npm run build; Python 3.12 устанавливает backend/requirements.txt; nginx обслуживает frontend и проксирует /api/ на 127.0.0.1:8000.
- amvera.yaml: путь к Dockerfile, порт 80 и /data согласованы с Dockerfile/nginx и UI.
- frontend/package-lock.json используется через npm ci; прямые зависимости backend закреплены версиями, транзитивные отдельно не зафиксированы.
- .gitattributes задаёт LF, в том числе для deploy/amvera/start.sh.
- start.sh сначала выполняет миграции и seed, затем запускает Uvicorn и nginx. PostgreSQL должен быть доступен до запуска Web.
- .env.example в исходниках предназначен для локального Compose. Для облака нужен отдельный набор адресов, см. amvera.env.example рядом с этим отчётом.

## Что необходимо до обновления облачного стенда

1. PostgreSQL с расширением vector и постоянным диском. Не заменять SQLite: код использует pgvector и PostgreSQL advisory locks.
2. Redis по приватному адресу. Если включена аутентификация, указать её в REDIS_URL; пароль URL-encode.
3. Web из Dockerfile.amvera. Команда запуска уже задана в CMD, переопределять не требуется.
4. Worker из backend/Dockerfile (target runtime): `celery -A app.tasks.celery worker --pool=threads --concurrency=2 --loglevel=INFO`.
5. Один Beat: `celery -A app.tasks.celery beat --loglevel=INFO --schedule=/tmp/celerybeat-schedule`.
6. Prometheus и учебный exporter либо действующий внешний Prometheus. Конфигурация deploy/prometheus сейчас использует Compose-имя demo-exporter:9101: в облаке нужен реальный приватный адрес exporter.
7. Одинаковые DATABASE_URL, REDIS_URL и параметры мониторинга у Web/worker/beat. SESSION_SECURE=true у Web при HTTPS.
8. Общий доступ Web и worker к загружаемым файлам: одинаковое имя /data/uploads в разных приложениях само по себе не означает общий диск. До подтверждения общего тома нельзя считать импорт готовым. Если общего тома нет, нужен отдельный вариант хранения/обработки файлов или размещение полного Compose на одном сервере.
9. При необходимости нового администратора задать ADMIN_EMAIL и ADMIN_PASSWORD в секретах Web. При существующем аккаунте пароль автоматически не меняется. Не хранить реальные значения в Git.
10. Выбрать окончательный commit после завершения параллельной работы в прежнем чате, повторить сборку и только затем обновлять Amvera.

Документация Amvera подтверждает настройки Docker и отсутствие поддержки docker-compose.yml: https://docs.amvera.ru/applications/configuration/docker.html.

## Особенности запуска, требующие внимания

- Web не запускает worker/beat. Сам по себе Dockerfile.amvera не поднимает полный стенд.
- start.sh запускает Uvicorn в фоне, а nginx — главным процессом. При падении Uvicorn nginx может остаться запущенным: проверять именно API, а не только статус контейнера.
- Создание администратора в start.sh содержит `|| true`: ошибку создания нельзя исключить по факту успешного запуска nginx.
- Модель загружается worker при первом использовании; /api/health/ready может оставаться initializing до завершения индексации.

## Повторяемые проверки

Выполнять в `F:\B2B_8case`:

```powershell
docker compose config --quiet
docker build --file Dockerfile.amvera --tag b2b8case-amvera:preflight .
docker compose --profile test run --rm --no-deps tests python -m pytest tests/test_config.py -q -o cache_dir=/tmp/pytest-amvera
Invoke-RestMethod http://localhost:8080/api/health/live
Invoke-RestMethod http://localhost:8080/api/health/ready
```

После деплоя: /api/health/live → 200, /api/health/ready → ready с indexed_runbooks > 0; затем проверить вход, импорт документа, поиск, получение события Prometheus, рекомендацию и ручное действие в аудите. Не считать локальную проверку доказательством облачной готовности.

## Результаты текущего прогона

- docker compose config --quiet: exit 0.
- Проверка синтаксиса start.sh через sh -n в Linux-контейнере: exit 0.
- test_config.py с текущими исходниками, смонтированными read-only: 2 passed.
- Локальный /api/health/live: {"status":"alive"}.
- Локальный /api/health/ready: {"status":"ready","indexed_runbooks":79}.
- Frontend в сборке Dockerfile.amvera: npm ci, TypeScript и Vite завершились успешно; два предупреждения lucide-react о директиве use client не прервали сборку.
- Полная сборка Dockerfile.amvera в b2b8case-amvera:preflight: exit 0.
- nginx -t в собранном образе: syntax is ok, test is successful, exit 0.
- python -m pip check в собранном образе: No broken requirements found, exit 0.
- Образ проверен без подключения к рабочей БД и без выполнения миграций в ней. Полный запуск именно этого образа в облаке и функциональная облачная цепочка остаются непроверенными.
