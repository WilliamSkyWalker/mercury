<template>
  <div class="pm-ws-steps">
    <div v-if="!modelValue?.length" class="pm-ws-empty">
      {{ t('testcase.noWsSteps') }}
    </div>

    <div v-for="(step, idx) in modelValue || []" :key="idx" class="pm-ws-step">
      <div class="pm-ws-step-head">
        <span class="pm-ws-step-idx">#{{ idx + 1 }}</span>
        <a-select :value="step.kind" @change="(v: any) => onKindChange(idx, v)" size="small" style="width: 110px">
          <a-select-option value="send">{{ t('testcase.stepSend') }}</a-select-option>
          <a-select-option value="recv">{{ t('testcase.stepReceive') }}</a-select-option>
          <a-select-option value="wait">{{ t('testcase.stepWait') }}</a-select-option>
          <a-select-option value="close">{{ t('testcase.stepClose') }}</a-select-option>
        </a-select>
        <div class="pm-ws-step-actions">
          <a-button size="small" :disabled="idx === 0" @click="move(idx, -1)" :title="t('testcase.moveUp')">↑</a-button>
          <a-button size="small" :disabled="idx === (modelValue?.length || 0) - 1" @click="move(idx, 1)" :title="t('testcase.moveDown')">↓</a-button>
          <a-button size="small" danger @click="remove(idx)" :title="t('common.delete')">×</a-button>
        </div>
      </div>

      <div v-if="step.kind === 'send'" class="pm-ws-step-body">
        <div class="pm-ws-row">
          <label class="pm-ws-label">{{ t('testcase.type') }}</label>
          <a-select :value="step.payload_type || 'text'" @change="(v: any) => updateStep(idx, { payload_type: v })" size="small" style="width: 140px">
            <a-select-option value="text">{{ t('testcase.textType') }}</a-select-option>
            <a-select-option value="json">{{ t('testcase.jsonType') }}</a-select-option>
            <a-select-option value="binary_b64">{{ t('testcase.binaryBase64Type') }}</a-select-option>
          </a-select>
        </div>
        <div class="pm-ws-row">
          <label class="pm-ws-label">{{ t('testcase.payload') }}</label>
          <textarea
            :value="payloadText(step)"
            @input="onPayloadInput(idx, ($event.target as HTMLTextAreaElement).value)"
            class="pm-code-textarea"
            rows="4"
            :placeholder="step.payload_type === 'json' ? '{&quot;type&quot;:&quot;subscribe&quot;}' : t('testcase.messageText')"
            spellcheck="false"
          ></textarea>
        </div>
      </div>

      <div v-else-if="step.kind === 'recv'" class="pm-ws-step-body">
        <div class="pm-ws-row">
          <label class="pm-ws-label">{{ t('testcase.timeoutMs') }}</label>
          <a-input-number
            :value="step.timeout_ms ?? 60000"
            @change="(v: any) => updateStep(idx, { timeout_ms: v })"
            :min="100"
            :max="3600000"
            :step="1000"
            size="small"
            style="width: 160px"
          />
          <span class="pm-ws-hint">{{ t('testcase.recvTimeoutHint') }}</span>
        </div>
      </div>

      <div v-else-if="step.kind === 'wait'" class="pm-ws-step-body">
        <div class="pm-ws-row">
          <label class="pm-ws-label">{{ t('testcase.durationMs') }}</label>
          <a-input-number
            :value="step.duration_ms ?? 1000"
            @change="(v: any) => updateStep(idx, { duration_ms: v })"
            :min="0"
            :max="3600000"
            :step="500"
            size="small"
            style="width: 160px"
          />
        </div>
      </div>

      <div v-else-if="step.kind === 'close'" class="pm-ws-step-body">
        <div class="pm-ws-row">
          <label class="pm-ws-label">{{ t('testcase.code') }}</label>
          <a-input-number
            :value="step.code ?? 1000"
            @change="(v: any) => updateStep(idx, { code: v })"
            :min="1000"
            :max="4999"
            size="small"
            style="width: 120px"
          />
          <label class="pm-ws-label">{{ t('testcase.reason') }}</label>
          <a-input
            :value="step.reason ?? ''"
            @change="(e: any) => updateStep(idx, { reason: e.target.value })"
            size="small"
            style="flex: 1"
          />
        </div>
      </div>
    </div>

    <div class="pm-ws-add">
      <a-button size="small" @click="add('send')">+ {{ t('testcase.stepSend') }}</a-button>
      <a-button size="small" @click="add('recv')">+ {{ t('testcase.stepReceive') }}</a-button>
      <a-button size="small" @click="add('wait')">+ {{ t('testcase.stepWait') }}</a-button>
      <a-button size="small" @click="add('close')">+ {{ t('testcase.stepClose') }}</a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { WsStep, WsStepKind } from '../../api/testcases.ts'
import { useI18n } from 'vue-i18n'

const props = defineProps<{ modelValue: WsStep[] | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: WsStep[]] }>()
const { t } = useI18n()

function steps(): WsStep[] {
  return props.modelValue ? [...props.modelValue] : []
}

function emitSteps(next: WsStep[]) {
  emit('update:modelValue', next)
}

function defaultStep(kind: WsStepKind): WsStep {
  if (kind === 'send') return { kind, payload_type: 'json', payload: '' }
  if (kind === 'recv') return { kind, timeout_ms: 60000 }
  if (kind === 'wait') return { kind, duration_ms: 1000 }
  return { kind, code: 1000, reason: '' }
}

function add(kind: WsStepKind) {
  emitSteps([...steps(), defaultStep(kind)])
}

function remove(idx: number) {
  const next = steps()
  next.splice(idx, 1)
  emitSteps(next)
}

function move(idx: number, delta: number) {
  const next = steps()
  const target = idx + delta
  if (target < 0 || target >= next.length) return
  ;[next[idx], next[target]] = [next[target], next[idx]]
  emitSteps(next)
}

function onKindChange(idx: number, newKind: WsStepKind) {
  const next = steps()
  next[idx] = defaultStep(newKind)
  emitSteps(next)
}

function updateStep(idx: number, patch: Partial<WsStep>) {
  const next = steps()
  next[idx] = { ...next[idx], ...patch }
  emitSteps(next)
}

function payloadText(step: WsStep): string {
  if (step.payload == null) return ''
  if (typeof step.payload === 'string') return step.payload
  try { return JSON.stringify(step.payload, null, 2) } catch { return String(step.payload) }
}

function onPayloadInput(idx: number, val: string) {
  const next = steps()
  const step = next[idx]
  // Keep raw text in the textarea; only parse JSON on submission if user
  // chose json type — avoids losing in-progress edits as they type.
  if (step.payload_type === 'json') {
    try {
      step.payload = JSON.parse(val)
    } catch {
      step.payload = val
    }
  } else {
    step.payload = val
  }
  emitSteps(next)
}
</script>

<style scoped>
.pm-ws-steps { display: flex; flex-direction: column; gap: 10px; padding: 8px; }
.pm-ws-empty {
  padding: 24px; text-align: center; color: var(--text-3);
  border: 1px dashed var(--border-2); border-radius: 6px;
}
.pm-ws-step {
  border: 1px solid var(--border-2); border-radius: 6px; padding: 10px;
  background: var(--bg-1);
}
.pm-ws-step-head { display: flex; align-items: center; gap: 8px; }
.pm-ws-step-idx { color: var(--text-3); font-family: monospace; min-width: 28px; }
.pm-ws-step-actions { margin-left: auto; display: flex; gap: 4px; }
.pm-ws-step-body { margin-top: 8px; display: flex; flex-direction: column; gap: 8px; }
.pm-ws-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pm-ws-label { color: var(--text-2); font-size: 12px; min-width: 80px; }
.pm-ws-hint { color: var(--text-3); font-size: 12px; }
.pm-code-textarea {
  flex: 1; min-width: 0; font-family: monospace; font-size: 12px;
  padding: 8px; border: 1px solid var(--border-2); border-radius: 4px;
  background: var(--bg-2); color: var(--text-1); resize: vertical;
}
.pm-ws-add { display: flex; gap: 8px; padding: 4px; }
</style>
