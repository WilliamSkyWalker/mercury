<template>
  <div class="pm-editor">
    <!-- Request URL bar -->
    <div class="pm-url-bar">
      <a-select
        v-if="!isWsCase"
        v-model:value="form.method"
        class="pm-method-select"
        :dropdown-match-select-width="false"
        popupClassName="pm-dropdown"
      >
        <a-select-option v-for="m in methods" :key="m" :value="m">
          <span :class="`pm-method-${m.toLowerCase()}`">{{ m }}</span>
        </a-select-option>
      </a-select>
      <span v-else class="pm-method-select pm-method-ws-badge" :title="t('testcase.websocketCase')">WS</span>
      <input
        v-model="form.url"
        class="pm-url-input"
        :placeholder="t('testcase.enterUrl')"
        @keydown.enter="onRun"
      />
      <button class="pm-send-btn" :disabled="running" @click="onRun">
        <span v-if="running" class="pm-sending">{{ t('testcase.sending') }}</span>
        <span v-else>{{ t('testcase.send') }}</span>
      </button>
      <button class="pm-save-btn" :disabled="saving" @click="onSave">{{ t('common.save') }}</button>
      <button class="pm-curl-btn" @click="onCopyAsCurl" :title="t('testcase.copyCurl')">cURL</button>
    </div>

    <!-- Case name -->
    <div class="pm-name-row">
      <input v-model="form.case_name" class="pm-name-input" :placeholder="t('testcase.requestName')" />
      <div class="pm-timeout-group" :title="t('testcase.timeout')">
        <span class="pm-timeout-label">{{ t('testcase.timeout') }}</span>
        <input
          v-model.number="form.timeout"
          type="number"
          min="1"
          max="600"
          class="pm-timeout-input"
        />
        <span class="pm-timeout-unit">s</span>
      </div>
      <div class="pm-env-group">
        <a-select v-model:value="selectedEnvId" :placeholder="t('testcase.noEnvironment')" allow-clear class="pm-env-select" popupClassName="pm-dropdown">
          <a-select-option v-for="env in envs" :key="env.id" :value="env.id">{{ env.name }}</a-select-option>
        </a-select>
        <button class="pm-env-manage-btn" :title="t('testcase.manageEnvironments')" @click="envDrawer.visible = true; loadEnvList()">
          <SettingOutlined />
        </button>
      </div>
    </div>

    <!-- Request config tabs -->
    <div class="pm-content">
      <div class="pm-request-section">
        <div class="pm-tabs">
          <div
            v-for="tab in requestTabs"
            :key="tab.key"
            :class="['pm-tab', { active: activeTab === tab.key }]"
            @click="activeTab = tab.key"
          >
            {{ tab.label }}
            <span v-if="tab.count" class="pm-tab-count">{{ tab.count }}</span>
          </div>
        </div>
        <div class="pm-tab-content">
          <div v-show="activeTab === 'params'">
            <HeaderEditor v-model="form.params" :label="t('testcase.param')" />
          </div>
          <div v-show="activeTab === 'headers'">
            <HeaderEditor v-model="form.headers" :label="t('testcase.header')" />
          </div>
          <div v-show="activeTab === 'steps'">
            <WsStepsEditor v-model="form.ws_steps" />
          </div>
          <div v-show="activeTab === 'body'">
            <div class="pm-body-type-bar">
              <label v-for="bt in bodyTypes" :key="bt.value" :class="['pm-body-type', { active: form.body_type === bt.value }]">
                <input type="radio" :value="bt.value" v-model="form.body_type" hidden />
                {{ bt.label }}
              </label>
            </div>
            <textarea
              v-if="form.body_type === 'json' || form.body_type === 'raw'"
              :value="bodyText"
              @input="onBodyChange(($event.target as HTMLTextAreaElement).value)"
              class="pm-code-textarea"
              rows="10"
              placeholder='{"key": "value"}'
              spellcheck="false"
            ></textarea>
            <HeaderEditor v-if="form.body_type === 'form'" v-model="formBody" :label="t('testcase.field')" />
            <div v-if="form.body_type === 'multipart'">
              <HeaderEditor v-model="multipartBody" :label="t('testcase.field')" />
              <div class="pm-multipart-files">
                <div v-for="(f, i) in multipartFiles" :key="i" class="pm-file-item">
                  <span class="pm-file-name">{{ f.name }}</span>
                  <span class="pm-file-size">{{ (f.size / 1024).toFixed(1) }}KB</span>
                  <a class="pm-file-remove" @click="removeFile(i)">{{ t('common.delete') }}</a>
                </div>
                <div v-if="props.caseId" class="pm-file-upload">
                  <input type="file" ref="fileInput" style="display:none" @change="onFileSelected" />
                  <a-button size="small" @click="($refs.fileInput as HTMLInputElement)?.click()">
                    <UploadOutlined /> {{ t('common.uploadFile') }}
                  </a-button>
                  <span class="pm-file-hint">{{ t('testcase.fileReferenceHint') }}</span>
                </div>
                <div v-else class="pm-file-hint">{{ t('testcase.saveBeforeUpload') }}</div>
              </div>
            </div>
            <div v-if="form.body_type === 'none'" class="pm-empty-body">{{ t('testcase.noBody') }}</div>
          </div>
          <div v-show="activeTab === 'assertions'">
            <AssertionEditor v-model="form.assertions" />
          </div>
          <div v-show="activeTab === 'pre-script'">
            <ScriptEditor v-model="form.pre_request_script" :placeholder="t('testcase.scriptPrePlaceholder')" />
          </div>
          <div v-show="activeTab === 'post-script'">
            <ScriptEditor v-model="form.post_request_script" :placeholder="t('testcase.scriptPostPlaceholder')" />
          </div>
        </div>
      </div>

      <!-- Response section -->
      <div class="pm-response-section" v-if="runResult">
        <div class="pm-response-bar">
          <span class="pm-response-title">{{ t('testcase.response') }}</span>
          <div class="pm-response-meta">
            <span :class="['pm-status-badge', runResult.status === 'passed' ? 'success' : 'error']">
              {{ runResult.response?.status || t('common.error') }}
            </span>
            <span class="pm-meta-item">{{ runResult.duration_ms }}ms</span>
            <template v-if="runResult.response?.stream_metrics">
              <span class="pm-meta-item" :title="t('testcase.timeToFirstToken')">TTFT {{ runResult.response.stream_metrics.first_token_ms }}ms</span>
              <span class="pm-meta-item">{{ runResult.response.stream_metrics.token_count }} tok</span>
              <span v-if="runResult.response.stream_metrics.tokens_per_sec != null" class="pm-meta-item">{{ runResult.response.stream_metrics.tokens_per_sec }} tok/s</span>
            </template>
          </div>
        </div>
        <div class="pm-response-tabs">
          <div
            v-for="rt in responseTabs"
            :key="rt.key"
            :class="['pm-tab', { active: responseTab === rt.key }]"
            @click="responseTab = rt.key"
          >
            {{ rt.label }}
          </div>
        </div>
        <div class="pm-response-content">
          <div v-if="runResult.error_message" class="pm-error-banner">{{ runResult.error_message }}</div>
          <div v-if="wsTranscript" v-show="responseTab === 'transcript'" class="pm-ws-transcript">
            <div
              v-for="(entry, i) in wsTranscript"
              :key="i"
              :class="['pm-ws-entry', `pm-ws-dir-${entry.dir}`]"
            >
              <span class="pm-ws-ts">{{ entry.t_ms }}ms</span>
              <span class="pm-ws-arrow">{{ wsArrow(entry.dir) }}</span>
              <span class="pm-ws-dir-label">{{ wsDirLabel(entry) }}</span>
              <pre v-if="entry.data !== undefined" class="pm-ws-data">{{ formatBody(entry.data) }}</pre>
              <span v-else-if="entry.note" class="pm-ws-note">{{ entry.note }}</span>
              <span v-else-if="entry.dir === 'close'" class="pm-ws-note">code={{ entry.code }}{{ entry.reason ? ' reason=' + entry.reason : '' }}</span>
              <span v-else-if="entry.dir === 'wait'" class="pm-ws-note">{{ entry.duration_ms }}ms</span>
              <span v-else-if="entry.dir === 'handshake'" class="pm-ws-note">HTTP {{ entry.status }}</span>
            </div>
            <div v-if="runResult.response?.stream_metrics?.transcript_truncated" class="pm-ws-truncated">
              {{ t('testcase.transcriptTruncated') }}
            </div>
          </div>
          <div v-show="responseTab === 'body'">
            <pre class="pm-response-body">{{ formatBody(runResult.response?.body) }}</pre>
          </div>
          <div v-show="responseTab === 'assertions'">
            <div v-for="(a, i) in runResult.assertion_results" :key="i" class="pm-assertion-item">
              <CheckCircleFilled v-if="a.passed" style="color: #49cc90" />
              <CloseCircleFilled v-else style="color: #f93e3e" />
              <code>{{ a.field }} {{ a.operator }} {{ JSON.stringify(a.expected) }}</code>
              <span v-if="!a.passed" class="pm-actual">{{ t('testcase.actual') }}: {{ JSON.stringify(a.actual) }}</span>
            </div>
            <div v-if="!runResult.assertion_results?.length" class="pm-empty-body">{{ t('testcase.noAssertions') }}</div>
          </div>
          <div v-show="responseTab === 'variables'">
            <pre class="pm-response-body">{{ JSON.stringify(runResult.extracted_variables, null, 2) }}</pre>
          </div>
          <div v-show="responseTab === 'request'">
            <div class="pm-req-summary">{{ runResult.request?.method }} {{ runResult.request?.url }}</div>
            <pre v-if="runResult.request?.body" class="pm-response-body">{{ formatBody(runResult.request.body) }}</pre>
          </div>
        </div>
      </div>
      <div v-else class="pm-response-placeholder">
        <div class="pm-placeholder-content">
          <SendOutlined style="font-size: 40px; color: var(--text-3)" />
          <p>{{ t('testcase.sendForResponse') }}</p>
        </div>
      </div>
    </div>

    <!-- Environment Management Drawer -->
    <a-drawer
      v-model:open="envDrawer.visible"
      :title="t('testcase.environments')"
      width="600px"
      :bodyStyle="{ padding: '16px' }"
    >
      <template #extra>
        <a-button type="primary" size="small" @click="openEnvModal()">+ {{ t('common.new') }}</a-button>
      </template>

      <a-spin :spinning="envDrawer.loading">
        <div v-for="env in envDrawer.list" :key="env.id" class="pm-env-card">
          <div class="pm-env-card-header">
            <span class="pm-env-card-name">{{ env.name }}</span>
            <a-space>
              <a class="pm-env-card-action" @click="openEnvModal(env)">{{ t('common.edit') }}</a>
              <a class="pm-env-card-action" @click="onCopyEnv(env)">{{ t('common.copy') }}</a>
              <a-popconfirm :title="t('testcase.deleteEnvironmentConfirm')" @confirm="onDeleteEnv(env.id)">
                <a class="pm-env-card-action danger">{{ t('common.delete') }}</a>
              </a-popconfirm>
            </a-space>
          </div>
          <div class="pm-env-card-vars">
            <span v-for="(v, k) in env.variables" :key="k" class="pm-var-tag">{{ k }}: {{ v }}</span>
            <span v-if="!Object.keys(env.variables || {}).length" class="pm-env-empty">{{ t('testcase.noVariables') }}</span>
          </div>
        </div>
        <div v-if="!envDrawer.list.length && !envDrawer.loading" class="pm-env-empty-state">
          {{ t('testcase.noEnvironments') }}
        </div>
      </a-spin>
    </a-drawer>

    <!-- Env Edit Modal -->
    <a-modal
      v-model:open="envModal.visible"
      :title="envModal.editId ? t('testcase.editEnvironment') : t('testcase.newEnvironment')"
      :confirm-loading="envModal.saving"
      @ok="onSaveEnv"
      width="500px"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('common.name')">
          <a-input v-model:value="envModal.name" :placeholder="t('testcase.environmentName')" />
        </a-form-item>
        <a-form-item>
          <template #label>
            <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
              <span>{{ t('common.variables') }}</span>
              <a style="font-size: 12px;" @click="toggleBulkMode">{{ envModal.bulkMode ? t('testcase.keyValueMode') : t('testcase.bulkEdit') }}</a>
            </div>
          </template>
          <template v-if="envModal.bulkMode">
            <textarea
              v-model="envModal.bulkText"
              class="pm-code-textarea"
              rows="12"
              :placeholder="t('testcase.bulkPlaceholder')"
              spellcheck="false"
            ></textarea>
          </template>
          <template v-else>
            <div v-for="(_, index) in envModal.vars" :key="index" style="display: flex; gap: 8px; margin-bottom: 8px;">
              <a-input v-model:value="envModal.vars[index].key" :placeholder="t('common.key')" style="width: 180px" />
              <a-input v-model:value="envModal.vars[index].value" :placeholder="t('common.value')" style="flex: 1" />
              <a-button danger size="small" @click="envModal.vars.splice(index, 1)">×</a-button>
            </div>
            <a-button type="dashed" block @click="envModal.vars.push({ key: '', value: '' })">+ {{ t('testcase.addVariable') }}</a-button>
          </template>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { CheckCircleFilled, CloseCircleFilled, SendOutlined, SettingOutlined, UploadOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import HeaderEditor from './HeaderEditor.vue'
import AssertionEditor from './AssertionEditor.vue'
import ScriptEditor from './ScriptEditor.vue'
import WsStepsEditor from './WsStepsEditor.vue'
import { testcaseApi, type Testcase, type RunResult, type WsStep } from '../../api/testcases.ts'
import { envApi, type Env } from '../../api/envs.ts'
import { useEnvStore } from '../../stores/env.ts'
import { useProjectStore } from '../../stores/project.ts'

const props = defineProps<{
  caseId: number | null
  folderId: number | null
}>()

const emit = defineEmits<{
  saved: []
}>()

const envStore = useEnvStore()
const projectStore = useProjectStore()
const { t } = useI18n()
const envs = computed(() => envStore.envs)

const methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
const bodyTypes = computed(() => [
  { value: 'none', label: t('common.none') },
  { value: 'json', label: t('testcase.rawJson') },
  { value: 'form', label: t('testcase.formUrlEncoded') },
  { value: 'multipart', label: t('testcase.multipart') },
  { value: 'raw', label: t('testcase.rawText') },
])

const activeTab = ref('params')
const responseTab = ref('body')
const selectedEnvId = ref<number>()
const running = ref(false)
const saving = ref(false)
const runResult = ref<RunResult | null>(null)

const form = reactive({
  case_name: '', method: 'GET', url: '', headers: [] as { key: string; value: string; enabled: boolean }[], params: [] as { key: string; value: string; enabled: boolean }[],
  body_type: 'none', body: {} as any, assertions: [] as { field: string; operator: string; expected: any }[], pre_request_script: '',
  post_request_script: '', script_type: 'python', timeout: 30, folder: null as number | null,
  sort_order: 0, tags: [] as string[], comment: '',
  ws_steps: null as WsStep[] | null,
})

// WS detection. Two signals: a literal ws:// / wss:// in the URL, or a
// {{var}} prefix whose resolved value (from the currently selected env) is
// ws/wss. We also fall back to "has ws_steps" so an existing WS case still
// renders the Steps tab even when no env is picked yet.
const isWsCase = computed(() => {
  const url = (form.url || '').trim()
  if (/^wss?:\/\//i.test(url)) return true

  const placeholder = url.match(/^\{\{(\w+)\}\}/)
  if (placeholder && selectedEnvId.value != null) {
    const env = envs.value.find((e: any) => e.id === selectedEnvId.value)
    const resolved = env?.variables?.[placeholder[1]]
    if (typeof resolved === 'string' && /^wss?:\/\//i.test(resolved)) return true
  }

  if (Array.isArray(form.ws_steps) && form.ws_steps.length > 0) return true
  return false
})

const requestTabs = computed(() => {
  const tabs: Array<{ key: string; label: string; count?: number }> = [
    { key: 'params', label: t('testcase.params'), count: (form.params as any[])?.filter((p: any) => p.key).length || 0 },
    { key: 'headers', label: t('testcase.headers'), count: (form.headers as any[])?.filter((h: any) => h.key).length || 0 },
  ]
  if (isWsCase.value) {
    tabs.push({ key: 'steps', label: t('testcase.steps'), count: (form.ws_steps as any[])?.length || 0 })
  } else {
    tabs.push({ key: 'body', label: t('common.body') })
  }
  tabs.push({ key: 'assertions', label: t('testcase.tests'), count: (form.assertions as any[])?.length || 0 })
  tabs.push({ key: 'pre-script', label: t('testcase.preRequest') })
  tabs.push({ key: 'post-script', label: t('testcase.postResponse') })
  return tabs
})

// Keep activeTab consistent when user toggles between WS and HTTP URLs.
watch(isWsCase, (ws) => {
  if (ws && activeTab.value === 'body') activeTab.value = 'steps'
  if (!ws && activeTab.value === 'steps') activeTab.value = 'body'
})

const wsTranscript = computed<any[] | null>(() => {
  const t = runResult.value?.response?.stream_metrics?.transcript
  return Array.isArray(t) ? t : null
})

const responseTabs = computed(() => {
  const tabs: Array<{ key: string; label: string; count?: number }> = []
  if (wsTranscript.value) {
    tabs.push({ key: 'transcript', label: t('testcase.transcript'), count: wsTranscript.value.length })
  }
  tabs.push({ key: 'body', label: t('common.body') })
  tabs.push({ key: 'assertions', label: t('testcase.testResults') })
  tabs.push({ key: 'variables', label: t('common.variables') })
  tabs.push({ key: 'request', label: t('common.request') })
  return tabs
})

// When a WS run lands, jump to the Transcript view by default; otherwise
// keep whatever the user was looking at.
watch(wsTranscript, (t) => {
  if (t && responseTab.value === 'body') responseTab.value = 'transcript'
})

const bodyText = ref('')
const formBody = ref<{ key: string; value: string; enabled: boolean }[]>([])
const multipartBody = ref<{ key: string; value: string; enabled: boolean }[]>([])
const multipartFiles = ref<{ name: string; size: number; s3_key: string; content_type: string }[]>([])
const fileInput = ref<HTMLInputElement>()

watch(() => props.caseId, async (id) => {
  runResult.value = null
  if (id) {
    const data = await testcaseApi.get(id)
    Object.assign(form, data)
    if (form.body_type === 'json' || form.body_type === 'raw') {
      bodyText.value = typeof form.body === 'string' ? form.body : JSON.stringify(form.body, null, 2)
    }
    if (form.body_type === 'form' && typeof form.body === 'object') {
      formBody.value = Object.entries(form.body as Record<string, string>).map(([key, value]) => ({
        key, value, enabled: true,
      }))
    }
    if (form.body_type === 'multipart' && typeof form.body === 'object') {
      multipartBody.value = Object.entries(form.body as Record<string, string>).map(([key, value]) => ({
        key, value, enabled: true,
      }))
    }
    multipartFiles.value = (data as any).files || []
  } else {
    resetForm()
  }
}, { immediate: true })

function resetForm() {
  Object.assign(form, {
    case_name: '', method: 'GET', url: '', headers: [], params: [],
    body_type: 'none', body: {}, assertions: [], pre_request_script: '',
    post_request_script: '', script_type: 'python', timeout: 30, folder: props.folderId,
    sort_order: 0, tags: [], comment: '', ws_steps: null,
  })
  bodyText.value = ''
  formBody.value = []
}

function onBodyChange(val: string) {
  bodyText.value = val
  try { form.body = JSON.parse(val) } catch { form.body = val }
}

function formatBody(body: any): string {
  if (!body) return ''
  if (typeof body === 'string') {
    try { return JSON.stringify(JSON.parse(body), null, 2) } catch { return body }
  }
  return JSON.stringify(body, null, 2)
}

function wsArrow(dir: string): string {
  if (dir === 'send') return '↑'
  if (dir === 'recv') return '↓'
  if (dir === 'close') return '×'
  if (dir === 'wait') return '⏳'
  if (dir === 'error') return '!'
  if (dir === 'handshake') return '⇄'
  return '·'
}

function wsDirLabel(entry: any): string {
  const d = entry?.dir
  if (d === 'send') return t('testcase.stepSend')
  if (d === 'recv') return t('testcase.stepReceive')
  if (d === 'close') return t('testcase.stepClose')
  if (d === 'wait') return t('testcase.stepWait')
  if (d === 'error') return entry?.kind ? `${t('common.error')} (${entry.kind})` : t('common.error')
  if (d === 'handshake') return t('testcase.handshake')
  return String(d || '')
}

async function onSave() {
  if (!form.case_name) { message.warning(t('testcase.enterCaseName')); return }
  if (!form.url) { message.warning(t('testcase.enterUrlWarning')); return }

  saving.value = true
  try {
    if (form.body_type === 'form') {
      form.body = Object.fromEntries(formBody.value.filter(f => f.key).map(f => [f.key, f.value]))
    } else if (form.body_type === 'multipart') {
      form.body = Object.fromEntries(multipartBody.value.filter(f => f.key).map(f => [f.key, f.value]))
    } else if (form.body_type === 'json') {
      try { form.body = JSON.parse(bodyText.value) } catch { form.body = bodyText.value }
    }

    form.folder = props.folderId
    if (props.caseId) {
      await testcaseApi.update(props.caseId, form)
      message.success(t('common.saved'))
    } else {
      await testcaseApi.create({ ...form, project: projectStore.currentProjectId })
      message.success(t('common.createdMessage'))
    }
    emit('saved')
  } finally {
    saving.value = false
  }
}

async function onRun() {
  if (!props.caseId) { message.warning(t('testcase.saveRequestFirst')); return }
  running.value = true
  try {
    runResult.value = await testcaseApi.run(props.caseId, selectedEnvId.value)
    responseTab.value = runResult.value.error_message ? 'body' : 'body'
  } catch (e) {
    message.error(t('common.requestFailed'))
  } finally {
    running.value = false
  }
}

function copyToClipboard(text: string) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text)
  } else {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
}

function onCopyAsCurl() {
  if (!runResult.value?.request?.url) {
    message.warning(t('testcase.runFirstForCurl'))
    return
  }
  const req = runResult.value.request
  const method = req.method || 'GET'
  const url = req.url || ''
  const headerParts = Object.entries(req.headers || {}).map(([k, v]) => `-H '${k}: ${v}'`)
  let bodyPart = ''
  if (req.body) {
    const isForm = Object.entries(req.headers || {}).some(([k, v]) =>
      k.toLowerCase() === 'content-type' && String(v).includes('form-urlencoded')
    )
    let bodyStr: string
    if (typeof req.body === 'string') {
      bodyStr = req.body
    } else if (isForm) {
      bodyStr = Object.entries(req.body).map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`).join('&')
    } else {
      bodyStr = JSON.stringify(req.body)
    }
    bodyPart = `-d '${bodyStr}'`
  }
  const parts = [`curl -X ${method}`, `'${url}'`, ...headerParts]
  if (bodyPart) parts.push(bodyPart)
  const curl = parts.join(' \\\n  ')
  copyToClipboard(curl)
  message.success(t('testcase.curlCopied'))
}

// --- Multipart File Management ---
async function onFileSelected(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !props.caseId) return
  try {
    const res = await testcaseApi.uploadFile(props.caseId, file)
    multipartFiles.value.push(res)
    message.success(t('testcase.uploadedFile', { name: file.name }))
  } catch {
    message.error(t('testcase.uploadFailed'))
  }
  input.value = ''
}

async function removeFile(index: number) {
  if (!props.caseId) return
  const file = multipartFiles.value[index]
  try {
    await testcaseApi.deleteFile(props.caseId, file.name)
    multipartFiles.value.splice(index, 1)
    message.success(t('common.deleted'))
  } catch {
    message.error(t('testcase.deleteFailed'))
  }
}

// --- Environment Management ---
const envDrawer = reactive({ visible: false, loading: false, list: [] as Env[] })
const envModal = reactive({
  visible: false, saving: false, editId: null as number | null,
  name: '', vars: [] as { key: string; value: string }[],
  bulkMode: false, bulkText: '',
})

async function loadEnvList() {
  envDrawer.loading = true
  try {
    const res = await envApi.list({ project: projectStore.currentProjectId, page_size: 100 })
    envDrawer.list = res.results || res
  } finally {
    envDrawer.loading = false
  }
}

function openEnvModal(env?: Env) {
  if (env) {
    envModal.editId = env.id
    envModal.name = env.name
    envModal.vars = Object.entries(env.variables || {}).map(([key, value]) => ({ key, value: String(value) }))
  } else {
    envModal.editId = null
    envModal.name = ''
    envModal.vars = [{ key: '', value: '' }]
  }
  envModal.visible = true
}

function toggleBulkMode() {
  if (envModal.bulkMode) {
    // Bulk text → key-value pairs
    envModal.vars = envModal.bulkText.split('\n').filter(l => l.includes('=')).map(l => {
      const idx = l.indexOf('=')
      return { key: l.slice(0, idx).trim(), value: l.slice(idx + 1).trim() }
    })
  } else {
    // Key-value pairs → bulk text
    envModal.bulkText = envModal.vars.filter(v => v.key).map(v => `${v.key}=${v.value}`).join('\n')
  }
  envModal.bulkMode = !envModal.bulkMode
}

function onCopyEnv(env: Env) {
  const newName = prompt(t('testcase.newEnvironmentPrompt'), `${env.name}_copy`)
  if (!newName) return
  if (envDrawer.list.some(e => e.name === newName)) {
    message.warning(t('testcase.envNameExists'))
    return
  }
  envApi.create({ name: newName, variables: { ...env.variables }, project: projectStore.currentProjectId } as any).then(() => {
    message.success(t('common.copiedMessage'))
    loadEnvList()
    envStore.fetchEnvs()
  }).catch(() => message.error(t('testcase.copyFailed')))
}

async function onSaveEnv() {
  if (!envModal.name) { message.warning(t('testcase.nameRequired')); return }
  // Check duplicate name
  const duplicate = envDrawer.list.find(e => e.name === envModal.name && e.id !== envModal.editId)
  if (duplicate) { message.warning(t('testcase.envNameExists')); return }

  // If in bulk mode, parse text to vars first
  let variables: Record<string, string>
  if (envModal.bulkMode) {
    variables = Object.fromEntries(
      envModal.bulkText.split('\n').filter(l => l.includes('=')).map(l => {
        const idx = l.indexOf('=')
        return [l.slice(0, idx).trim(), l.slice(idx + 1).trim()]
      })
    )
  } else {
    variables = Object.fromEntries(envModal.vars.filter(v => v.key).map(v => [v.key, v.value]))
  }

  envModal.saving = true
  try {
    if (envModal.editId) {
      await envApi.update(envModal.editId, { name: envModal.name, variables })
      message.success(t('common.updatedMessage'))
    } else {
      await envApi.create({ name: envModal.name, variables, project: projectStore.currentProjectId } as any)
      message.success(t('common.createdMessage'))
    }
    envModal.visible = false
    loadEnvList()
    envStore.fetchEnvs()
  } finally {
    envModal.saving = false
  }
}

async function onDeleteEnv(id: number) {
  await envApi.delete(id)
  message.success(t('common.deleted'))
  loadEnvList()
  envStore.fetchEnvs()
}

onMounted(() => { envStore.fetchEnvs() })
</script>

<style scoped>
.pm-editor { height: 100%; display: flex; flex-direction: column; background: var(--bg-deep); color: var(--text); }

/* URL Bar */
.pm-url-bar { display: flex; align-items: center; gap: 0; padding: 12px 16px; background: var(--bg-panel); border-bottom: 1px solid var(--border); }
.pm-method-select { width: 110px; flex-shrink: 0; }
.pm-method-select :deep(.ant-select-selector) { background: var(--bg-surface) !important; border: 1px solid var(--border) !important; border-right: none !important; border-radius: 4px 0 0 4px !important; color: var(--text) !important; height: 36px !important; font-weight: 700; font-size: 13px; }
.pm-method-select :deep(.ant-select-arrow) { color: var(--text-3); }
.pm-method-get { color: var(--method-get); }
.pm-method-ws-badge {
  display: inline-flex; align-items: center; justify-content: center;
  height: 36px; box-sizing: border-box;
  background: var(--bg-surface); color: #b966ff;
  border: 1px solid var(--border); border-right: none;
  border-radius: 4px 0 0 4px;
  font-weight: 700; font-size: 13px;
  user-select: none;
}
.pm-method-post { color: var(--method-post); }
.pm-method-put { color: var(--method-put); }
.pm-method-delete { color: var(--method-delete); }
.pm-method-patch { color: var(--method-patch); }

.pm-url-input { flex: 1; height: 36px; background: var(--bg-surface); border: 1px solid var(--border); border-left: none; border-right: none; color: var(--text); font-size: 13px; font-family: 'SF Mono', Monaco, Menlo, Consolas, monospace; padding: 0 12px; outline: none; }
.pm-url-input:focus { border-color: var(--accent); }
.pm-url-input::placeholder { color: var(--placeholder); }

.pm-send-btn { height: 36px; padding: 0 20px; background: var(--accent); color: #fff; border: none; font-weight: 600; font-size: 13px; cursor: pointer; transition: background 0.15s; }
.pm-send-btn:hover { background: var(--accent-hover); }
.pm-send-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.pm-save-btn { height: 36px; padding: 0 16px; background: var(--bg-surface); color: var(--text-2); border: 1px solid var(--border); border-radius: 0 4px 4px 0; font-size: 13px; cursor: pointer; transition: all 0.15s; }
.pm-save-btn:hover { background: var(--bg-hover); color: var(--text); }
.pm-save-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.pm-curl-btn { height: 36px; padding: 0 12px; background: var(--bg-surface); color: var(--text-3); border: 1px solid var(--border); border-left: none; border-radius: 0; font-size: 11px; font-family: monospace; cursor: pointer; transition: all 0.15s; }
.pm-curl-btn:hover { background: var(--bg-hover); color: var(--accent); }

/* Name row */
.pm-name-row { display: flex; align-items: center; gap: 12px; padding: 8px 16px; background: var(--bg-panel); border-bottom: 1px solid var(--border); }
.pm-name-input { flex: 1; background: transparent; border: none; color: var(--text); font-size: 14px; outline: none; padding: 4px 0; }
.pm-name-input::placeholder { color: var(--placeholder); }

/* Env selector group */
.pm-timeout-group { display: flex; align-items: center; gap: 4px; flex-shrink: 0; margin-right: 8px; padding: 0 8px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 4px; height: 30px; }
.pm-timeout-label { color: var(--text-3); font-size: 11px; }
.pm-timeout-input { width: 50px; background: transparent; border: none; outline: none; color: var(--text); font-size: 12px; text-align: right; -moz-appearance: textfield; }
.pm-timeout-input::-webkit-outer-spin-button,
.pm-timeout-input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
.pm-timeout-unit { color: var(--text-3); font-size: 11px; }
.pm-env-group { display: flex; align-items: center; gap: 0; flex-shrink: 0; }
.pm-env-select { width: 180px; flex-shrink: 0; }
.pm-env-select :deep(.ant-select-selector) { border-radius: 4px 0 0 4px !important; height: 30px !important; font-size: 12px; }
.pm-env-select :deep(.ant-select-selection-placeholder) { color: var(--placeholder) !important; }
.pm-env-manage-btn { height: 30px; width: 30px; background: var(--bg-surface); border: 1px solid var(--border); border-left: none; border-radius: 0 4px 4px 0; color: var(--text-3); cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 12px; transition: all 0.15s; }
.pm-env-manage-btn:hover { color: var(--accent); background: var(--bg-hover); }

/* Env Drawer cards */
.pm-env-card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: 6px; padding: 12px 14px; margin-bottom: 10px; }
.pm-env-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.pm-env-card-name { font-size: 14px; font-weight: 600; color: var(--text); }
.pm-env-card-action { font-size: 12px; color: var(--link); cursor: pointer; }
.pm-env-card-action.danger { color: var(--error); }
.pm-env-card-vars { display: flex; flex-wrap: wrap; gap: 6px; }
.pm-var-tag { display: inline-block; background: var(--bg-deep); color: var(--accent); padding: 2px 8px; border-radius: 4px; font-size: 11px; font-family: monospace; }
.pm-env-empty { color: var(--text-3); font-size: 12px; }
.pm-env-empty-state { text-align: center; color: var(--text-3); padding: 40px 0; font-size: 13px; }

/* Content: request + response */
.pm-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-height: 0; }
.pm-request-section { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-height: 200px; }

/* Tabs */
.pm-tabs { display: flex; gap: 0; padding: 0 16px; background: var(--bg-panel); border-bottom: 1px solid var(--border); }
.pm-tab { padding: 8px 14px; font-size: 12px; color: var(--text-3); cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.15s; display: flex; align-items: center; gap: 4px; }
.pm-tab:hover { color: var(--text); }
.pm-tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.pm-tab-count { background: var(--bg-hover); color: var(--text-2); font-size: 10px; padding: 0 5px; border-radius: 8px; min-width: 16px; text-align: center; }
.pm-tab.active .pm-tab-count { background: var(--accent); color: #fff; }

.pm-tab-content { flex: 1; overflow: auto; padding: 12px 16px; }

/* Body type bar */
.pm-body-type-bar { display: flex; gap: 16px; margin-bottom: 12px; }
.pm-body-type { font-size: 12px; color: var(--text-3); cursor: pointer; padding: 2px 0; }
.pm-body-type.active { color: var(--accent); }
.pm-code-textarea { width: 100%; background: var(--bg-deep); border: 1px solid var(--border); border-radius: 4px; color: var(--text); font-family: 'SF Mono', Monaco, Menlo, Consolas, monospace; font-size: 13px; padding: 12px; resize: vertical; outline: none; line-height: 1.6; }
.pm-code-textarea:focus { border-color: var(--accent); }
.pm-empty-body { text-align: center; color: var(--text-3); padding: 40px 0; font-size: 13px; }
.pm-multipart-files { margin-top: 12px; padding: 10px; background: var(--bg-deep); border: 1px solid var(--border); border-radius: 4px; }
.pm-file-item { display: flex; align-items: center; gap: 10px; padding: 4px 0; font-size: 12px; }
.pm-file-name { color: var(--text); font-family: monospace; }
.pm-file-size { color: var(--text-3); }
.pm-file-remove { color: var(--error); cursor: pointer; font-size: 12px; }
.pm-file-upload { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
.pm-file-hint { color: var(--text-3); font-size: 11px; }
.pm-file-hint code { color: var(--accent); background: var(--bg-surface); padding: 1px 4px; border-radius: 2px; }

/* Response section */
.pm-response-section { border-top: 2px solid var(--border); flex-shrink: 0; max-height: 45%; display: flex; flex-direction: column; }
.pm-response-bar { display: flex; justify-content: space-between; align-items: center; padding: 8px 16px; background: var(--bg-panel); }
.pm-response-title { font-size: 12px; font-weight: 600; color: var(--text); }
.pm-response-meta { display: flex; gap: 12px; align-items: center; }
.pm-status-badge { font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 4px; }
.pm-status-badge.success { background: rgba(92, 216, 145, 0.15); color: var(--success); }
.pm-status-badge.error { background: rgba(255, 107, 107, 0.15); color: var(--error); }
.pm-meta-item { font-size: 12px; color: var(--text-3); }

.pm-response-tabs { display: flex; padding: 0 16px; background: var(--bg-panel); border-bottom: 1px solid var(--border); }
.pm-response-content { flex: 1; overflow: auto; padding: 12px 16px; }
.pm-error-banner { background: rgba(249, 62, 62, 0.12); border: 1px solid rgba(249, 62, 62, 0.3); border-radius: 4px; padding: 8px 12px; margin-bottom: 10px; color: #f93e3e; font-size: 13px; font-family: monospace; word-break: break-all; }
.pm-response-body { background: var(--bg-deep); color: var(--text); font-family: 'SF Mono', Monaco, Menlo, Consolas, monospace; font-size: 12px; line-height: 1.6; padding: 12px; border-radius: 4px; border: 1px solid var(--border); max-height: 300px; overflow: auto; white-space: pre-wrap; word-break: break-all; margin: 0; }

/* WebSocket transcript viewer */
.pm-ws-transcript {
  background: var(--bg-deep);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 8px 12px;
  max-height: 360px;
  overflow: auto;
  font-family: 'SF Mono', Monaco, Menlo, Consolas, monospace;
  font-size: 12px;
}
.pm-ws-entry {
  display: grid;
  grid-template-columns: 64px 22px 90px 1fr;
  align-items: start;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px dashed var(--border);
}
.pm-ws-entry:last-child { border-bottom: none; }
.pm-ws-ts { color: var(--text-3); }
.pm-ws-arrow { font-weight: 700; text-align: center; }
.pm-ws-dir-label { color: var(--text-2); }
.pm-ws-data { margin: 0; white-space: pre-wrap; word-break: break-all; color: var(--text); }
.pm-ws-note { color: var(--text-2); }
.pm-ws-dir-send .pm-ws-arrow { color: #4cc38a; }
.pm-ws-dir-recv .pm-ws-arrow { color: #5ca5ff; }
.pm-ws-dir-error .pm-ws-arrow,
.pm-ws-dir-error .pm-ws-dir-label,
.pm-ws-dir-error .pm-ws-note { color: #f93e3e; }
.pm-ws-dir-close .pm-ws-arrow { color: #b966ff; }
.pm-ws-dir-wait .pm-ws-arrow { color: var(--text-3); }
.pm-ws-dir-handshake .pm-ws-arrow { color: #4cc38a; }
.pm-ws-truncated { padding: 8px 0 4px; color: #f9a03e; font-size: 11px; }
.pm-assertion-item { display: flex; gap: 8px; align-items: center; padding: 6px 0; font-size: 13px; }
.pm-assertion-item code { color: var(--text); font-size: 12px; }
.pm-actual { color: var(--text-3); font-size: 12px; }
.pm-req-summary { font-family: monospace; font-size: 13px; margin-bottom: 8px; color: var(--text); }

/* Response placeholder */
.pm-response-placeholder { border-top: 2px solid var(--border); flex-shrink: 0; height: 160px; display: flex; align-items: center; justify-content: center; }
.pm-placeholder-content { text-align: center; color: var(--text-3); font-size: 13px; }
.pm-placeholder-content p { margin-top: 12px; }

/* Ant overrides inside editor — only layout, no colors (global theme handles colors) */
.pm-editor :deep(.ant-table-thead > tr > th) { font-size: 11px; }
.pm-editor :deep(.ant-input) { background: transparent; }
.pm-editor :deep(textarea.ant-input) { background: var(--bg-deep); font-family: 'SF Mono', Monaco, Menlo, Consolas, monospace; }

/* Mobile responsive */
@media (max-width: 768px) {
  .pm-url-bar { padding: 8px 10px; flex-wrap: wrap; gap: 6px; }
  .pm-method-select { width: 90px; }
  .pm-url-input { font-size: 12px; height: 32px; }
  .pm-send-btn { height: 32px; padding: 0 12px; font-size: 12px; }
  .pm-save-btn { height: 32px; padding: 0 10px; font-size: 12px; }
  .pm-name-row { flex-wrap: wrap; padding: 6px 10px; gap: 6px; }
  .pm-env-group { width: 100%; }
  .pm-env-select { flex: 1; width: auto !important; }
  .pm-tabs { padding: 0 8px; overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .pm-tab { padding: 6px 8px; font-size: 11px; white-space: nowrap; }
  .pm-tab-content { padding: 8px 10px; }
  .pm-body-type-bar { gap: 8px; flex-wrap: wrap; }
  .pm-body-type { font-size: 11px; }
  .pm-response-section { max-height: 50%; }
  .pm-response-content { padding: 8px 10px; }
  .pm-response-body { font-size: 11px; padding: 8px; max-height: 200px; }
}
</style>
