<template>
  <div class="pm-page">
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between;">
      <a-input-search v-model:value="searchText" placeholder="Search plans" style="width: 300px" @search="loadPlans" />
      <a-button type="primary" @click="openDrawer()">Create Plan</a-button>
    </div>

    <a-table :data-source="plans" :columns="columns" :loading="loading" row-key="id">
      <template #bodyCell="{ column, record }">
        <template v-if="column.dataIndex === 'name'">
          <a @click="openDrawer(record)">{{ record.name }}</a>
        </template>
        <template v-if="column.dataIndex === 'action'">
          <a-space>
            <a-button type="primary" size="small" :loading="runLoading" @click="onRun(record)">Run</a-button>
            <a-popconfirm title="Delete?" @confirm="onDelete(record.id)">
              <a style="color: #ff4d4f">Delete</a>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- Edit/Create Drawer -->
    <a-drawer
      v-model:open="drawer.visible"
      :title="drawer.editId ? 'Edit Plan' : 'Create Plan'"
      :width="drawerWidth"
      :bodyStyle="{ padding: '16px 24px' }"
    >
      <template #extra>
        <a-button type="primary" :loading="saveLoading" @click="onSave">Save</a-button>
      </template>

      <a-form layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="Name">
              <a-input v-model:value="drawer.name" placeholder="Plan name" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="Environment">
              <a-select v-model:value="drawer.envId" allow-clear placeholder="Select env" style="width: 100%">
                <a-select-option v-for="e in envs" :key="e.id" :value="e.id">{{ e.name }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="Serial Execution">
              <a-switch v-model:checked="drawer.isSerial" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="Retry Count">
              <a-input-number v-model:value="drawer.retryCount" :min="0" :max="5" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="Notify on Failure">
              <a-switch v-model:checked="drawer.notifyOnFailure" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="Group Robot Webhook">
          <a-input v-model:value="drawer.feishuWebhook" placeholder="https://open.feishu.cn/..." />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="Phone alert on failure (Flashcat)">
              <a-switch v-model:checked="drawer.phoneOnFailure" />
              <span style="margin-left: 8px; color: var(--text-3); font-size: 12px;">
                Only fires for scheduled runs (manual runs never page).
              </span>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="Mute phone alert">
              <a-switch v-model:checked="drawer.phoneMuted" />
              <span style="margin-left: 8px; color: var(--text-3); font-size: 12px;">
                Suppresses Flashcat phone alerts (use during maintenance).
              </span>
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>

      <!-- Case management (only for existing plans) -->
      <template v-if="drawer.editId">
        <a-divider />
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <h3 style="margin: 0;">Test Cases ({{ drawer.cases.length }})</h3>
          <a-space>
            <a-button size="small" @click="openSyncModal">
              <SyncOutlined /> Sync
            </a-button>
            <a-button size="small" @click="openAddCasesModal">
              <PlusOutlined /> Add Cases
            </a-button>
          </a-space>
        </div>
        <a-spin :spinning="orderSaving" tip="Saving order...">
          <table class="drag-case-table">
            <thead>
              <tr>
                <th style="width: 30px"></th>
                <th style="width: 40px">#</th>
                <th style="width: 70px">Method</th>
                <th>Name</th>
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
                  <td><a style="color: #f93e3e" @click="onRemoveSingleCase(element.id)">Remove</a></td>
                </tr>
              </template>
            </draggable>
          </table>
        </a-spin>
      </template>
    </a-drawer>

    <!-- Sync Modal -->
    <a-modal v-model:open="syncModal.visible" title="Sync Cases" :confirm-loading="syncApplying" @ok="onApplySync" width="700px" ok-text="Sync Selected">
      <a-spin :spinning="syncModal.loading">
        <a-empty v-if="!syncModal.loading && !syncModal.diffs.length" description="All cases are up to date" />
        <div v-else>
          <div v-for="diff in syncModal.diffs" :key="diff.plan_case_id" class="sync-diff-item">
            <div class="sync-diff-header">
              <a-checkbox
                :checked="syncModal.selectedIds.includes(diff.plan_case_id)"
                @change="(e: any) => toggleSyncSelect(diff.plan_case_id, e.target.checked)"
              />
              <span :class="['pm-method', `pm-method-${diff.method.toLowerCase()}`]" style="margin: 0 8px;">{{ diff.method }}</span>
              <span style="font-weight: 500;">{{ diff.case_name }}</span>
              <a-tag color="orange" style="margin-left: 8px;">{{ Object.keys(diff.changed_fields).length }} changed</a-tag>
            </div>
            <div class="sync-diff-fields">
              <div v-for="(change, field) in diff.changed_fields" :key="field" class="sync-diff-field">
                <div class="sync-diff-field-name">{{ field }}</div>
                <div class="sync-diff-old">
                  <span class="sync-label">old:</span>
                  <pre>{{ formatDiffValue(change.old) }}</pre>
                </div>
                <div class="sync-diff-new">
                  <span class="sync-label">new:</span>
                  <pre>{{ formatDiffValue(change.new) }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </a-spin>
    </a-modal>

    <!-- Add Cases Modal -->
    <a-modal v-model:open="addCasesModal.visible" title="Add Cases" :confirm-loading="addCasesLoading" @ok="onAddCases" width="600px">
      <a-input-search v-model:value="addCasesModal.search" placeholder="Search cases" style="margin-bottom: 12px" @search="searchCasesForAdd" />
      <a-table
        :data-source="addCasesModal.cases"
        :columns="[{ title: 'Method', dataIndex: 'method', width: 80 }, { title: 'Name', dataIndex: 'case_name' }]"
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
import { PlusOutlined, HolderOutlined, SyncOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import draggable from 'vuedraggable'
import { testplanApi, type Testplan } from '../api/testplans.ts'
import { testcaseApi } from '../api/testcases.ts'
import { useEnvStore } from '../stores/env.ts'
import { useProjectStore } from '../stores/project.ts'
import { useLoading } from '../composables/useLoading.ts'

const projectStore = useProjectStore()

const envStore = useEnvStore()
const envs = computed(() => envStore.envs)

const drawerWidth = computed(() => window.innerWidth <= 768 ? '100%' : '800px')
const plans = ref<Testplan[]>([])
const loading = ref(false)
const searchText = ref('')

const columns = [
  { title: 'Name', dataIndex: 'name' },
  { title: 'Env', dataIndex: 'env_name', width: 120 },
  { title: 'Cases', dataIndex: 'case_count', width: 80 },
  { title: 'Serial', dataIndex: 'is_serial', width: 80 },
  { title: 'Updated', dataIndex: 'updated_at', width: 180 },
  { title: 'Action', dataIndex: 'action', width: 150 },
]

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
  if (!drawer.name) { message.warning('Name is required'); return }
  const data: any = {
    name: drawer.name, env: drawer.envId, is_serial: drawer.isSerial,
    retry_count: drawer.retryCount, feishu_webhook: drawer.feishuWebhook,
    notify_on_failure: drawer.notifyOnFailure,
    phone_on_failure: drawer.phoneOnFailure, phone_muted: drawer.phoneMuted,
  }
  if (drawer.editId) {
    await testplanApi.update(drawer.editId, data)
    message.success('Saved')
  } else {
    data.project = projectStore.currentProjectId
    const created = await testplanApi.create(data)
    drawer.editId = created.id
    message.success('Created')
  }
  loadPlans()
})

const [onDelete, deleteLoading] = useLoading(async (id: number) => {
  await testplanApi.delete(id)
  message.success('Deleted')
  loadPlans()
})

const [onRun, runLoading] = useLoading(async (record: Testplan) => {
  try {
    const res = await testplanApi.run(record.id, record.env ?? undefined)
    message.success(`Execution started: ${res.task_id}`)
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
  if (!addCasesModal.selectedIds.length) { message.warning('Select cases'); return }
  await testplanApi.addCases(drawer.editId!, addCasesModal.selectedIds)
  message.success('Cases added')
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
    message.error('Failed to save order')
  } finally {
    orderSaving.value = false
  }
}

async function onRemoveSingleCase(planCaseId: number) {
  await testplanApi.removeCases(drawer.editId!, [planCaseId])
  message.success('Removed')
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
  if (typeof val === 'string') return val || '(empty)'
  return JSON.stringify(val, null, 2)
}

const [onApplySync, syncApplying] = useLoading(async () => {
  if (!syncModal.selectedIds.length) { message.warning('Select cases to sync'); return }
  await testplanApi.applySync(drawer.editId!, syncModal.selectedIds)
  message.success(`Synced ${syncModal.selectedIds.length} cases`)
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
