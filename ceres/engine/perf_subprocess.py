"""Standalone subprocess entry point for one PerfRun.

Spawned by `PerfPlanViewSet.run` as:
    python /path/to/perf_subprocess.py <perf_run_id>

The `gevent.monkey.patch_all()` call MUST be the very first executable
statement — before any `import django`, `import requests`, `import socket`
etc. — otherwise those modules' locks/state get patched mid-life and
the interpreter falls over with "cannot release un-acquired lock". For
this reason we do NOT register this as a Django management command:
manage.py imports Django before our patch line ever runs.

This is the same gotcha that drives Locust to ship its own CLI rather
than slot into a Django/Flask CLI.
"""
# ── Step 1: monkey-patch. Nothing else may come before this. ─────────
from gevent import monkey
monkey.patch_all()

# ── Step 2: now Django + project imports are safe. ───────────────────
import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mercury.settings')

import django
django.setup()

from django.utils import timezone  # noqa: E402

logger = logging.getLogger(__name__)


def main():
    if len(sys.argv) != 2:
        sys.stderr.write('usage: perf_subprocess.py <perf_run_id>\n')
        sys.exit(2)
    try:
        run_id = int(sys.argv[1])
    except ValueError:
        sys.stderr.write(f'invalid run id: {sys.argv[1]!r}\n')
        sys.exit(2)

    from ceres.models_perf import PerfRun
    from ceres.engine.perf_driver import PerfDriver

    try:
        run = PerfRun.objects.select_related('perf_plan__env').get(id=run_id)
    except PerfRun.DoesNotExist:
        sys.stderr.write(f'PerfRun {run_id} not found\n')
        sys.exit(2)

    try:
        PerfDriver(run.perf_plan, run).run()
    except Exception as e:
        logger.exception(f'PerfRun {run_id} driver crashed')
        try:
            run.refresh_from_db()
            run.status = 'failed'
            run.error_message = str(e)[:5000]
            run.finished_at = timezone.now()
            run.save(update_fields=['status', 'error_message', 'finished_at', 'updated_at'])
        except Exception:
            logger.exception(f'Also failed to mark PerfRun {run_id} as failed')
        sys.exit(1)


if __name__ == '__main__':
    main()
