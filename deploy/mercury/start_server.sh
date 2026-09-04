#!/bin/bash

# Mercury (US) startup script
# Ceres ScheduledTask rows are synced into a managed crontab block by
#   `manage.py sync_scheduled_crontab` (also re-run on every API write).

service cron start
sleep 5

export MERCURY_SCHEDULER=true

python3 manage.py runserver 0.0.0.0:8000 >> server_log.txt 2>&1
