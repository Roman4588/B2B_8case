# ИИ-Ассистент Дежурного — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать готовый локальный проект кейса 8, подтвердить требования проверками и сохранить результат в Roman4588/B2B_8case.

**Architecture:** React SPA обращается к FastAPI через Nginx. PostgreSQL/pgvector хранит события, регламенты, задания и аудит; Celery/Redis выполняет импорт, индексацию и классификацию. Реальный Prometheus получает демонстрационные метрики, а приложение опрашивает его API.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL 17/pgvector, Celery, Redis, FastEmbed/ONNX, scikit-learn, React, TypeScript, Vite, Nginx, pytest, Playwright.

**Spec:** [Согласованная спецификация](../specs/2026-10-22-case8-design.md), подтверждена пользователем 22 октября 2026 года.

## Global Constraints

- Основной запуск: docker-compose up --build.
- Типы: критическое, предупреждение, информационное.
- Категории: сервер, сеть, БД, приложение.
- Приоритеты: P1–P4; политика отображается в документации и объяснении классификации.
- Порог приёмки — минимум 90% полностью верных троек на этом наборе; отдельные метрики также публикуются.
- Для PDF/DOCX больше 50 страниц используется очередь с отслеживанием прогресса.
- Эмбеддинги: FastEmbed/ONNX Runtime, sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2, 384 измерения.
- Подтверждение меняет только запись в приложении и создаёт запись аудита.
- Модель запускается на CPU; GPU, аккаунт в облаке и платный LLM не требуются.
- Секреты и пользовательские данные не коммитятся в GitHub.
- Без доступного Docker нельзя заявлять проверенный полный запуск контейнерного стенда.

## Review Focus

1. Повторная доставка Celery-задачи после сбоя: не создаёт дубликаты регламентов и рекомендаций; тест в задаче 4.
2. Пустой ответ Prometheus и отказ Prometheus: первый закрывает восстановленные события, второй сохраняет активные; тест в задаче 5.
3. Загрузка файла с неверным расширением, путём в имени или без текста: понятная ошибка без зависшего задания; тест в задаче 4.
4. Низкая уверенность, отсутствие близких инструкций, недоступная модель: явное состояние ручной проверки/ошибки; тесты в задачах 2–3.
5. Повторное ручное подтверждение, устаревшее окно и перезапуск сервисов: корректные переходы, отсутствие повторного аудита и сохранение данных; тесты в задачах 6 и 8.

## Карта файлов

- `backend/app/core/`: окружение, подключение к БД, авторизация, журналирование.
- `backend/app/models.py`, `schemas.py`: таблицы и публичные схемы API.
- `backend/alembic/`: последовательные миграции PostgreSQL и pgvector.
- `backend/app/classification/`: обучение, вывод модели и политика приоритетов.
- `backend/app/knowledge/`: модель эмбеддингов, разбиение текста, поиск.
- `backend/app/documents/`: чтение JSON/MD/TXT/PDF/DOCX и импорт.
- `backend/app/monitoring/`: клиент Prometheus и синхронизация событий.
- `backend/app/tasks/`: конфигурация Celery, задания, периодический опрос.
- `backend/app/api/`, `backend/app/main.py`: REST API и состояние готовности.
- `backend/tests/`: модульные и интеграционные проверки.
- `datasets/`, `backend/scripts/`: обучение и отдельная оценка классификатора.
- `frontend/src/features/`: события, база знаний, источники, аудит и вход.
- `frontend/src/lib/`: типизированный HTTP-клиент и общие компоненты.
- `deploy/`: Nginx, Prometheus, правила алертов и демонстрационный экспортёр.
- `tests/e2e/`, `scripts/`: браузерные проверки и проверка готового стенда.
- `docs/`: запуск, приёмка, отчёт проверки, сценарий демонстрации.
- `docker-compose.yml`, Dockerfile, файлы зависимостей: воспроизводимая сборка.

Каждый модуль имеет одну ответственность; обработчики API не запускают тяжёлые вычисления.

## Task 1: Контракт данных, PostgreSQL и миграции

**Files:** `backend/pyproject.toml`, `backend/app/core/config.py`, `backend/app/core/db.py`, `backend/app/models.py`, `backend/app/schemas.py`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_initial.py`, `backend/tests/conftest.py`, `backend/tests/test_persistence.py`, `.gitignore`, `.env.example`.

**Interfaces:**
- Produces: `Settings`, `get_settings() -> Settings`, `get_session() -> Iterator[Session]`.
- Produces: таблицы `User`, `SessionToken`, `Incident`, `Runbook`, `RunbookChunk`, `Recommendation`, `ImportJob`, `SourceState`, `AuditEntry`.
- `Incident`: UUID, source, external_id, title, description, host, labels, severity, category, priority, confidence, needs_review, lifecycle_state, handling_state, first_seen_at, last_seen_at, recovered_at.
- Уникальность: (source, external_id); lifecycle_state = firing/resolved; handling_state = new/accepted/completed/dismissed.
- Схемы: `IncidentInput`, `ClassificationResult`, `RunbookInput`, `RunbookHit`, `JobView`; перечисления имеют стабильные английские значения, русский текст задаёт интерфейс.

- [ ] Написать `test_migration_and_unique_incident`: применены миграции, vector extension доступно, повтор source/external_id отклоняется.
- [ ] Запустить `python -m pytest backend/tests/test_persistence.py -q`; до реализации ожидается ошибка отсутствующих модулей/таблиц.
- [ ] Реализовать модели, настройки, схемы и миграцию. PostgreSQL URL обязателен для основного режима; SQLite не подменяет интеграционные тесты.
- [ ] Выполнить тест с тестовой PostgreSQL и `alembic upgrade head`; проверить откат/повтор миграции на отдельной БД.
- [ ] Зафиксировать: `feat: add PostgreSQL domain model and migrations`.

## Task 2: Классификатор и независимый от обучения набор проверки

**Files:** `backend/app/classification/{types,policy,model,training}.py`, `backend/scripts/{train_classifier,evaluate_classifier}.py`, `datasets/{train,evaluation}.jsonl`, `datasets/README.md`, `backend/tests/test_classification.py`.

**Interfaces:**
- Consumes: `IncidentInput`, `ClassificationResult` из задачи 1.
- Produces: `classify(event: IncidentInput) -> ClassificationResult`.
- Produces: `train(data_path: Path, output_path: Path) -> None`; `evaluate(data_path: Path) -> dict`.
- Severity: critical/warning/info; category: server/network/database/application; priority: P1/P2/P3/P4.
- Приоритет: critical → P1; warning с impact=high → P2; остальные warning → P3; info → P4.
- Структурированные severity/category принимаются только из разрешённых значений; при отсутствии меток применяется обученная текстовая модель.
- Текстовая модель: word/character TF-IDF и логистическая регрессия; версия обучения и происхождение примеров документируются.
- Неизвестная лексика/низкая уверенность вызывает needs_review; оценка модели не называется гарантией правильности.

- [ ] Написать `test_label_mapping_and_priority_policy` с проверками `critical -> P1`, `warning + impact=high -> P2`, `warning -> P3`, `info -> P4`.
- [ ] Написать `test_unknown_event_needs_review` и `test_training_and_evaluation_groups_do_not_overlap`.
- [ ] Запустить `python -m pytest backend/tests/test_classification.py -q`; подтвердить ожидаемый провал.
- [ ] Создать размеченные наборы с идентификаторами семейств; исключить общие семейства и совпадающие тексты. Реализовать обучение и вывод без чтения evaluation при обучении.
- [ ] Выполнить `python -m backend.scripts.train_classifier` и `python -m backend.scripts.evaluate_classifier --output artifacts/classification-report.json`; вывести точности каждого поля, всей тройки и матрицы ошибок; ненулевой exit code при triple_accuracy < 0.90.
- [ ] Зафиксировать: `feat: classify incidents and add reproducible evaluation`.

## Task 3: База знаний, эмбеддинги и pgvector-поиск

**Files:** `backend/app/knowledge/{embedding,chunking,service}.py`, `backend/tests/test_knowledge.py`, `backend/seed/runbooks.json`.

**Interfaces:**
- Consumes: модели Runbook/RunbookChunk и `RunbookInput` из задачи 1.
- Produces: `EmbeddingService.embed(texts: list[str]) -> list[list[float]]` — 384 числа на вектор.
- Produces: `index_runbook(session: Session, runbook_id: UUID) -> None`.
- Produces: `search_runbooks(session: Session, query: str, limit: int = 3) -> list[RunbookHit]`.
- RunbookInput содержит title, condition, steps, cautions, category, source.
- Поиск использует cosine distance в PostgreSQL и ограниченный порог релевантности; оценка называется сходством.
- Эмбеддинги создаются из условия/контекста; рекомендации содержат сохранённые шаги и ссылку на исходный регламент.

- [ ] Написать `test_russian_and_english_queries_find_expected_runbook`: запросы о заполненном диске и Nginx находят соответствующие разные инструкции.
- [ ] Написать `test_unrelated_query_has_no_recommendation` и `test_model_failure_is_visible`.
- [ ] Запустить `python -m pytest backend/tests/test_knowledge.py -q`; подтвердить провал.
- [ ] Реализовать ленивую загрузку локальной модели, разбиение текста и поиск; обновление регламента атомарно заменяет его фрагменты.
- [ ] Повторить тесты с настоящей моделью и PostgreSQL; отдельный маркер integration исключает выдачу замоканного поиска за проверку модели.
- [ ] Зафиксировать: `feat: add multilingual pgvector runbook retrieval`.

## Task 4: Надёжный асинхронный импорт документов

**Files:** `backend/app/documents/{extractors,importer}.py`, `backend/app/tasks/{celery_app,documents}.py`, `backend/tests/{test_documents,test_document_worker}.py`.

**Interfaces:**
- Consumes: `index_runbook` из задачи 3, `ImportJob` из задачи 1.
- Produces: `extract_document(path: Path, media_type: str) -> str`.
- Produces: Celery `import_document(job_id: str) -> dict`.
- Состояния job: queued/running/succeeded/failed; поля processed/total/error.
- JSON требует condition и steps; текстовые инструкции разбираются по заголовкам и «Если … → …».
- Приём файла ограничен 25 МБ; допустимы .json/.md/.txt/.pdf/.docx; имя хранения — UUID.
- PDF читает pypdf, DOCX — python-docx; формат проверяется также содержимым. Для пустого/повреждённого документа сохраняется понятная ошибка.
- Файлы DOCX проверяются на суммарный распакованный размер до чтения XML.
- Задачи сериализуются JSON, повторяются ограниченно, повторный запуск использует стабильный ключ (job_id, fragment_index).

- [ ] Написать `test_accepts_60_page_pdf_as_background_job`: приём возвращает 202 и job_id до извлечения; worker обрабатывает минимум 60 страниц.
- [ ] Написать `test_retry_does_not_duplicate_runbooks`, `test_rejects_fake_extension_and_unsafe_filename`, `test_empty_pdf_job_fails_with_reason`.
- [ ] Запустить `python -m pytest backend/tests/test_documents.py backend/tests/test_document_worker.py -q`; подтвердить провал.
- [ ] Реализовать extractors и идемпотентную Celery-задачу; прогресс и ошибка хранятся в PostgreSQL.
- [ ] Выполнить тесты с отдельным worker и Redis, дождаться succeeded без удерживания HTTP-соединения.
- [ ] Зафиксировать: `feat: import large runbooks through Celery`.

## Task 5: Интеграция Prometheus и жизненный цикл событий

**Files:** `backend/app/monitoring/{prometheus,sync}.py`, `backend/app/tasks/monitoring.py`, `backend/tests/test_monitoring.py`, `deploy/prometheus/{prometheus,alerts}.yml`, `deploy/demo_exporter/{app.py,Dockerfile,requirements.txt}`.

**Interfaces:**
- Consumes: `classify`, `search_runbooks`, модели Incident/SourceState/Recommendation.
- Produces: `PrometheusClient.fetch_alerts() -> list[IncidentInput]` через GET /api/v1/alerts.
- Produces: `synchronize_source(session: Session, source: str) -> dict`.
- Produces: Celery `poll_monitoring() -> dict` и `enrich_incident(incident_id: str) -> dict`.
- external_id строится из стабильно отсортированных labels; annotations не меняют идентичность.
- Только firing alerts создают активные инциденты; pending не считаются firing.
- Опрос каждые 15 секунд, таймаут 10 секунд, проверка ответа status/data/alerts.
- При ошибке запроса обновляется SourceState.error, но инциденты не закрываются.
- Демонстрационный экспортёр отдаёт метрики сервера, сети, БД и приложения; имитация восстановления меняет метрику, затем настоящий Prometheus меняет alert.

- [ ] Написать `test_repeated_poll_is_idempotent`, `test_successful_empty_poll_resolves_incident`, `test_failed_poll_preserves_active_incidents`, `test_pending_alert_is_not_incident`.
- [ ] Запустить `python -m pytest backend/tests/test_monitoring.py -q`; подтвердить провал.
- [ ] Реализовать клиент, синхронизацию и фоновые задания; внешние URL/токен берутся из окружения.
- [ ] Выполнить контрактные тесты и интеграционный опрос настоящего Prometheus; проверить четыре категории и восстановление.
- [ ] Зафиксировать: `feat: ingest real Prometheus alerts with recovery tracking`.

## Task 6: REST API, профиль инженера и ручные действия

**Files:** `backend/app/core/auth.py`, `backend/app/api/{auth,incidents,runbooks,jobs,sources,audit,health}.py`, `backend/app/main.py`, `backend/tests/{test_api,test_manual_actions,test_auth}.py`.

**Interfaces:**
- Consumes: сервисы задач 1–5.
- Produces: /api/auth/login, /api/auth/logout, /api/auth/me.
- Produces: GET /api/incidents (q, severity, category, priority, state, page), GET /api/incidents/{id}.
- Produces: POST /api/incidents/{id}/actions с action=accept/complete/dismiss и comment.
- Produces: GET/POST /api/runbooks, PATCH /api/runbooks/{id}, POST /api/runbooks/import.
- Produces: GET /api/jobs/{id}, GET /api/sources, POST /api/sources/sync, GET /api/audit, GET /api/health/live, GET /api/health/ready.
- Учётная запись demo локального стенда задаётся в .env.example; пароль хранится как PBKDF2 hash.
- Сессия — случайный токен в HttpOnly SameSite cookie, в БД хранится hash; изменяющие запросы проверяют Origin.
- Правила действий: accept из new; complete из accepted; dismiss из new/accepted.
- Повтор того же действия идемпотентен; конфликт перехода — 409; восстановление мониторинга и ручной статус независимы.
- Аудит содержит actor, action, incident_id, timestamp, comment и не содержит секретов.
- Ни один обработчик не запускает инфраструктурную команду.

- [ ] Написать `test_confirm_only_changes_state_and_audit`: подтверждение обновляет статус и добавляет одну запись; повтор не добавляет вторую.
- [ ] Написать `test_stale_transition_returns_409`, `test_login_and_unauthenticated_write`, `test_readiness_reports_missing_model`.
- [ ] Запустить `python -m pytest backend/tests/test_api.py backend/tests/test_manual_actions.py backend/tests/test_auth.py -q`; подтвердить провал.
- [ ] Реализовать REST и авторизацию; OpenAPI описывает поля, ошибки и асинхронные ответы.
- [ ] Повторить тесты; проверить отсутствие shell/SSH/remediation зависимостей и путей выполнения в приложении.
- [ ] Зафиксировать: `feat: expose authenticated API and audited manual workflow`.

## Task 7: Готовый интерфейс дежурного

**Files:** `frontend/package.json`, `frontend/package-lock.json`, `frontend/{index.html,tsconfig.json,vite.config.ts}`, `frontend/src/{main.tsx,App.tsx,styles.css}`, `frontend/src/lib/{api,types}.ts`, `frontend/src/features/{incidents,knowledge,sources,audit,auth}/`, `tests/e2e/operator.spec.ts`.

**Interfaces:**
- Consumes: REST задачи 6; общие типы соответствуют OpenAPI.
- Produces: экраны «События», «База знаний», «Источники», «Журнал» и форма входа.
- Дашборд: сводка, фильтры, список инцидентов, детали и панель рекомендаций.
- По умолчанию новые события обновляются каждые 5 секунд; детали выбранного события сохраняются.
- Подтверждение имеет текст «Принято к ручному выполнению» и пояснение, что действия выполняет инженер.
- База знаний: форма «Если → действие», загрузка, статус прогресса, редактирование.
- Есть состояния загрузки, отсутствия событий/инструкций, ошибки API и недоступного источника.
- При ширине 375 px интерфейс не имеет горизонтальной прокрутки; цвет дополняется текстовыми обозначениями.

- [ ] Написать browser-тест `operator can filter, inspect and confirm an incident` с проверками статуса, источника инструкции и записи журнала.
- [ ] Написать `upload job shows progress and failure` и `mobile layout keeps controls accessible`.
- [ ] Запустить `npx playwright test tests/e2e/operator.spec.ts`; подтвердить провал до интерфейса.
- [ ] Реализовать SPA, типизированный клиент, обработку ошибок и адаптивное оформление; рекомендации показывают фактические регламенты API.
- [ ] Выполнить `npm run typecheck`, `npm run build`, затем браузерные сценарии на реальном API; осмотреть desktop/mobile.
- [ ] Зафиксировать: `feat: build Russian operator dashboard and knowledge interface`.

## Task 8: Воспроизводимый Docker-пакет и первоначальные данные

**Files:** `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `deploy/nginx.conf`, `backend/app/bootstrap.py`, `scripts/{wait_ready,smoke}.py`, `.dockerignore`.

**Interfaces:**
- Consumes: все компоненты задач 1–7.
- Produces: стандартный запуск одной командой, frontend на http://localhost:8080; OpenAPI на /api/docs.
- db использует образ pgvector с PostgreSQL 17; Redis и Prometheus имеют закреплённые теги; frontend собирается многоэтапно.
- init запускает миграции и идемпотентное создание профиля/регламентов до API и worker.
- worker загружает модель в общий volume и индексирует seed; readiness не сообщает ready до действительной готовности.
- beat работает в одном экземпляре; healthchecks и depends_on учитывают готовность сервисов.
- Только frontend публикуется на loopback; служебные порты доступны внутри Compose.
- Постоянные volumes: PostgreSQL, модель, файлы; логи контейнеров ограничены размером.
- .env.example не обязателен для копирования: безопасные локальные defaults позволяют указанную команду запуска.

- [ ] Написать smoke-проверки `ready -> login -> incident -> recommendation -> manual action -> audit`.
- [ ] Запустить на чистых volumes; до конфигурации ожидается провал smoke.
- [ ] Реализовать Compose, Dockerfile, Nginx и bootstrap; закрепить зависимости и исключить node_modules/.venv из контекста.
- [ ] Выполнить `docker compose config --quiet`, `docker-compose up --build -d`, `python scripts/wait_ready.py`, `python scripts/smoke.py`.
- [ ] Перезапустить сервисы; проверить сохранение принятого статуса/аудита и отсутствие повторных seed-записей.
- [ ] Если Docker недоступен, не отмечать задачу проверенной: подготовить контейнерные файлы, сохранить точную причину и завершить независящие проверки.
- [ ] Зафиксировать: `build: package complete local monitoring stack`.

## Task 9: Итоговая приёмка, документация и передача

**Files:** `README.md`, `docs/{acceptance,windows-setup,demo-script,verification}.md`, `artifacts/classification-report.json`, `scripts/verify.ps1`, `.github/workflows/ci.yml`.

**Interfaces:**
- Consumes: результаты всех проверок, зафиксированные зависимости и фактические ошибки среды.
- Produces: README на русском с Windows/Docker prerequisites, основным запуском, адресом интерфейса,
  локальными реквизитами, остановкой, сохранением/сбросом данных и curl-примерами.
- windows-setup объясняет размещение Docker disk image и модельных данных на D без переноса системных папок.
- acceptance сопоставляет каждый пункт согласованной спецификации с файлами и результатом проверки.
- demo-script: сценарий до 5 минут — проблема, архитектура, живое событие, регламент, ручное подтверждение, метрики.
- verification разделяет реально выполненное, не выполненное и требующее пользовательских материалов (видео команды).
- CI повторяет тесты на PostgreSQL/Redis и сборку SPA; отдельный полный Compose smoke проверяет доставку.

- [ ] Выполнить полный backend suite, оценку модели, сборку SPA, тест 60-страничного документа и браузерный сценарий.
- [ ] Выполнить проверку чистого Compose запуска; сохранить команды, дату, версии и результаты, а не предположения.
- [ ] Проверить по спецификации, что все критерии имеют фактическое подтверждение либо явно указанную незавершённость.
- [ ] Получить отдельное итоговое ревью реализации; исправить подтверждённые замечания и повторить только затронутые проверки.
- [ ] Написать документацию на основе фактически воспроизведённого запуска и результатов; не коммитить кэши, модели, токены и временные файлы.
- [ ] Сохранить все исходники и результаты в GitHub; проверить итоговый commit/tree удалённого репозитория.
- [ ] Передать пользователю ссылку на проект, короткие команды запуска и существенные ограничения.
- [ ] Зафиксировать: `docs: document verified case 8 delivery and launch`.

## Зависимости и исполнение

Порядок: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9.
Интерфейсы тесно связаны; для этого проекта рекомендовано последовательное исполнение
в текущем чате с отдельным итоговым ревью.
Альтернатива — отдельный исполнитель и проверяющий на каждую задачу: больше независимых
проверок, но дополнительные контексты и затраты.

План проверен на покрытие спецификации, согласованность типов и наличие проверок пяти
условий из Review Focus. Реализация начинается после рассмотрения плана пользователем
и выбора способа исполнения.
