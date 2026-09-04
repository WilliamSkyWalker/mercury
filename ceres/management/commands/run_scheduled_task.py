"""Crontab entry point for a single ScheduledTask.

Usage::

    python3 manage.py run_scheduled_task <task_id>

Reuses the execution path the old APScheduler callback used: skip if a
previous scheduled run for the same plan is still in flight, otherwise
create an ``ExecutionRecord(trigger_type='scheduled')`` and hand it to
``TestExecutor.execute_plan_async``.

Runs the executor in a daemon thread and then waits for that thread to
finish before exiting — the cron process needs to stay alive until the
plan completes so we don't lose work on container restarts mid-run.
"""
import logging
import threading
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Execute a ScheduledTask by id (invoked by crontab).'

    def add_arguments(self, parser):
        parser.add_argument('task_id', type=int, help='ScheduledTask.id')
        parser.add_argument(
            '--detach',
            action='store_true',
            help='Return immediately after spawning the executor thread.',
        )

    def handle(self, *args, **options):
        from ceres.models import ScheduledTask, ExecutionRecord
        from ceres.engine.executor import TestExecutor

        task_id = options['task_id']
        try:
            task = (
                ScheduledTask.objects
                .select_related('testplan', 'env')
                .get(id=task_id, is_active=True)
            )
        except ScheduledTask.DoesNotExist:
            raise CommandError(f'ScheduledTask {task_id} not found or inactive')

        testplan = task.testplan
        env = task.env or testplan.env

        running_exists = ExecutionRecord.objects.filter(
            testplan=testplan,
            trigger_type='scheduled',
            status='running',
        ).exists()
        if running_exists:
            self.stdout.write(
                f'[{datetime.now():%Y-%m-%d %H:%M:%S}] task {task_id} '
                f'({task.name}): previous scheduled run still in flight, skipping'
            )
            return

        plan_cases = testplan.plan_cases.select_related('testcase').order_by('sort_order')
        testcases = [pc.to_executable() for pc in plan_cases]
        if not testcases:
            self.stdout.write(
                f'[{datetime.now():%Y-%m-%d %H:%M:%S}] task {task_id} '
                f'({task.name}): plan has no cases, skipping'
            )
            return

        task_run_id = f"task-{testplan.name}-scheduled-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        execution = ExecutionRecord.objects.create(
            project=testplan.project,
            task_id=task_run_id,
            testplan=testplan,
            env=env,
            env_snapshot=env.variables if env else {},
            trigger_type='scheduled',
            status='running',
            total_cases=len(testcases),
        )

        self.stdout.write(
            f'[{datetime.now():%Y-%m-%d %H:%M:%S}] task {task_id} ({task.name}) '
            f'-> execution {execution.id} ({task_run_id})'
        )

        executor = TestExecutor(env=env)
        thread = threading.Thread(
            target=executor.execute_plan_async,
            args=(execution.id, testcases, testplan),
            daemon=False,
        )
        thread.start()

        if options['detach']:
            return

        thread.join()
        rec = ExecutionRecord.all_objects.get(id=execution.id)
        self.stdout.write(
            f'[{datetime.now():%Y-%m-%d %H:%M:%S}] task {task_id} done: '
            f'status={rec.status} pass={rec.passed_cases} fail={rec.failed_cases} '
            f'err={rec.error_cases} skip={rec.skipped_cases}/{rec.total_cases}'
        )
