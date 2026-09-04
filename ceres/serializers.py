from rest_framework import serializers
from ceres.models import (
    Project, Folder, Env, Testcase, Testplan, TestplanCase,
    ScheduledTask, ExecutionRecord, ExecutionCaseResult, Report,
    User, WhitelistEmail, ProjectPermission, AuditLog,
)


# ==================== 项目 ====================

class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class ProjectListSerializer(serializers.ModelSerializer):
    testcase_count = serializers.SerializerMethodField()
    env_count = serializers.SerializerMethodField()
    testplan_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'testcase_count', 'env_count',
                  'testplan_count', 'created_at', 'updated_at']

    def get_testcase_count(self, obj):
        return obj.testcases.count()

    def get_env_count(self, obj):
        return obj.envs.count()

    def get_testplan_count(self, obj):
        return obj.testplans.count()


# ==================== 用例管理 ====================

class FolderSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    testcase_count = serializers.SerializerMethodField()

    class Meta:
        model = Folder
        fields = ['id', 'project', 'name', 'parent', 'sort_order', 'children',
                  'testcase_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def get_children(self, obj):
        if self.context.get('flat', False):
            return []
        children = Folder.objects.filter(parent=obj)
        return FolderSerializer(children, many=True, context=self.context).data

    def get_testcase_count(self, obj):
        return Testcase.objects.filter(folder=obj).count()


class FolderListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Folder
        fields = ['id', 'project', 'name', 'parent', 'sort_order', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class TestcaseSerializer(serializers.ModelSerializer):
    folder_name = serializers.CharField(source='folder.name', read_only=True, default='')

    class Meta:
        model = Testcase
        fields = [
            'id', 'project', 'case_name', 'method', 'url', 'headers', 'params',
            'body_type', 'body', 'assertions', 'pre_request_script',
            'post_request_script', 'script_type', 'folder', 'folder_name',
            'timeout', 'sort_order', 'tags', 'comment', 'files', 'ws_steps',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class TestcaseListSerializer(serializers.ModelSerializer):
    folder_name = serializers.CharField(source='folder.name', read_only=True, default='')

    class Meta:
        model = Testcase
        fields = ['id', 'project', 'case_name', 'method', 'url', 'folder', 'folder_name',
                  'sort_order', 'tags', 'updated_at']


# ==================== 环境 ====================

class EnvSerializer(serializers.ModelSerializer):
    class Meta:
        model = Env
        fields = ['id', 'project', 'name', 'variables', 'runtime_variables', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


# ==================== 测试计划 ====================

class TestplanCaseSerializer(serializers.ModelSerializer):
    case_name = serializers.CharField(source='testcase.case_name', read_only=True)
    method = serializers.CharField(source='testcase.method', read_only=True)
    url = serializers.CharField(source='testcase.url', read_only=True)

    class Meta:
        model = TestplanCase
        fields = ['id', 'testcase', 'case_name', 'method', 'url', 'sort_order']


class TestplanSerializer(serializers.ModelSerializer):
    env_name = serializers.CharField(source='env.name', read_only=True, default='')

    class Meta:
        model = Testplan
        fields = [
            'id', 'project', 'name', 'folder', 'env', 'env_name', 'is_serial',
            'retry_count', 'feishu_webhook', 'notify_on_failure',
            'phone_on_failure', 'phone_muted',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class TestplanDetailSerializer(serializers.ModelSerializer):
    plan_cases = TestplanCaseSerializer(many=True, read_only=True)
    env_name = serializers.CharField(source='env.name', read_only=True, default='')

    class Meta:
        model = Testplan
        fields = [
            'id', 'project', 'name', 'folder', 'env', 'env_name', 'is_serial',
            'retry_count', 'feishu_webhook', 'notify_on_failure',
            'phone_on_failure', 'phone_muted',
            'plan_cases', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class TestplanListSerializer(serializers.ModelSerializer):
    env_name = serializers.CharField(source='env.name', read_only=True, default='')
    case_count = serializers.SerializerMethodField()

    class Meta:
        model = Testplan
        fields = ['id', 'project', 'name', 'folder', 'env', 'env_name', 'is_serial',
                  'retry_count', 'feishu_webhook', 'notify_on_failure',
            'phone_on_failure', 'phone_muted',
                  'case_count', 'updated_at']

    def get_case_count(self, obj):
        return obj.plan_cases.count()


class ScheduledTaskSerializer(serializers.ModelSerializer):
    testplan_name = serializers.CharField(source='testplan.name', read_only=True)
    env_name = serializers.CharField(source='env.name', read_only=True, default='')

    class Meta:
        model = ScheduledTask
        fields = [
            'id', 'name', 'testplan', 'testplan_name', 'env', 'env_name',
            'trigger_type', 'cron_expression', 'interval_seconds',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'trigger_type', 'interval_seconds']

    def validate_cron_expression(self, value):
        value = (value or '').strip()
        if len(value.split()) != 5:
            raise serializers.ValidationError(
                'cron_expression must be a 5-field cron string (m h dom mon dow).'
            )
        try:
            from croniter import croniter
            croniter(value)
        except Exception as e:
            raise serializers.ValidationError(f'invalid cron expression: {e}')
        return value

    def validate(self, attrs):
        # Crontab-backed scheduler only supports cron triggers. Reject the
        # legacy 'interval' option so the UI and API stay in sync with what
        # the scheduler can actually run.
        incoming_trigger = self.initial_data.get('trigger_type') if hasattr(self, 'initial_data') else None
        if incoming_trigger and incoming_trigger != 'cron':
            raise serializers.ValidationError(
                {'trigger_type': "Only 'cron' is supported; interval triggers were removed."}
            )
        attrs['trigger_type'] = 'cron'
        if 'cron_expression' not in attrs and not (self.instance and self.instance.cron_expression):
            raise serializers.ValidationError({'cron_expression': 'This field is required.'})
        return attrs


# ==================== 执行记录 & 报告 ====================

class ExecutionCaseResultSerializer(serializers.ModelSerializer):
    """Full detail — used when fetching a single case result."""
    class Meta:
        model = ExecutionCaseResult
        fields = [
            'id', 'testcase', 'case_name', 'status',
            'request_method', 'request_url', 'request_headers', 'request_body',
            'response_status', 'response_headers', 'response_body',
            'duration_ms', 'assertion_results', 'extracted_variables',
            'error_message', 'stream_metrics', 'created_at',
        ]


class ExecutionCaseResultListSerializer(serializers.ModelSerializer):
    """Lightweight — excludes large body/header fields for listing."""
    class Meta:
        model = ExecutionCaseResult
        fields = [
            'id', 'testcase', 'case_name', 'status',
            'request_method', 'request_url', 'response_status',
            'duration_ms', 'assertion_results',
            'error_message', 'created_at',
        ]


class ExecutionRecordSerializer(serializers.ModelSerializer):
    testplan_name = serializers.CharField(source='testplan.name', read_only=True, default='')
    env_name = serializers.CharField(source='env.name', read_only=True, default='')

    class Meta:
        model = ExecutionRecord
        fields = [
            'id', 'project', 'task_id', 'testplan', 'testplan_name', 'env', 'env_name',
            'env_snapshot', 'trigger_type', 'status',
            'total_cases', 'passed_cases', 'failed_cases', 'error_cases', 'skipped_cases',
            'pass_rate', 'duration_ms', 'report_url',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class ExecutionRecordDetailSerializer(ExecutionRecordSerializer):
    class Meta(ExecutionRecordSerializer.Meta):
        pass


# ==================== 用户 & 白名单 & 权限 & 审计 ====================

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'display_name', 'username', 'is_admin', 'last_login', 'created_at']


class WhitelistEmailSerializer(serializers.ModelSerializer):
    is_admin = serializers.SerializerMethodField()

    class Meta:
        model = WhitelistEmail
        fields = ['id', 'email', 'note', 'is_admin', 'created_at']
        read_only_fields = ['created_at']

    def get_is_admin(self, obj):
        return User.objects.filter(email=obj.email, is_admin=True).exists()


class ProjectPermissionSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_display_name = serializers.CharField(source='user.display_name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model = ProjectPermission
        fields = ['id', 'user', 'user_email', 'user_display_name', 'project', 'project_name', 'created_at']
        read_only_fields = ['created_at']


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ['id', 'user_email', 'action', 'path', 'body', 'status_code', 'ip_address', 'created_at']


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ['id', 'project', 'name', 'result', 'detail', 'store_link', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
