# Публичный просмотр через Render

В корне проекта есть `render.yaml`. Он описывает frontend, FastAPI, Celery worker,
Celery beat, PostgreSQL, Redis-compatible Key Value, Prometheus и учебный exporter.
Render Blueprints создают связанные ресурсы из одного файла.

1. Откройте Render и выберите **New → Blueprint**.
2. Подключите GitHub и репозиторий `Roman4588/B2B_8case`.
3. Выберите ветку `main` и подтвердите Blueprint.
4. В переменной `POSTGRES_PASSWORD` задайте отдельный пароль базы данных.
5. После успешного деплоя откройте публичный URL сервиса `b2b8case-frontend`.
6. Создайте первого администратора через Shell API-контейнера:

```bash
python -m app.manage create-admin
```

Не публикуйте пароли, ключи Prometheus или cookies в GitHub. Для учебной демонстрации
включён синтетический источник; реальные данные мониторинга в него не передаются.

Free web services могут засыпать после простоя. Prometheus и demo exporter в Blueprint
описаны как private services, поэтому их внутренние адреса доступны API и worker,
а наружу публикуется только frontend.
