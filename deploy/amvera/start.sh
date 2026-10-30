#!/bin/sh
set -eu
case "${APP_ROLE:-web}" in
  web)
    python -m app.bootstrap
    if [ -n "${ADMIN_EMAIL:-}" ] && [ -n "${ADMIN_PASSWORD:-}" ]; then
      python -m app.manage create-admin --non-interactive || {
        echo 'Administrator provisioning did not complete; inspect the message above. Existing accounts require reset-password.' >&2
      }
    fi
    uvicorn app.main:app --host 127.0.0.1 --port 8000 &
    exec nginx -g 'daemon off;'
    ;;
  worker)
    exec celery -A app.tasks.celery worker --pool=threads --concurrency=2 --loglevel=INFO
    ;;
  beat)
    exec celery -A app.tasks.celery beat --loglevel=INFO --schedule=/tmp/celerybeat-schedule
    ;;
  *) echo 'APP_ROLE must be web, worker or beat' >&2; exit 1 ;;
esac