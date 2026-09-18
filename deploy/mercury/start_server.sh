#!/bin/bash

# Mercury (US) startup script
# Ceres ScheduledTask rows are synced into a managed crontab block by
#   `manage.py sync_scheduled_crontab` (also re-run on every API write).

service cron start
sleep 5

export MERCURY_SCHEDULER=true

exec gunicorn mercury.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-4}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --access-logfile - \
  --error-logfile -
