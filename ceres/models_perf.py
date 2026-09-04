"""Load testing data model — in-process Mercury engine.

PerfPlan defines what to load and how (rate, duration, cases, data sources).
PerfPlanCase is the junction with role='setup'|'transaction', mirroring the
TestplanCase pattern (snapshot for stability across testcase edits).
PerfRun captures one execution with live-flushed summary metrics.

Schema is included in scripts/mercury_mysql_schema.sql. Django migrations are
not used (managed=False, mirrors the project convention).
"""
from django.db import models
from ceres.models import SoftDeleteModel, SoftDeleteManager, Project, Env, Testcase


class PerfPlan(SoftDeleteModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='perf_plans')
    env = models.ForeignKey(Env, null=True, blank=True, on_delete=models.SET_NULL, related_name='perf_plans')
    name = models.CharField(max_length=200)
    description = models.TextField(default='', blank=True)

    target_rate = models.IntegerField(default=100)
    duration_secs = models.IntegerField(default=60)
    max_vus = models.IntegerField(default=50)

    # [{name, weight, sort_order}] — metadata only. The cases of each transaction
    # live in PerfPlanCase rows (joined on transaction_name).
    transactions = models.JSONField(default=list, blank=True)

    # Optional per-VU account pool (CSV/JSON in S3, one row per VU).
    account_data_file_s3_key = models.CharField(max_length=500, default='', blank=True)

    notify_feishu_webhook = models.CharField(max_length=500, default='', blank=True)
    notify_on_completion = models.BooleanField(default=False)
    notify_on_failure = models.BooleanField(default=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'ceres_perf_plan'
        managed = False
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class PerfPlanCase(models.Model):
    ROLE_CHOICES = [
        ('setup', 'Setup'),
        ('transaction', 'Transaction'),
    ]
    DATA_MODE_CHOICES = [
        ('round_robin', 'Round Robin'),
        ('random', 'Random'),
        ('sequential_once', 'Sequential Once'),
    ]

    perf_plan = models.ForeignKey(PerfPlan, on_delete=models.CASCADE, related_name='plan_cases')
    testcase = models.ForeignKey(Testcase, on_delete=models.CASCADE, related_name='in_perf_plans')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    # For role='transaction': matches a name in PerfPlan.transactions[].name.
    # For role='setup': empty string.
    transaction_name = models.CharField(max_length=100, default='', blank=True)
    sort_order = models.IntegerField(default=0)

    data_file_s3_key = models.CharField(max_length=500, default='', blank=True)
    data_mode = models.CharField(max_length=20, choices=DATA_MODE_CHOICES, default='round_robin')

    case_snapshot = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ceres_perf_plan_case'
        managed = False
        ordering = ['role', 'transaction_name', 'sort_order']

    def __str__(self):
        return f"{self.perf_plan.name} {self.role}:{self.transaction_name or '-'} -> {self.testcase.case_name}"

    SNAPSHOT_FIELDS = [
        'case_name', 'method', 'url', 'headers', 'params',
        'body_type', 'body', 'assertions',
        'pre_request_script', 'post_request_script', 'script_type', 'timeout',
        'files',
    ]

    @staticmethod
    def snapshot_from_testcase(tc):
        return {f: getattr(tc, f) for f in PerfPlanCase.SNAPSHOT_FIELDS}

    def take_snapshot(self):
        self.case_snapshot = self.snapshot_from_testcase(self.testcase)
        self.save(update_fields=['case_snapshot', 'updated_at'])

    def to_executable(self):
        """Return a testcase-like object for execution.

        Uses snapshot if present, falls back to the live testcase row.
        Mirrors TestplanCase.to_executable() so the same TestExecutor consumes both.
        """
        from types import SimpleNamespace
        snap = self.case_snapshot
        if not snap:
            return self.testcase
        obj = SimpleNamespace(**snap)
        obj.id = self.testcase_id
        return obj


class PerfRun(SoftDeleteModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('aborting', 'Aborting'),
        ('aborted', 'Aborted'),
        ('setup_failed', 'Setup Failed'),
    ]

    perf_plan = models.ForeignKey(PerfPlan, on_delete=models.CASCADE, related_name='runs')

    target_rate = models.IntegerField()
    duration_secs = models.IntegerField()
    max_vus = models.IntegerField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)

    summary_json = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(default='', blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'ceres_perf_run'
        managed = False
        ordering = ['-started_at', '-created_at']

    def __str__(self):
        return f"PerfRun#{self.id} plan={self.perf_plan_id} status={self.status}"
