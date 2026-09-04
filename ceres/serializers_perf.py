"""Serializers for PerfPlan / PerfPlanCase / PerfRun.

The plan-edit flow expects clients to send the full case list nested inside
the plan payload (similar to TestplanSerializer's pattern). Setup cases and
transaction cases are differentiated by `role`.
"""
from rest_framework import serializers
from ceres.models_perf import PerfPlan, PerfPlanCase, PerfRun


class PerfPlanCaseSerializer(serializers.ModelSerializer):
    case_name = serializers.CharField(source='testcase.case_name', read_only=True, default='')

    class Meta:
        model = PerfPlanCase
        fields = [
            'id', 'testcase', 'case_name',
            'role', 'transaction_name', 'sort_order',
            'data_file_s3_key', 'data_mode',
            'case_snapshot',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['case_snapshot', 'created_at', 'updated_at']


class PerfPlanSerializer(serializers.ModelSerializer):
    env_name = serializers.CharField(source='env.name', read_only=True, default='')
    plan_cases = PerfPlanCaseSerializer(many=True, read_only=True)

    class Meta:
        model = PerfPlan
        fields = [
            'id', 'project', 'env', 'env_name',
            'name', 'description',
            'target_rate', 'duration_secs', 'max_vus',
            'transactions',
            'account_data_file_s3_key',
            'notify_feishu_webhook', 'notify_on_completion', 'notify_on_failure',
            'plan_cases',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class PerfPlanListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views — no nested cases."""
    env_name = serializers.CharField(source='env.name', read_only=True, default='')
    transaction_count = serializers.SerializerMethodField()
    case_count = serializers.SerializerMethodField()

    class Meta:
        model = PerfPlan
        fields = [
            'id', 'project', 'env', 'env_name',
            'name', 'description',
            'target_rate', 'duration_secs', 'max_vus',
            'transaction_count', 'case_count',
            'created_at', 'updated_at',
        ]

    def get_transaction_count(self, obj):
        return len(obj.transactions or [])

    def get_case_count(self, obj):
        return obj.plan_cases.count()


class PerfRunSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='perf_plan.name', read_only=True, default='')

    class Meta:
        model = PerfRun
        fields = [
            'id', 'perf_plan', 'plan_name',
            'target_rate', 'duration_secs', 'max_vus',
            'status',
            'started_at', 'finished_at', 'last_heartbeat_at',
            'summary_json', 'error_message',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class PerfRunListSerializer(serializers.ModelSerializer):
    """Trimmed serializer for run history — drops the full summary_json blob."""
    plan_name = serializers.CharField(source='perf_plan.name', read_only=True, default='')
    total_reqs = serializers.SerializerMethodField()
    error_rate = serializers.SerializerMethodField()
    p95_ms = serializers.SerializerMethodField()

    class Meta:
        model = PerfRun
        fields = [
            'id', 'perf_plan', 'plan_name',
            'target_rate', 'duration_secs',
            'status',
            'started_at', 'finished_at',
            'total_reqs', 'error_rate', 'p95_ms',
            'created_at',
        ]

    def get_total_reqs(self, obj):
        v = getattr(obj, '_ann_total_reqs', None)
        if v is not None:
            return int(v) if str(v).isdigit() else 0
        return (obj.summary_json or {}).get('total_reqs', 0)

    def get_error_rate(self, obj):
        total = getattr(obj, '_ann_total_reqs', None)
        errors = getattr(obj, '_ann_error_count', None)
        if total is not None and errors is not None:
            try:
                t, e = int(total), int(errors)
                return round(e / t, 4) if t else 0.0
            except (TypeError, ValueError):
                pass
        s = obj.summary_json or {}
        t = s.get('total_reqs', 0) or 0
        e = s.get('error_count', 0) or 0
        return round(e / t, 4) if t else 0.0

    def get_p95_ms(self, obj):
        v = getattr(obj, '_ann_p95', None)
        if v is not None:
            try:
                return int(float(v))
            except (TypeError, ValueError):
                pass
        return ((obj.summary_json or {}).get('latency_ms') or {}).get('p95', 0)
