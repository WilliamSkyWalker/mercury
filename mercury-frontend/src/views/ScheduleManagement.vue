<template>
  <div class="pm-page">
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between;">
      <a-input-search v-model:value="searchText" :placeholder="t('schedules.search')" style="width: 300px" @search="loadSchedules" />
      <a-button type="primary" @click="openModal()">{{ t('schedules.create') }}</a-button>
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
            <a @click="openModal(record)">{{ t('common.edit') }}</a>
            <a-popconfirm :title="t('schedules.deleteConfirm')" @confirm="onDelete(record.id)">
              <a style="color: #ff4d4f">{{ t('common.delete') }}</a>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal v-model:open="modal.visible" :title="modal.editId ? t('schedules.edit') : t('schedules.create')" :confirm-loading="saveLoading" @ok="onSave" :width="modalWidth">
      <a-form layout="vertical">
        <a-form-item :label="t('common.name')">
          <a-input v-model:value="modal.name" :placeholder="t('schedules.scheduleName')" />
        </a-form-item>
        <a-form-item :label="t('schedules.testPlan')">
          <a-select v-model:value="modal.testplanId" :placeholder="t('schedules.selectPlan')" style="width: 100%" show-search :filter-option="(input: string, option: any) => option.label?.toLowerCase().includes(input.toLowerCase())" :options="plans.map(p => ({ value: p.id, label: p.name }))" />
        </a-form-item>
        <a-form-item :label="t('common.environment')">
          <a-select v-model:value="modal.envId" :placeholder="t('schedules.selectOptionalEnv')" allow-clear style="width: 100%" :options="envs.map((e: any) => ({ value: e.id, label: e.name }))" />
        </a-form-item>
        <a-form-item :label="t('schedules.cronExpression')">
          <a-input v-model:value="modal.cronExpression" placeholder="*/15 * * * *" />
          <div style="color: var(--text-3); font-size: 12px; margin-top: 4px;">{{ t('schedules.cronHelp') }}</div>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { scheduleApi, type ScheduledTask } from '../api/schedules.ts'
import { testplanApi } from '../api/testplans.ts'
import { useEnvStore } from '../stores/env.ts'
import { useProjectStore } from '../stores/project.ts'
import { useLoading } from '../composables/useLoading.ts'

const projectStore = useProjectStore()
const { t } = useI18n()

const envStore = useEnvStore()
const envs = computed(() => envStore.envs)

const modalWidth = computed(() => window.innerWidth <= 768 ? '95%' : '600px')
const schedules = ref<ScheduledTask[]>([])
const plans = ref<any[]>([])
const loading = ref(false)
const searchText = ref('')

const columns = computed(() => [
  { title: t('common.name'), dataIndex: 'name' },
  { title: t('executions.plan'), dataIndex: 'testplan_name', width: 150 },
  { title: t('executions.env'), dataIndex: 'env_name', width: 100 },
  { title: t('common.active'), dataIndex: 'is_active', width: 80 },
  { title: t('common.trigger'), dataIndex: 'trigger_info', width: 150 },
  { title: t('common.updated'), dataIndex: 'updated_at', width: 180 },
  { title: t('common.action'), dataIndex: 'action', width: 150 },
])

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
  if (!modal.name || !modal.testplanId) { message.warning(t('schedules.required')); return }
  if (!modal.cronExpression || modal.cronExpression.trim().split(/\s+/).length !== 5) {
    message.warning(t('schedules.invalidCron'))
    return
  }
  const data: any = {
    name: modal.name, testplan: modal.testplanId, env: modal.envId,
    trigger_type: 'cron',
    cron_expression: modal.cronExpression.trim(),
  }
  if (modal.editId) {
    await scheduleApi.update(modal.editId, data)
    message.success(t('common.updatedMessage'))
  } else {
    await scheduleApi.create(data)
    message.success(t('common.createdMessage'))
  }
  modal.visible = false
  loadSchedules()
})

const [onToggle, toggleLoading] = useLoading(async (record: ScheduledTask) => {
  await scheduleApi.toggle(record.id)
  message.success(record.is_active ? t('schedules.deactivated') : t('schedules.activated'))
  loadSchedules()
})

const [onDelete, deleteLoading] = useLoading(async (id: number) => {
  await scheduleApi.delete(id)
  message.success(t('common.deleted'))
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
