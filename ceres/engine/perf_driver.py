"""In-process gevent load testing driver.

Reused by `ceres/management/commands/run_perf.py` (which monkey-patches
gevent FIRST, so any subsequent `requests` HTTP call yields its greenlet
while the socket is waiting). This file therefore looks synchronous —
no explicit await/spawn-and-wait scaffolding — but every `time.sleep`
and `requests.*` call cooperatively yields.

Architecture (Locust-inspired):
  - Pre-allocate `max_vus` VUs in parallel. Each VU is a Python object
    with a private VariableContext seeded with env vars + account row +
    post-setup runtime vars.
  - One dispatcher greenlet wakes every `1/target_rate` seconds and tries
    to acquire an idle VU. If found, spawns a transaction greenlet on
    that VU. If all VUs are busy, the tick is dropped — schedule still
    advances by wall clock.
  - One flusher greenlet writes summary_json + heartbeat to DB every ~2s.
  - One abort poller greenlet refreshes status from DB every ~1s.
  - Per-case metrics are recorded as each case completes so the UI sees
    live RPS even mid-chain.

DB state machine:
  pending → running → completed | failed | setup_failed
                  ↘ aborting → aborted
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import random
import tempfile
import time
from collections import deque
from typing import Any

import gevent
from gevent.event import Event
from gevent.lock import RLock
from gevent.pool import Pool
from gevent.queue import Empty, Queue

from django.utils import timezone

from ceres.engine.executor import TestExecutor
from ceres.models_perf import PerfPlan, PerfPlanCase, PerfRun

logger = logging.getLogger(__name__)


# ── Data sources (CSV / JSON files loaded from S3) ──────────────────────

class DataSource:
    """In-memory rows + thread-safe (greenlet-safe) row picker."""

    def __init__(self, rows: list[dict], mode: str = 'round_robin'):
        self.rows = rows
        self.mode = mode
        self._idx = 0
        self._lock = RLock()

    def pick(self) -> dict | None:
        if not self.rows:
            return None
        if self.mode == 'random':
            return random.choice(self.rows)
        with self._lock:
            if self.mode == 'sequential_once':
                if self._idx >= len(self.rows):
                    return None
                row = self.rows[self._idx]
                self._idx += 1
                return row
            row = self.rows[self._idx % len(self.rows)]
            self._idx += 1
            return row


def _load_data_file(s3_key: str) -> list[dict]:
    """Download an S3 object and parse as JSON array or CSV with header."""
    from ceres.engine.s3_utils import download_testdata
    if not s3_key:
        return []
    tf = tempfile.NamedTemporaryFile(delete=False, suffix='_' + os.path.basename(s3_key))
    tf.close()
    try:
        download_testdata(s3_key, tf.name)
        with open(tf.name, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return [dict(r) if isinstance(r, dict) else {} for r in data]
        except json.JSONDecodeError:
            pass
        reader = csv.DictReader(io.StringIO(content))
        return [dict(r) for r in reader]
    finally:
        try:
            os.unlink(tf.name)
        except OSError:
            pass


# ── Metrics ─────────────────────────────────────────────────────────────

class MetricsAccumulator:
    """Reservoir-sampled latency stats + per-transaction + per-case breakdown.

    All mutating methods are guarded by an RLock since multiple greenlets
    record concurrently. Lock contention is minimal because the critical
    section only does dict updates / reservoir slot writes.
    """

    def __init__(self, reservoir_size: int = 10000):
        self._lock = RLock()
        self.reservoir_size = reservoir_size
        self.total_reqs = 0
        self.success_count = 0
        self.error_count = 0
        self.dropped_count = 0
        self.reservoir: list[float] = []
        self.per_transaction: dict[str, dict] = {}
        self.per_case: dict[str, dict] = {}
        self.fire_window: deque = deque()  # 5s rolling timestamps for current_rps

    def record(self, transaction_name: str, duration_ms: float, status: str,
               case_name: str = '') -> None:
        with self._lock:
            self.total_reqs += 1
            if status == 'passed':
                self.success_count += 1
            else:
                self.error_count += 1
            self._reservoir_add(self.reservoir, duration_ms, self.total_reqs)

            tx = self.per_transaction.setdefault(transaction_name, {
                'count': 0, 'errors': 0, 'reservoir': [],
            })
            tx['count'] += 1
            if status != 'passed':
                tx['errors'] += 1
            self._reservoir_add(tx['reservoir'], duration_ms, tx['count'])

            if case_name:
                cs = self.per_case.setdefault(case_name, {
                    'count': 0, 'errors': 0, 'reservoir': [],
                    'transaction': transaction_name,
                })
                cs['count'] += 1
                if status != 'passed':
                    cs['errors'] += 1
                self._reservoir_add(cs['reservoir'], duration_ms, cs['count'])

            now = time.monotonic()
            self.fire_window.append(now)
            cutoff = now - 5.0
            while self.fire_window and self.fire_window[0] < cutoff:
                self.fire_window.popleft()

    def record_dropped(self) -> None:
        with self._lock:
            self.dropped_count += 1

    def _reservoir_add(self, r: list, value: float, total_seen: int) -> None:
        if len(r) < self.reservoir_size:
            r.append(value)
        else:
            idx = random.randint(0, total_seen - 1)
            if idx < self.reservoir_size:
                r[idx] = value

    def snapshot(self, active_vus: int) -> dict:
        with self._lock:
            return {
                'total_reqs': self.total_reqs,
                'success_count': self.success_count,
                'error_count': self.error_count,
                'dropped_count': self.dropped_count,
                'active_vus': active_vus,
                'current_rps': round(len(self.fire_window) / 5.0, 2),
                'latency_ms': _percentiles(self.reservoir),
                'per_transaction': {
                    name: {
                        'count': tx['count'],
                        'error_rate': (
                            round(tx['errors'] / tx['count'], 4) if tx['count'] else 0.0
                        ),
                        'p95_ms': _percentiles(tx['reservoir']).get('p95', 0),
                    }
                    for name, tx in self.per_transaction.items()
                },
                'per_case': {
                    name: {
                        'transaction': cs.get('transaction', ''),
                        'count': cs['count'],
                        'error_rate': (
                            round(cs['errors'] / cs['count'], 4) if cs['count'] else 0.0
                        ),
                        **{k: v for k, v in _percentiles(cs['reservoir']).items()
                           if k in ('p50', 'p95', 'p99', 'avg')},
                    }
                    for name, cs in self.per_case.items()
                },
            }


def _percentiles(samples: list[float]) -> dict:
    if not samples:
        return {'p50': 0, 'p95': 0, 'p99': 0, 'avg': 0, 'min': 0, 'max': 0}
    s = sorted(samples)
    n = len(s)
    return {
        'p50': round(s[int(n * 0.5)], 2),
        'p95': round(s[min(int(n * 0.95), n - 1)], 2),
        'p99': round(s[min(int(n * 0.99), n - 1)], 2),
        'avg': round(sum(s) / n, 2),
        'min': round(s[0], 2),
        'max': round(s[-1], 2),
    }


# ── Virtual User ────────────────────────────────────────────────────────

class VU:
    """One virtual user. Holds a baseline runtime-var snapshot after setup.

    A VU is single-greenlet by contract: the dispatcher only hands it out
    when idle. We don't need internal locks — the idle/busy state is
    enforced by the Queue in PerfDriver.
    """

    def __init__(self, vu_id: int, env: Any, account_row: dict):
        self.vu_id = vu_id
        self.env = env
        self.account_row = dict(account_row or {})
        self.baseline_runtime_vars: dict = {}
        self.failed_setup = False

    def _make_executor(self) -> TestExecutor:
        ex = TestExecutor(env=self.env)
        for k, v in self.account_row.items():
            ex.variable_context.set_var(k, v)
        for k, v in self.baseline_runtime_vars.items():
            ex.variable_context.set_var(k, v)
        return ex

    def initialize(self, setup_pcs: list[PerfPlanCase],
                   metrics: 'MetricsAccumulator | None' = None) -> bool:
        ex = TestExecutor(env=self.env)
        for k, v in self.account_row.items():
            ex.variable_context.set_var(k, v)
        for pc in setup_pcs:
            tc = pc.to_executable()
            try:
                result = ex.run_single_case(tc)
            except Exception:
                logger.exception(f'VU {self.vu_id} setup crashed on {getattr(tc, "case_name", "?")}')
                self.failed_setup = True
                return False
            if metrics is not None:
                metrics.record('__setup__', result.get('duration_ms', 0) or 0,
                               'passed' if result.get('status') == 'passed' else 'failed',
                               case_name=getattr(tc, 'case_name', '') or '')
            # Strict setup: any script error (pre or post) counts as VU init
            # failure, even if assertions pass. Post-scripts on login cases
            # extract tokens; if they crash silently, the VU runs the rest
            # of the test with no token and poisons the global error rate.
            err_msg = result.get('error_message', '') or ''
            if result.get('status') != 'passed' or 'script error' in err_msg.lower():
                logger.warning(
                    f'VU {self.vu_id} setup case {getattr(tc, "case_name", "?")} '
                    f'failed: status={result.get("status")} err={err_msg[:200]}'
                )
                self.failed_setup = True
                return False
        self.baseline_runtime_vars = dict(ex.variable_context.runtime_variables)
        return True

    def run_transaction(
        self,
        pcs: list[PerfPlanCase],
        data_sources: dict[int, DataSource],
        metrics: 'MetricsAccumulator | None' = None,
        tx_name: str = '',
        abort_event: 'Event | None' = None,
        rate_limiter: 'RateLimiter | None' = None,
    ) -> bool:
        """Run an ordered list of cases as one transaction.

        Each case is recorded into ``metrics`` as it completes (live RPS
        reflects the per-case fire rate). If a ``rate_limiter`` is given,
        the VU yields before EACH case until a token is available — this
        is what enforces a true case-level RPS target across all VUs
        (chain semantics preserve setVar order; the limiter just paces).
        If the ``abort_event`` is set partway through, we bail out of the
        loop between cases.
        """
        ex = self._make_executor()
        all_passed = True
        for pc in pcs:
            if abort_event is not None and abort_event.is_set():
                break
            if rate_limiter is not None:
                rate_limiter.acquire(abort_event=abort_event)
                if abort_event is not None and abort_event.is_set():
                    break
            ds = data_sources.get(pc.id)
            if ds is not None:
                row = ds.pick()
                if row:
                    for k, v in row.items():
                        ex.variable_context.set_var(k, v)
            tc = pc.to_executable()
            try:
                result = ex.run_single_case(tc)
            except Exception as e:
                logger.exception(f'VU {self.vu_id} tx case {getattr(tc, "case_name", "?")} crashed')
                result = {'status': 'error', 'duration_ms': 0, 'error_message': str(e)[:300]}
            if metrics is not None:
                metrics.record(tx_name, result.get('duration_ms', 0) or 0,
                               'passed' if result.get('status') == 'passed' else 'failed',
                               case_name=getattr(tc, 'case_name', '') or '')
            if result.get('status') != 'passed':
                all_passed = False
        return all_passed


# ── Rate limiter (token-bucket pacing) ─────────────────────────────────

class RateLimiter:
    """Greenlet-safe constant-arrival-rate limiter.

    Treats `rate` as the case-level RPS cap. Each acquire() returns at the
    next available slot (1/rate seconds apart). Callers that lag behind
    schedule get immediate return — slots that elapse without a consumer
    are NOT banked (otherwise a slow ramp could burst-fire).
    """

    def __init__(self, rate_per_sec: float):
        self.interval = 1.0 / max(rate_per_sec, 1)
        self._next = time.monotonic()
        self._lock = RLock()

    def acquire(self, abort_event: 'Event | None' = None) -> None:
        with self._lock:
            now = time.monotonic()
            # Anti-burst: if we're way behind (long pause / slow case),
            # reset baseline to now instead of releasing N tokens at once.
            if self._next < now - self.interval:
                self._next = now
            slot = self._next
            self._next = slot + self.interval
        wait = slot - time.monotonic()
        if wait > 0:
            # Sleep in chunks so we react to abort within ~0.1s.
            while wait > 0:
                if abort_event is not None and abort_event.is_set():
                    return
                gevent.sleep(min(wait, 0.1))
                wait = slot - time.monotonic()


# ── Driver ──────────────────────────────────────────────────────────────

ABORT_POLL_INTERVAL_S = 1.0
DB_FLUSH_INTERVAL_S = 2.0
SETUP_FAILURE_THRESHOLD = 0.5  # >50% of VU setups failing aborts the run
SETUP_PARALLELISM = 20         # cap concurrent VU inits — auth endpoints throttle fast under stampede


class PerfDriver:
    def __init__(self, plan: PerfPlan, run: PerfRun):
        self.plan = plan
        self.perf_run = run
        self.metrics = MetricsAccumulator()

        self.vus: list[VU] = []
        self.idle_queue: Queue = Queue()

        self.abort_event: Event = Event()
        self._setup_pcs: list[PerfPlanCase] = []
        self._tx_cases: dict[str, list[PerfPlanCase]] = {}
        self._tx_names: list[str] = []
        self._tx_weights: list[int] = []
        self._data_sources: dict[int, DataSource] = {}

        self._active_count = 0  # currently busy VU greenlets
        self._active_lock = RLock()

    # ── Lifecycle ───────────────────────────────────────────────────────
    def run(self) -> None:
        self._load_structure()

        if not self._tx_names:
            self._fail('Plan has no transactions with cases')
            return

        self.perf_run.status = 'running'
        self.perf_run.started_at = timezone.now()
        self.perf_run.last_heartbeat_at = self.perf_run.started_at
        self.perf_run.save(update_fields=[
            'status', 'started_at', 'last_heartbeat_at', 'updated_at',
        ])

        account_pool = self._load_account_pool()
        self._init_vus(account_pool)
        if not self.vus:
            return  # already marked status='setup_failed' in _init_vus

        # Background greenlets
        flusher = gevent.spawn(self._flusher_loop)
        aborter = gevent.spawn(self._abort_poller_loop)

        # Per-VU loops + global rate limiter — true case-level RPS pacing.
        # Each VU runs transactions back-to-back; before EACH case fires it
        # acquires a token from the limiter. Achieved RPS is the minimum
        # of target_rate and (sum of per-VU max throughput).
        self.rate_limiter = RateLimiter(self.perf_run.target_rate)
        self.deadline = time.monotonic() + self.perf_run.duration_secs
        vu_greenlets = [gevent.spawn(self._vu_main_loop, vu) for vu in self.vus]
        try:
            gevent.joinall(vu_greenlets)
        finally:
            flusher.kill(block=False)
            aborter.kill(block=False)

        self._flush_summary()
        if self.abort_event.is_set():
            final_status = 'aborted'
        else:
            final_status = 'completed'
        self.perf_run.status = final_status
        self.perf_run.finished_at = timezone.now()
        self.perf_run.save(update_fields=['status', 'finished_at', 'updated_at'])

        self._maybe_notify(final_status)

    def _fail(self, msg: str, status: str = 'failed') -> None:
        logger.error(f'PerfRun {self.perf_run.id} {status}: {msg}')
        self.perf_run.status = status
        self.perf_run.error_message = msg[:5000]
        self.perf_run.finished_at = timezone.now()
        self.perf_run.save(update_fields=[
            'status', 'error_message', 'finished_at', 'updated_at',
        ])

    # ── Plan loading ────────────────────────────────────────────────────
    def _load_structure(self) -> None:
        plan_cases = list(
            self.plan.plan_cases.select_related('testcase')
            .order_by('role', 'transaction_name', 'sort_order')
        )
        for pc in plan_cases:
            if pc.role == 'setup':
                self._setup_pcs.append(pc)
            elif pc.role == 'transaction':
                self._tx_cases.setdefault(pc.transaction_name, []).append(pc)
            if pc.data_file_s3_key:
                try:
                    rows = _load_data_file(pc.data_file_s3_key)
                    self._data_sources[pc.id] = DataSource(rows, mode=pc.data_mode)
                except Exception:
                    logger.exception(
                        f'Failed to load data file {pc.data_file_s3_key} for plan_case {pc.id}'
                    )

        tx_meta = {t['name']: t for t in (self.plan.transactions or []) if 'name' in t}
        for name in self._tx_cases:
            self._tx_names.append(name)
            self._tx_weights.append(int(tx_meta.get(name, {}).get('weight', 1)))

    def _load_account_pool(self) -> list[dict]:
        if not self.plan.account_data_file_s3_key:
            return [{}]
        try:
            rows = _load_data_file(self.plan.account_data_file_s3_key)
        except Exception:
            logger.exception(f'Failed to load account pool {self.plan.account_data_file_s3_key}')
            rows = []
        return rows or [{}]

    # ── VU init ─────────────────────────────────────────────────────────
    def _init_vus(self, account_pool: list[dict]) -> None:
        """Initialize all VUs in parallel (capped at SETUP_PARALLELISM to
        avoid stampeding the auth endpoint when max_vus is large)."""
        target = self.perf_run.max_vus
        threshold = max(1, int(target * SETUP_FAILURE_THRESHOLD))

        def _init_one(i: int) -> tuple[int, VU, bool]:
            account_row = account_pool[i % len(account_pool)]
            vu = VU(vu_id=i, env=self.plan.env, account_row=account_row)
            if not self._setup_pcs:
                return i, vu, True
            ok = vu.initialize(self._setup_pcs, metrics=self.metrics)
            return i, vu, ok

        pool = Pool(size=min(target, SETUP_PARALLELISM))
        greenlets = [pool.spawn(_init_one, i) for i in range(target)]
        pool.join()

        setup_failed = 0
        for g in greenlets:
            _, vu, ok = g.value
            if ok:
                self.vus.append(vu)
                self.idle_queue.put(vu)
            else:
                setup_failed += 1

        if setup_failed >= threshold and not self.vus:
            self._fail(
                f'Setup failed for {setup_failed} of {target} VUs '
                f'(threshold {SETUP_FAILURE_THRESHOLD*100:.0f}%); aborting',
                status='setup_failed',
            )

    # ── Per-VU main loop (true case-level RPS pacing) ───────────────────
    def _vu_main_loop(self, vu: VU) -> None:
        """A single VU greenlet — runs transactions back-to-back until
        the run deadline or abort. Each case fire is gated by the global
        RateLimiter so total achieved RPS across all VUs ≤ target_rate.
        """
        while time.monotonic() < self.deadline:
            if self.abort_event.is_set():
                return
            tx_name = random.choices(self._tx_names, weights=self._tx_weights, k=1)[0]
            pcs = self._tx_cases.get(tx_name, [])
            with self._active_lock:
                self._active_count += 1
            try:
                vu.run_transaction(
                    pcs, self._data_sources,
                    metrics=self.metrics, tx_name=tx_name,
                    abort_event=self.abort_event,
                    rate_limiter=self.rate_limiter,
                )
            except Exception:
                logger.exception(
                    f'PerfRun {self.perf_run.id} VU {vu.vu_id} tx {tx_name} crashed'
                )
                self.metrics.record(tx_name, 0.0, 'failed')
            finally:
                with self._active_lock:
                    self._active_count -= 1

    # ── Background greenlets ────────────────────────────────────────────
    def _flusher_loop(self) -> None:
        while True:
            try:
                self._flush_summary()
            except Exception:
                logger.exception('summary flush crashed')
            gevent.sleep(DB_FLUSH_INTERVAL_S)

    def _abort_poller_loop(self) -> None:
        while not self.abort_event.is_set():
            try:
                self.perf_run.refresh_from_db(fields=['status'])
                if self.perf_run.status == 'aborting':
                    logger.info(f'PerfRun {self.perf_run.id} abort flag detected')
                    self.abort_event.set()
                    return
            except Exception:
                logger.exception('abort poll crashed')
            gevent.sleep(ABORT_POLL_INTERVAL_S)

    # ── Metrics flush ───────────────────────────────────────────────────
    def _flush_summary(self) -> None:
        with self._active_lock:
            active = self._active_count
        summary = self.metrics.snapshot(active_vus=active)
        try:
            self.perf_run.summary_json = summary
            self.perf_run.last_heartbeat_at = timezone.now()
            self.perf_run.save(update_fields=[
                'summary_json', 'last_heartbeat_at', 'updated_at',
            ])
        except Exception:
            logger.exception(f'PerfRun {self.perf_run.id} summary flush failed')

    # ── Notification ────────────────────────────────────────────────────
    def _maybe_notify(self, final_status: str) -> None:
        if not self.plan.notify_feishu_webhook:
            return
        if final_status == 'completed' and not self.plan.notify_on_completion:
            return
        if final_status == 'failed' and not self.plan.notify_on_failure:
            return
        logger.info(
            f'PerfRun {self.perf_run.id} would notify '
            f'{self.plan.notify_feishu_webhook} (notify TODO)'
        )
