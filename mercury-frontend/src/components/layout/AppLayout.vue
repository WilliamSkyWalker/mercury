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
        <a-dropdown v-model:open="userMenuOpen" :trigger="['click']">
          <div class="pm-project-btn">
            <ProjectOutlined class="pm-project-btn-icon" />
            <span class="pm-project-btn-name">{{ projectStore.currentProject?.name || t('common.project') }}</span>
            <DownOutlined style="font-size: 10px; opacity: 0.6" />
          </div>
          <template #overlay>
            <div class="pm-project-dropdown">
              <div class="pm-project-dropdown-header">{{ t('nav.switchProject') }}</div>
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
                <span>{{ t('nav.manageProjects') }}</span>
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
                <ReadOutlined /> {{ t('nav.referenceDocs') }}
              </a-menu-item>
              <a-menu-item key="settings">
                <GlobalOutlined /> {{ t('nav.settings') }}
              </a-menu-item>
              <a-menu-divider />
              <a-menu-item v-if="authStore.user?.is_admin" key="admin">
                <SettingOutlined /> {{ t('common.admin') }}
              </a-menu-item>
              <a-menu-divider v-if="authStore.user?.is_admin" />
              <a-menu-item key="logout">
                <LogoutOutlined /> {{ t('nav.logout') }}
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

    <!-- Settings Modal -->
    <a-modal v-model:open="settingsVisible" :title="t('settings.title')" width="480px" :footer="null">
      <a-form layout="vertical">
        <a-form-item :label="t('settings.language')">
          <p class="pm-settings-description">{{ t('settings.languageDescription') }}</p>
          <a-radio-group :value="locale" button-style="solid" @change="onLocaleChange">
            <a-radio-button value="zh-CN">{{ t('settings.chinese') }}</a-radio-button>
            <a-radio-button value="en-US">{{ t('settings.english') }}</a-radio-button>
          </a-radio-group>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- Reference Docs Modal -->
    <a-modal v-model:open="docsVisible" :title="t('docs.title')" width="720px" :footer="null">
      <div class="pm-docs">
        <h3>{{ t('docs.scriptLanguage') }}</h3>
        <p>{{ t('docs.scriptLanguageDescription') }}</p>

        <h3>{{ t('docs.mercuryApi') }}</h3>
        <table class="pm-docs-table">
          <tbody>
          <tr><td><code>mercury.getVar(name)</code></td><td>{{ t('docs.getRuntimeVar') }}</td></tr>
          <tr><td><code>mercury.setVar(name, value)</code></td><td>{{ t('docs.setRuntimeVar') }}</td></tr>
          <tr><td><code>mercury.getEnvVar(name)</code></td><td>{{ t('docs.getEnvVar') }}</td></tr>
          <tr><td><code>mercury.getEnvName()</code></td><td>{{ t('docs.getEnvName') }}</td></tr>
          </tbody>
        </table>

        <h3>{{ t('docs.requestObject') }}</h3>
        <table class="pm-docs-table">
          <tbody>
          <tr><td><code>req.url</code></td><td>{{ t('docs.requestUrl') }}</td></tr>
          <tr><td><code>req.method</code></td><td>{{ t('docs.httpMethod') }}</td></tr>
          <tr><td><code>req.headers</code></td><td>{{ t('docs.headersDict') }}</td></tr>
          <tr><td><code>req.body</code></td><td>{{ t('docs.requestBody') }}</td></tr>
          </tbody>
        </table>

        <h3>{{ t('docs.responseObject') }}</h3>
        <table class="pm-docs-table">
          <tbody>
          <tr><td><code>res.status</code></td><td>{{ t('docs.statusCode') }}</td></tr>
          <tr><td><code>res.body</code></td><td>{{ t('docs.responseBody') }}</td></tr>
          <tr><td><code>res.headers</code></td><td>{{ t('docs.responseHeaders') }}</td></tr>
          </tbody>
        </table>

        <h3>{{ t('docs.availableModules') }}</h3>
        <p>{{ t('docs.modulesDescription') }}</p>

        <h3>{{ t('docs.scriptExample') }}</h3>
        <pre class="pm-docs-code"># Pre-request: modify headers per environment
if mercury.getEnvName() in ("prod_visit", "newtest_visit"):
    req.headers.pop("Authorization", None)
    req.headers["visitor_identity"] = mercury.getEnvVar("visitor_identity")

# Post-response: extract token for subsequent cases
token = res.body.access_token
mercury.setVar("token", token)
payload = json.loads(base64.b64decode(token.split('.')[1] + '=='))
mercury.setVar("userId", payload["sub"])</pre>

        <h3>{{ t('docs.variableSubstitution') }}</h3>
        <p>{{ t('docs.variableSubstitutionDescription') }}</p>

        <h3>{{ t('docs.assertionFields') }}</h3>
        <table class="pm-docs-table">
          <tbody>
          <tr><td><code>res.status</code></td><td>{{ t('docs.statusCode') }}</td></tr>
          <tr><td><code>res.responseTime</code></td><td>{{ t('docs.responseDuration') }}</td></tr>
          <tr><td><code>res.body</code></td><td>{{ t('docs.entireResponseBody') }}</td></tr>
          <tr><td><code>res.body.data.id</code></td><td>{{ t('docs.nestedFieldAccess') }}</td></tr>
          <tr><td><code>res.body.items[0].name</code></td><td>{{ t('docs.arrayIndexAccess') }}</td></tr>
          <tr><td><code>res.body.items[*].status</code></td><td>{{ t('docs.wildcardAccess') }}</td></tr>
          <tr><td><code>res.body.data.length</code></td><td>{{ t('docs.arrayStringLength') }}</td></tr>
          <tr><td><code>res.headers.x-trace-id</code></td><td>{{ t('docs.caseInsensitiveHeader') }}</td></tr>
          </tbody>
        </table>

        <h3>{{ t('docs.commonExamples') }}</h3>
        <table class="pm-docs-table">
          <tbody>
          <tr><td><code>res.status</code> <code>eq</code> <code>200</code></td><td>{{ t('docs.statusIs200') }}</td></tr>
          <tr><td><code>res.responseTime</code> <code>lte</code> <code>1000</code></td><td>{{ t('docs.responseWithin') }}</td></tr>
          <tr><td><code>res.body.data.length</code> <code>gt</code> <code>0</code></td><td>{{ t('docs.atLeastOne') }}</td></tr>
          <tr><td><code>res.body.data.length</code> <code>eq</code> <code>10</code></td><td>{{ t('docs.exactlyTen') }}</td></tr>
          <tr><td><code>res.body.total</code> <code>gte</code> <code>100</code></td><td>{{ t('docs.numericAtLeast') }}</td></tr>
          <tr><td><code>res.body.name</code> <code>contains</code> <code>"test"</code></td><td>{{ t('docs.stringContains') }}</td></tr>
          <tr><td><code>res.body.items[*].status</code> <code>eq</code> <code>"active"</code></td><td>{{ t('docs.allActive') }}</td></tr>
          <tr><td><code>res.body.data.name</code> <code>eq</code> <code>"Alice"</code></td><td>{{ t('docs.jsonKeyValue') }}</td></tr>
          <tr><td><code>res.body.data.tags[1]</code> <code>eq</code> <code>"vip"</code></td><td>{{ t('docs.arrayElement') }}</td></tr>
          <tr><td><code>res.body.code</code> <code>eq</code> <code>0</code></td><td>{{ t('docs.topLevelKey') }}</td></tr>
          </tbody>
        </table>

        <h3>{{ t('docs.assertionOperators') }}</h3>
        <table class="pm-docs-table">
          <tbody>
          <tr><td><code>eq</code> / <code>neq</code></td><td>{{ t('docs.equalNotEqual') }}</td></tr>
          <tr><td><code>gt</code> / <code>gte</code> / <code>lt</code> / <code>lte</code></td><td>{{ t('docs.comparisons') }}</td></tr>
          <tr><td><code>in</code> / <code>nin</code></td><td>{{ t('docs.listMembership') }}</td></tr>
          <tr><td><code>contains</code> / <code>notContains</code></td><td>{{ t('docs.stringContainment') }}</td></tr>
          <tr><td><code>isNull</code> / <code>isNotNull</code></td><td>{{ t('docs.nullChecks') }}</td></tr>
          <tr><td><code>isEmpty</code> / <code>isNotEmpty</code></td><td>{{ t('docs.emptyChecks') }}</td></tr>
          <tr><td><code>matches</code></td><td>{{ t('docs.regexMatch') }}</td></tr>
          </tbody>
        </table>

        <h3>{{ t('docs.fileUpload') }}</h3>
        <p>{{ t('docs.fileUploadDescription') }}</p>

        <h3>{{ t('docs.performanceFiles') }}</h3>
        <p>{{ t('docs.performanceFilesDescription') }}</p>
        <table class="pm-docs-table">
          <tbody>
          <tr><td><strong>{{ t('docs.variables') }}</strong></td><td>{{ t('docs.variablesDescription') }}</td></tr>
          <tr><td><strong>{{ t('docs.filename') }}</strong></td><td>{{ t('docs.filenameDescription') }}</td></tr>
          <tr><td><strong>{{ t('docs.mode') }}</strong></td><td>{{ t('docs.modeDescription') }}</td></tr>
          </tbody>
        </table>
        <p>{{ t('docs.testcaseVariableDescription') }}</p>
        <p>{{ t('docs.exampleTsv') }}</p>
        <pre class="pm-docs-code">article001	user001
article002	user002
article003	user003</pre>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
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
  GlobalOutlined,
} from '@ant-design/icons-vue'
import { useProjectStore } from '../../stores/project.ts'
import { useAuthStore } from '../../stores/auth.ts'
import { setAppLocale, type AppLocale } from '../../locales'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const authStore = useAuthStore()
const { t, locale } = useI18n()
const docsVisible = ref(false)
const settingsVisible = ref(false)
const userMenuOpen = ref(false)

const navTabs = computed(() => [
  { key: 'dashboard', label: t('nav.dashboard'), short: t('nav.home'), icon: DashboardOutlined },
  { key: 'testcases', label: t('nav.collections'), short: t('nav.cases'), icon: ExperimentOutlined },
  { key: 'testplans', label: t('nav.plans'), short: t('nav.plans'), icon: OrderedListOutlined },
  { key: 'executions', label: t('nav.tasks'), short: t('nav.tasks'), icon: HistoryOutlined },
  { key: 'schedules', label: t('nav.schedules'), short: t('nav.cron'), icon: ClockCircleOutlined },
  { key: 'perf', label: t('nav.loadTest'), short: t('nav.perf'), icon: ThunderboltOutlined },
])

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

async function onUserMenuClick({ key, domEvent }: { key: string | number; domEvent?: Event }) {
  domEvent?.stopPropagation()
  userMenuOpen.value = false
  await nextTick()
  const menuKey = String(key)

  if (menuKey === 'docs') {
    settingsVisible.value = false
    docsVisible.value = true
  } else if (menuKey === 'settings') {
    docsVisible.value = false
    settingsVisible.value = true
  } else if (menuKey === 'admin') {
    router.push('/admin')
  } else if (menuKey === 'logout') {
    authStore.logout()
    router.replace('/login')
  }
}

function onLocaleChange(event: { target: { value: AppLocale } }) {
  setAppLocale(event.target.value)
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
.pm-settings-description { color: var(--text-3); margin: 0 0 12px; }

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
