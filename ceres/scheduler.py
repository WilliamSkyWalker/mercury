"""Crontab-backed scheduler for ScheduledTask rows.

Linux cron is the timing engine. This module's only job is to render the
active ScheduledTask rows into a marked block inside the current user's
crontab. The block is rewritten in place on each sync so existing manual
crontab entries (monitor curls in start_server.sh, anything the user added by
hand) are preserved verbatim.

Public functions (``start_scheduler`` / ``add_job`` / ``remove_job``) keep the
APScheduler-era names so existing call sites do not need to change; each one
now triggers a full re-sync of the managed block.

Only ``trigger_type='cron'`` is supported. Interval triggers were removed when
this module was switched to crontab.
"""
import logging
import os
import subprocess
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

BEGIN_MARKER = '# >>> MERCURY_CERES_SCHEDULES >>>'
END_MARKER = '# <<< MERCURY_CERES_SCHEDULES <<<'

# Repo root (parent of ``ceres/``). Resolved once at import time so the
# crontab block carries an absolute path even when cron's $PWD is /.
REPO_DIR = str(Path(__file__).resolve().parent.parent)
LOG_PATH = os.environ.get('CERES_SCHEDULE_LOG', '/opt/apps/mercury/ceres_schedule_log.txt')

_sync_lock = threading.Lock()


def _validate_cron_expression(expr: str) -> str:
    """Return ``expr`` stripped, raising ValueError if it isn't a 5-field cron."""
    expr = (expr or '').strip()
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError(f'invalid cron expression: {expr!r}')
    return expr


def _build_cron_line(task) -> str:
    """Render one ScheduledTask as a single crontab line."""
    expr = _validate_cron_expression(task.cron_expression)
    cmd = (
        f'cd {REPO_DIR} && python3 manage.py run_scheduled_task {task.id} '
        f'>> {LOG_PATH} 2>&1'
    )
    return f'{expr} {cmd}'


def _render_block() -> str:
    """Render the managed crontab block for all currently active tasks."""
    from ceres.models import ScheduledTask

    lines = [BEGIN_MARKER]
    qs = (
        ScheduledTask.objects
        .filter(is_active=True)
        .select_related('testplan')
        .order_by('id')
    )
    for task in qs:
        try:
            cron_line = _build_cron_line(task)
        except ValueError as e:
            logger.warning(f'sync_crontab: skipping task {task.id} ({task.name}): {e}')
            continue
        lines.append(f'# [{task.id}] {task.name}')
        lines.append(cron_line)
    lines.append(END_MARKER)
    return '\n'.join(lines)


def _splice_block(current: str, block: str) -> str:
    """Replace the managed block in ``current`` (or append) with ``block``.

    Lines outside the marker pair are preserved byte-for-byte.
    """
    if BEGIN_MARKER in current and END_MARKER in current:
        before, _, rest = current.partition(BEGIN_MARKER)
        _, _, after = rest.partition(END_MARKER)
        before = before.rstrip('\n')
        after = after.lstrip('\n')
        joined = ''
        if before:
            joined += before + '\n'
        joined += block + '\n'
        if after:
            joined += after.rstrip('\n') + '\n'
        return joined
    prefix = current.rstrip('\n')
    return (prefix + '\n' if prefix else '') + block + '\n'


def _read_crontab() -> str:
    """Return the current user's crontab, or '' if empty / unset."""
    try:
        proc = subprocess.run(
            ['crontab', '-l'], capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        raise
    stderr = (proc.stderr or '').lower()
    # Treat "no crontab for ..." as empty, not as a failure.
    if proc.returncode != 0 and 'no crontab' not in stderr:
        raise RuntimeError(f'crontab -l failed (rc={proc.returncode}): {proc.stderr.strip()}')
    return proc.stdout or ''


def _write_crontab(content: str) -> None:
    proc = subprocess.run(
        ['crontab', '-'], input=content, text=True, capture_output=True, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f'crontab - failed (rc={proc.returncode}): {proc.stderr.strip()}')


def sync_crontab() -> int:
    """Rewrite the managed crontab block to match the active ScheduledTask set.

    Returns the number of schedule lines written. ``-1`` is returned on
    environments where ``crontab`` is unavailable (e.g. local dev on macOS in
    a sandbox); callers should treat that as a soft warning, not an error.
    """
    with _sync_lock:
        try:
            current = _read_crontab()
        except FileNotFoundError:
            logger.info('sync_crontab: crontab binary not available; skipping')
            return -1
        except RuntimeError as e:
            logger.error(f'sync_crontab: read failed: {e}')
            return -1

        block = _render_block()
        new_content = _splice_block(current, block)
        schedule_count = sum(
            1
            for line in block.splitlines()
            if line and not line.startswith('#')
        )

        if new_content == current:
            logger.info(f'sync_crontab: crontab already in sync ({schedule_count} schedule(s))')
            return schedule_count

        try:
            _write_crontab(new_content)
        except FileNotFoundError:
            logger.info('sync_crontab: crontab binary not available; skipping')
            return -1
        except RuntimeError as e:
            logger.error(f'sync_crontab: write failed: {e}')
            return -1

        logger.info(f'sync_crontab: wrote {schedule_count} active schedule(s)')
        return schedule_count


# ─── Compatibility shims for the APScheduler-era call sites ──────────────────
# Behavior is now "re-sync the managed crontab block"; the per-task arguments
# are accepted but only used for logging since cron itself is the source of
# truth.


def start_scheduler() -> int:
    """Boot-time sync. Called from apps.ready()/start_server.sh."""
    logger.info('start_scheduler: syncing managed crontab block')
    return sync_crontab()


def add_job(task) -> int:
    """Register or update the crontab entry for ``task``."""
    logger.info(f'add_job: re-syncing crontab for task {task.id} ({task.name})')
    return sync_crontab()


def remove_job(task_id) -> int:
    """Remove the crontab entry for ``task_id``."""
    logger.info(f'remove_job: re-syncing crontab after removing task {task_id}')
    return sync_crontab()


def get_scheduler():
    """Deprecated. Returns ``None`` — kept only so legacy imports don't crash."""
    return None
