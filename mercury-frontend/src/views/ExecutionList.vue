<template>
  <div class="pm-page">
    <div style="margin-bottom: 16px; display: flex; gap: 12px;">
      <a-input-search v-model:value="filters.search" :placeholder="t('executions.searchTaskId')" style="width: 300px" @search="onFilterChange" />
      <a-select v-model:value="filters.status" :placeholder="t('common.status')" allow-clear style="width: 120px" @change="onFilterChange">
        <a-select-option value="passed">{{ t('status.passed') }}</a-select-option>
        <a-select-option value="failed">{{ t('status.failed') }}</a-select-option>
        <a-select-option value="running">{{ t('status.running') }}</a-select-option>
        <a-select-option value="interrupted">{{ t('status.interrupted') }}</a-select-option>
        <a-select-option value="error">{{ t('status.error') }}</a-select-option>
      </a-select>
      <a-select v-model:value="filters.trigger_type" :placeholder="t('common.trigger')" allow-clear style="width: 120px" @change="onFilterChange">
        <a-select-option value="manual">{{ t('status.manual') }}</a-select-option>
        <a-select-option value="scheduled">{{ t('status.scheduled') }}</a-select-option>
      </a-select>
    </div>

    <a-table :data-source="executions" :columns="columns" :loading="loading" row-key="id" :pagination="pagination" :scroll="{ y: 'calc(100vh - 220px)' }" @change="onTableChange">
      <template #bodyCell="{ column, record }">
        <template v-if="column.dataIndex === 'task_id'">
          <router-link :to="`/executions/${record.id}`">{{ record.task_id }}</router-link>
        </template>
        <template v-if="column.dataIndex === 'status'">
          <span :class="['pm-status', `pm-status-${record.status}`]">
            <LoadingOutlined v-if="record.status === 'running'" spin />
            <CheckCircleFilled v-else-if="record.status === 'passed'" />
            <CloseCircleFilled v-else-if="record.status === 'failed'" />
            <ExclamationCircleFilled v-else-if="record.status === 'error'" />
            <MinusCircleFilled v-else-if="record.status === 'interrupted'" />
            <ClockCircleFilled v-else />
            {{ t(`status.${record.status}`, record.status) }}
          </span>
        </template>
        <template v-if="column.dataIndex === 'pass_rate'">
          <a-progress :percent="record.pass_rate" :size="'small'" :status="record.pass_rate === 100 ? 'success' : 'exception'" />
        </template>
        <template v-if="column.dataIndex === 'counts'">
          <span style="color: #52c41a">{{ record.passed_cases }}</span> /
          <span style="color: #ff4d4f">{{ record.failed_cases }}</span> /
          <span v-if="record.skipped_cases" style="color: #faad14">{{ t('executions.skippedCount', { count: record.skipped_cases }) }}</span>
          <span v-if="record.skipped_cases"> / </span>
          <span>{{ record.total_cases }}</span>
        </template>
        <template v-if="column.dataIndex === 'trigger_type'">
          {{ t(`status.${record.trigger_type}`, record.trigger_type) }}
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  CheckCircleFilled, CloseCircleFilled, ExclamationCircleFilled,
  ClockCircleFilled, LoadingOutlined, MinusCircleFilled,
} from '@ant-design/icons-vue'
import { executionApi, type Execution } from '../api/executions.ts'
import { useProjectStore } from '../stores/project.ts'

const projectStore = useProjectStore()
const { t } = useI18n()

const executions = ref<Execution[]>([])
const loading = ref(false)
const filters = reactive({ search: '', status: undefined as string | undefined, trigger_type: undefined as string | undefined })
const pagination = reactive({ current: 1, pageSize: 20, total: 0, showTotal: (total: number) => t('executions.executionsCount', { count: total }), showSizeChanger: true, pageSizeOptions: ['20', '50', '100'] })

const isMobile = window.innerWidth <= 768
const columns = computed(() => {
  if (isMobile) {
    return [
      { title: t('executions.taskId'), dataIndex: 'task_id', ellipsis: true },
      { title: t('common.status'), dataIndex: 'status', width: 80 },
      { title: t('executions.counts'), dataIndex: 'counts', width: 90 },
    ]
  }
  return [
    { title: t('executions.taskId'), dataIndex: 'task_id' },
    { title: t('executions.plan'), dataIndex: 'testplan_name', width: 150 },
    { title: t('executions.env'), dataIndex: 'env_name', width: 100 },
    { title: t('common.status'), dataIndex: 'status', width: 90 },
    { title: t('executions.passRate'), dataIndex: 'pass_rate', width: 150 },
    { title: t('executions.counts'), dataIndex: 'counts', width: 100 },
    { title: t('executions.duration'), dataIndex: 'duration_ms', width: 90, customRender: ({ text }: any) => `${text}ms` },
    { title: t('common.trigger'), dataIndex: 'trigger_type', width: 90 },
    { title: t('common.time'), dataIndex: 'created_at', width: 180 },
  ]
})

async function loadExecutions() {
  loading.value = true
  try {
    const params: any = { page: pagination.current, page_size: pagination.pageSize, project: projectStore.currentProjectId }
    if (filters.search) params.search = filters.search
    if (filters.status) params.status = filters.status
    if (filters.trigger_type) params.trigger_type = filters.trigger_type
    const res = await executionApi.list(params)
    executions.value = res.results || res
    pagination.total = res.count || executions.value.length
  } finally {
    loading.value = false
  }
}

function onFilterChange() {
  pagination.current = 1
  loadExecutions()
}

function onTableChange(pag: any) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadExecutions()
}

onMounted(loadExecutions)
</script>

<style scoped>
/* Status badges */
.pm-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.pm-status-passed {
  background: rgba(92, 216, 145, 0.15);
  color: var(--success);
}
.pm-status-failed {
  background: rgba(255, 107, 107, 0.15);
  color: var(--error);
}
.pm-status-running {
  background: rgba(110, 170, 255, 0.15);
  color: var(--link);
  animation: pulse 1.5s ease-in-out infinite;
}
.pm-status-error {
  background: rgba(252, 161, 48, 0.15);
  color: var(--warning);
}
.pm-status-interrupted {
  background: rgba(136, 136, 160, 0.15);
  color: var(--text-3);
}
.pm-status-pending {
  background: rgba(136, 136, 160, 0.15);
  color: var(--text-3);
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

@media (max-width: 768px) {
  .pm-page > div:first-child { flex-wrap: wrap !important; gap: 8px !important; }
}
</style>
