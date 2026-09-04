<template>
  <div v-if="execution" class="pm-page">
    <a-page-header :title="execution.task_id" @back="$router.back()">
      <template #extra>
        <span :class="['pm-status', `pm-status-${execution.status}`]">
          <LoadingOutlined v-if="execution.status === 'running'" spin />
          <CheckCircleFilled v-else-if="execution.status === 'passed'" />
          <CloseCircleFilled v-else-if="execution.status === 'failed'" />
          <ExclamationCircleFilled v-else-if="execution.status === 'error'" />
          <ClockCircleFilled v-else />
          {{ execution.status }}
        </span>
      </template>
    </a-page-header>

    <a-descriptions bordered :column="descColumns" size="small" style="margin-bottom: 24px">
      <a-descriptions-item label="Plan">{{ execution.testplan_name || 'N/A' }}</a-descriptions-item>
      <a-descriptions-item label="Env">{{ execution.env_name || 'N/A' }}</a-descriptions-item>
      <a-descriptions-item label="Trigger">{{ execution.trigger_type }}</a-descriptions-item>
      <a-descriptions-item label="Pass Rate">
        <a-progress :percent="execution.pass_rate" :size="'small'" />
      </a-descriptions-item>
      <a-descriptions-item label="Duration">{{ execution.duration_ms }}ms</a-descriptions-item>
      <a-descriptions-item label="Cases">
        <span class="text-success">{{ execution.passed_cases }} passed</span> /
        <span class="text-error">{{ execution.failed_cases }} failed</span> /
        <template v-if="execution.skipped_cases">
          <span class="text-skipped">{{ execution.skipped_cases }} skipped</span> /
        </template>
        {{ execution.total_cases }} total
      </a-descriptions-item>
      <a-descriptions-item label="Created">{{ execution.created_at }}</a-descriptions-item>
    </a-descriptions>

    <div class="pm-filter-bar">
      <h3 style="margin: 0;">Case Results</h3>
      <a-radio-group v-model:value="statusFilter" size="small" @change="onFilterChange">
        <a-radio-button value="">All</a-radio-button>
        <a-radio-button value="passed">Passed</a-radio-button>
        <a-radio-button value="failed">Failed</a-radio-button>
        <a-radio-button value="error">Error</a-radio-button>
        <a-radio-button value="skipped">Skipped</a-radio-button>
      </a-radio-group>
    </div>

    <a-table
      :data-source="caseResults"
      :columns="columns"
      :loading="tableLoading"
      :pagination="pagination"
      :expandedRowKeys="expandedKeys"
      row-key="id"
      size="small"
      @change="onTableChange"
      @expand="onExpand"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.dataIndex === 'status'">
          <span :class="['pm-status', `pm-status-${record.status}`]">
            <CheckCircleFilled v-if="record.status === 'passed'" />
            <CloseCircleFilled v-else-if="record.status === 'failed'" />
            <MinusCircleFilled v-else-if="record.status === 'skipped'" />
            <ExclamationCircleFilled v-else />
            {{ record.status }}
          </span>
        </template>
        <template v-if="column.dataIndex === 'assertion_results'">
          <span v-if="record.assertion_results?.length">
            <span class="text-success">{{ record.assertion_results.filter((a: any) => a.passed).length }}</span>
            /
            <span>{{ record.assertion_results.length }}</span>
          </span>
          <span v-else class="text-muted">-</span>
        </template>
      </template>

      <template #expandedRowRender="{ record }">
        <a-spin v-if="!caseDetails[record.id]" size="small" style="display: block; padding: 20px; text-align: center;" />
        <div v-else class="pm-expand-content">
          <div class="pm-summary-bar">
            <span class="pm-summary-method" :class="`pm-method-${record.request_method?.toLowerCase()}`">{{ record.request_method }}</span>
            <span class="pm-summary-url">{{ record.request_url }}</span>
            <span :class="['pm-summary-http', record.response_status >= 400 ? 'text-error' : 'text-success']">{{ record.response_status }}</span>
            <span class="pm-summary-duration">{{ record.duration_ms }}ms</span>
            <span v-if="record.assertion_results?.length" class="pm-summary-assertions">
              <CheckCircleFilled v-if="record.assertion_results.every((a: any) => a.passed)" style="color: #49cc90" />
              <CloseCircleFilled v-else style="color: #f93e3e" />
              {{ record.assertion_results.filter((a: any) => a.passed).length }}/{{ record.assertion_results.length }}
            </span>
          </div>

          <div v-if="record.assertion_results?.length" style="margin-bottom: 12px">
            <h4>Assertions</h4>
            <div v-for="(a, i) in record.assertion_results" :key="i" class="pm-assertion-row">
              <CheckCircleFilled v-if="a.passed" style="color: #49cc90" />
              <CloseCircleFilled v-else style="color: #f93e3e" />
              <code>{{ a.field }} {{ a.operator }} {{ JSON.stringify(a.expected) }}</code>
              <span v-if="!a.passed" style="color: var(--text-3)">| Actual: {{ JSON.stringify(a.actual) }}</span>
            </div>
          </div>

          <div v-if="record.error_message" style="margin-bottom: 12px">
            <a-alert :message="record.error_message" type="error" />
          </div>

          <div v-if="caseDetails[record.id].stream_metrics" class="pm-stream-metrics">
            <span class="pm-stream-label">Streaming</span>
            <span class="pm-stream-item">First token <b>{{ caseDetails[record.id].stream_metrics!.first_token_ms }}ms</b></span>
            <span class="pm-stream-item">Last token <b>{{ caseDetails[record.id].stream_metrics!.last_token_ms }}ms</b></span>
            <span class="pm-stream-item"><b>{{ caseDetails[record.id].stream_metrics!.token_count }}</b> tokens</span>
            <span v-if="caseDetails[record.id].stream_metrics!.tokens_per_sec != null" class="pm-stream-item"><b>{{ caseDetails[record.id].stream_metrics!.tokens_per_sec }}</b> tok/s</span>
          </div>

          <div v-if="caseDetails[record.id].request_headers && Object.keys(caseDetails[record.id].request_headers).length" style="margin-bottom: 12px">
            <h4>Request Headers</h4>
            <div class="pm-headers-table">
              <div v-for="(val, key) in caseDetails[record.id].request_headers" :key="key" class="pm-header-row">
                <span class="pm-header-key">{{ key }}</span>
                <span class="pm-header-val">{{ val }}</span>
              </div>
            </div>
          </div>

          <div v-if="caseDetails[record.id].request_body" style="margin-bottom: 12px">
            <h4>Request Body</h4>
            <pre class="pm-code-block">{{ formatBody(caseDetails[record.id].request_body) }}</pre>
          </div>

          <div v-if="caseDetails[record.id].response_headers && Object.keys(caseDetails[record.id].response_headers).length" style="margin-bottom: 12px">
            <h4>Response Headers</h4>
            <div class="pm-headers-table">
              <div v-for="(val, key) in caseDetails[record.id].response_headers" :key="key" class="pm-header-row">
                <span class="pm-header-key">{{ key }}</span>
                <span class="pm-header-val">{{ val }}</span>
              </div>
            </div>
          </div>

          <h4>Response Body</h4>
          <pre class="pm-code-block">{{ formatBody(caseDetails[record.id].response_body) }}</pre>
        </div>
      </template>
    </a-table>
  </div>
  <a-spin v-else style="display: block; text-align: center; padding: 60px;" />
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  CheckCircleFilled, CloseCircleFilled, ExclamationCircleFilled,
  ClockCircleFilled, LoadingOutlined, MinusCircleFilled,
} from '@ant-design/icons-vue'
import { executionApi, type Execution, type CaseResult } from '../api/executions.ts'

const route = useRoute()
const execution = ref<Execution | null>(null)
const caseResults = ref<any[]>([])
const caseDetails = reactive<Record<number, CaseResult>>({})
const tableLoading = ref(false)
const statusFilter = ref('')
const expandedKeys = ref<number[]>([])
const pagination = reactive({ current: 1, pageSize: 20, total: 0, showSizeChanger: true, pageSizeOptions: ['20', '50', '100'] })

const screenWidth = ref(window.innerWidth)
const isMobile = computed(() => screenWidth.value <= 768)
const descColumns = computed(() => isMobile.value ? 1 : 3)

const columns = computed(() => {
  if (isMobile.value) {
    return [
      { title: 'Case', dataIndex: 'case_name', ellipsis: true },
      { title: 'Status', dataIndex: 'status', width: 90 },
      { title: 'ms', dataIndex: 'duration_ms', width: 65, customRender: ({ text }: any) => `${text}` },
    ]
  }
  return [
    { title: 'Case', dataIndex: 'case_name', ellipsis: true },
    { title: 'Method', dataIndex: 'request_method', width: 80 },
    { title: 'URL', dataIndex: 'request_url', ellipsis: true, width: 300 },
    { title: 'Status', dataIndex: 'status', width: 110 },
    { title: 'HTTP', dataIndex: 'response_status', width: 70 },
    { title: 'Assertions', dataIndex: 'assertion_results', width: 100 },
    { title: 'Duration', dataIndex: 'duration_ms', width: 90, customRender: ({ text }: any) => `${text}ms` },
  ]
})

function formatBody(body: string): string {
  if (!body) return ''
  try { return JSON.stringify(JSON.parse(body), null, 2) } catch { return body }
}

async function loadCaseResults() {
  if (!execution.value) return
  tableLoading.value = true
  try {
    const params: any = { page: pagination.current, page_size: pagination.pageSize }
    if (statusFilter.value) params.status = statusFilter.value
    const res = await executionApi.listCaseResults(execution.value.id, params)
    caseResults.value = res.results || res
    pagination.total = res.count || caseResults.value.length
  } finally {
    tableLoading.value = false
  }
}

function onTableChange(pag: any) {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  expandedKeys.value = []
  loadCaseResults()
}

function onFilterChange() {
  pagination.current = 1
  expandedKeys.value = []
  loadCaseResults()
}

async function onExpand(expanded: boolean, record: any) {
  if (expanded) {
    expandedKeys.value = [record.id]
    if (!caseDetails[record.id]) {
      const data = await executionApi.getCaseResult(execution.value!.id, record.id)
      caseDetails[record.id] = data
    }
  } else {
    expandedKeys.value = []
  }
}

onMounted(async () => {
  const id = Number(route.params.id)
  execution.value = await executionApi.get(id)
  await loadCaseResults()
})
</script>

<style scoped>
.pm-page { height: 100%; overflow: auto; }

.pm-filter-bar {
  margin-bottom: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.pm-expand-content {
  padding: 8px 0;
}
.pm-summary-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  margin-bottom: 12px;
  background: var(--bg-deep);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  font-family: 'SF Mono', Monaco, Menlo, Consolas, monospace;
  flex-wrap: wrap;
}
.pm-summary-method {
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  flex-shrink: 0;
}
.pm-method-get { color: #49cc90; background: rgba(73, 204, 144, 0.1); }
.pm-method-post { color: #61affe; background: rgba(97, 175, 254, 0.1); }
.pm-method-put { color: #fca130; background: rgba(252, 161, 48, 0.1); }
.pm-method-delete { color: #f93e3e; background: rgba(249, 62, 62, 0.1); }
.pm-method-patch { color: #50e3c2; background: rgba(80, 227, 194, 0.1); }
.pm-summary-url {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-2);
}
.pm-summary-http {
  font-weight: 700;
  flex-shrink: 0;
}
.pm-summary-duration {
  color: var(--text-3);
  flex-shrink: 0;
}
.pm-summary-assertions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.pm-assertion-row {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 4px 0;
  font-size: 13px;
}
.pm-assertion-row code {
  color: var(--text);
  font-size: 12px;
}
.pm-code-block {
  background: var(--bg-deep);
  color: var(--text);
  padding: 12px;
  border-radius: 4px;
  border: 1px solid var(--border);
  max-height: 300px;
  overflow: auto;
  font-size: 12px;
  font-family: 'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace;
  white-space: pre-wrap;
  word-break: break-all;
}
.pm-stream-metrics {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  background: var(--bg-deep);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 8px 12px;
  margin-bottom: 12px;
  font-size: 12px;
}
.pm-stream-label { color: var(--accent); font-weight: 600; letter-spacing: 0.4px; }
.pm-stream-item { color: var(--text-3); }
.pm-stream-item b { color: var(--text); font-weight: 600; margin: 0 2px; }

/* Request headers table */
.pm-headers-table { background: var(--bg-deep); border: 1px solid var(--border); border-radius: 4px; overflow: hidden; }
.pm-header-row { display: flex; border-bottom: 1px solid var(--border); font-size: 12px; font-family: 'SF Mono', Monaco, Menlo, Consolas, monospace; }
.pm-header-row:last-child { border-bottom: none; }
.pm-header-key { width: 200px; flex-shrink: 0; padding: 5px 10px; color: var(--accent); background: var(--bg-surface); font-weight: 600; }
.pm-header-val { flex: 1; padding: 5px 10px; color: var(--text); word-break: break-all; }

/* Expanded row background */
.pm-page :deep(.ant-table-expanded-row > td) { background: var(--bg-panel); }

/* Expand icon visibility */
.pm-page :deep(.ant-table-row-expand-icon) {
  background: var(--bg-surface) !important;
  border-color: var(--text-3) !important;
  color: var(--text) !important;
}
.pm-page :deep(.ant-table-row-expand-icon::before),
.pm-page :deep(.ant-table-row-expand-icon::after) {
  background: var(--text) !important;
}

/* Mobile responsive */
@media (max-width: 768px) {
  .pm-page { padding: 12px; }
  .pm-page :deep(.ant-descriptions) { margin-bottom: 12px !important; }
  .pm-page :deep(.ant-descriptions-bordered .ant-descriptions-item-label),
  .pm-page :deep(.ant-descriptions-bordered .ant-descriptions-item-content) { padding: 6px 10px !important; font-size: 12px; }
  .pm-page :deep(.ant-page-header) { padding: 8px 0 !important; }
  .pm-page :deep(.ant-page-header-heading-title) { font-size: 14px !important; word-break: break-all; }
  .pm-header-key { width: 120px; font-size: 11px; }
  .pm-header-val { font-size: 11px; }
  .pm-page :deep(.ant-table) { font-size: 12px; }
}

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
.pm-status-skipped {
  background: rgba(136, 136, 160, 0.15);
  color: var(--text-3);
}
.pm-status-pending {
  background: rgba(136, 136, 160, 0.15);
  color: var(--text-3);
}
.text-skipped {
  color: var(--text-3);
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
</style>
