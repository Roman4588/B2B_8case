# Полный деплой в Amvera

Одного контейнера API+Nginx недостаточно для кейса 8. Используйте общую приватную сеть:

| Сервис | Конфигурация |
|---|---|
| PostgreSQL | PostgreSQL 17 с расширением vector; постоянный диск; база copilot |
| Redis | Redis 7, приватный адрес, постоянный диск |
| Web | Dockerfile.amvera, порт 80, /data для uploads/models |
| Worker | backend/Dockerfile, celery -A app.tasks.celery worker --pool=threads --concurrency=2 --loglevel=INFO; тот же доступ к uploads/models |
| Beat | backend/Dockerfile, celery -A app.tasks.celery beat --loglevel=INFO --schedule=/tmp/celerybeat-schedule |
| Prometheus | deploy/prometheus, порт 9090 внутри сети |
| Учебный exporter | deploy/demo-exporter, порт 9101 внутри сети |

Для API, worker и beat задайте одинаковые DATABASE_URL (postgresql+psycopg://...), REDIS_URL,
PROMETHEUS_URL и DEMO_EXPORTER_URL. Не используйте localhost для другого приложения.
SESSION_SECURE=true для HTTPS. ADMIN_EMAIL/ADMIN_PASSWORD — только секреты приложения.
Пароль применяется при создании нового аккаунта; существующий не сбрасывается автоматически.

Если хостинг не поддерживает общий файловый том для API и worker, используйте полноценный
Compose на одном сервере: файлы импорта должны быть доступны обработчику, а не только web.
Не переключайте на SQLite: поиск и фоновые блокировки требуют PostgreSQL/pgvector.

Перед публикацией: миграции завершены, worker готов, /api/health/ready возвращает ready,
Prometheus online, новый документ индексируется, поиск находит его, событие получает рекомендацию,
ручное действие попадает в аудит. Только после этого помечайте ссылку как рабочее демо.

Размер тарифа выбирается по измеренной памяти всех процессов; самый маленький тариф может
не вместить модель. Создание платных ресурсов и изменение тарифа согласуются с владельцем.

Альтернатива для платформы с одним Dockerfile: Dockerfile.amvera поддерживает APP_ROLE=web (по умолчанию), worker и beat. Создайте три приложения из одного образа; задайте общую БД/Redis и общий доступ к uploads. Это не заменяет отдельные PostgreSQL, Redis и мониторинг. Сначала запустите web для миграций.
