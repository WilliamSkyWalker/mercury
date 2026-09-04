<template>
  <div class="pm-layout">
    <!-- Top nav bar -->
    <div class="pm-topbar">
      <div class="pm-topbar-left">
        <span class="pm-logo">Mercury</span>
      </div>
      <div class="pm-topbar-center">
        <div
          v-for="tab in navTabs"
          :key="tab.key"
          :class="['pm-nav-tab', { active: currentRoute === tab.key }]"
          @click="onMenuClick(tab.key)"
        >
          <component :is="tab.icon" class="pm-nav-icon" />
          <span>{{ tab.label }}</span>
        </div>
      </div>
      <div class="pm-topbar-right">
        <a-dropdown :trigger="['click']">
          <div class="pm-project-btn">
            <ProjectOutlined class="pm-project-btn-icon" />
            <span class="pm-project-btn-name">{{ projectStore.currentProject?.name || 'Project' }}</span>
            <DownOutlined style="font-size: 10px; opacity: 0.6" />
          </div>
          <template #overlay>
            <div class="pm-project-dropdown">
              <div class="pm-project-dropdown-header">Switch Project</div>
              <div class="pm-project-dropdown-list">
                <div
                  v-for="p in projectStore.projects"
                  :key="p.id"
                  :class="['pm-project-dropdown-item', { 'is-active': p.id === projectStore.currentProjectId }]"
                  @click="onProjectSwitch({ key: String(p.id) })"
                >
                  <CheckOutlined v-if="p.id === projectStore.currentProjectId" class="pm-project-check" />
                  <span v-else class="pm-project-check-placeholder" />
                  <span class="pm-project-item-name">{{ p.name }}</span>
                </div>
              </div>
              <div class="pm-project-dropdown-divider" />
              <div class="pm-project-dropdown-item pm-project-manage" @click="onProjectSwitch({ key: 'manage' })">
                <SettingOutlined style="font-size: 13px" />
                <span>Manage Projects</span>
              </div>
            </div>
          </template>
        </a-dropdown>

        <a-dropdown :trigger="['click']">
          <div class="pm-user-btn">
            <UserOutlined />
            <span class="pm-user-name">{{ authStore.user?.display_name || authStore.user?.username || '' }}</span>
          </div>
          <template #overlay>
            <a-menu @click="onUserMenuClick">
              <a-menu-item key="docs">
                <ReadOutlined /> Reference Docs
              </a-menu-item>
              <a-menu-divider />
              <a-menu-item v-if="authStore.user?.is_admin" key="admin">
                <SettingOutlined /> Admin
              </a-menu-item>
              <a-menu-divider v-if="authStore.user?.is_admin" />
              <a-menu-item key="logout">
                <LogoutOutlined /> Logout
              </a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>
      </div>
    </div>

    <!-- Main content -->
    <div class="pm-main">
      <router-view :key="projectStore.currentProjectId ?? undefined" />
    </div>

    <!-- Mobile bottom nav bar -->
    <div class="pm-bottombar">
      <div
        v-for="tab in navTabs"
        :key="tab.key"
        :class="['pm-bottom-tab', { active: currentRoute === tab.key }]"
        @click="onMenuClick(tab.key)"
      >
        <component :is="tab.icon" class="pm-bottom-icon" />
        <span class="pm-bottom-label">{{ tab.short || tab.label }}</span>
      </div>
    </div>

    <!-- Reference Docs Modal -->
    <a-modal v-model:open="docsVisible" title="Script & Assertion Reference" width="720px" :footer="null">
      <div class="pm-docs">
        <h3>Script Language</h3>
        <p>Scripts use <strong>Python</strong> syntax. Available in Pre-request and Post-response tabs.</p>

        <h3>mercury API</h3>
        <table class="pm-docs-table">
          <tbody>
          <tr><td><code>mercury.getVar(name)</code></td><td>Get a runtime variable (set by previous cases)</td></tr>
          <tr><td><code>mercury.setVar(name, value)</code></td><td>Set a runtime variable (available in subsequent cases)</td></tr>
          <tr><td><code>mercury.getEnvVar(name)</code></td><td>Get an environment variable</td></tr>
          <tr><td><code>mercury.getEnvName()</code></td><td>Get current environment name</td></tr>
          </tbody>
        </table>

        <h3>Request Object <code>req</code> (Pre-request only)</h3>
        <table class="pm-docs-table">
          <tbody>
          <tr><td><code>req.url</code></td><td>Request URL (read/write)</td></tr>
          <tr><td><code>req.method</code></td><td>HTTP method (read/write)</td></tr>
          <tr><td><code>req.headers</code></td><td>Headers dict (read/write/delete)</td></tr>
          <tr><td><code>req.body</code></td><td>Request body (read/write)</td></tr>
          </tbody>
        </table>

        <h3>Response Object <code>res</code> (Post-response only)</h3>
        <table class="pm-docs-table">
          <tbody>
          <tr><td><code>res.status</code></td><td>HTTP status code</td></tr>
          <tr><td><code>res.body</code></td><td>Response body (supports dot access: <code>res.body.data.id</code>)</td></tr>
          <tr><td><code>res.headers</code></td><td>Response headers dict</td></tr>
          </tbody>
        </table>

        <h3>Available Modules</h3>
        <p><code>json</code>, <code>base64</code>, and Python builtins (<code>str</code>, <code>int</code>, <code>len</code>, <code>range</code>, <code>sorted</code>, <code>map</code>, <code>filter</code>, etc.)</p>

        <h3>Script Example</h3>
        <pre class="pm-docs-code"># Pre-request: modify headers per environment
if mercury.getEnvName() in ("prod_visit", "newtest_visit"):
    req.headers.pop("Authorization", None)
    req.headers["shanda_identity"] = mercury.getEnvVar("shanda_identity")

# Post-response: extract token for subsequent cases
token = res.body.access_token
mercury.setVar("token", token)
payload = json.loads(base64.b64decode(token.split('.')[1] + '=='))
mercury.setVar("userId", payload["sub"])</pre>

        <h3>Variable Substitution</h3>
        <p>Use <code v-pre>{{variableName}}</code> in URL, headers, params, and body. Runtime variables (from <code>mercury.setVar</code>) take priority over environment variables.</p>

        <h3>Assertion Fields</h3>
        <table class="pm-docs-table">
          <tbody>
          <tr><td><code>res.status</code></td><td>HTTP status code</td></tr>
          <tr><td><code>res.responseTime</code></td><td>Response duration in ms</td></tr>
          <tr><td><code>res.body</code></td><td>Entire response body</td></tr>
          <tr><td><code>res.body.data.id</code></td><td>Nested field access</td></tr>
          <tr><td><code>res.body.items[0].name</code></td><td>Array index access</td></tr>
          <tr><td><code>res.body.items[*].status</code></td><td>Wildcard: assert all items</td></tr>
          <tr><td><code>res.body.data.length</code></td><td>Array/string length</td></tr>
          <tr><td><code>res.headers.x-trace-id</code></td><td>Response header (case-insensitive)</td></tr>
          </tbody>
        </table>

        <h3>Common Assertion Examples</h3>
        <table class="pm-docs-table">
          <tbody>
          <tr><td><code>res.status</code> <code>eq</code> <code>200</code></td><td>Status code is 200</td></tr>
          <tr><td><code>res.responseTime</code> <code>lte</code> <code>1000</code></td><td>Response time &le; 1000ms</td></tr>
          <tr><td><code>res.body.data.length</code> <code>gt</code> <code>0</code></td><td>Array has at least 1 item</td></tr>
          <tr><td><code>res.body.data.length</code> <code>eq</code> <code>10</code></td><td>Array has exactly 10 items</td></tr>
          <tr><td><code>res.body.total</code> <code>gte</code> <code>100</code></td><td>Numeric field &ge; 100</td></tr>
          <tr><td><code>res.body.name</code> <code>contains</code> <code>"test"</code></td><td>String contains "test"</td></tr>
          <tr><td><code>res.body.items[*].status</code> <code>eq</code> <code>"active"</code></td><td>All items have status "active"</td></tr>
          <tr><td><code>res.body.data.name</code> <code>eq</code> <code>"Alice"</code></td><td>JSON key value: <code>{"data":{"name":"Alice"}}</code></td></tr>
          <tr><td><code>res.body.data.tags[1]</code> <code>eq</code> <code>"vip"</code></td><td>Array element: <code>{"data":{"tags":["new","vip"]}}</code></td></tr>
          <tr><td><code>res.body.code</code> <code>eq</code> <code>0</code></td><td>Top-level key: <code>{"code":0,"data":{...}}</code></td></tr>
          </tbody>
        </table>

        <h3>Assertion Operators</h3>
        <table class="pm-docs-table">
          <tbody>
          <tr><td><code>eq</code> / <code>neq</code></td><td>Equal / Not equal</td></tr>
          <tr><td><code>gt</code> / <code>gte</code> / <code>lt</code> / <code>lte</code></td><td>Greater than / Greater or equal / Less than / Less or equal</td></tr>
          <tr><td><code>in</code> / <code>nin</code></td><td>Value in list / Not in list</td></tr>
          <tr><td><code>contains</code> / <code>notContains</code></td><td>String contains / Not contains</td></tr>
          <tr><td><code>isNull</code> / <code>isNotNull</code></td><td>Value is null / Not null</td></tr>
          <tr><td><code>isEmpty</code> / <code>isNotEmpty</code></td><td>Empty (null or length 0) / Not empty</td></tr>
          <tr><td><code>matches</code></td><td>Regex match</td></tr>
          </tbody>
        </table>

        <h3>File Upload (multipart/form-data)</h3>
        <p>Upload files via the Body tab (multipart type). Reference uploaded files in field values with <code>@file(filename)</code>.</p>

        <h3>Performance Data Files</h3>
        <p>Parameterize performance test requests with external data. Each data file is a <strong>TSV</strong> (tab-separated) file where each column maps to a variable name.</p>
        <table class="pm-docs-table">
          <tbody>
          <tr><td><strong>Variables</strong></td><td>Comma-separated column names, e.g. <code>articleId,userId</code></td></tr>
          <tr><td><strong>Filename</strong></td><td>TSV file placed next to the compiled binary</td></tr>
          <tr><td><strong>Mode</strong></td><td><code>sequential</code> (round-robin rows) or <code>random</code></td></tr>
          </tbody>
        </table>
        <p v-pre>Use <code>{{variableName}}</code> in testcase URL, headers, or body to reference data file values. Each virtual user picks a row from the TSV file per request.</p>
        <p>Example TSV file (<code>data.tsv</code>):</p>
        <pre class="pm-docs-code">article001	user001
article002	user002
article003	user003</pre>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  DashboardOutlined,
  ExperimentOutlined,
  OrderedListOutlined,
  HistoryOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
  ProjectOutlined,
  DownOutlined,
  SettingOutlined,
  CheckOutlined,
  UserOutlined,
  LogoutOutlined,
  ReadOutlined,
} from '@ant-design/icons-vue'
import { useProjectStore } from '../../stores/project.ts'
import { useAuthStore } from '../../stores/auth.ts'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const authStore = useAuthStore()
const docsVisible = ref(false)

const navTabs = [
  { key: 'dashboard', label: 'Dashboard', short: 'Home', icon: DashboardOutlined },
  { key: 'testcases', label: 'Collections', short: 'Cases', icon: ExperimentOutlined },
  { key: 'testplans', label: 'Plans', short: 'Plans', icon: OrderedListOutlined },
  { key: 'executions', label: 'Tasks', short: 'Tasks', icon: HistoryOutlined },
  { key: 'schedules', label: 'Schedules', short: 'Cron', icon: ClockCircleOutlined },
  { key: 'perf', label: 'Load Test', short: 'Perf', icon: ThunderboltOutlined },
]

const currentRoute = computed(() => {
  const name = route.name as string
  if (name === 'ExecutionDetail') return 'executions'
  return route.path.split('/')[1] || 'dashboard'
})

function onMenuClick(key: string) {
  router.push(`/${key}`)
}

function onProjectSwitch({ key }: { key: string }) {
  if (key === 'manage') {
    projectStore.clearCurrentProject()
    router.push('/projects')
    return
  }
  const id = Number(key)
  if (id !== projectStore.currentProjectId) {
    projectStore.setCurrentProject(id)
  }
}

function onUserMenuClick({ key }: { key: string }) {
  if (key === 'docs') {
    docsVisible.value = true
  } else if (key === 'admin') {
    router.push('/admin')
  } else if (key === 'logout') {
    authStore.logout()
    router.replace('/login')
  }
}

onMounted(() => { projectStore.fetchProjects() })
</script>

<style scoped>
.pm-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-deep);
  color: var(--text);
}

/* Top bar */
.pm-topbar {
  height: 48px;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 16px;
  flex-shrink: 0;
}
.pm-topbar-left {
  width: 140px;
  flex-shrink: 0;
}
.pm-logo {
  font-size: 18px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: 1px;
}
.pm-topbar-center {
  flex: 1;
  display: flex;
  gap: 2px;
  justify-content: center;
}
.pm-nav-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-3);
  transition: all 0.15s;
}
.pm-nav-tab:hover {
  color: var(--text);
  background: var(--bg-hover);
}
.pm-nav-tab.active {
  color: #fff;
  background: var(--accent);
}
.pm-nav-icon {
  font-size: 14px;
}
.pm-topbar-right {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: flex-end;
}
.pm-user-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-2);
  font-size: 13px;
  transition: all 0.15s;
}
.pm-user-btn:hover {
  color: var(--text);
  background: var(--bg-hover);
}
.pm-user-name {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pm-project-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 14px;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text);
  font-size: 13px;
  transition: all 0.15s;
  border: 1px solid var(--border);
  background: var(--bg-deep);
}
.pm-project-btn:hover {
  background: var(--bg-hover);
  border-color: var(--accent);
}
.pm-project-btn-icon {
  font-size: 14px;
  color: var(--accent);
}
.pm-project-btn-name {
  font-weight: 600;
  font-size: 13px;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Project dropdown */
.pm-project-dropdown {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
  min-width: 220px;
  padding: 4px 0;
  overflow: hidden;
}
.pm-project-dropdown-header {
  padding: 10px 16px 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-3);
}
.pm-project-dropdown-list {
  padding: 2px 0;
}
.pm-project-dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 16px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-2);
  transition: all 0.12s;
}
.pm-project-dropdown-item:hover {
  background: var(--bg-hover);
  color: var(--text);
}
.pm-project-dropdown-item.is-active {
  color: var(--accent);
  font-weight: 600;
  background: rgba(255, 108, 55, 0.08);
}
.pm-project-check {
  font-size: 12px;
  color: var(--accent);
  flex-shrink: 0;
  width: 14px;
}
.pm-project-check-placeholder {
  width: 14px;
  flex-shrink: 0;
}
.pm-project-item-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pm-project-dropdown-divider {
  height: 1px;
  background: var(--border);
  margin: 4px 12px;
}
.pm-project-manage {
  color: var(--text-3);
  font-size: 12px;
}
.pm-project-manage:hover {
  color: var(--text);
}

/* Docs modal */
.pm-docs h3 { font-size: 14px; font-weight: 600; margin: 18px 0 8px; color: var(--text); }
.pm-docs h3:first-child { margin-top: 0; }
.pm-docs p { font-size: 13px; color: var(--text-2); line-height: 1.6; margin: 0 0 8px; }
.pm-docs code { background: var(--bg-deep); color: var(--accent); padding: 1px 5px; border-radius: 3px; font-size: 12px; }
.pm-docs-table { width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 8px; }
.pm-docs-table td { padding: 5px 10px; border-bottom: 1px solid var(--border); color: var(--text-2); }
.pm-docs-table td:first-child { white-space: nowrap; width: 45%; }
.pm-docs-table td:first-child code { font-size: 12px; }
.pm-docs-code { background: var(--bg-deep); color: var(--text); font-family: 'SF Mono', Monaco, Menlo, Consolas, monospace; font-size: 12px; line-height: 1.6; padding: 12px; border-radius: 6px; border: 1px solid var(--border); white-space: pre-wrap; overflow-x: auto; margin: 0; }

/* Bottom bar — hidden on desktop */
.pm-bottombar { display: none; }

/* Mobile responsive */
@media (max-width: 768px) {
  .pm-topbar { padding: 0 12px; height: 44px; }
  .pm-topbar-left { width: auto; }
  .pm-logo { font-size: 15px; }
  .pm-topbar-center { display: none; }
  .pm-topbar-right { gap: 6px; flex: 1; justify-content: flex-end; }
  .pm-project-btn { padding: 4px 8px; font-size: 11px; }
  .pm-project-btn-name { max-width: 80px; font-size: 11px; }
  .pm-user-btn { padding: 4px 6px; }
  .pm-user-name { display: none; }

  .pm-main { padding-bottom: 56px; }

  .pm-bottombar {
    display: flex;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 56px;
    background: var(--bg-panel);
    border-top: 1px solid var(--border);
    z-index: 100;
    justify-content: space-around;
    align-items: center;
    padding: 0 4px;
  }
  .pm-bottom-tab {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 4px 8px;
    cursor: pointer;
    border-radius: 8px;
    transition: all 0.15s;
    min-width: 48px;
  }
  .pm-bottom-icon { font-size: 20px; color: #888; transition: color 0.15s; }
  .pm-bottom-label { font-size: 9px; color: #888; transition: color 0.15s; }
  .pm-bottom-tab.active .pm-bottom-icon { color: #FF6C37; }
  .pm-bottom-tab.active .pm-bottom-label { color: #FF6C37; }
}

/* Main content */
.pm-main {
  flex: 1;
  /* `auto` vertical so long pages (perf run detail, testcase list) scroll;
   * `hidden` horizontal so wide tables expose their own horizontal scroll
   * inside .ant-table-wrapper instead of pushing the whole viewport. */
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--bg-deep);
}
</style>
