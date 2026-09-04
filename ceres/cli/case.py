"""`ceres case` subcommand — testcase CRUD + run."""
import json

from django.core.management.base import CommandError

from ceres.cli import common_parser
from ceres.cli.output import emit
from ceres.cli.resolvers import (
    parse_json_arg,
    resolve_env,
    resolve_folder,
    resolve_project,
    resolve_testcase,
)


# ─── Fields emitted by list/get ────────────────────────────────────────────
LIST_COLUMNS = [
    ('ID', 'id', 8),
    ('NAME', 'case_name', 40),
    ('METHOD', 'method', 7),
    ('URL', 'url', 80),
    ('FOLDER', 'folder_id', 8),
    ('UPDATED', 'updated_at', 16),
]

DETAIL_FIELDS = [
    'id', 'project_id', 'folder_id', 'case_name', 'method', 'url',
    'headers', 'params', 'body_type', 'body', 'assertions',
    'pre_request_script', 'post_request_script', 'script_type',
    'timeout', 'files', 'ws_steps', 'sort_order', 'tags', 'comment',
    'is_deleted', 'created_at', 'updated_at',
]


def _to_row(tc, fields=LIST_COLUMNS):
    return {col[1]: getattr(tc, col[1], None) for col in fields}


def _to_detail(tc):
    return {f: getattr(tc, f, None) for f in DETAIL_FIELDS}


# ─── Handlers ───────────────────────────────────────────────────────────────
def do_list(args):
    from ceres.models import Testcase
    qs = Testcase.objects.all()
    if args.project:
        qs = qs.filter(project=resolve_project(args.project))
    if args.folder:
        qs = qs.filter(folder=resolve_folder(args.folder))
    if args.search:
        qs = qs.filter(case_name__icontains=args.search)
    qs = qs.order_by('id')[: args.limit]
    rows = [_to_row(tc) for tc in qs]
    emit(rows, args.output, LIST_COLUMNS)


def do_get(args):
    tc = resolve_testcase(args.ident)
    emit(_to_detail(tc), args.output, [(f.upper(), f, 120) for f in DETAIL_FIELDS])


def do_create(args):
    from ceres.models import Testcase
    project = resolve_project(args.project)
    if project is None:
        raise CommandError('--project is required')
    folder = resolve_folder(args.folder, project) if args.folder else None

    payload = parse_json_arg(args) or {}
    data = {
        'project': project,
        'folder': folder,
        'case_name': args.name or payload.get('case_name'),
        'method': (args.method or payload.get('method') or 'GET').upper(),
        'url': args.url or payload.get('url') or '',
        'headers': payload.get('headers', []),
        'params': payload.get('params', []),
        'body_type': payload.get('body_type', 'none'),
        'body': payload.get('body', {}),
        'assertions': payload.get('assertions', []),
        'pre_request_script': payload.get('pre_request_script', ''),
        'post_request_script': payload.get('post_request_script', ''),
        'script_type': payload.get('script_type', 'python'),
        'timeout': payload.get('timeout', 30),
        'files': payload.get('files', []),
        'sort_order': payload.get('sort_order', 0),
        'tags': payload.get('tags', []),
        'comment': payload.get('comment', ''),
    }
    if not data['case_name']:
        raise CommandError('--name (or case_name in json) is required')
    if not data['url']:
        raise CommandError('--url (or url in json) is required')

    tc = Testcase.objects.create(**data)
    emit(_to_detail(tc), args.output, [(f.upper(), f, 120) for f in DETAIL_FIELDS])


def do_update(args):
    tc = resolve_testcase(args.ident)
    payload = parse_json_arg(args) or {}
    simple_flags = {
        'case_name': args.name,
        'method': args.method.upper() if args.method else None,
        'url': args.url,
    }
    changed = []
    for f, v in simple_flags.items():
        if v is not None:
            setattr(tc, f, v)
            changed.append(f)
    updatable = {
        'headers', 'params', 'body_type', 'body', 'assertions',
        'pre_request_script', 'post_request_script', 'script_type',
        'timeout', 'files', 'sort_order', 'tags', 'comment',
        'folder_id',
    }
    for k, v in payload.items():
        if k in updatable:
            setattr(tc, k, v)
            changed.append(k)
    if args.folder is not None:
        tc.folder = resolve_folder(args.folder)
        changed.append('folder')
    if not changed:
        raise CommandError('Nothing to update; pass --name/--url/--method or --json-file/--json/--stdin')
    tc.save()
    emit(_to_detail(tc), args.output, [(f.upper(), f, 120) for f in DETAIL_FIELDS])


def do_delete(args):
    tc = resolve_testcase(args.ident)
    tc.soft_delete() if hasattr(tc, 'soft_delete') else tc.delete()
    print(f'Testcase {tc.id} ({tc.case_name}) deleted (soft).')


def do_run(args):
    from ceres.engine.executor import TestExecutor

    tc = resolve_testcase(args.ident)
    env = resolve_env(args.env, tc.project) if args.env else None
    executor = TestExecutor(env=env)
    result = executor.run_single_case(tc)

    # Persist extracted variables back to env (same as the API view does)
    extracted = result.get('extracted_variables', {})
    if extracted and env:
        env.variables.update(extracted)
        env.save(update_fields=['variables'])

    if args.output == 'json':
        emit(result, 'json', [])
        return
    # Summary table
    summary = {
        'case_id': tc.id,
        'case_name': tc.case_name,
        'status': result.get('status'),
        'http': result.get('response', {}).get('status'),
        'duration_ms': result.get('duration_ms'),
        'passed_assertions': sum(1 for a in result.get('assertion_results', []) if a.get('passed')),
        'failed_assertions': sum(1 for a in result.get('assertion_results', []) if not a.get('passed')),
        'error': result.get('error_message') or '',
    }
    emit(summary, 'table', [
        ('CASE_ID', 'case_id', 10),
        ('CASE_NAME', 'case_name', 40),
        ('STATUS', 'status', 8),
        ('HTTP', 'http', 5),
        ('DUR_MS', 'duration_ms', 8),
        ('PASSED', 'passed_assertions', 6),
        ('FAILED', 'failed_assertions', 6),
        ('ERROR', 'error', 60),
    ])
    failed = [a for a in result.get('assertion_results', []) if not a.get('passed')]
    if failed:
        print('\nFailed assertions:')
        for a in failed:
            print(f"  - {a.get('field')} {a.get('operator')} {a.get('expected')!r}: {a.get('message')}")


# ─── Subparser registration ────────────────────────────────────────────────
def _add_json_flags(sp):
    sp.add_argument('--json-file', help='Read full payload from JSON file')
    sp.add_argument('--json', help='Inline JSON payload')
    sp.add_argument('--stdin', action='store_true', help='Read JSON payload from stdin')


def register(parser):
    sub = parser.add_subparsers(dest='action', metavar='<action>', required=True)
    common = common_parser()

    p_list = sub.add_parser('list', help='List testcases', parents=[common])
    p_list.add_argument('--project', '-p', help='Project id or name')
    p_list.add_argument('--folder', '-f', help='Folder id or name')
    p_list.add_argument('--search', '-s', help='Case name substring (case-insensitive)')
    p_list.add_argument('--limit', '-n', type=int, default=200)
    p_list.set_defaults(handler=do_list)

    p_get = sub.add_parser('get', help='Show a testcase', parents=[common])
    p_get.add_argument('ident', help='Testcase id or case_name')
    p_get.set_defaults(handler=do_get)

    p_create = sub.add_parser('create', help='Create a testcase', parents=[common])
    p_create.add_argument('--project', '-p', required=True)
    p_create.add_argument('--folder', '-f')
    p_create.add_argument('--name')
    p_create.add_argument('--url')
    p_create.add_argument('--method', default='GET')
    _add_json_flags(p_create)
    p_create.set_defaults(handler=do_create)

    p_update = sub.add_parser('update', help='Update a testcase', parents=[common])
    p_update.add_argument('ident', help='Testcase id or case_name')
    p_update.add_argument('--name')
    p_update.add_argument('--url')
    p_update.add_argument('--method')
    p_update.add_argument('--folder')
    _add_json_flags(p_update)
    p_update.set_defaults(handler=do_update)

    p_delete = sub.add_parser('delete', help='Soft-delete a testcase', parents=[common])
    p_delete.add_argument('ident', help='Testcase id or case_name')
    p_delete.set_defaults(handler=do_delete)

    p_run = sub.add_parser('run', help='Run a testcase', parents=[common])
    p_run.add_argument('ident', help='Testcase id or case_name')
    p_run.add_argument('--env', '-e', help='Env id or name')
    p_run.set_defaults(handler=do_run)
