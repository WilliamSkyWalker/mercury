<template>
  <div class="pm-page">
    <a-page-header @back="$router.back()" :title="`Run history: ${planName || 'Plan #' + planId}`">
      <template #extra>
        <a-button @click="refresh">Refresh</a-button>
      </template>
    </a-page-header>

    <a-table
      :data-source="runs"
      :columns="columns"
      :loading="loading"
      row-key="id"
      :pagination="historyPagination"
      @change="onTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.dataIndex === 'id'">
          <a @click="goTo(record.id)">#{{ record.id }}</a>
        </template>
        <template v-if="column.dataIndex === 'status'">
          <a-tag :color="statusColor(record.status)">{{ record.status }}</a-tag>
        </template>
        <template v-if="column.dataIndex === 'started_at'">
          {{ record.started_at ? dayjs(record.started_at).format('YYYY-MM-DD HH:mm:ss') : '—' }}
        </template>
        <template v-if="column.dataIndex === 'error_rate'">
          {{ ((record.error_rate || 0) * 100).toFixed(2) }}%
        </template>
        <template v-if="column.dataIndex === 'action'">
          <a-button size="small" @click="goTo(record.id)">Detail</a-button>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { perfApi, type PerfRun } from '../api/perf.ts'

const route = useRoute()
const router = useRouter()
const planId = computed(() => Number(route.params.id))

const runs = ref<PerfRun[]>([])
const loading = ref(false)
const planName = ref('')
const historyPagination = reactive({ pageSize: 20, current: 1, showSizeChanger: true })

function onTableChange(p: any) {
  historyPagination.current = p.current
  historyPagination.pageSize = p.pageSize
}

const columns = [
  { title: 'Run', dataIndex: 'id', width: 80 },
  { title: 'Status', dataIndex: 'status', width: 110 },
  { title: 'Target RPS', dataIndex: 'target_rate', width: 100 },
  { title: 'Duration', dataIndex: 'duration_secs', width: 90, customRender: ({ text }: any) => `${text}s` },
  { title: 'Total Reqs', dataIndex: 'total_reqs', width: 100 },
  { title: 'p95 ms', dataIndex: 'p95_ms', width: 100 },
  { title: 'Error Rate', dataIndex: 'error_rate', width: 110 },
  { title: 'Started', dataIndex: 'started_at', width: 180 },
  { title: 'Action', dataIndex: 'action', width: 100 },
]

function statusColor(s: string) {
  if (s === 'completed') return 'green'
  if (s === 'running' || s === 'pending') return 'blue'
  if (s === 'aborting' || s === 'aborted') return 'orange'
  return 'red'
}

async function refresh() {
  loading.value = true
  try {
    const res: any = await perfApi.listRuns(planId.value, 100)
    runs.value = res
    if (runs.value.length > 0 && runs.value[0].plan_name) {
      planName.value = runs.value[0].plan_name as string
    }
  } finally {
    loading.value = false
  }
}

function goTo(runId: number) {
  router.push({ name: 'PerfRunDetail', params: { id: String(runId) } })
}

onMounted(refresh)
</script>
