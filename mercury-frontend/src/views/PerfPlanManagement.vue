<template>
  <div class="pm-page">
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
      <a-input-search
        v-model:value="searchText"
        :placeholder="t('perf.searchPlans')"
        style="width: 300px"
        @search="loadPlans"
      />
      <a-button type="primary" @click="openDrawer()">{{ t('perf.createPlan') }}</a-button>
    </div>

    <a-table
      :data-source="plans"
      :columns="columns"
      :loading="loading"
      row-key="id"
      :pagination="planTablePagination"
      @change="onPlanTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.dataIndex === 'name'">
          <a @click="openDrawer(record)">{{ record.name }}</a>
        </template>
        <template v-if="column.dataIndex === 'rate'">
          {{ record.target_rate }} RPS
        </template>
        <template v-if="column.dataIndex === 'duration'">
          {{ record.duration_secs }}s
        </template>
        <template v-if="column.dataIndex === 'action'">
          <a-space>
            <a-button type="primary" size="small" @click="openRunDialog(record)">{{ t('common.run') }}</a-button>
            <a @click="goToHistory(record)">{{ t('common.history') }}</a>
            <a-popconfirm :title="t('perf.deletePlanConfirm')" @confirm="onDelete(record.id)">
              <a style="color: #ff4d4f">{{ t('common.delete') }}</a>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- ───── Create/Edit Drawer ───── -->
    <a-drawer
      v-model:open="drawer.visible"
      :title="drawer.editId ? t('perf.editPlan', { name: drawer.name }) : t('perf.createPlan')"
      :width="drawerWidth"
      :bodyStyle="{ padding: '16px 24px' }"
    >
      <template #extra>
        <a-button type="primary" :loading="saveLoading" @click="onSave">{{ t('common.save') }}</a-button>
      </template>

      <a-form layout="vertical">
        <a-row :gutter="16">
          <a-col :span="14">
            <a-form-item :label="t('common.name')" required>
              <a-input v-model:value="drawer.name" :placeholder="t('plans.planName')" />
            </a-form-item>
          </a-col>
          <a-col :span="10">
            <a-form-item :label="t('common.environment')">
              <a-select
                v-model:value="drawer.envId"
                allow-clear
                :placeholder="t('plans.selectEnv')"
                style="width: 100%"
              >
                <a-select-option v-for="e in envs" :key="e.id" :value="e.id">
                  {{ e.name }}
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item :label="t('common.description')">
          <a-input v-model:value="drawer.description" :placeholder="t('common.optional')" />
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item :label="t('perf.targetRps')">
              <a-input-number v-model:value="drawer.targetRate" :min="1" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item :label="`${t('common.duration')} (s)`">
              <a-input-number v-model:value="drawer.durationSecs" :min="1" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item :label="t('perf.maxVus')">
              <a-input-number v-model:value="drawer.maxVus" :min="1" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item :label="t('perf.notifyWebhook')">
          <a-input v-model:value="drawer.notifyWebhook" :placeholder="t('common.optional')" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item :label="t('perf.notifyCompletion')">
              <a-switch v-model:checked="drawer.notifyOnCompletion" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('perf.notifyFailure')">
              <a-switch v-model:checked="drawer.notifyOnFailure" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>

      <!-- Transactions metadata + cases (only after plan exists) -->
      <template v-if="drawer.editId">
        <a-divider />

        <!-- Account pool -->
        <div style="margin-bottom: 16px;">
          <h3 style="margin: 0 0 8px;">{{ t('perf.accountPool') }}</h3>
          <div style="font-size: 12px; color: var(--text-3); margin-bottom: 8px;">
            {{ t('perf.accountPoolHelp') }}
          </div>
          <a-space>
            <a-upload
              :show-upload-list="false"
              :before-upload="onUploadAccountPool"
              :accept="'.csv,.json,.tsv'"
            >
              <a-button>
                <UploadOutlined />
                {{ drawer.accountFileKey ? t('perf.replaceFile') : t('common.uploadFile') }}
              </a-button>
            </a-upload>
            <span v-if="drawer.accountFileKey" style="font-size: 12px; color: var(--text-3);">
              {{ shortenKey(drawer.accountFileKey) }}
            </span>
          </a-space>
        </div>

        <a-divider />

        <!-- Setup cases -->
        <div style="margin-bottom: 16px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <h3 style="margin: 0;">{{ t('perf.setupCases', { count: setupCases.length }) }}</h3>
            <a-space>
              <a-button size="small" @click="syncSnapshots">
                <SyncOutlined /> {{ t('common.sync') }}
              </a-button>
              <a-button size="small" @click="openAddCases('setup')">
                <PlusOutlined /> {{ t('common.add') }}
              </a-button>
            </a-space>
          </div>
          <div style="font-size: 12px; color: var(--text-3); margin-bottom: 8px;">
            {{ t('perf.setupHelp') }}
          </div>
          <a-table
            :data-source="setupCases"
            :columns="caseColumns"
            row-key="id"
            size="small"
            :pagination="false"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.dataIndex === 'data'">
                <a-space>
                  <a-upload
                    :show-upload-list="false"
                    :before-upload="(file: any) => onUploadCaseData(record.id, file)"
                    :accept="'.csv,.json,.tsv'"
                  >
                    <a-tag v-if="record.data_file_s3_key" color="blue" style="cursor: pointer">
                      {{ record.data_mode }}
                    </a-tag>
                    <a v-else style="font-size: 12px;">{{ t('perf.bindFile') }}</a>
                  </a-upload>
                </a-space>
              </template>
              <template v-if="column.dataIndex === 'action'">
                <a style="color: #ff4d4f" @click="removeCase(record.id)">{{ t('common.remove') }}</a>
              </template>
            </template>
          </a-table>
        </div>

        <a-divider />

        <!-- Transactions -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <h3 style="margin: 0;">{{ t('perf.transactionsCount', { count: drawer.transactions.length }) }}</h3>
          <a-button size="small" @click="addTransaction">
            <PlusOutlined /> {{ t('perf.addTransaction') }}
          </a-button>
        </div>
        <div style="font-size: 12px; color: var(--text-3); margin-bottom: 12px;">
          {{ t('perf.transactionHelp') }}
        </div>

        <div v-for="(tx, idx) in drawer.transactions" :key="tx.name" class="tx-block">
          <div class="tx-header">
            <a-input
              v-model:value="tx.name"
              size="small"
              style="width: 180px"
              :placeholder="t('perf.transactionName')"
              @change="markTxRename(idx, tx.name)"
            />
            <span style="font-size: 12px; color: var(--text-3);">{{ t('perf.weight') }}</span>
            <a-input-number v-model:value="tx.weight" :min="1" size="small" style="width: 80px" />
            <a-button size="small" @click="openAddCases('transaction', tx.name)">
              <PlusOutlined /> {{ t('perf.addCase') }}
            </a-button>
            <a-popconfirm :title="t('perf.removeTransactionConfirm')" @confirm="removeTransaction(idx)">
              <a style="color: #ff4d4f; font-size: 12px;">{{ t('common.remove') }}</a>
            </a-popconfirm>
          </div>
          <a-table
            :data-source="transactionCases(tx.name)"
            :columns="caseColumns"
            row-key="id"
            size="small"
            :pagination="false"
            style="margin-top: 8px;"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.dataIndex === 'data'">
                <a-upload
                  :show-upload-list="false"
                  :before-upload="(file: any) => onUploadCaseData(record.id, file)"
                  :accept="'.csv,.json,.tsv'"
                >
                  <a-tag v-if="record.data_file_s3_key" color="blue" style="cursor: pointer">
                    {{ record.data_mode }}
                  </a-tag>
                  <a v-else style="font-size: 12px;">{{ t('perf.bindFile') }}</a>
                </a-upload>
              </template>
              <template v-if="column.dataIndex === 'action'">
                <a style="color: #ff4d4f" @click="removeCase(record.id)">{{ t('common.remove') }}</a>
              </template>
            </template>
          </a-table>
        </div>
      </template>
    </a-drawer>

    <!-- ───── Add cases modal ───── -->
    <a-modal
      v-model:open="addCasesModal.visible"
      :title="t('perf.addCasesTitle', {
        role: addCasesModal.role === 'setup' ? t('perf.setupRole') : t('perf.transactionRole'),
        target: addCasesModal.transactionName ? t('perf.toTransaction', { name: addCasesModal.transactionName }) : '',
      })"
      :width="700"
      @ok="confirmAddCases"
    >
      <a-input-search
        v-model:value="addCasesModal.search"
        :placeholder="t('perf.searchCases')"
        style="margin-bottom: 12px;"
        @search="reloadAvailableCases"
      />
      <a-table
        :data-source="addCasesModal.available"
        :columns="addCasesColumns"
        :row-selection="{ selectedRowKeys: addCasesModal.selectedIds, onChange: (keys: any) => (addCasesModal.selectedIds = keys) }"
        row-key="id"
        :pagination="addCasesPagination"
        @change="onAddCasesTableChange"
        size="small"
      />
    </a-modal>

    <!-- ───── Run trigger modal ───── -->
    <a-modal
      v-model:open="runModal.visible"
      :title="t('perf.runPlan', { name: runModal.planName })"
      @ok="confirmRun"
      :confirm-loading="runModal.loading"
    >
      <a-form layout="vertical">
        <div style="margin-bottom: 12px; font-size: 12px; color: var(--text-3);">
          {{ t('perf.defaultsHint') }}
        </div>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item :label="t('perf.targetDefault', { value: runModal.defaults.target_rate })">
              <a-input-number v-model:value="runModal.target_rate" :min="1" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item :label="t('perf.durationDefault', { value: runModal.defaults.duration_secs })">
              <a-input-number v-model:value="runModal.duration_secs" :min="1" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item :label="t('perf.maxVusDefault', { value: runModal.defaults.max_vus })">
              <a-input-number v-model:value="runModal.max_vus" :min="1" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, SyncOutlined, UploadOutlined } from '@ant-design/icons-vue'
import { perfApi, type PerfPlan, type PerfPlanCase, type PerfPlanListItem, type Transaction } from '../api/perf.ts'
import { testcaseApi } from '../api/testcases.ts'
import { useEnvStore } from '../stores/env.ts'
import { useProjectStore } from '../stores/project.ts'
import { useLoading } from '../composables/useLoading.ts'

const router = useRouter()
const { t } = useI18n()
const projectStore = useProjectStore()
const envStore = useEnvStore()
const envs = computed(() => envStore.envs)

const drawerWidth = computed(() => (window.innerWidth <= 768 ? '95%' : 900))
const plans = ref<PerfPlanListItem[]>([])
const loading = ref(false)
const searchText = ref('')

// a-table's `pagination` prop with an explicit `current` field puts the
// table in controlled mode — the parent owns the page state and must
// update it via @change. Without the handler, clicking page N is a no-op
// because `current` stays at 1.
const planTablePagination = reactive({ pageSize: 20, current: 1, showSizeChanger: true })
const addCasesPagination = reactive({
  pageSize: 20,
  current: 1,
  showSizeChanger: true,
  pageSizeOptions: ['10', '20', '50', '100'],
})

function onPlanTableChange(p: any) {
  planTablePagination.current = p.current
  planTablePagination.pageSize = p.pageSize
}

function onAddCasesTableChange(p: any) {
  addCasesPagination.current = p.current
  addCasesPagination.pageSize = p.pageSize
}

const columns = computed(() => [
  { title: t('common.name'), dataIndex: 'name' },
  { title: t('executions.env'), dataIndex: 'env_name', width: 140 },
  { title: 'RPS', dataIndex: 'rate', width: 80 },
  { title: t('common.duration'), dataIndex: 'duration', width: 90 },
  { title: t('perf.maxVus'), dataIndex: 'max_vus', width: 100 },
  { title: t('perf.transactions'), dataIndex: 'transaction_count', width: 100 },
  { title: t('common.cases'), dataIndex: 'case_count', width: 80 },
  { title: t('common.updated'), dataIndex: 'updated_at', width: 180 },
  { title: t('common.action'), dataIndex: 'action', width: 220 },
])

async function loadPlans() {
  loading.value = true
  try {
    const params: any = { project: projectStore.currentProjectId, page_size: 200 }
    if (searchText.value) params.search = searchText.value
    const res: any = await perfApi.listPlans(params)
    plans.value = res.results || res
  } finally {
    loading.value = false
  }
}

// ────── Drawer (create / edit) ──────
const drawer = reactive({
  visible: false,
  editId: null as number | null,
  name: '',
  description: '',
  envId: null as number | null,
  targetRate: 100,
  durationSecs: 60,
  maxVus: 50,
  notifyWebhook: '',
  notifyOnCompletion: false,
  notifyOnFailure: true,
  transactions: [] as Transaction[],
  cases: [] as PerfPlanCase[],
  accountFileKey: '',
})

const setupCases = computed(() => drawer.cases.filter((c) => c.role === 'setup').sort((a, b) => a.sort_order - b.sort_order))

function transactionCases(name: string) {
  return drawer.cases.filter((c) => c.role === 'transaction' && c.transaction_name === name).sort((a, b) => a.sort_order - b.sort_order)
}

const caseColumns = computed(() => [
  { title: '#', dataIndex: 'sort_order', width: 50 },
  { title: t('common.name'), dataIndex: 'case_name' },
  { title: t('common.data'), dataIndex: 'data', width: 130 },
  { title: t('common.action'), dataIndex: 'action', width: 80 },
])

async function openDrawer(record?: PerfPlanListItem) {
  await envStore.fetchEnvs()
  if (record) {
    drawer.editId = record.id
    // Fetch full detail (with nested cases)
    const full: PerfPlan = await perfApi.getPlan(record.id)
    drawer.name = full.name
    drawer.description = full.description
    drawer.envId = full.env
    drawer.targetRate = full.target_rate
    drawer.durationSecs = full.duration_secs
    drawer.maxVus = full.max_vus
    drawer.notifyWebhook = full.notify_feishu_webhook
    drawer.notifyOnCompletion = full.notify_on_completion
    drawer.notifyOnFailure = full.notify_on_failure
    drawer.transactions = [...full.transactions].sort((a, b) => a.sort_order - b.sort_order)
    drawer.cases = full.plan_cases
    drawer.accountFileKey = full.account_data_file_s3_key
  } else {
    drawer.editId = null
    drawer.name = ''
    drawer.description = ''
    drawer.envId = null
    drawer.targetRate = 100
    drawer.durationSecs = 60
    drawer.maxVus = 50
    drawer.notifyWebhook = ''
    drawer.notifyOnCompletion = false
    drawer.notifyOnFailure = true
    drawer.transactions = []
    drawer.cases = []
    drawer.accountFileKey = ''
  }
  drawer.visible = true
}

const [onSave, saveLoading] = useLoading(async () => {
  if (!drawer.name) {
    message.warning(t('common.requiredName'))
    return
  }
  const payload: any = {
    project: projectStore.currentProjectId,
    name: drawer.name,
    description: drawer.description,
    env: drawer.envId,
    target_rate: drawer.targetRate,
    duration_secs: drawer.durationSecs,
    max_vus: drawer.maxVus,
    transactions: drawer.transactions.map((t, i) => ({ ...t, sort_order: i })),
    notify_feishu_webhook: drawer.notifyWebhook,
    notify_on_completion: drawer.notifyOnCompletion,
    notify_on_failure: drawer.notifyOnFailure,
  }
  if (drawer.editId) {
    await perfApi.updatePlan(drawer.editId, payload)
    message.success(t('common.updatedMessage'))
  } else {
    const created = await perfApi.createPlan(payload)
    drawer.editId = created.id
    message.success(t('perf.createdAddCases'))
  }
  loadPlans()
})

async function refreshDrawerCases() {
  if (!drawer.editId) return
  drawer.cases = await perfApi.listCases(drawer.editId)
}

// ────── Transactions metadata ──────
function addTransaction() {
  let i = drawer.transactions.length + 1
  while (drawer.transactions.some((t) => t.name === `tx_${i}`)) i++
  drawer.transactions.push({ name: `tx_${i}`, weight: 1, sort_order: drawer.transactions.length })
}

const txRenames = ref<{ idx: number; oldName: string }[]>([])
function markTxRename(idx: number, _newName: string) {
  // No-op for now — rename happens via Save (full PATCH). If we need to
  // migrate plan_cases.transaction_name on rename, do it server-side later.
}

function removeTransaction(idx: number) {
  drawer.transactions.splice(idx, 1)
}

// ────── Case add/remove ──────
const addCasesModal = reactive({
  visible: false,
  role: 'setup' as 'setup' | 'transaction',
  transactionName: '',
  search: '',
  available: [] as any[],
  selectedIds: [] as number[],
})

const addCasesColumns = computed(() => [
  { title: t('common.name'), dataIndex: 'case_name' },
  { title: t('common.method'), dataIndex: 'method', width: 80 },
  { title: 'URL', dataIndex: 'url', ellipsis: true },
])

async function reloadAvailableCases() {
  const res: any = await testcaseApi.list({
    project: projectStore.currentProjectId,
    search: addCasesModal.search || undefined,
    page_size: 200,
  })
  const items = (res.results || res) as any[]
  // Exclude cases already in this plan with the same role+transaction
  const inSet = new Set(
    drawer.cases
      .filter(
        (c) =>
          c.role === addCasesModal.role &&
          c.transaction_name === addCasesModal.transactionName
      )
      .map((c) => c.testcase)
  )
  addCasesModal.available = items.filter((c) => !inSet.has(c.id))
}

function openAddCases(role: 'setup' | 'transaction', txName = '') {
  addCasesModal.role = role
  addCasesModal.transactionName = txName
  addCasesModal.search = ''
  addCasesModal.selectedIds = []
  addCasesPagination.current = 1
  addCasesModal.visible = true
  reloadAvailableCases()
}

async function confirmAddCases() {
  if (!drawer.editId || addCasesModal.selectedIds.length === 0) {
    addCasesModal.visible = false
    return
  }
  await perfApi.addCases(drawer.editId, {
    role: addCasesModal.role,
    transaction_name: addCasesModal.transactionName,
    case_ids: addCasesModal.selectedIds,
  })
  addCasesModal.visible = false
  await refreshDrawerCases()
  message.success(t('common.addedMessage'))
}

async function removeCase(planCaseId: number) {
  if (!drawer.editId) return
  await perfApi.removeCases(drawer.editId, [planCaseId])
  await refreshDrawerCases()
  message.success(t('common.removedMessage'))
}

// ────── Snapshot sync ──────
async function syncSnapshots() {
  if (!drawer.editId) return
  const res: any = await perfApi.syncSnapshots(drawer.editId)
  message.success(t('perf.syncedUpdated', { count: res.diffs?.length || 0 }))
  await refreshDrawerCases()
}

// ────── Data file uploads ──────
async function onUploadAccountPool(file: File) {
  if (!drawer.editId) return false
  const res: any = await perfApi.uploadAccountPool(drawer.editId, file)
  drawer.accountFileKey = res.s3_key
  message.success(t('perf.accountUploaded'))
  return false // prevent default upload behavior
}

async function onUploadCaseData(planCaseId: number, file: File) {
  if (!drawer.editId) return false
  const res: any = await perfApi.uploadCaseData(drawer.editId, planCaseId, file, 'round_robin')
  message.success(t('perf.dataUploaded', { mode: res.mode }))
  await refreshDrawerCases()
  return false
}

function shortenKey(key: string) {
  return key.split('/').pop() || key
}

// ────── Delete ──────
const [onDelete] = useLoading(async (id: number) => {
  await perfApi.deletePlan(id)
  message.success(t('common.deleted'))
  loadPlans()
})

// ────── Run ──────
const runModal = reactive({
  visible: false,
  planId: 0,
  planName: '',
  defaults: { target_rate: 0, duration_secs: 0, max_vus: 0 },
  target_rate: null as number | null,
  duration_secs: null as number | null,
  max_vus: null as number | null,
  loading: false,
})

function openRunDialog(record: PerfPlanListItem) {
  runModal.planId = record.id
  runModal.planName = record.name
  runModal.defaults = {
    target_rate: record.target_rate,
    duration_secs: record.duration_secs,
    max_vus: record.max_vus,
  }
  runModal.target_rate = null
  runModal.duration_secs = null
  runModal.max_vus = null
  runModal.visible = true
}

async function confirmRun() {
  runModal.loading = true
  try {
    const overrides: any = {}
    if (runModal.target_rate) overrides.target_rate = runModal.target_rate
    if (runModal.duration_secs) overrides.duration_secs = runModal.duration_secs
    if (runModal.max_vus) overrides.max_vus = runModal.max_vus
    const run = await perfApi.triggerRun(runModal.planId, overrides)
    runModal.visible = false
    message.success(t('perf.runStarted', { id: run.id }))
    router.push({ name: 'PerfRunDetail', params: { id: String(run.id) } })
  } catch (e: any) {
    message.error(e?.response?.data?.error || t('perf.runStartFailed'))
  } finally {
    runModal.loading = false
  }
}

function goToHistory(record: PerfPlanListItem) {
  router.push({ name: 'PerfPlanHistory', params: { id: String(record.id) } })
}

onMounted(() => {
  loadPlans()
  envStore.fetchEnvs()
})
</script>

<style scoped>
.tx-block {
  border: 1px solid var(--border, #303030);
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 12px;
}
.tx-header {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
</style>
