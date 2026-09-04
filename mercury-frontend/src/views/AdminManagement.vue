<template>
  <div class="pm-page">
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px">
      <h2 style="margin: 0; color: var(--text)">Admin</h2>
      <a-button @click="$router.back()">Back</a-button>
    </div>

    <a-tabs v-model:activeKey="activeTab">
      <!-- Whitelist Tab -->
      <a-tab-pane key="whitelist" tab="Email Whitelist">
        <div style="margin-bottom: 16px; display: flex; gap: 8px">
          <a-input v-model:value="newEmail" placeholder="email@shanda.com" style="width: 260px" @pressEnter="handleAddWhitelist" />
          <a-input v-model:value="newNote" placeholder="Note (optional)" style="width: 200px" @pressEnter="handleAddWhitelist" />
          <a-button type="primary" @click="handleAddWhitelist" :loading="adding">Add</a-button>
        </div>
        <a-table :columns="whitelistColumns" :data-source="whitelist" :pagination="false" row-key="id" size="small">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'is_admin'">
              <a-switch :checked="record.is_admin" size="small" @change="handleToggleAdmin(record)" />
            </template>
            <template v-if="column.key === 'action'">
              <a-popconfirm title="Remove this email?" @confirm="handleDeleteWhitelist(record.id)">
                <a-button danger size="small">Remove</a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>
      </a-tab-pane>

      <!-- Permissions Tab -->
      <a-tab-pane key="permissions" tab="Project Permissions">
        <div style="margin-bottom: 16px; display: flex; gap: 8px">
          <a-select v-model:value="permUserId" placeholder="Select user" style="width: 240px" show-search option-filter-prop="label"
            :options="users.map((u: any) => ({ value: u.id, label: u.display_name || u.email }))" />
          <a-select v-model:value="permProjectId" placeholder="Select project" style="width: 200px" show-search option-filter-prop="label"
            :options="projects.map((p: any) => ({ value: p.id, label: p.name }))" />
          <a-button type="primary" @click="handleAddPermission">Grant</a-button>
        </div>
        <a-table :columns="permColumns" :data-source="permissions" :pagination="false" row-key="id" size="small">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'action'">
              <a-popconfirm title="Revoke this permission?" @confirm="handleDeletePermission(record.id)">
                <a-button danger size="small">Revoke</a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>
      </a-tab-pane>

      <!-- Audit Tab -->
      <a-tab-pane key="audit" tab="Audit Logs">
        <div style="margin-bottom: 16px; display: flex; gap: 8px">
          <a-input v-model:value="auditSearch" placeholder="Search by email or path" style="width: 260px" allow-clear @pressEnter="fetchAuditLogs" />
          <a-select v-model:value="auditAction" placeholder="Method" style="width: 120px" allow-clear
            :options="['POST','PUT','PATCH','DELETE'].map(m => ({ value: m, label: m }))" />
          <a-button @click="fetchAuditLogs">Search</a-button>
        </div>
        <a-table :columns="auditColumns" :data-source="auditLogs" row-key="id" size="small"
          :pagination="{ current: auditPage, total: auditTotal, pageSize: 20, showSizeChanger: false }"
          @change="onAuditPageChange">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'body'">
              <span class="audit-body">{{ JSON.stringify(record.body).substring(0, 80) }}</span>
            </template>
            <template v-if="column.key === 'action'">
              <a-tag :color="methodColor(record.action)">{{ record.action }}</a-tag>
            </template>
          </template>
        </a-table>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { getUsers, toggleWhitelistAdmin, getWhitelist, addWhitelist, deleteWhitelist, getPermissions, addPermission, deletePermission, getAuditLogs } from '../api/admin.ts'
import { projectApi } from '../api/projects.ts'

const activeTab = ref('whitelist')

// Whitelist
const whitelist = ref<any[]>([])
const newEmail = ref('')
const newNote = ref('')
const adding = ref(false)
const whitelistColumns = [
  { title: 'Email', dataIndex: 'email', key: 'email' },
  { title: 'Note', dataIndex: 'note', key: 'note' },
  { title: 'Admin', key: 'is_admin', width: 80 },
  { title: 'Added', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '', key: 'action', width: 100 },
]

async function fetchWhitelist() {
  const res: any = await getWhitelist()
  whitelist.value = res
}

async function handleAddWhitelist() {
  if (!newEmail.value) return
  adding.value = true
  try {
    await addWhitelist({ email: newEmail.value, note: newNote.value })
    newEmail.value = ''
    newNote.value = ''
    await fetchWhitelist()
  } catch (e) { /* handled by interceptor */ }
  adding.value = false
}

async function handleDeleteWhitelist(id: number) {
  await deleteWhitelist(id)
  await fetchWhitelist()
}

async function handleToggleAdmin(record: any) {
  try {
    const res: any = await toggleWhitelistAdmin(record.id)
    record.is_admin = res.is_admin
  } catch (e) { /* handled by interceptor */ }
}

// Permissions
const users = ref<any[]>([])
const projects = ref<any[]>([])
const permissions = ref<any[]>([])
const permUserId = ref<number>()
const permProjectId = ref<number>()
const permColumns = [
  { title: 'User', dataIndex: 'user_email', key: 'user_email' },
  { title: 'Name', dataIndex: 'user_display_name', key: 'user_display_name' },
  { title: 'Project', dataIndex: 'project_name', key: 'project_name' },
  { title: 'Granted', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '', key: 'action', width: 100 },
]

async function fetchPermissions() {
  const res: any = await getPermissions()
  permissions.value = res
}

async function handleAddPermission() {
  if (!permUserId.value || !permProjectId.value) {
    message.warning('Select both user and project')
    return
  }
  try {
    await addPermission({ user: permUserId.value, project: permProjectId.value })
    permUserId.value = undefined
    permProjectId.value = undefined
    await fetchPermissions()
  } catch (e) { /* handled by interceptor */ }
}

async function handleDeletePermission(id: number) {
  await deletePermission(id)
  await fetchPermissions()
}

// Audit
const auditLogs = ref<any[]>([])
const auditPage = ref(1)
const auditTotal = ref(0)
const auditSearch = ref('')
const auditAction = ref<string>()
const auditColumns = [
  { title: 'Time', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: 'User', dataIndex: 'user_email', key: 'user_email', width: 200 },
  { title: 'Method', key: 'action', width: 90 },
  { title: 'Path', dataIndex: 'path', key: 'path' },
  { title: 'Status', dataIndex: 'status_code', key: 'status_code', width: 80 },
  { title: 'Body', key: 'body' },
  { title: 'IP', dataIndex: 'ip_address', key: 'ip_address', width: 130 },
]

function methodColor(m: string) {
  const map: Record<string, string> = { POST: 'green', PUT: 'orange', PATCH: 'blue', DELETE: 'red' }
  return map[m] || 'default'
}

async function fetchAuditLogs() {
  const res: any = await getAuditLogs({
    page: auditPage.value,
    search: auditSearch.value || undefined,
    action: auditAction.value || undefined,
  })
  auditLogs.value = res.results || []
  auditTotal.value = res.count || 0
}

function onAuditPageChange(pagination: any) {
  auditPage.value = pagination.current
  fetchAuditLogs()
}

onMounted(async () => {
  fetchWhitelist()
  fetchPermissions()
  fetchAuditLogs()
  const [usersRes, projectsRes]: any[] = await Promise.all([getUsers(), projectApi.list()])
  users.value = usersRes
  projects.value = projectsRes?.results || projectsRes || []
})
</script>

<style scoped>
.audit-body {
  font-size: 12px;
  color: var(--text-3);
  font-family: monospace;
}

@media (max-width: 768px) {
  .pm-page > div:first-child { flex-wrap: wrap !important; }
  .pm-page > div:first-child > * { flex: 1 1 100% !important; min-width: 0 !important; }
  .pm-page > div:first-child .ant-input { width: 100% !important; }
  .pm-page > div:first-child .ant-select { width: 100% !important; }
}
</style>
