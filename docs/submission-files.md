> Историческая локальная приёмка до публикации в GitHub. Текущая доставка описана в [github-amvera-sync-2026-11-12.md](github-amvera-sync-2026-11-12.md). Указанные ниже архивы и dirty-статус относятся к моменту локальной приёмки.

# Состав передачи текущей локальной версии

Передаётся полный комплект текущих исходников, а не только diff и не прежняя main.
База Git: 875dfc8b7f91f26016d87bc0c301556312dcbdb2. Коммитов/push в этой приёмке нет.
Изменённые tracked-файлы тоже обязательны: в особенности README, backend main/models/documents/tasks/knowledge/requirements/evaluate/Dockerfile, frontend исходники/CSS/config и operator.spec.ts. Их полный актуальный состав подтверждает `source-manifest.json` в комплекте.

## Обязательные untracked для выполнения A/B

- `backend/app/explanations.py`
- `backend/app/feedback.py`
- `backend/migrations/versions/0004_engineer_feedback.py`
- `backend/scripts/export_corrections.py`
- `frontend/src/EngineerFeedback.tsx`
- `frontend/src/engineer-feedback.css`

## Untracked для воспроизводимой проверки

- `backend/tests/test_engineer_feedback.py`
- `backend/tests/test_feedback_postgres.py`
- `backend/tests/test_security_postgres.py`
- `backend/tests/test_security_review.py`
- `frontend/e2e/design-live.spec.ts`
- `frontend/e2e/design-states.spec.ts`
- `frontend/e2e/feedback-live.spec.ts`
- `frontend/e2e/feedback.spec.ts`
- `scripts/acceptance_extra.py`

## Документы комплекта

- `PRODUCT.md`
- `docs/requirements-additional.docx`
- `docs/acceptance.md` (уже tracked; передать изменённую версию)
- `docs/final-readiness.md`
- `docs/demo-script.md`
- `docs/submission-files.md`
- `docs/final-results.json`
- `docs/final-benchmark.json`
- `docs/final-correction-metrics.json`
- `docs/final-empty-metrics.json`

## Исторические материалы

`docs/design-verification-current.md`, `docs/engineer-feedback-current-verification.md` и `docs/superpowers/plans/2026-11-12-feedback-current-main.md` сохранены для происхождения прежних изменений. Они не являются доказательством текущего успешного прогона. `PRODUCT.md` сохраняет согласованный контекст дизайна. Видео и необходимые иллюстрации README берутся из `docs/media`.

## Исключено из сдачи

- `.git`, `.env`, cookies и любые персональные реквизиты.
- Логи `*.log`, outputs, test-results, traces, временные скриншоты и загрузки.
- Кеши Python/pytest/Ruff/npm, node_modules, dist, локальные БД и данные Docker-томов.
- `.hallmark/` (локальные журналы инструментов), `test-documents/` (чужие локальные тестовые загрузки, не используются текущими проверками).
- `docs/amvera-evidence/` (исторические снимки, журналы и данные размещения; не нужны для локального запуска). Исторические отчёты о размещении могут ссылаться на исключённые вложения; актуальная локальная приёмка от них не зависит.

Исходный дополнительный DOCX включён без изменения. Оригинальное ТЗ организаторов не найдено; его отсутствие нельзя компенсировать старыми заявлениями README.
Модель и базовые Docker-образы не вложены: их подготовка по README требует интернета. Секреты, тома и тестовые загрузки передавать не нужно.

## Что остаётся команде

1. Передать именно подготовленный архив/каталог и его SHA256 проверяющему; сверить `source-manifest.json`.
2. Либо отдельно согласовать коммит и публикацию этой версии. Не ссылаться на прежнюю main как на проверенную версию.
3. Создать администратора при первом запуске на машине проверяющего и заранее подготовить модель для демонстрации.
4. Использовать `demo-script.md` для A/B; старый ролик их не показывает. Если организаторы требуют новое видео, решение о его пересборке остаётся отдельной задачей.
