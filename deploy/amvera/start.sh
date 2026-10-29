#!/bin/sh
set -eu
python -m app.bootstrap
if [ -n "${ADMIN_EMAIL:-}" ] && [ -n "${ADMIN_PASSWORD:-}" ]; then
  ADMIN_EMAIL="$ADMIN_EMAIL" ADMIN_PASSWORD="$ADMIN_PASSWORD" python -m app.manage create-admin --non-interactive || true
fi
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
exec nginx -g 'daemon off;'
