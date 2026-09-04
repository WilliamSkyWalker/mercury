import threading
from collections import deque
from datetime import datetime

from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from ceres.models import (
    Project, Folder, Env, Testcase, Testplan, TestplanCase,
    ScheduledTask, ExecutionRecord, ExecutionCaseResult,
    User, WhitelistEmail, ProjectPermission, AuditLog,
)
from ceres.serializers import (
    ProjectSerializer, ProjectListSerializer,
    FolderSerializer, FolderListSerializer,
    EnvSerializer,
    TestcaseSerializer, TestcaseListSerializer,
    TestplanSerializer, TestplanDetailSerializer, TestplanListSerializer, TestplanCaseSerializer,
    ScheduledTaskSerializer,
    ExecutionRecordSerializer, ExecutionRecordDetailSerializer,
    ExecutionCaseResultSerializer,
    UserSerializer, WhitelistEmailSerializer, ProjectPermissionSerializer, AuditLogSerializer,
)


def _get_user_email(request):
    """Extract email from JWT payload set by JWTAuthentication."""
    if hasattr(request, 'user_info') and isinstance(request.user_info, dict):
        return request.user_info.get('email', '')
    return ''


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    search_fields = ['name']

    def get_queryset(self):
        qs = super().get_queryset()
        email = _get_user_email(self.request)
        if email:
            is_admin = User.objects.filter(email=email, is_admin=True).exists()
            if not is_admin:
                allowed_ids = ProjectPermission.objects.filter(
                    user__email=email
                ).values_list('project_id', flat=True)
                qs = qs.filter(id__in=allowed_ids)
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return ProjectListSerializer
        return ProjectSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        project = self.get_object()

        # Folders in BFS order (parents before children)
        all_folders = list(Folder.objects.filter(project=project).order_by('sort_order', 'name'))
        folder_by_id = {f.id: f for f in all_folders}

        ordered_folders = []
        roots = [f for f in all_folders if f.parent_id is None or f.parent_id not in folder_by_id]
        queue = deque(roots)
        while queue:
            folder = queue.popleft()
            ordered_folders.append(folder)
            children = sorted(
                [f for f in all_folders if f.parent_id == folder.id],
                key=lambda f: (f.sort_order, f.name),
            )
            queue.extend(children)

        folders_data = [{
            'source_id': f.id,
            'name': f.name,
            'parent_source_id': f.parent_id,
            'sort_order': f.sort_order,
        } for f in ordered_folders]

        # Testcases
        case_fields = [
            'case_name', 'method', 'url', 'headers', 'params',
            'body_type', 'body', 'assertions', 'pre_request_script',
            'post_request_script', 'script_type', 'timeout',
            'sort_order', 'tags', 'comment', 'files', 'ws_steps',
        ]
        cases_data = []
        for tc in Testcase.objects.filter(project=project).order_by('sort_order', 'case_name'):
            item = {'source_id': tc.id, 'folder_source_id': tc.folder_id}
            for field in case_fields:
                item[field] = getattr(tc, field)
            cases_data.append(item)

        # Envs (export variables, exclude runtime_variables)
        envs_data = []
        for env in Env.objects.filter(project=project).order_by('name'):
            envs_data.append({
                'source_id': env.id,
                'name': env.name,
                'variables': env.variables,
            })

        # Testplans with plan_cases (include env reference)
        plans_data = []
        for tp in Testplan.objects.filter(project=project).order_by('-updated_at'):
            plan_cases = tp.plan_cases.order_by('sort_order')
            plans_data.append({
                'source_id': tp.id,
                'name': tp.name,
                'folder_source_id': tp.folder_id,
                'env_source_id': tp.env_id,
                'is_serial': tp.is_serial,
                'retry_count': tp.retry_count,
                'feishu_webhook': tp.feishu_webhook,
                'notify_on_failure': tp.notify_on_failure,
                'phone_on_failure': tp.phone_on_failure,
                'phone_muted': tp.phone_muted,
                'plan_cases': [
                    {'testcase_source_id': pc.testcase_id, 'sort_order': pc.sort_order}
                    for pc in plan_cases
                ],
            })

        return Response({
            'version': 1,
            'project_name': project.name,
            'exported_at': timezone.now().isoformat(),
            'folders': folders_data,
            'envs': envs_data,
            'testcases': cases_data,
            'testplans': plans_data,
        })

    @action(detail=True, methods=['post'], url_path='import')
    def import_data(self, request, pk=None):
        """Import project data (overwrite mode). Clears existing folders, testcases,
        testplans and envs, then recreates from import data."""
        project = self.get_object()
        data = request.data

        if data.get('version') != 1:
            return Response({'error': f'Unsupported export version: {data.get("version")}'},
                            status=status.HTTP_400_BAD_REQUEST)

        folders_data = data.get('folders', [])
        envs_data = data.get('envs', [])
        cases_data = data.get('testcases', [])
        plans_data = data.get('testplans', [])

        try:
            with transaction.atomic():
                # Clear existing data
                TestplanCase.objects.filter(testplan__project=project).delete()
                Testplan.all_objects.filter(project=project).delete()
                Testcase.all_objects.filter(project=project).delete()
                Folder.all_objects.filter(project=project).delete()
                Env.all_objects.filter(project=project).delete()

                # --- Phase 1: Folders (BFS order guaranteed by export) ---
                folder_id_map = {}
                for fd in folders_data:
                    folder = Folder.objects.create(
                        project=project,
                        name=fd['name'],
                        parent_id=folder_id_map.get(fd.get('parent_source_id')),
                        sort_order=fd.get('sort_order', 0),
                    )
                    folder_id_map[fd['source_id']] = folder.id

                # --- Phase 2: Envs ---
                env_id_map = {}
                for ed in envs_data:
                    env = Env.objects.create(
                        project=project,
                        name=ed['name'],
                        variables=ed.get('variables', {}),
                    )
                    env_id_map[ed['source_id']] = env.id

                # --- Phase 3: Testcases ---
                case_id_map = {}
                case_fields = [
                    'case_name', 'method', 'url', 'headers', 'params',
                    'body_type', 'body', 'assertions', 'pre_request_script',
                    'post_request_script', 'script_type', 'timeout',
                    'sort_order', 'tags', 'comment', 'files',
                ]
                for cd in cases_data:
                    kwargs = {field: cd[field] for field in case_fields if field in cd}
                    kwargs['folder_id'] = folder_id_map.get(cd.get('folder_source_id'))
                    kwargs['project'] = project
                    tc = Testcase.objects.create(**kwargs)
                    case_id_map[cd['source_id']] = tc.id

                # --- Phase 4: Testplans + TestplanCases ---
                for pd in plans_data:
                    plan = Testplan.objects.create(
                        project=project,
                        name=pd['name'],
                        folder_id=folder_id_map.get(pd.get('folder_source_id')),
                        env_id=env_id_map.get(pd.get('env_source_id')),
                        is_serial=pd.get('is_serial', True),
                        retry_count=pd.get('retry_count', 0),
                        feishu_webhook=pd.get('feishu_webhook', ''),
                        notify_on_failure=pd.get('notify_on_failure', True),
                        phone_on_failure=pd.get('phone_on_failure', False),
                        phone_muted=pd.get('phone_muted', False),
                    )
                    for pc_data in pd.get('plan_cases', []):
                        new_case_id = case_id_map.get(pc_data.get('testcase_source_id'))
                        if new_case_id:
                            TestplanCase.objects.create(
                                testplan=plan,
                                testcase_id=new_case_id,
                                sort_order=pc_data.get('sort_order', 0),
                            )

        except Exception as e:
            return Response({'error': f'Import failed: {str(e)}'},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'message': 'Import completed',
            'stats': {
                'folders': len(folders_data),
                'envs': len(envs_data),
                'testcases': len(cases_data),
                'testplans': len(plans_data),
            },
            'case_id_map': {str(k): v for k, v in case_id_map.items()},
        }, status=status.HTTP_201_CREATED)


class FolderViewSet(viewsets.ModelViewSet):
    queryset = Folder.objects.all()
    serializer_class = FolderSerializer
    filterset_fields = ['project', 'parent']
    search_fields = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return FolderListSerializer
        return FolderSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def tree(self, request):
        project_id = request.query_params.get('project')
        qs = Folder.objects.all()
        if project_id:
            qs = qs.filter(project_id=project_id)

        # 2 queries total: all folders + testcase counts per folder
        from django.db.models import Count
        folders = list(
            qs.annotate(testcase_count=Count('testcases'))
            .values('id', 'project_id', 'name', 'parent_id', 'sort_order', 'testcase_count')
        )

        # Build lookup and tree in Python
        by_id = {f['id']: {
            'id': f['id'], 'project': f['project_id'], 'name': f['name'],
            'parent': f['parent_id'], 'sort_order': f['sort_order'],
            'testcase_count': f['testcase_count'], 'children': [],
        } for f in folders}

        roots = []
        for node in by_id.values():
            pid = node['parent']
            if pid and pid in by_id:
                by_id[pid]['children'].append(node)
            else:
                roots.append(node)

        # Sort children at each level
        def sort_nodes(nodes):
            nodes.sort(key=lambda n: (n['sort_order'], n['name']))
            for n in nodes:
                sort_nodes(n['children'])
        sort_nodes(roots)

        return Response(roots)


class EnvViewSet(viewsets.ModelViewSet):
    queryset = Env.objects.all()
    serializer_class = EnvSerializer
    filterset_fields = ['project']
    search_fields = ['name']

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='clear-runtime')
    def clear_runtime(self, request, pk=None):
        env = self.get_object()
        env.runtime_variables = {}
        env.save(update_fields=['runtime_variables'])
        return Response({'message': 'Runtime variables cleared'})


class TestcaseViewSet(viewsets.ModelViewSet):
    queryset = Testcase.objects.select_related('folder').all()
    serializer_class = TestcaseSerializer
    pagination_class = None
    filterset_fields = ['project', 'folder', 'method']
    search_fields = ['case_name', 'url', 'comment']
    ordering_fields = ['sort_order', 'case_name', 'updated_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return TestcaseListSerializer
        return TestcaseSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        testcase = self.get_object()
        env_id = request.data.get('env_id')
        env = Env.objects.filter(id=env_id).first() if env_id else None

        from ceres.engine.executor import TestExecutor
        executor = TestExecutor(env=env)
        result = executor.run_single_case(testcase)

        # Persist extracted variables (e.g. token) back to env for future debug runs
        extracted = result.get('extracted_variables', {})
        if extracted and env:
            env.variables.update(extracted)
            env.save(update_fields=['variables'])

        return Response(result)

    @action(detail=False, methods=['post'], url_path='batch-run')
    def batch_run(self, request):
        case_ids = request.data.get('case_ids', [])
        env_id = request.data.get('env_id')
        project_id = request.data.get('project_id')
        if not case_ids:
            return Response({'error': 'case_ids is required'}, status=status.HTTP_400_BAD_REQUEST)

        env = Env.objects.filter(id=env_id).first() if env_id else None
        testcases = Testcase.objects.filter(id__in=case_ids).order_by('sort_order')

        task_id = f"task-batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        execution = ExecutionRecord.objects.create(
            project_id=project_id,
            task_id=task_id,
            env=env,
            env_snapshot=env.variables if env else {},
            trigger_type='manual',
            status='running',
            total_cases=testcases.count(),
        )

        from ceres.engine.executor import TestExecutor
        executor = TestExecutor(env=env)
        thread = threading.Thread(
            target=executor.execute_cases_async,
            args=(execution.id, list(testcases)),
        )
        thread.start()

        return Response({
            'task_id': task_id,
            'execution_id': execution.id,
            'status': 'running',
        })

    @action(detail=True, methods=['post'], url_path='upload-file')
    def upload_file(self, request, pk=None):
        """Upload a test data file to S3 and attach to this testcase."""
        from rest_framework.parsers import MultiPartParser
        testcase = self.get_object()
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'file is required'}, status=status.HTTP_400_BAD_REQUEST)
        if file_obj.size > 50 * 1024 * 1024:
            return Response({'error': 'File too large (max 50MB)'}, status=status.HTTP_400_BAD_REQUEST)

        import uuid
        import mimetypes
        from ceres.engine.s3_utils import upload_testdata, TESTDATA_PREFIX

        content_type = file_obj.content_type or mimetypes.guess_type(file_obj.name)[0] or 'application/octet-stream'
        s3_key = f"{TESTDATA_PREFIX}{testcase.id}/{uuid.uuid4().hex[:8]}_{file_obj.name}"
        upload_testdata(file_obj, s3_key, content_type=content_type)

        file_meta = {
            'name': file_obj.name,
            's3_key': s3_key,
            'content_type': content_type,
            'size': file_obj.size,
        }
        files = testcase.files or []
        files.append(file_meta)
        testcase.files = files
        testcase.save(update_fields=['files'])

        return Response(file_meta, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def files(self, request, pk=None):
        """List all files attached to this testcase."""
        testcase = self.get_object()
        return Response(testcase.files or [])

    @action(detail=True, methods=['get'], url_path='download-file')
    def download_file(self, request, pk=None):
        """Download a test data file by name from S3."""
        testcase = self.get_object()
        file_name = request.query_params.get('name')
        if not file_name:
            return Response({'error': 'name query param is required'}, status=status.HTTP_400_BAD_REQUEST)
        files = testcase.files or []
        target = next((f for f in files if f.get('name') == file_name), None)
        if not target:
            return Response({'error': 'File not found'}, status=status.HTTP_404_NOT_FOUND)

        from ceres.engine.s3_utils import get_s3_client
        client, bucket = get_s3_client()
        if not client:
            return Response({'error': 'S3 not configured'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        s3_obj = client.get_object(Bucket=bucket, Key=target['s3_key'])
        from django.http import StreamingHttpResponse
        response = StreamingHttpResponse(
            s3_obj['Body'].iter_chunks(),
            content_type=target.get('content_type', 'application/octet-stream'),
        )
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        return response

    @action(detail=True, methods=['delete'], url_path='delete-file')
    def delete_file(self, request, pk=None):
        """Delete a file from this testcase by name."""
        testcase = self.get_object()
        file_name = request.data.get('name')
        if not file_name:
            return Response({'error': 'name is required'}, status=status.HTTP_400_BAD_REQUEST)

        files = testcase.files or []
        target = None
        for f in files:
            if f.get('name') == file_name:
                target = f
                break
        if not target:
            return Response({'error': 'File not found'}, status=status.HTTP_404_NOT_FOUND)

        from ceres.engine.s3_utils import delete_testdata
        try:
            delete_testdata(target['s3_key'])
        except Exception:
            pass  # S3 delete is best-effort

        files = [f for f in files if f.get('name') != file_name]
        testcase.files = files
        testcase.save(update_fields=['files'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class TestplanViewSet(viewsets.ModelViewSet):
    queryset = Testplan.objects.select_related('env', 'folder').all()
    serializer_class = TestplanSerializer
    filterset_fields = ['project', 'folder', 'env']
    search_fields = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return TestplanListSerializer
        if self.action == 'retrieve':
            return TestplanDetailSerializer
        return TestplanSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'retrieve':
            qs = qs.prefetch_related('plan_cases__testcase')
        return qs

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        testplan = self.get_object()
        env_id = request.data.get('env_id', testplan.env_id)
        env = Env.objects.filter(id=env_id).first() if env_id else testplan.env

        plan_cases = testplan.plan_cases.select_related('testcase').order_by('sort_order')
        testcases = [pc.to_executable() for pc in plan_cases]

        if not testcases:
            return Response({'error': 'No test cases in this plan'}, status=status.HTTP_400_BAD_REQUEST)

        task_id = f"task-{testplan.name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        execution = ExecutionRecord.objects.create(
            project=testplan.project,
            task_id=task_id,
            testplan=testplan,
            env=env,
            env_snapshot=env.variables if env else {},
            trigger_type='manual',
            status='running',
            total_cases=len(testcases),
        )

        from ceres.engine.executor import TestExecutor
        executor = TestExecutor(env=env)
        thread = threading.Thread(
            target=executor.execute_plan_async,
            args=(execution.id, testcases, testplan),
        )
        thread.start()

        return Response({
            'task_id': task_id,
            'execution_id': execution.id,
            'status': 'running',
        })

    @action(detail=True, methods=['get', 'post', 'put', 'delete'])
    def cases(self, request, pk=None):
        testplan = self.get_object()

        if request.method == 'GET':
            plan_cases = testplan.plan_cases.select_related('testcase').order_by('sort_order')
            serializer = TestplanCaseSerializer(plan_cases, many=True)
            return Response(serializer.data)

        if request.method == 'POST':
            case_ids = request.data.get('case_ids', [])
            max_order = testplan.plan_cases.count()
            testcases_by_id = {tc.id: tc for tc in Testcase.objects.filter(id__in=case_ids)}
            created = []
            for i, cid in enumerate(case_ids):
                tc = testcases_by_id.get(cid)
                if not tc:
                    continue
                pc, was_created = TestplanCase.objects.get_or_create(
                    testplan=testplan, testcase_id=cid,
                    defaults={
                        'sort_order': max_order + i,
                        'case_snapshot': TestplanCase.snapshot_from_testcase(tc),
                    }
                )
                if was_created:
                    created.append(pc)
            serializer = TestplanCaseSerializer(created, many=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == 'PUT':
            ordering = request.data.get('ordering', [])
            order_map = {item['id']: item['sort_order'] for item in ordering}
            plan_cases = list(TestplanCase.objects.filter(id__in=order_map.keys(), testplan=testplan))
            for pc in plan_cases:
                pc.sort_order = order_map[pc.id]
            TestplanCase.objects.bulk_update(plan_cases, ['sort_order'])
            return Response({'status': 'ok'})

        if request.method == 'DELETE':
            plan_case_ids = request.data.get('plan_case_ids', [])
            deleted, _ = TestplanCase.objects.filter(
                id__in=plan_case_ids, testplan=testplan
            ).delete()
            return Response({'deleted': deleted})

    @action(detail=True, methods=['get', 'post'])
    def sync(self, request, pk=None):
        """GET: return diff between snapshots and live testcases.
        POST: apply sync for selected plan_case_ids."""
        testplan = self.get_object()
        plan_cases = testplan.plan_cases.select_related('testcase').order_by('sort_order')

        if request.method == 'GET':
            diffs = []
            for pc in plan_cases:
                snap = pc.case_snapshot or {}
                live = TestplanCase.snapshot_from_testcase(pc.testcase)
                changed_fields = {}
                for field in TestplanCase.SNAPSHOT_FIELDS:
                    old_val = snap.get(field)
                    new_val = live.get(field)
                    if old_val != new_val:
                        changed_fields[field] = {'old': old_val, 'new': new_val}
                if changed_fields:
                    diffs.append({
                        'plan_case_id': pc.id,
                        'testcase_id': pc.testcase_id,
                        'case_name': pc.testcase.case_name,
                        'method': pc.testcase.method,
                        'changed_fields': changed_fields,
                    })
            return Response(diffs)

        if request.method == 'POST':
            plan_case_ids = request.data.get('plan_case_ids', [])
            updated = 0
            for pc in plan_cases:
                if pc.id in plan_case_ids:
                    pc.take_snapshot()
                    updated += 1
            return Response({'synced': updated})


class ScheduledTaskViewSet(viewsets.ModelViewSet):
    queryset = ScheduledTask.objects.select_related('testplan', 'env').all()
    serializer_class = ScheduledTaskSerializer
    filterset_fields = ['is_active', 'trigger_type', 'testplan__project']
    search_fields = ['name']

    def perform_create(self, serializer):
        task = serializer.save()
        from ceres.scheduler import add_job
        if task.is_active:
            add_job(task)

    def perform_update(self, serializer):
        task = serializer.save()
        from ceres.scheduler import add_job, remove_job
        if task.is_active:
            add_job(task)
        else:
            remove_job(task.id)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        from ceres.scheduler import remove_job
        remove_job(instance.id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        task = self.get_object()
        task.is_active = not task.is_active
        task.save(update_fields=['is_active', 'updated_at'])

        from ceres.scheduler import add_job, remove_job
        if task.is_active:
            add_job(task)
        else:
            remove_job(task.id)

        return Response({
            'id': task.id,
            'is_active': task.is_active,
        })


class ExecutionRecordViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ExecutionRecord.objects.select_related('testplan', 'env').all()
    serializer_class = ExecutionRecordSerializer
    filterset_fields = ['project', 'testplan', 'env', 'status', 'trigger_type']
    search_fields = ['task_id']
    ordering_fields = ['created_at', 'pass_rate', 'duration_ms']

    # 报告详情页(retrieve)及其子action允许匿名访问，列表页仍需登录
    ANONYMOUS_ACTIONS = {'retrieve', 'report', 'case_results_list', 'case_result_detail'}

    def get_permissions(self):
        if self.action in self.ANONYMOUS_ACTIONS:
            return [permissions.AllowAny()]
        return super().get_permissions()

    def get_authenticators(self):
        if getattr(self, 'action', None) in self.ANONYMOUS_ACTIONS:
            return []
        return super().get_authenticators()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ExecutionRecordDetailSerializer
        return ExecutionRecordSerializer


    @action(detail=True, methods=['get'], url_path='case-results')
    def case_results_list(self, request, pk=None):
        """Paginated list of case results (lightweight, no body fields)."""
        from ceres.models import ExecutionCaseResult
        from ceres.serializers import ExecutionCaseResultListSerializer
        qs = ExecutionCaseResult.objects.filter(execution_id=pk).order_by('id')
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ExecutionCaseResultListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ExecutionCaseResultListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='case-results/(?P<result_id>[0-9]+)')
    def case_result_detail(self, request, pk=None, result_id=None):
        """Get full detail of a single case result (includes response body)."""
        from ceres.models import ExecutionCaseResult
        cr = ExecutionCaseResult.objects.get(id=result_id, execution_id=pk)
        return Response(ExecutionCaseResultSerializer(cr).data)

    @action(detail=True, methods=['get'])
    def report(self, request, pk=None):
        execution = self.get_object()
        if execution.report_url:
            return Response({'report_url': execution.report_url})
        return Response({'error': 'No report available'}, status=status.HTTP_404_NOT_FOUND)


class StatsViewSet(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        from django.db.models import Count, Avg
        from django.utils import timezone
        from datetime import timedelta

        project_id = request.query_params.get('project')

        now = timezone.now()
        last_7_days = now - timedelta(days=7)
        last_30_days = now - timedelta(days=30)

        cases_qs = Testcase.objects.all()
        plans_qs = Testplan.objects.all()
        envs_qs = Env.objects.all()
        execs_qs = ExecutionRecord.objects.all()

        if project_id:
            cases_qs = cases_qs.filter(project_id=project_id)
            plans_qs = plans_qs.filter(project_id=project_id)
            envs_qs = envs_qs.filter(project_id=project_id)
            execs_qs = execs_qs.filter(project_id=project_id)

        total_cases = cases_qs.count()
        total_plans = plans_qs.count()
        total_envs = envs_qs.count()

        recent_executions = execs_qs.filter(created_at__gte=last_7_days)
        total_runs_7d = recent_executions.count()
        avg_pass_rate_7d = recent_executions.filter(
            status__in=['passed', 'failed']
        ).aggregate(avg=Avg('pass_rate'))['avg'] or 0

        daily_stats = []
        for i in range(7):
            day = (now - timedelta(days=6 - i)).date()
            day_execs = execs_qs.filter(
                created_at__date=day,
                status__in=['passed', 'failed'],
            )
            count = day_execs.count()
            avg_rate = day_execs.aggregate(avg=Avg('pass_rate'))['avg'] or 0
            daily_stats.append({
                'date': str(day),
                'executions': count,
                'avg_pass_rate': round(avg_rate, 2),
            })

        recent_failures = execs_qs.filter(
            status='failed', created_at__gte=last_30_days,
        ).order_by('-created_at')[:10]

        return Response({
            'summary': {
                'total_cases': total_cases,
                'total_plans': total_plans,
                'total_envs': total_envs,
                'total_runs_7d': total_runs_7d,
                'avg_pass_rate_7d': round(avg_pass_rate_7d, 2),
            },
            'daily_stats': daily_stats,
            'recent_failures': ExecutionRecordSerializer(recent_failures, many=True).data,
        })

    @action(detail=False, methods=['get'])
    def monitors(self, request):
        """Health snapshot for every active scheduled task.

        For each ScheduledTask, returns the most recent execution and a
        freshness verdict (ok / stale / dead) based on age vs. the trigger's
        expected cadence.
        """
        from django.utils import timezone

        project_id = request.query_params.get('project')

        tasks_qs = ScheduledTask.objects.filter(is_active=True).select_related('testplan', 'env')
        if project_id:
            tasks_qs = tasks_qs.filter(testplan__project_id=project_id)

        try:
            from croniter import croniter
        except ImportError:
            croniter = None

        now = timezone.now()
        results = []
        for task in tasks_qs:
            last_exec = ExecutionRecord.objects.filter(
                testplan_id=task.testplan_id,
                trigger_type='scheduled',
            ).order_by('-created_at').first()

            age_seconds = None
            if last_exec:
                age_seconds = int((now - last_exec.created_at).total_seconds())

            # Cron-only scheduler — interval triggers were removed. Estimate
            # expected cadence from the gap between the next two cron fires.
            cadence_label = task.cron_expression or 'cron'
            expected = 86400
            next_run_iso = None
            if croniter is not None and task.cron_expression:
                try:
                    itr = croniter(task.cron_expression, now)
                    next_dt = itr.get_next(datetime)
                    following_dt = itr.get_next(datetime)
                    expected = max(int((following_dt - next_dt).total_seconds()), 60)
                    next_run_iso = next_dt.isoformat()
                except Exception:
                    pass

            if age_seconds is None:
                health = 'dead'
            elif age_seconds > expected * 3:
                health = 'dead'
            elif age_seconds > expected * 1.5:
                health = 'stale'
            else:
                health = 'ok'

            results.append({
                'id': task.id,
                'name': task.name,
                'testplan_id': task.testplan_id,
                'testplan_name': task.testplan.name if task.testplan else '',
                'env_name': task.env.name if task.env else '',
                'trigger_type': task.trigger_type,
                'cadence': cadence_label,
                'is_active': task.is_active,
                'last_status': last_exec.status if last_exec else None,
                'last_pass_rate': round(last_exec.pass_rate, 2) if last_exec else None,
                'last_run_at': last_exec.created_at.isoformat() if last_exec else None,
                'last_execution_id': last_exec.id if last_exec else None,
                'age_seconds': age_seconds,
                'expected_seconds': expected,
                'next_run_at': next_run_iso,
                'health': health,
            })

        # Sort: dead/stale first, then by name.
        order = {'dead': 0, 'stale': 1, 'ok': 2}
        results.sort(key=lambda r: (order.get(r['health'], 9), r['name']))

        return Response({'monitors': results})

    @action(detail=False, methods=['get'], url_path='top-failures')
    def top_failures(self, request):
        """Top failing testcases over the last 7 days.

        Aggregates ExecutionCaseResult by testcase, ranks by failure count
        (ties broken by failure rate). Cases with <3 runs are excluded so
        one-off failures don't dominate the list.
        """
        from django.db.models import Count, Q
        from django.utils import timezone
        from datetime import timedelta

        project_id = request.query_params.get('project')
        limit = int(request.query_params.get('limit', 10))
        min_runs = int(request.query_params.get('min_runs', 3))

        since = timezone.now() - timedelta(days=7)
        results_qs = ExecutionCaseResult.objects.filter(
            created_at__gte=since,
            testcase__isnull=False,
        )
        if project_id:
            results_qs = results_qs.filter(execution__project_id=project_id)

        agg = (
            results_qs
            .values('testcase_id')
            .annotate(
                total_runs=Count('id'),
                failed_count=Count('id', filter=Q(status__in=['failed', 'error'])),
            )
            .filter(total_runs__gte=min_runs, failed_count__gt=0)
        )
        agg = sorted(
            agg,
            key=lambda r: (r['failed_count'], r['failed_count'] / r['total_runs']),
            reverse=True,
        )[:limit]

        # Resolve testcase names + last error message in a follow-up batch query.
        case_ids = [r['testcase_id'] for r in agg]
        case_map = {c.id: c for c in Testcase.objects.filter(id__in=case_ids)}
        last_errors = {}
        for cid in case_ids:
            last_failed = (
                results_qs
                .filter(testcase_id=cid, status__in=['failed', 'error'])
                .order_by('-created_at')
                .values('case_name', 'error_message', 'response_status', 'execution_id')
                .first()
            )
            if last_failed:
                last_errors[cid] = last_failed

        out = []
        for row in agg:
            cid = row['testcase_id']
            case = case_map.get(cid)
            err = last_errors.get(cid, {})
            err_msg = (err.get('error_message') or '').strip()
            if not err_msg and err.get('response_status'):
                err_msg = f"HTTP {err['response_status']}"
            out.append({
                'testcase_id': cid,
                'name': case.case_name if case else err.get('case_name') or f'#{cid}',
                'method': case.method if case else '',
                'url': case.url if case else '',
                'total_runs': row['total_runs'],
                'failed_count': row['failed_count'],
                'fail_rate': round(row['failed_count'] * 100.0 / row['total_runs'], 1),
                'last_error': err_msg[:200],
                'last_execution_id': err.get('execution_id'),
            })

        return Response({'top_failures': out})

    @action(detail=False, methods=['get'], url_path='plan-trends')
    def plan_trends(self, request):
        """Per-testplan 7-day pass-rate trends.

        Replaces the all-plans-merged trend chart so a daily monitor with 5
        cases isn't drowned by a 15-minute monitor with 100 cases.
        """
        from django.db.models import Avg, Count
        from django.utils import timezone
        from datetime import timedelta

        project_id = request.query_params.get('project')
        now = timezone.now()
        since = now - timedelta(days=7)

        execs_qs = ExecutionRecord.objects.filter(
            created_at__gte=since,
            status__in=['passed', 'failed'],
            testplan__isnull=False,
        )
        if project_id:
            execs_qs = execs_qs.filter(project_id=project_id)

        plan_ids = list(execs_qs.values_list('testplan_id', flat=True).distinct())
        plan_map = {p.id: p.name for p in Testplan.objects.filter(id__in=plan_ids)}

        # Single-pass aggregate: bucket by (plan_id, date)
        from collections import defaultdict
        buckets = defaultdict(lambda: {'count': 0, 'sum': 0.0})
        for row in execs_qs.values('testplan_id', 'created_at', 'pass_rate').iterator():
            day = row['created_at'].astimezone(now.tzinfo).date()
            key = (row['testplan_id'], day)
            buckets[key]['count'] += 1
            buckets[key]['sum'] += row['pass_rate']

        days = [(now - timedelta(days=6 - i)).date() for i in range(7)]

        plans = []
        for pid in plan_ids:
            daily = []
            total_runs = 0
            sum_rate = 0.0
            for d in days:
                b = buckets.get((pid, d), {'count': 0, 'sum': 0.0})
                avg = round(b['sum'] / b['count'], 2) if b['count'] else None
                daily.append({
                    'date': str(d),
                    'executions': b['count'],
                    'avg_pass_rate': avg,
                })
                total_runs += b['count']
                sum_rate += b['sum']
            if total_runs == 0:
                continue
            plans.append({
                'testplan_id': pid,
                'name': plan_map.get(pid, f'#{pid}'),
                'total_runs_7d': total_runs,
                'avg_pass_rate_7d': round(sum_rate / total_runs, 2),
                'daily': daily,
            })

        plans.sort(key=lambda p: (p['avg_pass_rate_7d'], -p['total_runs_7d']))

        return Response({'plans': plans})


def _human_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    search_fields = ['email', 'display_name', 'username']
    pagination_class = None


class WhitelistEmailViewSet(viewsets.ModelViewSet):
    queryset = WhitelistEmail.objects.all()
    serializer_class = WhitelistEmailSerializer
    search_fields = ['email', 'note']
    pagination_class = None

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='toggle-admin')
    def toggle_admin(self, request, pk=None):
        caller_email = _get_user_email(request)
        if not User.objects.filter(email=caller_email, is_admin=True).exists():
            return Response({'detail': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
        wl = self.get_object()
        if wl.email == caller_email:
            return Response({'detail': 'Cannot change your own admin status'}, status=status.HTTP_400_BAD_REQUEST)
        user_obj = User.objects.filter(email=wl.email).first()
        if not user_obj:
            return Response({'detail': 'User has not logged in yet'}, status=status.HTTP_400_BAD_REQUEST)
        user_obj.is_admin = not user_obj.is_admin
        user_obj.save(update_fields=['is_admin'])
        return Response({'is_admin': user_obj.is_admin})


class ProjectPermissionViewSet(viewsets.ModelViewSet):
    queryset = ProjectPermission.objects.select_related('user', 'project').all()
    serializer_class = ProjectPermissionSerializer
    filterset_fields = ['user', 'project']
    pagination_class = None

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    filterset_fields = ['user_email', 'action']
    search_fields = ['user_email', 'path']
    ordering_fields = ['created_at']
