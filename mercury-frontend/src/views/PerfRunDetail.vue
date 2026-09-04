<template>
  <div class="pm-page" v-if="run">
    <a-page-header @back="$router.back()" :title="t('perf.runTitle', { id: run.id, name: run.plan_name || '' })">
      <template #extra>
        <a-tag :color="statusColor">{{ t(`status.${run.status}`, run.status) }}</a-tag>
        <a-button
          v-if="canAbort"
          danger
          @click="onAbort"
          :loading="aborting"
        >
          {{ t('perf.abort') }}
        </a-button>
        <a-button @click="refresh">{{ t('common.refresh') }}</a-button>
      </template>

      <div class="run-meta">
        <div class="run-meta-cell"><label>{{ t('perf.targetRps') }}</label><span>{{ run.target_rate }}</span></div>
        <div class="run-meta-cell"><label>{{ t('common.duration') }}</label><span>{{ run.duration_secs }}s</span></div>
        <div class="run-meta-cell"><label>{{ t('perf.maxVus') }}</label><span>{{ run.max_vus }}</span></div>
        <div class="run-meta-cell"><label>{{ t('common.started') }}</label><span>{{ fmt(run.started_at) }}</span></div>
        <div class="run-meta-cell"><label>{{ t('common.finished') }}</label><span>{{ fmt(run.finished_at) }}</span></div>
        <div class="run-meta-cell"><label>{{ t('perf.lastHeartbeat') }}</label><span>{{ fmt(run.last_heartbeat_at) }}</span></div>
        <div class="run-meta-cell"><label>{{ t('perf.elapsed') }}</label><span>{{ elapsedStr }}</span></div>
      </div>
    </a-page-header>

    <a-alert
      v-if="run.error_message"
      type="error"
      :message="`${t('common.error')}: ${run.error_message}`"
      style="margin-bottom: 16px;"
    />

    <!-- ── Stats Cards ────────────────────────────── -->
    <a-row :gutter="16" style="margin-bottom: 16px;">
      <a-col :span="4">
        <a-card size="small">
          <a-statistic :title="t('perf.currentRps')" :value="summary.current_rps || 0" :precision="1" />
        </a-card>
      </a-col>
      <a-col :span="4">
        <a-card size="small">
          <a-statistic :title="t('perf.activeVus')" :value="summary.active_vus || 0" />
        </a-card>
      </a-col>
      <a-col :span="4">
        <a-card size="small">
          <a-statistic :title="t('perf.totalReqs')" :value="summary.total_reqs || 0" />
        </a-card>
      </a-col>
      <a-col :span="4">
        <a-card size="small">
          <a-statistic
            :title="t('perf.success')"
            :value="summary.success_count || 0"
            :value-style="{ color: '#52c41a' }"
          />
        </a-card>
      </a-col>
      <a-col :span="4">
        <a-card size="small">
          <a-statistic
            :title="t('common.errors')"
            :value="summary.error_count || 0"
            :value-style="(summary.error_count || 0) > 0 ? { color: '#ff4d4f' } : undefined"
          />
        </a-card>
      </a-col>
      <a-col :span="4">
        <a-card size="small">
          <a-statistic
            :title="t('perf.dropped')"
            :value="summary.dropped_count || 0"
            :value-style="(summary.dropped_count || 0) > 0 ? { color: '#faad14' } : undefined"
          />
        </a-card>
      </a-col>
    </a-row>

    <!-- ── Latency ────────────────────────────────── -->
    <a-card :title="t('perf.latency')" size="small" style="margin-bottom: 16px;">
      <a-row :gutter="16">
        <a-col :span="4">
          <a-statistic title="p50" :value="latency.p50 || 0" :precision="1" />
        </a-col>
        <a-col :span="4">
          <a-statistic title="p95" :value="latency.p95 || 0" :precision="1" />
        </a-col>
        <a-col :span="4">
          <a-statistic title="p99" :value="latency.p99 || 0" :precision="1" />
        </a-col>
        <a-col :span="4">
          <a-statistic :title="t('perf.average')" :value="latency.avg || 0" :precision="1" />
        </a-col>
        <a-col :span="4">
          <a-statistic :title="t('perf.minimum')" :value="latency.min || 0" :precision="1" />
        </a-col>
        <a-col :span="4">
          <a-statistic :title="t('perf.maximum')" :value="latency.max || 0" :precision="1" />
        </a-col>
      </a-row>
    </a-card>

    <!-- ── Live RPS chart ─────────────────────────── -->
    <a-card :title="t('perf.rpsOverTime')" size="small" style="margin-bottom: 16px;">
      <div ref="chartContainer" style="width: 100%; height: 280px;"></div>
      <div style="font-size: 12px; color: var(--text-3); margin-top: 4px;">
        {{ t('perf.chartHint', { seconds: POLL_MS / 1000 }) }}
      </div>
    </a-card>

    <!-- ── Per-Endpoint (case) ────────────────────── -->
    <a-card :title="t('perf.perEndpoint')" size="small" style="margin-bottom: 16px;">
      <template #extra>
        <a-input-search
          v-model:value="caseFilter"
          :placeholder="t('perf.filterCaseName')"
          style="width: 220px"
          size="small"
          allow-clear
        />
      </template>
      <a-table
        :data-source="caseRowsFiltered"
        :columns="caseColumns"
        row-key="name"
        size="small"
        :pagination="endpointPagination"
        @change="onEndpointTableChange"
      />
    </a-card>

    <!-- ── Per-Transaction (kept for plans with multiple chains) ─── -->
    <a-card :title="t('perf.perTransaction')" size="small" v-if="txRows.length > 1 || (txRows[0] && txRows[0].name !== '__setup__' && txRows[0].name !== 'regression')">
      <a-table
        :data-source="txRows"
        :columns="txColumns"
        row-key="name"
        size="small"
        :pagination="false"
      />
    </a-card>
  </div>
  <a-spin v-else size="large" style="margin: 200px auto; display: block;" />
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import { perfApi, type PerfRun } from '../api/perf.ts'

const POLL_MS = 2000

const route = useRoute()
const { t, locale } = useI18n()
const runId = computed(() => Number(route.params.id))

const run = ref<PerfRun | null>(null)
const aborting = ref(false)
let pollTimer: any = null
let chartInst: echarts.ECharts | null = null
const chartContainer = ref<HTMLDivElement | null>(null)

const summary = computed(() => run.value?.summary_json || {})
const latency = computed(() => (summary.value as any).latency_ms || {})

const canAbort = computed(
  () => run.value && ['pending', 'running'].includes(run.value.status)
)

const statusColor = computed(() => {
  const s = run.value?.status
  if (s === 'completed') return 'green'
  if (s === 'running' || s === 'pending') return 'blue'
  if (s === 'aborting' || s === 'aborted') return 'orange'
  if (s === 'failed' || s === 'setup_failed') return 'red'
  return 'default'
})

const elapsedStr = computed(() => {
  if (!run.value?.started_at) return '—'
  const start = dayjs(run.value.started_at)
  const end = run.value.finished_at ? dayjs(run.value.finished_at) : dayjs()
  const secs = end.diff(start, 'second')
  return `${secs}s`
})

function fmt(s: string | null | undefined) {
  return s ? dayjs(s).format('YYYY-MM-DD HH:mm:ss') : '—'
}

const txRows = computed(() => {
  const perTx = (summary.value as any).per_transaction || {}
  return Object.entries(perTx).map(([name, v]: [string, any]) => ({
    name,
    count: v.count,
    p95_ms: v.p95_ms,
    error_rate: v.error_rate,
  }))
})

// ─── Per-case (per-endpoint) breakdown ────────────────────────────
const caseFilter = ref('')
const endpointPagination = reactive({
  pageSize: 25,
  current: 1,
  showSizeChanger: true,
  pageSizeOptions: ['10', '25', '50', '100'],
})
function onEndpointTableChange(p: any) {
  endpointPagination.current = p.current
  endpointPagination.pageSize = p.pageSize
}

const caseRows = computed(() => {
  const perCase = (summary.value as any).per_case || {}
  return Object.entries(perCase).map(([name, v]: [string, any]) => ({
    name,
    transaction: v.transaction || '',
    count: v.count || 0,
    p50: v.p50 || 0,
    p95: v.p95 || 0,
    p99: v.p99 || 0,
    avg: v.avg || 0,
    error_rate: v.error_rate || 0,
  }))
    .sort((a, b) => b.p95 - a.p95)  // worst latency first
})

const caseRowsFiltered = computed(() => {
  const f = caseFilter.value.trim().toLowerCase()
  if (!f) return caseRows.value
  return caseRows.value.filter((r) => r.name.toLowerCase().includes(f))
})

const caseColumns = computed(() => [
  {
    title: t('perf.endpointCase'), dataIndex: 'name',
    customRender: ({ text }: any) => text || t('common.unnamed'),
  },
  { title: t('perf.transaction'), dataIndex: 'transaction', width: 140 },
  { title: t('common.count'), dataIndex: 'count', width: 90, sorter: (a: any, b: any) => a.count - b.count },
  { title: 'p50 ms', dataIndex: 'p50', width: 90, sorter: (a: any, b: any) => a.p50 - b.p50 },
  { title: 'p95 ms', dataIndex: 'p95', width: 90, sorter: (a: any, b: any) => a.p95 - b.p95, defaultSortOrder: 'descend' },
  { title: 'p99 ms', dataIndex: 'p99', width: 90, sorter: (a: any, b: any) => a.p99 - b.p99 },
  { title: 'avg ms', dataIndex: 'avg', width: 90, sorter: (a: any, b: any) => a.avg - b.avg },
  {
    title: t('perf.errorRate'), dataIndex: 'error_rate', width: 110,
    sorter: (a: any, b: any) => a.error_rate - b.error_rate,
    customRender: ({ text }: any) => (text * 100).toFixed(2) + '%',
  },
])

const txColumns = computed(() => [
  { title: t('perf.transaction'), dataIndex: 'name' },
  { title: t('common.count'), dataIndex: 'count', width: 100 },
  { title: 'p95 (ms)', dataIndex: 'p95_ms', width: 120 },
  {
    title: t('perf.errorRate'),
    dataIndex: 'error_rate',
    width: 120,
    customRender: ({ text }: any) => (text * 100).toFixed(2) + '%',
  },
])

// ── chart state (client-side time series) ────────────────────────────
const chartSamples = ref<{ t: number; rps: number; p95: number }[]>([])

function ensureChart() {
  if (chartInst || !chartContainer.value) return
  chartInst = echarts.init(chartContainer.value)
  chartInst.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['RPS', t('perf.p95Ms')], textStyle: { color: '#ccc' } },
    grid: { left: 50, right: 60, top: 30, bottom: 30 },
    xAxis: {
      type: 'time',
      axisLabel: { color: '#999' },
    },
    yAxis: [
      { type: 'value', name: 'RPS', position: 'left', axisLabel: { color: '#999' } },
      { type: 'value', name: t('perf.p95Ms'), position: 'right', axisLabel: { color: '#999' } },
    ],
    series: [
      { name: 'RPS', type: 'line', smooth: true, yAxisIndex: 0, data: [], itemStyle: { color: '#1890ff' } },
      { name: t('perf.p95Ms'), type: 'line', smooth: true, yAxisIndex: 1, data: [], itemStyle: { color: '#faad14' } },
    ],
  })
}

function pushSample() {
  const s: any = summary.value
  if (!s || !run.value) return
  chartSamples.value.push({
    t: Date.now(),
    rps: s.current_rps || 0,
    p95: (s.latency_ms || {}).p95 || 0,
  })
  // Cap history at 600 samples (~20min @ 2s)
  if (chartSamples.value.length > 600) chartSamples.value.shift()
  if (chartInst) {
    chartInst.setOption({
      series: [
        { data: chartSamples.value.map((x) => [x.t, x.rps]) },
        { data: chartSamples.value.map((x) => [x.t, x.p95]) },
      ],
    })
  }
}

async function refresh() {
  if (!runId.value) return
  try {
    run.value = await perfApi.getRun(runId.value)
    pushSample()
  } catch (e) {
    console.error('refresh failed', e)
  }
}

function schedulePoll() {
  if (pollTimer) return
  pollTimer = setInterval(() => {
    if (!run.value) return
    const stillRunning = ['pending', 'running', 'aborting'].includes(run.value.status)
    if (stillRunning) {
      refresh()
    } else {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }, POLL_MS)
}

async function onAbort() {
  if (!run.value) return
  aborting.value = true
  try {
    await perfApi.abortRun(run.value.id)
    message.success(t('perf.abortSignaled'))
    refresh()
  } catch (e: any) {
    message.error(e?.response?.data?.error || t('perf.abortFailed'))
  } finally {
    aborting.value = false
  }
}

watch(
  () => run.value?.status,
  (s) => {
    if (s && ['pending', 'running', 'aborting'].includes(s)) {
      schedulePoll()
    }
  }
)

watch(locale, () => {
  if (!chartInst) return
  chartInst.dispose()
  chartInst = null
  ensureChart()
  pushSample()
})

onMounted(async () => {
  await refresh()
  await nextTick()
  ensureChart()
  pushSample()
  schedulePoll()
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  if (chartInst) {
    chartInst.dispose()
    chartInst = null
  }
})
</script>

<style scoped>
.run-meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 8px 24px;
  padding: 8px 0 4px;
}
.run-meta-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.4;
}
.run-meta-cell label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.78);  /* was 0.55 — too dim against dark theme highlights */
  font-weight: normal;
  user-select: none;
}
.run-meta-cell span {
  font-size: 14px;
  color: #fff;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

/* Ant Design dims the sorted column with a lighter background in dark
 * theme which makes the cell text hard to read. Override to keep
 * cells uniform. (Use :deep because a-table renders shadow-y wrappers
 * outside scoped CSS.) */
:deep(.ant-table-cell.ant-table-column-sort) {
  background: transparent !important;
}
:deep(.ant-table-thead > tr > th.ant-table-column-sort) {
  background: rgba(255, 255, 255, 0.04) !important;
}
</style>
