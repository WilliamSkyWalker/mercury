<template>
  <div class="pm-page">
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between;">
      <a-input-search v-model:value="searchText" placeholder="Search schedules" style="width: 300px" @search="loadSchedules" />
      <a-button type="primary" @click="openModal()">Create Schedule</a-button>
    </div>

    <a-table :data-source="schedules" :columns="columns" :loading="loading" row-key="id">
      <template #bodyCell="{ column, record }">
        <template v-if="column.dataIndex === 'is_active'">
          <a-switch :checked="record.is_active" @change="onToggle(record)" />
        </template>
        <template v-if="column.dataIndex === 'trigger_info'">
          <span>{{ record.cron_expression }}</span>
        </template>
        <template v-if="column.dataIndex === 'action'">
          <a-space>
            <a @click="openModal(record)">Edit</a>
            <a-popconfirm title="Delete?" @confirm="onDelete(record.id)">
              <a style="color: #ff4d4f">Delete</a>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal v-model:open="modal.visible" :title="modal.editId ? 'Edit Schedule' : 'Create Schedule'" :confirm-loading="saveLoading" @ok="onSave" :width="modalWidth">
      <a-form layout="vertical">
        <a-form-item label="Name">
          <a-input v-model:value="modal.name" placeholder="Schedule name" />
        </a-form-item>
        <a-form-item label="Test Plan">
          <a-select v-model:value="modal.testplanId" placeholder="Select plan" style="width: 100%" show-search :filter-option="(input: string, option: any) => option.label?.toLowerCase().includes(input.toLowerCase())" :options="plans.map(p => ({ value: p.id, label: p.name }))" />
        </a-form-item>
        <a-form-item label="Environment">
          <a-select v-model:value="modal.envId" placeholder="Select env (optional)" allow-clear style="width: 100%" :options="envs.map((e: any) => ({ value: e.id, label: e.name }))" />
        </a-form-item>
        <a-form-item label="Cron Expression">
          <a-input v-model:value="modal.cronExpression" placeholder="*/15 * * * *" />
          <div style="color: var(--text-3); font-size: 12px; margin-top: 4px;">Format: minute hour day month weekday. e.g. <code style="color: var(--accent);">0 9 * * *</code> = daily 9AM, <code style="color: var(--accent);">*/15 * * * *</code> = every 15 min. Linux crontab runs the schedules.</div>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import { scheduleApi, type ScheduledTask } from '../api/schedules.ts'
import { testplanApi } from '../api/testplans.ts'
import { useEnvStore } from '../stores/env.ts'
import { useProjectStore } from '../stores/project.ts'
import { useLoading } from '../composables/useLoading.ts'

const projectStore = useProjectStore()

const envStore = useEnvStore()
const envs = computed(() => envStore.envs)

const modalWidth = computed(() => window.innerWidth <= 768 ? '95%' : '600px')
const schedules = ref<ScheduledTask[]>([])
const plans = ref<any[]>([])
const loading = ref(false)
const searchText = ref('')

const columns = [
  { title: 'Name', dataIndex: 'name' },
  { title: 'Plan', dataIndex: 'testplan_name', width: 150 },
  { title: 'Env', dataIndex: 'env_name', width: 100 },
  { title: 'Active', dataIndex: 'is_active', width: 80 },
  { title: 'Trigger', dataIndex: 'trigger_info', width: 150 },
  { title: 'Updated', dataIndex: 'updated_at', width: 180 },
  { title: 'Action', dataIndex: 'action', width: 150 },
]

const modal = reactive({
  visible: false, editId: null as number | null,
  name: '', testplanId: null as number | null, envId: null as number | null,
  cronExpression: '',
})

async function loadSchedules() {
  loading.value = true
  try {
    const res = await scheduleApi.list({ search: searchText.value, testplan__project: projectStore.currentProjectId })
    schedules.value = res.results || res
  } finally {
    loading.value = false
  }
}

async function loadPlans() {
  const res = await testplanApi.list({ page_size: 200, project: projectStore.currentProjectId })
  plans.value = res.results || res
}

async function openModal(record?: ScheduledTask) {
  await Promise.all([loadPlans(), envStore.fetchEnvs()])
  if (record) {
    modal.editId = record.id; modal.name = record.name; modal.testplanId = record.testplan
    modal.envId = record.env; modal.cronExpression = record.cron_expression
  } else {
    modal.editId = null; modal.name = ''; modal.testplanId = null; modal.envId = null
    modal.cronExpression = ''
  }
  modal.visible = true
}

const [onSave, saveLoading] = useLoading(async () => {
  if (!modal.name || !modal.testplanId) { message.warning('Name and plan are required'); return }
  if (!modal.cronExpression || modal.cronExpression.trim().split(/\s+/).length !== 5) {
    message.warning('Cron expression must have 5 fields (m h dom mon dow)')
    return
  }
  const data: any = {
    name: modal.name, testplan: modal.testplanId, env: modal.envId,
    trigger_type: 'cron',
    cron_expression: modal.cronExpression.trim(),
  }
  if (modal.editId) {
    await scheduleApi.update(modal.editId, data)
    message.success('Updated')
  } else {
    await scheduleApi.create(data)
    message.success('Created')
  }
  modal.visible = false
  loadSchedules()
})

const [onToggle, toggleLoading] = useLoading(async (record: ScheduledTask) => {
  await scheduleApi.toggle(record.id)
  message.success(record.is_active ? 'Deactivated' : 'Activated')
  loadSchedules()
})

const [onDelete, deleteLoading] = useLoading(async (id: number) => {
  await scheduleApi.delete(id)
  message.success('Deleted')
  loadSchedules()
})

onMounted(() => { loadSchedules(); loadPlans(); envStore.fetchEnvs() })
</script>

<style scoped>
@media (max-width: 768px) {
  .pm-page > div:first-child { flex-wrap: wrap !important; gap: 8px !important; }
  .pm-page > div:first-child .ant-input-search { width: 100% !important; }
}
</style>
