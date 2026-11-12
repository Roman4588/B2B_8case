# Матрица приёмки на 13 ноября 2026

## Источники и границы

Первичный документ дополнительных требований прочитан целиком: `14. Дополнительные_задачи_Задача_8_переформулировано.docx` из предоставленного пути Downloads; неизменённая копия включена в комплект как [requirements-additional.docx](requirements-additional.docx). Задачи A/B ниже основаны на нём; уточняющие проверки — на задании финальной приёмки.
Исходного ТЗ/презентации организаторов в репозитории не найдено. Прежняя версия этого файла ссылалась на слайды 30–32 и 5–7. Утверждения о пороге 90%, видео, стеке и документе >50 страниц считаются утверждениями README/старых отчётов, а не независимо сверенными требованиями оригинала. Независимый корпус организаторов отсутствует.

Все команды выполняются из корня **текущего комплекта**. Полный backend: `docker compose -p signalis-final-20261112 --profile test run --rm tests`. Браузер: из `frontend`, `BASE_URL=http://localhost:18095`, реквизиты тестового администратора, `npm run test:e2e`. Итоги публикации — в `github-amvera-sync-2026-11-12.md`; `final-readiness.md` сохраняет историческую локальную приёмку.

| Требование | Место реализации | Воспроизводимая проверка | Фактический результат |
|---|---|---|---|
| A: инженер меняет тип, категорию, приоритет; комментарий необязателен | `EngineerFeedback.tsx`, `main.CorrectionInput`, `feedback.save_correction` | `test_correction_auth_validation_idempotence_and_effective_queries`, `feedback-live.spec.ts` | Пройдено в итоговых проверках |
| A: автор, время, атомарный аудит; повтор обновляет одну запись | `feedback.py`, `models.ClassificationCorrection`, миграция 0004 | `test_correction_audit_failure_rolls_back`, `test_concurrent_corrections_and_feedback_are_unique` | Пройдено в итоговых проверках |
| A: отметка «Исправлено инженером» | `main.incident_public`, `Incidents.tsx` | `feedback-live.spec.ts`, перезагрузка | Пройдено в итоговых проверках |
| A: ручные значения в карточке, списке, фильтрах, сортировке и сводке | `main.incidents`, `main.summary`, `feedback.effective` | `test_correction_auth_validation_idempotence_and_effective_queries`, `test_effective_priority_controls_sorting` | Пройдено в итоговых проверках |
| A: опрос не стирает правку; новый эпизод не наследует | `monitoring.ingest_alerts`, отдельная связь по `incidents.id` | `test_ingest_preserves_correction_but_new_episode_does_not_inherit` | Пройдено в итоговых проверках |
| A: экспорт одной командой и пересчёт исходного классификатора | `scripts/export_corrections.py`, `scripts/evaluate.py` | CLI из README; `test_export_uses_saved_inputs_and_evaluates_automatic_classifier` | Пройдено в итоговых проверках; низкие метрики исправленного примера допустимы |
| A: понятный пустой корпус | `evaluate.evaluate` | `test_lexical_explanation_and_empty_evaluation`, CLI с `[]` | Пройдено в итоговых проверках |
| A: обучение и проверка разделены | `classifier.text_models` читает только `app/seed/training.json`; evaluate читает переданный dataset | Просмотр путей чтения, `test_classifier.py`, экспорт вне training/evaluation | Автодообучения нет; экспорт не изменяет обучающий набор |
| B: реальные совпадения слов, честное отсутствие и семантическое сходство | `explanations.py`, `knowledge.search_runbooks`, `Incidents.tsx` | `test_lexical_explanation_and_empty_evaluation`, `test_existing_recommendation_gets_factual_explanation`, live UI | Пройдено в итоговых проверках; лексика и векторы обозначены отдельными сигналами |
| B: сходство не называется вероятностью | `explanations.explain`, UI | `feedback-live.spec.ts` | Пройдено в итоговых проверках |
| B: обе оценки с автором, временем и аудитом | `feedback.save_feedback`, миграция 0004, `RecommendationRating` | `test_feedback_unique_revision_generation_aggregates_and_audit`, `test_feedback_audit_failure_rolls_back`, live UI | Пройдено в итоговых проверках |
| B: повтор идемпотентен, смена оценки обновляет запись | Уникальность author/episode/book/revision, блокировка эпизода | `test_concurrent_corrections_and_feedback_are_unique`, `feedback-live.spec.ts` | Пройдено в итоговых проверках |
| B: сводка соответствует БД по всем редакциям | `feedback.usefulness_counts`, `main.runbooks`, `Knowledge.tsx` | `test_feedback_is_per_author_and_revision_but_summary_combines_revisions`, live UI | Пройдено в итоговых проверках |
| B: редактирование/удаление не портит историю | `recommendation_snapshot`, исторический ID без FK на живую инструкцию | `test_deleting_instruction_preserves_feedback_snapshot`, `test_deleted_runbook_does_not_delete_or_block_historical_feedback` | Пройдено в итоговых проверках |
| B: запоздавший ответ/polling не возвращает старые данные | `api.useResource` version, `Incidents` generation, backend блокировки | `feedback.spec.ts`, `test_feedback_waiting_for_invalidation_rejects_stale_generation` | Пройдено в итоговых проверках |
| Настоящий Prometheus → классификация → рекомендация pgvector | `monitoring`, `classifier`, `knowledge`, Celery | `scripts/smoke.py`, `operator.spec.ts`, `test_knowledge_integration.py` | Пройдено в итоговых проверках |
| Ручные решения и история | `operations.py`, `/actions`, `/history` | `test_workflows.py`, `operator.spec.ts`, smoke | Пройдено в итоговых проверках |
| Создание, правка, импорт, ошибка/retry и удаление | `main`, `documents.py`, `tasks.py` | `test_api.py`, `test_recovery_integration.py`, live UI; PDF60 через smoke | Пройдено в итоговых проверках |
| Вход/выход, инженер/админ в общем рабочем пространстве | `auth.py`, `accounts.py`, `require_admin` для удаления/учётных записей | `test_accounts.py`, `test_api.py`, smoke, браузерные role checks | Пройдено в итоговых проверках; новые ограничения доступа не вводились |
| Чистый старт, миграции и повторный запуск | Compose init, bootstrap, тома models/uploads/postgres | Новый проект/тома, подготовка модели без копирования, restart | Пройдено в итоговых проверках |
| Совместимость изменений безопасности импорта/экспорта | лимиты PDF/DOCX, скрытие путей/ошибок, повторное чтение job под блокировкой | `test_security_review.py`, `test_security_postgres.py`, сборки и общая регрессия | Пройдено в итоговых проверках; пентест не выполнялся |
| Адаптивность и доступность существующих экранов | Текущие CSS и компоненты | `design-live.spec.ts`, `design-states.spec.ts`, остальные UI-тесты | Пройдено в итоговых проверках; Chromium/Edge, не сертификация WCAG |
| Комплектность, актуальность README и видео | README, final-readiness, demo-script, submission-files | Манифест SHA256, ffprobe и просмотр кадров видео | Пройдено в итоговых проверках; старый ролик не демонстрирует A/B |

Итоги версии к публикации: 108 backend-тестов и полный браузерный прогон 35/35. Standalone при 950 MiB / 0,5 CPU прошёл реальные рекомендации и PDF60. Подробности и незасчитанные попытки — в `github-amvera-sync-2026-11-12.md`; предыдущие результаты сохранены в `final-readiness.md`.
