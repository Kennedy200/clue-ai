#!/bin/sh
# api    : run migrations, then serve
# worker : wait for the API to have migrated, then process jobs
set -e
case "$1" in
  api)
    python -m alembic upgrade head
    exec python -m uvicorn clue.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
    ;;
  worker)
    until curl -fsS http://api:8000/api/health >/dev/null 2>&1; do echo "waiting for the API..."; sleep 3; done
    exec python -m clue.worker
    ;;
  backup)
    exec python -m clue.backup create --out /data/backups
    ;;
  *)
    exec "$@"
    ;;
esac
