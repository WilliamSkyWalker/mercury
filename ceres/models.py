from django.db import models
from django.db.models import Q
import json


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self):
        self.is_deleted = True
        self.save(update_fields=['is_deleted', 'updated_at'])


# ==================== 用户 ====================

class User(models.Model):
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=200, default='')
    username = models.CharField(max_length=200, default='')
    is_admin = models.BooleanField(default=False)
    last_login = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ceres_user'

    def __str__(self):
        return self.display_name or self.email


# ==================== 项目 ====================

class Project(SoftDeleteModel):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(default='', blank=True)

    class Meta:
        db_table = 'ceres_project'
        ordering = ['name']

    def __str__(self):
        return self.name


# ==================== 用例管理 ====================

class Folder(SoftDeleteModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='folders')
    name = models.CharField(max_length=200)
    parent = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='children'
    )
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'ceres_folder'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name

    def soft_delete(self):
        for child in Folder.objects.filter(parent=self):
            child.soft_delete()
        super().soft_delete()


class Testcase(SoftDeleteModel):
    METHOD_CHOICES = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('DELETE', 'DELETE'),
        ('PATCH', 'PATCH'),
        ('HEAD', 'HEAD'),
        ('OPTIONS', 'OPTIONS'),
    ]
    BODY_TYPE_CHOICES = [
        ('none', 'None'),
        ('json', 'JSON'),
        ('form', 'Form URL Encoded'),
        ('multipart', 'Multipart Form'),
        ('raw', 'Raw Text'),
    ]
    SCRIPT_TYPE_CHOICES = [
        ('python', 'Python'),
        ('javascript', 'JavaScript (unconverted)'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='testcases')
    case_name = models.CharField(max_length=200)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default='GET')
    url = models.CharField(max_length=2000)
    headers = models.JSONField(default=list, blank=True, help_text='[{"key":"k","value":"v","enabled":true}]')
    params = models.JSONField(default=list, blank=True, help_text='[{"key":"k","value":"v","enabled":true}]')
    body_type = models.CharField(max_length=20, choices=BODY_TYPE_CHOICES, default='none')
    body = models.JSONField(default=dict, blank=True)
    assertions = models.JSONField(default=list, blank=True, help_text='[{"field":"res.status","operator":"eq","expected":200}]')
    pre_request_script = models.TextField(default='', blank=True)
    post_request_script = models.TextField(default='', blank=True)
    script_type = models.CharField(max_length=20, choices=SCRIPT_TYPE_CHOICES, default='python')
    folder = models.ForeignKey(Folder, null=True, blank=True, on_delete=models.SET_NULL, related_name='testcases')
    timeout = models.IntegerField(default=30, help_text='Request timeout in seconds')
    sort_order = models.IntegerField(default=0)
    tags = models.JSONField(default=list, blank=True)
    comment = models.TextField(default='', blank=True)
    files = models.JSONField(default=list, blank=True,
        help_text='[{"name":"avatar.png","s3_key":"qa/mercury/testdata/...","content_type":"image/png","size":12345}]')
    ws_steps = models.JSONField(null=True, blank=True,
        help_text='WebSocket-only. Ordered steps: [{"kind":"send","payload_type":"json|text|binary_b64","payload":...},'
                  ' {"kind":"recv","timeout_ms":60000}, {"kind":"wait","duration_ms":1000},'
                  ' {"kind":"close","code":1000}]. Required when url starts with ws:// or wss://.')

    class Meta:
        db_table = 'ceres_testcase'
        ordering = ['sort_order', 'case_name']

    def __str__(self):
        return f"[{self.method}] {self.case_name}"


# ==================== 环境 ====================

class Env(SoftDeleteModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='envs')
    name = models.CharField(max_length=100)
    variables = models.JSONField(default=dict, blank=True)
    runtime_variables = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'ceres_env'
        ordering = ['name']
        unique_together = ['project', 'name']

    def __str__(self):
        return self.name


# ==================== 测试计划 ====================

class Testplan(SoftDeleteModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='testplans')
    name = models.CharField(max_length=200)
    folder = models.ForeignKey(Folder, null=True, blank=True, on_delete=models.SET_NULL, related_name='testplans')
    env = models.ForeignKey(Env, null=True, blank=True, on_delete=models.SET_NULL, related_name='testplans')
    is_serial = models.BooleanField(default=True)
    retry_count = models.IntegerField(default=0)
    feishu_webhook = models.CharField(max_length=500, default='', blank=True)
    notify_on_failure = models.BooleanField(default=True)
    phone_on_failure = models.BooleanField(default=False)
    phone_muted = models.BooleanField(default=False)

    class Meta:
        db_table = 'ceres_testplan'
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class TestplanCase(models.Model):
    testplan = models.ForeignKey(Testplan, on_delete=models.CASCADE, related_name='plan_cases')
    testcase = models.ForeignKey(Testcase, on_delete=models.CASCADE, related_name='in_plans')
    sort_order = models.IntegerField(default=0)
    case_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'ceres_testplan_case'
        ordering = ['sort_order']
        unique_together = ['testplan', 'testcase']

    def __str__(self):
        return f"{self.testplan.name} -> {self.testcase.case_name}"

    SNAPSHOT_FIELDS = [
        'case_name', 'method', 'url', 'headers', 'params',
        'body_type', 'body', 'assertions',
        'pre_request_script', 'post_request_script', 'script_type', 'timeout',
        'files', 'ws_steps',
    ]

    @staticmethod
    def snapshot_from_testcase(tc):
        """Create a snapshot dict from a Testcase instance."""
        return {f: getattr(tc, f) for f in TestplanCase.SNAPSHOT_FIELDS}

    def take_snapshot(self):
        """Snapshot the current state of the linked testcase."""
        self.case_snapshot = self.snapshot_from_testcase(self.testcase)
        self.save(update_fields=['case_snapshot'])

    def to_executable(self):
        """Return a testcase-like object for execution.

        Uses snapshot if available, falls back to live testcase.
        """
        from types import SimpleNamespace
        snap = self.case_snapshot
        if not snap:
            return self.testcase
        obj = SimpleNamespace(**snap)
        obj.id = self.testcase_id
        return obj


class ScheduledTask(SoftDeleteModel):
    TRIGGER_CHOICES = [
        ('interval', 'Interval'),
        ('cron', 'Cron'),
    ]

    name = models.CharField(max_length=200)
    testplan = models.ForeignKey(Testplan, on_delete=models.CASCADE, related_name='schedules')
    env = models.ForeignKey(Env, null=True, blank=True, on_delete=models.SET_NULL)
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default='interval')
    cron_expression = models.CharField(max_length=100, default='', blank=True)
    interval_seconds = models.IntegerField(default=900)
    is_active = models.BooleanField(default=False)

    class Meta:
        db_table = 'ceres_scheduled_task'

    def __str__(self):
        return self.name


# ==================== 执行记录 & 报告 ====================

class ExecutionRecord(SoftDeleteModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('interrupted', 'Interrupted'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('error', 'Error'),
    ]
    TRIGGER_CHOICES = [
        ('manual', 'Manual'),
        ('scheduled', 'Scheduled'),
        ('api', 'API'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='executions')
    task_id = models.CharField(max_length=200, unique=True, db_index=True)
    testplan = models.ForeignKey(Testplan, null=True, blank=True, on_delete=models.SET_NULL, related_name='executions')
    env = models.ForeignKey(Env, null=True, blank=True, on_delete=models.SET_NULL)
    env_snapshot = models.JSONField(default=dict, blank=True)
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default='manual')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_cases = models.IntegerField(default=0)
    passed_cases = models.IntegerField(default=0)
    failed_cases = models.IntegerField(default=0)
    error_cases = models.IntegerField(default=0)
    skipped_cases = models.IntegerField(default=0)
    pass_rate = models.FloatField(default=0.0)
    duration_ms = models.IntegerField(default=0)
    report_url = models.CharField(max_length=500, default='', blank=True)

    class Meta:
        db_table = 'ceres_execution_record'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.task_id} [{self.status}]"


class ExecutionCaseResult(models.Model):
    STATUS_CHOICES = [
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('error', 'Error'),
        ('skipped', 'Skipped'),
    ]

    execution = models.ForeignKey(ExecutionRecord, on_delete=models.CASCADE, related_name='case_results')
    testcase = models.ForeignKey(Testcase, null=True, blank=True, on_delete=models.SET_NULL)
    case_name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='passed')
    request_method = models.CharField(max_length=10, default='')
    request_url = models.CharField(max_length=2000, default='')
    request_headers = models.JSONField(default=dict, blank=True)
    request_body = models.TextField(default='', blank=True)
    response_status = models.IntegerField(default=0)
    response_headers = models.JSONField(default=dict, blank=True)
    response_body = models.TextField(default='', blank=True)
    duration_ms = models.IntegerField(default=0)
    assertion_results = models.JSONField(default=list, blank=True)
    extracted_variables = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(default='', blank=True)
    stream_metrics = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ceres_execution_case_result'
        ordering = ['id']

    def __str__(self):
        return f"{self.case_name} [{self.status}]"


# ==================== 白名单 & 权限 & 审计 ====================

class WhitelistEmail(models.Model):
    email = models.EmailField(unique=True)
    note = models.CharField(max_length=200, default='', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ceres_whitelist_email'
        ordering = ['email']

    def __str__(self):
        return self.email


class ProjectPermission(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='permissions')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='permissions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ceres_project_permission'
        unique_together = ['user', 'project']
        ordering = ['user__email']

    def __str__(self):
        return f"{self.user.email} -> {self.project.name}"


class AuditLog(models.Model):
    user_email = models.CharField(max_length=254)
    action = models.CharField(max_length=20)  # GET, POST, PUT, PATCH, DELETE
    path = models.CharField(max_length=500)
    body = models.JSONField(default=dict, blank=True)
    status_code = models.IntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ceres_audit_log'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user_email} {self.action} {self.path}"


class Report(SoftDeleteModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='reports')
    name = models.CharField(max_length=100)
    result = models.TextField(default='')
    detail = models.TextField(default='')
    store_link = models.CharField(max_length=500, default='')

    class Meta:
        db_table = 'ceres_report'

    def __str__(self):
        return self.name
