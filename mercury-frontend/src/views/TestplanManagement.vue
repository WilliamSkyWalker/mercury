<template>
  <div class="pm-page">
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between;">
      <a-input-search v-model:value="searchText" :placeholder="t('plans.search')" style="width: 300px" @search="loadPlans" />
      <a-button type="primary" @click="openDrawer()">{{ t('plans.create') }}</a-button>
    </div>

    <a-table :data-source="plans" :columns="columns" :loading="loading" row-key="id">
      <template #bodyCell="{ column, record }">
        <template v-if="column.dataIndex === 'name'">
          <a @click="openDrawer(record)">{{ record.name }}</a>
        </template>
        <template v-if="column.dataIndex === 'action'">
          <a-space>
            <a-button type="primary" size="small" :loading="runLoading" @click="onRun(record)">{{ t('common.run') }}</a-button>
            <a-popconfirm :title="t('schedules.deleteConfirm')" @confirm="onDelete(record.id)">
              <a style="color: #ff4d4f">{{ t('common.delete') }}</a>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- Edit/Create Drawer -->
    <a-drawer
      v-model:open="drawer.visible"
      :title="drawer.editId ? t('plans.edit') : t('plans.create')"
      :width="drawerWidth"
      :bodyStyle="{ padding: '16px 24px' }"
    >
      <template #extra>
        <a-button type="primary" :loading="saveLoading" @click="onSave">{{ t('common.save') }}</a-button>
      </template>

      <a-form layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item :label="t('common.name')">
              <a-input v-model:value="drawer.name" :placeholder="t('plans.planName')" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('common.environment')">
              <a-select v-model:value="drawer.envId" allow-clear :placeholder="t('plans.selectEnv')" style="width: 100%">
                <a-select-option v-for="e in envs" :key="e.id" :value="e.id">{{ e.name }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item :label="t('plans.serialExecution')">
              <a-switch v-model:checked="drawer.isSerial" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item :label="t('plans.retryCount')">
              <a-input-number v-model:value="drawer.retryCount" :min="0" :max="5" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item :label="t('plans.notifyOnFailure')">
              <a-switch v-model:checked="drawer.notifyOnFailure" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item :label="t('plans.groupWebhook')">
          <a-input v-model:value="drawer.feishuWebhook" placeholder="https://open.feishu.cn/..." />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item :label="t('plans.phoneOnFailure')">
              <a-switch v-model:checked="drawer.phoneOnFailure" />
              <span style="margin-left: 8px; color: var(--text-3); font-size: 12px;">
                {{ t('plans.scheduledOnlyHint') }}
              </span>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('plans.mutePhone')">
              <a-switch v-model:checked="drawer.phoneMuted" />
              <span style="margin-left: 8px; color: var(--text-3); font-size: 12px;">
                {{ t('plans.mutePhoneHint') }}
              </span>
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>

      <!-- Case management (only for existing plans) -->
      <template v-if="drawer.editId">
        <a-divider />
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <h3 style="margin: 0;">{{ t('plans.testCasesCount', { count: drawer.cases.length }) }}</h3>
          <a-space>
            <a-button size="small" @click="openSyncModal">
              <SyncOutlined /> {{ t('common.sync') }}
            </a-button>
            <a-button size="small" @click="openAddCasesModal">
              <PlusOutlined /> {{ t('plans.addCases') }}
            </a-button>
          </a-space>
        </div>
        <a-spin :spinning="orderSaving" :tip="t('plans.savingOrder')">
          <table class="drag-case-table">
            <thead>
              <tr>
                <th style="width: 30px"></th>
                <th style="width: 40px">#</th>
                <th style="width: 70px">{{ t('common.method') }}</th>
                <th>{{ t('common.name') }}</th>
                <th>URL</th>
                <th style="width: 70px"></th>
              </tr>
            </thead>
            <draggable
              v-model="drawer.cases"
              tag="tbody"
              item-key="id"
              handle=".drag-handle"
              @end="onDragEnd"
            >
              <template #item="{ element }">
                <tr>
                  <td><HolderOutlined class="drag-handle" /></td>
                  <td>{{ element.sort_order }}</td>
                  <td><span :class="['pm-method', `pm-method-${element.method.toLowerCase()}`]">{{ element.method }}</span></td>
                  <td class="ellipsis-cell">{{ element.case_name }}</td>
                  <td class="ellipsis-cell">{{ element.url }}</td>
                  <td><a style="color: #f93e3e" @click="onRemoveSingleCase(element.id)">{{ t('common.remove') }}</a></td>
                </tr>
              </template>
            </draggable>
          </table>
        </a-spin>
      </template>
    </a-drawer>

    <!-- Sync Modal -->
    <a-modal v-model:open="syncModal.visible" :title="t('plans.syncCases')" :confirm-loading="syncApplying" @ok="onApplySync" width="700px" :ok-text="t('plans.syncSelected')">
      <a-spin :spinning="syncModal.loading">
        <a-empty v-if="!syncModal.loading && !syncModal.diffs.length" :description="t('plans.allUpToDate')" />
        <div v-else>
          <div v-for="diff in syncModal.diffs" :key="diff.plan_case_id" class="sync-diff-item">
            <div class="sync-diff-header">
              <a-checkbox
                :checked="syncModal.selectedIds.includes(diff.plan_case_id)"
                @change="(e: any) => toggleSyncSelect(diff.plan_case_id, e.target.checked)"
              />
              <span :class="['pm-method', `pm-method-${diff.method.toLowerCase()}`]" style="margin: 0 8px;">{{ diff.method }}</span>
              <span style="font-weight: 500;">{{ diff.case_name }}</span>
              <a-tag color="orange" style="margin-left: 8px;">{{ t('plans.changedCount', { count: Object.keys(diff.changed_fields).length }) }}</a-tag>
            </div>
            <div class="sync-diff-fields">
              <div v-for="(change, field) in diff.changed_fields" :key="field" class="sync-diff-field">
                <div class="sync-diff-field-name">{{ field }}</div>
                <div class="sync-diff-old">
                  <span class="sync-label">{{ t('plans.old') }}</span>
                  <pre>{{ formatDiffValue(change.old) }}</pre>
                </div>
                <div class="sync-diff-new">
                  <span class="sync-label">{{ t('plans.new') }}</span>
                  <pre>{{ formatDiffValue(change.new) }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </a-spin>
    </a-modal>

    <!-- Add Cases Modal -->
    <a-modal v-model:open="addCasesModal.visible" :title="t('plans.addCases')" :confirm-loading="addCasesLoading" @ok="onAddCases" width="600px">
      <a-input-search v-model:value="addCasesModal.search" :placeholder="t('plans.searchCases')" style="margin-bottom: 12px" @search="searchCasesForAdd" />
      <a-table
        :data-source="addCasesModal.cases"
        :columns="[{ title: t('common.method'), dataIndex: 'method', width: 80 }, { title: t('common.name'), dataIndex: 'case_name' }]"
        :row-selection="{ selectedRowKeys: addCasesModal.selectedIds, onChange: (keys: any) => addCasesModal.selectedIds = keys }"
        row-key="id"
        size="small"
        :pagination="false"
      />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { PlusOutlined, HolderOutlined, SyncOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import draggable from 'vuedraggable'
import { testplanApi, type Testplan } from '../api/testplans.ts'
import { testcaseApi } from '../api/testcases.ts'
import { useEnvStore } from '../stores/env.ts'
import { useProjectStore } from '../stores/project.ts'
import { useLoading } from '../composables/useLoading.ts'

const projectStore = useProjectStore()
const { t } = useI18n()

const envStore = useEnvStore()
const envs = computed(() => envStore.envs)

const drawerWidth = computed(() => window.innerWidth <= 768 ? '100%' : '800px')
const plans = ref<Testplan[]>([])
const loading = ref(false)
const searchText = ref('')

const columns = computed(() => [
  { title: t('common.name'), dataIndex: 'name' },
  { title: t('executions.env'), dataIndex: 'env_name', width: 120 },
  { title: t('common.cases'), dataIndex: 'case_count', width: 80 },
  { title: t('plans.serial'), dataIndex: 'is_serial', width: 80 },
  { title: t('common.updated'), dataIndex: 'updated_at', width: 180 },
  { title: t('common.action'), dataIndex: 'action', width: 150 },
])

const drawer = reactive({
  visible: false, editId: null as number | null,
  name: '', envId: null as number | null, isSerial: true,
  retryCount: 0, feishuWebhook: '', notifyOnFailure: true,
  phoneOnFailure: false, phoneMuted: false,
  cases: [] as any[],
})

const addCasesModal = reactive({
  visible: false, search: '', cases: [] as any[], selectedIds: [] as number[],
})

const syncModal = reactive({
  visible: false, loading: false, diffs: [] as any[], selectedIds: [] as number[],
})

async function loadPlans() {
  loading.value = true
  try {
    const res = await testplanApi.list({ search: searchText.value, project: projectStore.currentProjectId })
    plans.value = res.results || res
  } finally {
    loading.value = false
  }
}

async function openDrawer(record?: Testplan) {
  if (record) {
    drawer.editId = record.id; drawer.name = record.name; drawer.envId = record.env
    drawer.isSerial = record.is_serial; drawer.retryCount = record.retry_count
    drawer.feishuWebhook = record.feishu_webhook; drawer.notifyOnFailure = record.notify_on_failure
    drawer.phoneOnFailure = (record as any).phone_on_failure ?? false
    drawer.phoneMuted = (record as any).phone_muted ?? false
    drawer.cases = await testplanApi.getCases(record.id)
  } else {
    drawer.editId = null; drawer.name = ''; drawer.envId = null
    drawer.isSerial = true; drawer.retryCount = 0; drawer.feishuWebhook = ''; drawer.notifyOnFailure = true
    drawer.phoneOnFailure = false; drawer.phoneMuted = false
    drawer.cases = []
  }
  drawer.visible = true
}

const [onSave, saveLoading] = useLoading(async () => {
  if (!drawer.name) { message.warning(t('common.requiredName')); return }
  const data: any = {
    name: drawer.name, env: drawer.envId, is_serial: drawer.isSerial,
    retry_count: drawer.retryCount, feishu_webhook: drawer.feishuWebhook,
    notify_on_failure: drawer.notifyOnFailure,
    phone_on_failure: drawer.phoneOnFailure, phone_muted: drawer.phoneMuted,
  }
  if (drawer.editId) {
    await testplanApi.update(drawer.editId, data)
    message.success(t('common.saved'))
  } else {
    data.project = projectStore.currentProjectId
    const created = await testplanApi.create(data)
    drawer.editId = created.id
    message.success(t('common.createdMessage'))
  }
  loadPlans()
})

const [onDelete, deleteLoading] = useLoading(async (id: number) => {
  await testplanApi.delete(id)
  message.success(t('common.deleted'))
  loadPlans()
})

const [onRun, runLoading] = useLoading(async (record: Testplan) => {
  try {
    const res = await testplanApi.run(record.id, record.env ?? undefined)
    message.success(t('plans.executionStarted', { taskId: res.task_id }))
  } catch { /* handled by interceptor */ }
})

async function openAddCasesModal() {
  addCasesModal.search = ''
  addCasesModal.selectedIds = []
  addCasesModal.visible = true
  await searchCasesForAdd()
}

async function searchCasesForAdd() {
  const all = await testcaseApi.list({ search: addCasesModal.search, project: projectStore.currentProjectId })
  const existing = new Set(drawer.cases.map((c: any) => c.testcase))
  addCasesModal.cases = all.filter((c: any) => !existing.has(c.id))
}

const [onAddCases, addCasesLoading] = useLoading(async () => {
  if (!addCasesModal.selectedIds.length) { message.warning(t('plans.selectCases')); return }
  await testplanApi.addCases(drawer.editId!, addCasesModal.selectedIds)
  message.success(t('plans.casesAdded'))
  addCasesModal.visible = false
  addCasesModal.selectedIds = []
  drawer.cases = await testplanApi.getCases(drawer.editId!)
  loadPlans()
})

const orderSaving = ref(false)
async function onDragEnd() {
  const ordering = drawer.cases.map((c: any, i: number) => ({ id: c.id, sort_order: i }))
  drawer.cases.forEach((c: any, i: number) => { c.sort_order = i })
  orderSaving.value = true
  try {
    await testplanApi.updateCaseOrder(drawer.editId!, ordering)
  } catch {
    message.error(t('plans.orderSaveFailed'))
  } finally {
    orderSaving.value = false
  }
}

async function onRemoveSingleCase(planCaseId: number) {
  await testplanApi.removeCases(drawer.editId!, [planCaseId])
  message.success(t('common.removedMessage'))
  drawer.cases = await testplanApi.getCases(drawer.editId!)
  loadPlans()
}

async function openSyncModal() {
  syncModal.visible = true
  syncModal.loading = true
  syncModal.diffs = []
  syncModal.selectedIds = []
  try {
    syncModal.diffs = await testplanApi.getSyncDiff(drawer.editId!)
    // Auto-select all
    syncModal.selectedIds = syncModal.diffs.map((d: any) => d.plan_case_id)
  } finally {
    syncModal.loading = false
  }
}

function toggleSyncSelect(id: number, checked: boolean) {
  if (checked) {
    syncModal.selectedIds.push(id)
  } else {
    syncModal.selectedIds = syncModal.selectedIds.filter(i => i !== id)
  }
}

function formatDiffValue(val: any): string {
  if (val === null || val === undefined) return ''
  if (typeof val === 'string') return val || t('common.empty')
  return JSON.stringify(val, null, 2)
}

const [onApplySync, syncApplying] = useLoading(async () => {
  if (!syncModal.selectedIds.length) { message.warning(t('plans.selectCasesToSync')); return }
  await testplanApi.applySync(drawer.editId!, syncModal.selectedIds)
  message.success(t('plans.syncedCases', { count: syncModal.selectedIds.length }))
  syncModal.visible = false
  drawer.cases = await testplanApi.getCases(drawer.editId!)
})

onMounted(() => { loadPlans(); envStore.fetchEnvs() })
</script>

<style scoped>
/* Uses global .pm-page and .pm-method-* from dark-theme.css */
.pm-page a { color: var(--link); }

.drag-case-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.drag-case-table th { text-align: left; padding: 6px 8px; color: var(--text-2); background: var(--bg-surface); border-bottom: 1px solid var(--border); font-weight: 500; }
.drag-case-table td { padding: 6px 8px; border-bottom: 1px solid var(--border-light); color: var(--text); }
.drag-case-table tr:hover td { background: var(--bg-hover); }
.drag-handle { cursor: grab; color: var(--text-3); font-size: 14px; }
.drag-handle:active { cursor: grabbing; }
.ellipsis-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.sync-diff-item { border: 1px solid var(--border); border-radius: 6px; margin-bottom: 12px; overflow: hidden; }
.sync-diff-header { display: flex; align-items: center; padding: 8px 12px; background: var(--bg-surface); border-bottom: 1px solid var(--border); }
.sync-diff-fields { padding: 8px 12px; }
.sync-diff-field { margin-bottom: 8px; }
.sync-diff-field:last-child { margin-bottom: 0; }
.sync-diff-field-name { font-size: 11px; font-weight: 600; color: var(--text-3); text-transform: uppercase; margin-bottom: 4px; }
.sync-diff-old, .sync-diff-new { display: flex; gap: 6px; font-size: 12px; }
.sync-diff-old pre, .sync-diff-new pre { margin: 0; white-space: pre-wrap; word-break: break-all; flex: 1; max-height: 100px; overflow: auto; }
.sync-diff-old { color: #f93e3e; }
.sync-diff-new { color: #49cc90; }
.sync-label { font-size: 11px; font-weight: 500; min-width: 30px; }

@media (max-width: 768px) {
  .pm-page > div:first-child { flex-wrap: wrap !important; gap: 8px !important; }
  .pm-page > div:first-child .ant-input-search { width: 100% !important; }
}
</style>
