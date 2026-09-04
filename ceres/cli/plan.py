"""`ceres plan` subcommand — testplan CRUD + add/remove cases + sync + run."""
import threading
import time
from datetime import datetime

from django.core.management.base import CommandError

from ceres.cli import common_parser
from ceres.cli.output import emit
from ceres.cli.resolvers import (
    parse_json_arg,
    resolve_env,
    resolve_folder,
    resolve_project,
    resolve_testcase,
    resolve_testplan,
)


LIST_COLUMNS = [
    ('ID', 'id', 6),
    ('NAME', 'name', 40),
    ('PROJECT', 'project_id', 8),
    ('ENV', 'env_id', 6),
    ('SERIAL', 'is_serial', 6),
    ('RETRY', 'retry_count', 5),
    ('UPDATED', 'updated_at', 16),
]

DETAIL_FIELDS = [
    'id', 'project_id', 'name', 'folder_id', 'env_id',
    'is_serial', 'retry_count', 'feishu_webhook', 'notify_on_failure',
    'phone_on_failure', 'phone_muted',
    'is_deleted', 'created_at', 'updated_at',
]


def _to_detail(tp):
    return {f: getattr(tp, f, None) for f in DETAIL_FIELDS}


# ─── CRUD ──────────────────────────────────────────────────────────────────
def do_list(args):
    from ceres.models import Testplan
    qs = Testplan.objects.all()
    if args.project:
        qs = qs.filter(project=resolve_project(args.project))
    if args.search:
        qs = qs.filter(name__icontains=args.search)
    qs = qs.order_by('id')[: args.limit]
    rows = [{c[1]: getattr(tp, c[1], None) for c in LIST_COLUMNS} for tp in qs]
    emit(rows, args.output, LIST_COLUMNS)


def do_get(args):
    tp = resolve_testplan(args.ident)
    detail = _to_detail(tp)
    # Include case summary
    detail['case_count'] = tp.plan_cases.count()
    columns = [(f.upper(), f, 120) for f in list(detail.keys())]
    emit(detail, args.output, columns)


def do_create(args):
    from ceres.models import Testplan
    project = resolve_project(args.project)
    if project is None:
        raise CommandError('--project is required')
    env = resolve_env(args.env, project) if args.env else None
    folder = resolve_folder(args.folder, project) if args.folder else None
    payload = parse_json_arg(args) or {}

    tp = Testplan.objects.create(
        project=project,
        name=args.name or payload.get('name'),
        folder=folder,
        env=env,
        is_serial=args.serial if args.serial is not None else payload.get('is_serial', True),
        retry_count=args.retry if args.retry is not None else payload.get('retry_count', 0),
        feishu_webhook=args.webhook if args.webhook is not None else payload.get('feishu_webhook', ''),
        notify_on_failure=payload.get('notify_on_failure', True),
        phone_on_failure=args.phone if args.phone is not None else payload.get('phone_on_failure', False),
        phone_muted=args.phone_muted if args.phone_muted is not None else payload.get('phone_muted', False),
    )
    if not tp.name:
        tp.delete()
        raise CommandError('--name is required')
    emit(_to_detail(tp), args.output, [(f.upper(), f, 120) for f in DETAIL_FIELDS])


def do_update(args):
    tp = resolve_testplan(args.ident)
    changed = []
    if args.name is not None:
        tp.name = args.name; changed.append('name')
    if args.env is not None:
        tp.env = resolve_env(args.env, tp.project); changed.append('env')
    if args.folder is not None:
        tp.folder = resolve_folder(args.folder, tp.project); changed.append('folder')
    if args.serial is not None:
        tp.is_serial = args.serial; changed.append('is_serial')
    if args.retry is not None:
        tp.retry_count = args.retry; changed.append('retry_count')
    if args.webhook is not None:
        tp.feishu_webhook = args.webhook; changed.append('feishu_webhook')
    if args.phone is not None:
        tp.phone_on_failure = args.phone; changed.append('phone_on_failure')
    if args.phone_muted is not None:
        tp.phone_muted = args.phone_muted; changed.append('phone_muted')

    payload = parse_json_arg(args) or {}
    for k in ('name', 'is_serial', 'retry_count', 'feishu_webhook', 'notify_on_failure',
              'phone_on_failure', 'phone_muted'):
        if k in payload:
            setattr(tp, k, payload[k]); changed.append(k)
    if not changed:
        raise CommandError('Nothing to update')
    tp.save()
    emit(_to_detail(tp), args.output, [(f.upper(), f, 120) for f in DETAIL_FIELDS])


def do_delete(args):
    tp = resolve_testplan(args.ident)
    tp.soft_delete() if hasattr(tp, 'soft_delete') else tp.delete()
    print(f'Testplan {tp.id} ({tp.name}) deleted (soft).')


# ─── Case management ───────────────────────────────────────────────────────
def do_list_cases(args):
    tp = resolve_testplan(args.ident)
    qs = tp.plan_cases.select_related('testcase').order_by('sort_order')
    rows = [
        {
            'plan_case_id': pc.id,
            'testcase_id': pc.testcase_id,
            'case_name': pc.testcase.case_name,
            'method': pc.testcase.method,
            'url': pc.testcase.url,
            'sort_order': pc.sort_order,
            'has_snapshot': bool(pc.case_snapshot),
        } for pc in qs
    ]
    emit(rows, args.output, [
        ('PLAN_CASE', 'plan_case_id', 10),
        ('TC_ID', 'testcase_id', 8),
        ('NAME', 'case_name', 40),
        ('METHOD', 'method', 7),
        ('URL', 'url', 80),
        ('ORDER', 'sort_order', 6),
        ('SNAP', 'has_snapshot', 5),
    ])


def do_add_cases(args):
    from ceres.models import TestplanCase
    tp = resolve_testplan(args.ident)
    max_order = tp.plan_cases.count()
    created = []
    for i, ident in enumerate(args.case_ids):
        tc = resolve_testcase(ident, tp.project)
        obj, was_created = TestplanCase.objects.get_or_create(
            testplan=tp, testcase=tc,
            defaults={
                'sort_order': max_order + i,
                'case_snapshot': TestplanCase.snapshot_from_testcase(tc),
            },
        )
        created.append({
            'plan_case_id': obj.id,
            'testcase_id': tc.id,
            'case_name': tc.case_name,
            'status': 'created' if was_created else 'exists',
        })
    emit(created, args.output, [
        ('PLAN_CASE', 'plan_case_id', 10),
        ('TC_ID', 'testcase_id', 8),
        ('NAME', 'case_name', 40),
        ('STATUS', 'status', 8),
    ])


def do_remove_cases(args):
    from ceres.models import TestplanCase
    tp = resolve_testplan(args.ident)
    deleted = 0
    if args.all:
        deleted = tp.plan_cases.count()
        tp.plan_cases.all().delete()
    else:
        qs = tp.plan_cases.filter(id__in=args.plan_case_ids)
        deleted = qs.count()
        qs.delete()
    print(f'Removed {deleted} case(s) from plan {tp.id}')


def do_sync(args):
    tp = resolve_testplan(args.ident)
    qs = tp.plan_cases.select_related('testcase')
    if not args.all:
        if not args.plan_case_ids:
            raise CommandError('--all or --plan-case-ids required')
        qs = qs.filter(id__in=args.plan_case_ids)
    updated = 0
    for pc in qs:
        pc.take_snapshot()
        updated += 1
    print(f'Synced snapshots for {updated} case(s).')


# ─── Run ───────────────────────────────────────────────────────────────────
def do_run(args):
    from ceres.engine.executor import TestExecutor
    from ceres.models import ExecutionRecord

    tp = resolve_testplan(args.ident)
    env = resolve_env(args.env, tp.project) if args.env else tp.env
    plan_cases = tp.plan_cases.select_related('testcase').order_by('sort_order')
    testcases = [pc.to_executable() for pc in plan_cases]
    if not testcases:
        raise CommandError('Testplan has no cases')

    task_id = f"task-{tp.name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    execution = ExecutionRecord.objects.create(
        project=tp.project,
        task_id=task_id,
        testplan=tp,
        env=env,
        env_snapshot=env.variables if env else {},
        trigger_type='manual',
        status='running',
        total_cases=len(testcases),
    )

    executor = TestExecutor(env=env)
    thread = threading.Thread(target=executor.execute_plan_async, args=(execution.id, testcases, tp))
    thread.start()

    if args.async_mode:
        emit(
            {'task_id': task_id, 'execution_id': execution.id, 'status': 'running'},
            args.output,
            [('TASK_ID', 'task_id', 60), ('EXEC_ID', 'execution_id', 8), ('STATUS', 'status', 10)],
        )
        return

    # Poll until done
    print(f'Running plan {tp.id} (execution {execution.id}, task {task_id})…')
    deadline = time.time() + args.wait_timeout
    last_summary = None
    while time.time() < deadline:
        if not thread.is_alive():
            break
        time.sleep(3)
        rec = ExecutionRecord.all_objects.get(id=execution.id)
        cur = f"passed={rec.passed_cases} failed={rec.failed_cases} error={rec.error_cases} skipped={rec.skipped_cases}/{rec.total_cases}"
        if cur != last_summary:
            print(f'  [{rec.status}] {cur}')
            last_summary = cur

    rec = ExecutionRecord.all_objects.get(id=execution.id)
    emit(
        {
            'execution_id': rec.id,
            'task_id': rec.task_id,
            'status': rec.status,
            'total': rec.total_cases,
            'passed': rec.passed_cases,
            'failed': rec.failed_cases,
            'error': rec.error_cases,
            'skipped': rec.skipped_cases,
            'pass_rate': rec.pass_rate,
            'duration_ms': rec.duration_ms,
        },
        args.output,
        [
            ('EXEC_ID', 'execution_id', 8),
            ('TASK_ID', 'task_id', 50),
            ('STATUS', 'status', 10),
            ('TOTAL', 'total', 5),
            ('PASS', 'passed', 5),
            ('FAIL', 'failed', 5),
            ('ERR', 'error', 5),
            ('SKIP', 'skipped', 5),
            ('RATE', 'pass_rate', 6),
            ('DUR_MS', 'duration_ms', 8),
        ],
    )


# ─── Subparser registration ────────────────────────────────────────────────
def _add_json_flags(sp):
    sp.add_argument('--json-file', help='Read full payload from JSON file')
    sp.add_argument('--json', help='Inline JSON payload')
    sp.add_argument('--stdin', action='store_true', help='Read JSON payload from stdin')


def _bool_arg(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('true', 'yes', 'y', '1'):
        return True
    if v.lower() in ('false', 'no', 'n', '0'):
        return False
    raise ValueError(v)


def register(parser):
    sub = parser.add_subparsers(dest='action', metavar='<action>', required=True)
    common = common_parser()

    p_list = sub.add_parser('list', help='List testplans', parents=[common])
    p_list.add_argument('--project', '-p')
    p_list.add_argument('--search', '-s')
    p_list.add_argument('--limit', '-n', type=int, default=200)
    p_list.set_defaults(handler=do_list)

    p_get = sub.add_parser('get', help='Show a testplan', parents=[common])
    p_get.add_argument('ident')
    p_get.set_defaults(handler=do_get)

    p_create = sub.add_parser('create', help='Create a testplan', parents=[common])
    p_create.add_argument('--project', '-p', required=True)
    p_create.add_argument('--name', required=False)
    p_create.add_argument('--env', '-e')
    p_create.add_argument('--folder', '-f')
    p_create.add_argument('--serial', type=_bool_arg, default=None,
                          help='true/false (default true)')
    p_create.add_argument('--retry', type=int, default=None)
    p_create.add_argument('--webhook')
    p_create.add_argument('--phone', type=_bool_arg, default=None,
                          help='Enable Flashcat phone alert on failure (true/false)')
    p_create.add_argument('--phone-muted', dest='phone_muted', type=_bool_arg, default=None,
                          help='Mute Flashcat phone alert (true/false)')
    _add_json_flags(p_create)
    p_create.set_defaults(handler=do_create)

    p_update = sub.add_parser('update', help='Update a testplan', parents=[common])
    p_update.add_argument('ident')
    p_update.add_argument('--name')
    p_update.add_argument('--env')
    p_update.add_argument('--folder')
    p_update.add_argument('--serial', type=_bool_arg, default=None)
    p_update.add_argument('--retry', type=int, default=None)
    p_update.add_argument('--webhook')
    p_update.add_argument('--phone', type=_bool_arg, default=None,
                          help='Enable Flashcat phone alert on failure (true/false)')
    p_update.add_argument('--phone-muted', dest='phone_muted', type=_bool_arg, default=None,
                          help='Mute Flashcat phone alert (true/false)')
    _add_json_flags(p_update)
    p_update.set_defaults(handler=do_update)

    p_delete = sub.add_parser('delete', help='Soft-delete a testplan', parents=[common])
    p_delete.add_argument('ident')
    p_delete.set_defaults(handler=do_delete)

    p_cases = sub.add_parser('cases', help='List cases in a testplan', parents=[common])
    p_cases.add_argument('ident')
    p_cases.set_defaults(handler=do_list_cases)

    p_add = sub.add_parser('add-cases', help='Add testcases to a plan', parents=[common])
    p_add.add_argument('ident')
    p_add.add_argument('case_ids', nargs='+', help='Testcase ids or names')
    p_add.set_defaults(handler=do_add_cases)

    p_rm = sub.add_parser('remove-cases', help='Remove testcases from a plan', parents=[common])
    p_rm.add_argument('ident')
    p_rm.add_argument('plan_case_ids', type=int, nargs='*', help='PlanCase ids')
    p_rm.add_argument('--all', action='store_true', help='Remove every case in this plan')
    p_rm.set_defaults(handler=do_remove_cases)

    p_sync = sub.add_parser('sync', help='Refresh plan-case snapshots from live testcases', parents=[common])
    p_sync.add_argument('ident')
    p_sync.add_argument('--all', action='store_true')
    p_sync.add_argument('--plan-case-ids', type=int, nargs='*', default=[])
    p_sync.set_defaults(handler=do_sync)

    p_run = sub.add_parser('run', help='Run a testplan', parents=[common])
    p_run.add_argument('ident')
    p_run.add_argument('--env', '-e', help='Override plan env')
    p_run.add_argument('--async', dest='async_mode', action='store_true', help='Do not wait; return immediately')
    p_run.add_argument('--wait-timeout', type=int, default=1800, help='Max seconds to wait in foreground (default 1800)')
    p_run.set_defaults(handler=do_run)
