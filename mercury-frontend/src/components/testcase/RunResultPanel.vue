<template>
  <div v-if="result" class="run-result">
    <a-result
      :status="result.status === 'passed' ? 'success' : result.status === 'failed' ? 'warning' : 'error'"
      :title="t(`status.${result.status}`, result.status).toUpperCase()"
      :sub-title="`${result.duration_ms}ms`"
      style="padding: 12px"
    />

    <a-collapse>
      <a-collapse-panel key="response" :header="t('common.response')">
        <p><strong>{{ t('testcase.runResult.status') }}</strong> {{ result.response?.status }}</p>
        <pre class="code-block">{{ formatBody(result.response?.body) }}</pre>
      </a-collapse-panel>

      <a-collapse-panel v-if="result.assertion_results?.length" key="assertions" :header="t('testcase.runResult.assertions')">
        <div v-for="(a, i) in result.assertion_results" :key="i" class="assertion-result">
          <CheckCircleFilled v-if="a.passed" style="color: #52c41a" />
          <CloseCircleFilled v-else style="color: #ff4d4f" />
          <span>{{ a.field }} {{ a.operator }} {{ JSON.stringify(a.expected) }}</span>
          <span v-if="!a.passed" class="actual">{{ t('testcase.actual') }}: {{ JSON.stringify(a.actual) }}</span>
        </div>
      </a-collapse-panel>

      <a-collapse-panel v-if="Object.keys(result.extracted_variables || {}).length" key="vars" :header="t('testcase.runResult.extractedVariables')">
        <pre class="code-block">{{ JSON.stringify(result.extracted_variables, null, 2) }}</pre>
      </a-collapse-panel>

      <a-collapse-panel key="request" :header="t('common.request')">
        <p><strong>{{ result.request?.method }}</strong> {{ result.request?.url }}</p>
        <pre v-if="result.request?.body" class="code-block">{{ result.request.body }}</pre>
      </a-collapse-panel>

      <a-collapse-panel v-if="result.error_message" key="error" :header="t('common.error')">
        <a-alert :message="result.error_message" type="error" />
      </a-collapse-panel>
    </a-collapse>
  </div>
</template>

<script setup lang="ts">
import { CheckCircleFilled, CloseCircleFilled } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import type { RunResult } from '../../api/testcases.ts'

defineProps<{ result: RunResult | null }>()
const { t } = useI18n()

function formatBody(body: any): string {
  if (!body) return ''
  if (typeof body === 'string') {
    try { return JSON.stringify(JSON.parse(body), null, 2) } catch { return body }
  }
  return JSON.stringify(body, null, 2)
}
</script>

<style scoped>
.run-result { margin-top: 16px; }
.code-block { background: var(--bg-surface); padding: 12px; border-radius: 4px; font-size: 12px; max-height: 400px; overflow: auto; white-space: pre-wrap; word-break: break-all; }
.assertion-result { display: flex; gap: 8px; align-items: center; padding: 4px 0; }
.actual { color: var(--text-3); font-size: 12px; }
</style>
