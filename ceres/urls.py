from django.urls import path
from rest_framework.routers import DefaultRouter
from ceres.views_v2 import (
    ProjectViewSet, FolderViewSet, EnvViewSet, TestcaseViewSet,
    TestplanViewSet, ScheduledTaskViewSet,
    ExecutionRecordViewSet, StatsViewSet,
    UserViewSet, WhitelistEmailViewSet, ProjectPermissionViewSet, AuditLogViewSet,
)
from ceres.auth import login, me
from ceres.views_perf import PerfPlanViewSet, PerfRunViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet)
router.register(r'folders', FolderViewSet)
router.register(r'envs', EnvViewSet)
router.register(r'testcases', TestcaseViewSet)
router.register(r'testplans', TestplanViewSet)
router.register(r'schedules', ScheduledTaskViewSet)
router.register(r'executions', ExecutionRecordViewSet)
router.register(r'stats', StatsViewSet, basename='stats')
router.register(r'users', UserViewSet)
router.register(r'whitelist', WhitelistEmailViewSet)
router.register(r'permissions', ProjectPermissionViewSet)
router.register(r'audit-logs', AuditLogViewSet)
router.register(r'perf-plans', PerfPlanViewSet)
router.register(r'perf-runs', PerfRunViewSet)

urlpatterns = [
    path('auth/login/', login),
    path('auth/me/', me),
] + router.urls
