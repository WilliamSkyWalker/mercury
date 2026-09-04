"""ViewSets for PerfPlan and PerfRun.

PerfPlan endpoints cover CRUD + nested case management + snapshot sync +
run-trigger (stub; driver lands in Task #4).
PerfRun endpoints cover read + abort + soft-delete. OpenMetrics export and
data-file upload land in later tasks.
"""
import logging
from datetime import datetime

from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from ceres.models import Testcase, Env
from ceres.models_perf import PerfPlan, PerfPlanCase, PerfRun
from ceres.serializers_perf import (
    PerfPlanSerializer, PerfPlanListSerializer, PerfPlanCaseSerializer,
    PerfRunSerializer, PerfRunListSerializer,
)

logger = logging.getLogger(__name__)

# Limits for perf data file uploads — large enough for realistic test pools,
# small enough to keep in-memory loading sane.
_MAX_DATA_FILE_BYTES = 50 * 1024 * 1024  # 50 MB
_ALLOWED_DATA_EXTENSIONS = ('.csv', '.json', '.tsv')


def _save_perf_data_file(plan_id: int, prefix: str, request):
    """Validate + upload a multipart file to S3 under qa/mercury/perf_data/.

    Returns the s3_key string on success, or a DRF Response (4xx) on validation
    failure (caller forwards as the response).
    """
    import uuid
    from ceres.engine.s3_utils import upload_testdata, PERF_DATA_PREFIX

    file_obj = request.FILES.get('file')
    if not file_obj:
        return Response({'error': 'file is required'}, status=status.HTTP_400_BAD_REQUEST)
    if file_obj.size > _MAX_DATA_FILE_BYTES:
        return Response(
            {'error': f'File too large (max {_MAX_DATA_FILE_BYTES // (1024*1024)}MB)'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    name_lower = (file_obj.name or '').lower()
    if not any(name_lower.endswith(ext) for ext in _ALLOWED_DATA_EXTENSIONS):
        return Response(
            {'error': f'Unsupported extension. Allowed: {_ALLOWED_DATA_EXTENSIONS}'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    s3_key = f'{PERF_DATA_PREFIX}{plan_id}/{prefix}_{uuid.uuid4().hex[:8]}_{file_obj.name}'
    upload_testdata(file_obj, s3_key, content_type=file_obj.content_type or 'text/plain')
    return s3_key


class PerfPlanViewSet(viewsets.ModelViewSet):
    queryset = PerfPlan.objects.select_related('env').all()
    serializer_class = PerfPlanSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'env']
    search_fields = ['name']
    ordering_fields = ['created_at', 'updated_at', 'name']

    def get_serializer_class(self):
        if self.action == 'list':
            return PerfPlanListSerializer
        return PerfPlanSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'retrieve':
            qs = qs.prefetch_related('plan_cases__testcase')
        return qs

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Case management (mirrors TestplanViewSet.cases) ─────────────────
    @action(detail=True, methods=['get', 'post', 'put', 'delete'])
    def cases(self, request, pk=None):
        plan = self.get_object()

        if request.method == 'GET':
            role = request.query_params.get('role')
            tx_name = request.query_params.get('transaction_name')
            qs = plan.plan_cases.select_related('testcase')
            if role:
                qs = qs.filter(role=role)
            if tx_name is not None:
                qs = qs.filter(transaction_name=tx_name)
            return Response(PerfPlanCaseSerializer(qs, many=True).data)

        if request.method == 'POST':
            # Body: {role, transaction_name?, case_ids: [int]}
            role = request.data.get('role')
            if role not in ('setup', 'transaction'):
                return Response({'error': "role must be 'setup' or 'transaction'"}, status=status.HTTP_400_BAD_REQUEST)
            tx_name = request.data.get('transaction_name', '') if role == 'transaction' else ''
            if role == 'transaction' and not tx_name:
                return Response({'error': "transaction_name required for role='transaction'"}, status=status.HTTP_400_BAD_REQUEST)
            case_ids = request.data.get('case_ids', [])
            if not case_ids:
                return Response({'error': 'case_ids is required'}, status=status.HTTP_400_BAD_REQUEST)

            existing_max = plan.plan_cases.filter(role=role, transaction_name=tx_name).count()
            testcases_by_id = {tc.id: tc for tc in Testcase.objects.filter(id__in=case_ids)}
            created = []
            for i, cid in enumerate(case_ids):
                tc = testcases_by_id.get(cid)
                if not tc:
                    continue
                pc, was_created = PerfPlanCase.objects.get_or_create(
                    perf_plan=plan, testcase_id=cid, role=role, transaction_name=tx_name,
                    defaults={
                        'sort_order': existing_max + i,
                        'case_snapshot': PerfPlanCase.snapshot_from_testcase(tc),
                    }
                )
                if was_created:
                    created.append(pc)
            return Response(PerfPlanCaseSerializer(created, many=True).data, status=status.HTTP_201_CREATED)

        if request.method == 'PUT':
            # Body: {ordering: [{id, sort_order}], or update data_file_s3_key/data_mode per row}
            ordering_payload = request.data.get('ordering', [])
            data_payload = request.data.get('data_bindings', [])

            if ordering_payload:
                order_map = {item['id']: item['sort_order'] for item in ordering_payload}
                rows = list(PerfPlanCase.objects.filter(id__in=order_map.keys(), perf_plan=plan))
                for pc in rows:
                    pc.sort_order = order_map[pc.id]
                PerfPlanCase.objects.bulk_update(rows, ['sort_order'])

            if data_payload:
                # [{id, data_file_s3_key?, data_mode?}]
                ids = [d['id'] for d in data_payload]
                by_id = {pc.id: pc for pc in PerfPlanCase.objects.filter(id__in=ids, perf_plan=plan)}
                for d in data_payload:
                    pc = by_id.get(d['id'])
                    if not pc:
                        continue
                    if 'data_file_s3_key' in d:
                        pc.data_file_s3_key = d['data_file_s3_key'] or ''
                    if 'data_mode' in d:
                        pc.data_mode = d['data_mode']
                PerfPlanCase.objects.bulk_update(by_id.values(), ['data_file_s3_key', 'data_mode'])

            return Response({'status': 'ok'})

        if request.method == 'DELETE':
            plan_case_ids = request.data.get('plan_case_ids', [])
            deleted, _ = PerfPlanCase.objects.filter(
                id__in=plan_case_ids, perf_plan=plan
            ).delete()
            return Response({'deleted': deleted})

    # ── Snapshot sync (mirrors TestplanViewSet.sync) ────────────────────
    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """Refresh case_snapshot on every PerfPlanCase from the current testcase row."""
        plan = self.get_object()
        synced = 0
        diffs = []
        for pc in plan.plan_cases.select_related('testcase'):
            new_snap = PerfPlanCase.snapshot_from_testcase(pc.testcase)
            if new_snap != pc.case_snapshot:
                pc.case_snapshot = new_snap
                pc.save(update_fields=['case_snapshot', 'updated_at'])
                diffs.append({'plan_case_id': pc.id, 'case_name': pc.testcase.case_name})
            synced += 1
        return Response({'synced': synced, 'diffs': diffs})

    # ── Trigger a run ───────────────────────────────────────────────────
    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        """Create a PerfRun and spawn the driver thread.

        Driver implementation lives in ceres/engine/perf_driver.py (Task #4).
        Run params can override plan defaults via request body:
          {target_rate?, duration_secs?, max_vus?, env_id?}
        """
        plan = self.get_object()

        # Override snapshot
        target_rate = int(request.data.get('target_rate', plan.target_rate))
        duration_secs = int(request.data.get('duration_secs', plan.duration_secs))
        max_vus = int(request.data.get('max_vus', plan.max_vus))

        if target_rate <= 0 or duration_secs <= 0 or max_vus <= 0:
            return Response(
                {'error': 'target_rate, duration_secs, max_vus must all be positive'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Before refusing, sweep orphaned runs whose driver subprocess died
        # (heartbeat stale > 60s, or pending too long without ever starting).
        # Otherwise a crashed/killed driver leaves the plan permanently
        # blocked from new runs.
        from datetime import timedelta
        now = timezone.now()
        stale_threshold = now - timedelta(seconds=60)
        orphans = PerfRun.objects.filter(
            perf_plan=plan,
            status__in=['pending', 'running', 'aborting'],
        )
        for o in orphans:
            heartbeat_ok = o.last_heartbeat_at and o.last_heartbeat_at > stale_threshold
            still_starting = (
                o.status == 'pending'
                and (o.created_at and o.created_at > stale_threshold)
            )
            if not heartbeat_ok and not still_starting:
                logger.warning(
                    f'Sweeping orphaned PerfRun {o.id} (status={o.status}, '
                    f'last_heartbeat={o.last_heartbeat_at}) → aborted'
                )
                o.status = 'aborted'
                o.finished_at = o.finished_at or now
                o.error_message = o.error_message or 'Driver subprocess died (orphan-swept)'
                o.save(update_fields=['status', 'finished_at', 'error_message', 'updated_at'])

        active = PerfRun.objects.filter(
            perf_plan=plan,
            status__in=['pending', 'running', 'aborting'],
        ).first()
        if active:
            return Response(
                {'error': f'Run {active.id} is already {active.status}'},
                status=status.HTTP_409_CONFLICT,
            )

        # Validate plan has cases
        if not plan.plan_cases.filter(role='transaction').exists():
            return Response(
                {'error': 'Plan has no transaction cases — nothing to load'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with db_transaction.atomic():
            run = PerfRun.objects.create(
                perf_plan=plan,
                target_rate=target_rate,
                duration_secs=duration_secs,
                max_vus=max_vus,
                status='pending',
                summary_json={},
            )

        # Spawn the driver as a subprocess so gevent monkey-patching stays
        # isolated from the main Django process. The standalone script
        # (not a Django management command) must monkey-patch BEFORE
        # Django setup — manage.py imports Django too early.
        import os
        import subprocess
        import sys
        from django.conf import settings
        script_path = os.path.join(settings.BASE_DIR, 'ceres', 'engine', 'perf_subprocess.py')
        log_path = f'/tmp/perf-run-{run.id}.log'
        try:
            subprocess.Popen(
                [sys.executable, script_path, str(run.id)],
                cwd=str(settings.BASE_DIR),
                stdout=open(log_path, 'ab'),
                stderr=subprocess.STDOUT,
                start_new_session=True,  # detach from the Django parent
                env={**os.environ, 'DJANGO_SETTINGS_MODULE': 'mercury.settings'},
            )
            logger.info(f'PerfRun {run.id} subprocess launched (log: {log_path})')
        except Exception:
            logger.exception(f'Failed to spawn perf-run subprocess for run {run.id}')
            run.status = 'failed'
            run.error_message = 'Failed to launch driver subprocess'
            run.finished_at = timezone.now()
            run.save(update_fields=['status', 'error_message', 'finished_at', 'updated_at'])

        return Response(PerfRunSerializer(run).data, status=status.HTTP_201_CREATED)

    # ── Upload account pool data file (CSV/JSON in S3) ───────────────────
    @action(detail=True, methods=['post'], url_path='upload-account-pool')
    def upload_account_pool(self, request, pk=None):
        """Upload a CSV or JSON file as the per-VU account pool.

        Stored at qa/mercury/perf_data/{plan_id}/account_{uuid}_{name}.
        Sets PerfPlan.account_data_file_s3_key to the new key. Old file is
        not deleted (keep history for debugging).
        """
        plan = self.get_object()
        s3_key = _save_perf_data_file(plan_id=plan.id, prefix='account', request=request)
        if isinstance(s3_key, Response):
            return s3_key
        plan.account_data_file_s3_key = s3_key
        plan.save(update_fields=['account_data_file_s3_key', 'updated_at'])
        return Response({'s3_key': s3_key})

    # ── Upload per-case data file ────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='cases/(?P<plan_case_id>[0-9]+)/upload-data')
    def upload_case_data(self, request, pk=None, plan_case_id=None):
        """Upload a CSV/JSON file bound to one PerfPlanCase (the row picked
        per case fire). Stored at qa/mercury/perf_data/{plan_id}/case{id}_{uuid}_{name}.
        """
        plan = self.get_object()
        try:
            pc = plan.plan_cases.get(id=int(plan_case_id))
        except PerfPlanCase.DoesNotExist:
            return Response({'error': 'plan_case not found'}, status=status.HTTP_404_NOT_FOUND)
        s3_key = _save_perf_data_file(plan_id=plan.id, prefix=f'case{pc.id}', request=request)
        if isinstance(s3_key, Response):
            return s3_key
        mode = request.data.get('mode')
        pc.data_file_s3_key = s3_key
        if mode in ('round_robin', 'random', 'sequential_once'):
            pc.data_mode = mode
        pc.save(update_fields=['data_file_s3_key', 'data_mode', 'updated_at'])
        return Response({'s3_key': s3_key, 'mode': pc.data_mode})

    # ── List recent runs for this plan ──────────────────────────────────
    @action(detail=True, methods=['get'])
    def runs(self, request, pk=None):
        """Return up to `limit` runs (default 50) for this plan, ordered newest first.

        summary_json can be ~20-50KB per run (170+ endpoints × stats),
        so we defer the column and extract just the three list-view fields
        via jsonb path operators. The detail endpoint still loads the full blob.
        """
        from django.db.models import F
        plan = self.get_object()
        limit = int(request.query_params.get('limit', 50))
        qs = (
            plan.runs
            .select_related('perf_plan')
            .annotate(
                _ann_total_reqs=F('summary_json__total_reqs'),
                _ann_error_count=F('summary_json__error_count'),
                _ann_p95=F('summary_json__latency_ms__p95'),
            )
            .defer('summary_json')
            # `F('started_at').desc(nulls_last=True)` keeps runs that
            # never reached the driver (started_at IS NULL, e.g. aborted
            # before init) at the BOTTOM of the list. Postgres default
            # DESC puts NULLs first, which is the wrong UX here.
            .order_by(F('started_at').desc(nulls_last=True), '-created_at')[:limit]
        )
        return Response(PerfRunListSerializer(qs, many=True).data)


class PerfRunViewSet(viewsets.ReadOnlyModelViewSet):
    """Read + abort + delete. Creation only via PerfPlanViewSet.run."""
    queryset = PerfRun.objects.select_related('perf_plan').all()
    serializer_class = PerfRunSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['perf_plan', 'status']
    ordering_fields = ['started_at', 'created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'list':
            from django.db.models import F
            qs = (
                qs.annotate(
                    _ann_total_reqs=F('summary_json__total_reqs'),
                    _ann_error_count=F('summary_json__error_count'),
                    _ann_p95=F('summary_json__latency_ms__p95'),
                ).defer('summary_json')
            )
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return PerfRunListSerializer
        return PerfRunSerializer

    @action(detail=True, methods=['get'], permission_classes=[])
    def metrics(self, request, pk=None):
        """OpenMetrics exporter for one PerfRun (Prometheus-scrapable).

        Permission is open (no auth) so Prometheus / Grafana Agent can scrape
        directly. The run_id is opaque — knowing a valid id is the only
        access control here. Tighten with allow-list IPs at the LB layer
        if needed.
        """
        from django.http import HttpResponse
        run = self.get_object()
        s = run.summary_json or {}
        lat = s.get('latency_ms') or {}
        plan_name = run.perf_plan.name if run.perf_plan else ''
        rid = run.id
        labels = f'run_id="{rid}",plan="{plan_name}",status="{run.status}"'
        lines: list[str] = []

        def metric(name: str, mtype: str, help_text: str, samples: list[tuple[str, float]]):
            lines.append(f'# HELP {name} {help_text}')
            lines.append(f'# TYPE {name} {mtype}')
            for label_str, value in samples:
                lines.append(f'{name}{{{label_str}}} {value}')

        metric(
            'mercury_perf_requests_total', 'counter',
            'Total fired requests, by status',
            [
                (f'{labels},result="success"', s.get('success_count', 0)),
                (f'{labels},result="error"', s.get('error_count', 0)),
            ],
        )
        metric(
            'mercury_perf_dropped_total', 'counter',
            'Ticks dropped due to all VUs busy (saturation)',
            [(labels, s.get('dropped_count', 0))],
        )
        metric(
            'mercury_perf_active_vus', 'gauge',
            'Number of VUs currently executing a transaction',
            [(labels, s.get('active_vus', 0))],
        )
        metric(
            'mercury_perf_current_rps', 'gauge',
            'Achieved request rate over the last 5 seconds',
            [(labels, s.get('current_rps', 0))],
        )
        metric(
            'mercury_perf_latency_ms', 'gauge',
            'Latency distribution (ms) over the full run window',
            [
                (f'{labels},quantile="0.5"', lat.get('p50', 0)),
                (f'{labels},quantile="0.95"', lat.get('p95', 0)),
                (f'{labels},quantile="0.99"', lat.get('p99', 0)),
                (f'{labels},quantile="avg"', lat.get('avg', 0)),
                (f'{labels},quantile="max"', lat.get('max', 0)),
            ],
        )
        per_tx = s.get('per_transaction') or {}
        if per_tx:
            tx_samples_count = []
            tx_samples_err = []
            tx_samples_p95 = []
            for tx_name, tx in per_tx.items():
                tx_label = f'{labels},transaction="{tx_name}"'
                tx_samples_count.append((tx_label, tx.get('count', 0)))
                tx_samples_err.append((tx_label, tx.get('error_rate', 0)))
                tx_samples_p95.append((tx_label, tx.get('p95_ms', 0)))
            metric('mercury_perf_transaction_requests_total', 'counter',
                   'Per-transaction request count', tx_samples_count)
            metric('mercury_perf_transaction_error_rate', 'gauge',
                   'Per-transaction error rate (0..1)', tx_samples_err)
            metric('mercury_perf_transaction_p95_ms', 'gauge',
                   'Per-transaction p95 latency (ms)', tx_samples_p95)
        lines.append('# EOF')
        body = '\n'.join(lines) + '\n'
        return HttpResponse(body, content_type='application/openmetrics-text; version=1.0.0; charset=utf-8')

    @action(detail=True, methods=['post'])
    def abort(self, request, pk=None):
        """Signal the driver to stop. Driver polls status every ~1s and
        terminates gracefully (finishes in-flight requests, marks status=aborted).
        """
        run = self.get_object()
        if run.status not in ('pending', 'running'):
            return Response(
                {'error': f'Cannot abort a run in status {run.status!r}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        run.status = 'aborting'
        run.save(update_fields=['status', 'updated_at'])
        return Response({'status': 'aborting'})

    @action(detail=True, methods=['delete'])
    def soft_delete(self, request, pk=None):
        run = self.get_object()
        run.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
