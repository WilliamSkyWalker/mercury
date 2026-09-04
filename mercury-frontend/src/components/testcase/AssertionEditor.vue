<template>
  <div>
    <div v-for="(item, index) in items" :key="index" class="assertion-row">
      <a-auto-complete
        v-model:value="item.field"
        :options="fieldSuggestions"
        placeholder="res.status"
        style="width: 200px"
        size="small"
        :filter-option="filterOption"
        @change="emitChange"
      />
      <a-select v-model:value="item.operator" style="width: 130px" size="small" @change="emitChange">
        <a-select-option v-for="op in operators" :key="op.value" :value="op.value">{{ op.label }}</a-select-option>
      </a-select>
      <a-input v-model:value="item.expectedStr" :placeholder="t('testcase.expected')" style="flex: 1" size="small" @change="onExpectedChange(index)" />
      <a-button type="link" danger size="small" @click="removeItem(index)">
        <DeleteOutlined />
      </a-button>
    </div>
    <a-button type="dashed" size="small" block style="margin-top: 8px" @click="addItem">
      <PlusOutlined /> {{ t('testcase.addAssertion') }}
    </a-button>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons-vue'

interface AssertionItem {
  field: string
  operator: string
  expected: any
  expectedStr: string
}

const props = defineProps<{
  modelValue: { field: string; operator: string; expected: any }[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: { field: string; operator: string; expected: any }[]]
}>()

const { t } = useI18n()

const operators = computed(() => [
  { value: 'eq', label: t('testcase.operators.eq') },
  { value: 'neq', label: t('testcase.operators.neq') },
  { value: 'gt', label: '>' },
  { value: 'gte', label: '>=' },
  { value: 'lt', label: '<' },
  { value: 'lte', label: '<=' },
  { value: 'in', label: t('testcase.operators.in') },
  { value: 'nin', label: t('testcase.operators.nin') },
  { value: 'contains', label: t('testcase.operators.contains') },
  { value: 'notContains', label: t('testcase.operators.notContains') },
  { value: 'isNull', label: t('testcase.operators.isNull') },
  { value: 'isNotNull', label: t('testcase.operators.isNotNull') },
  { value: 'isEmpty', label: t('testcase.operators.isEmpty') },
  { value: 'isNotEmpty', label: t('testcase.operators.isNotEmpty') },
  { value: 'matches', label: t('testcase.operators.matches') },
])

const fieldSuggestions = [
  { value: 'res.status' },
  { value: 'res.body' },
  { value: 'res.body.data' },
  { value: 'res.body.items' },
  { value: 'res.body.items.length' },
  { value: 'res.body.message' },
  { value: 'res.body.code' },
  { value: 'res.headers.content-type' },
]

function filterOption(input: string, option: { value: string }) {
  return option.value.toLowerCase().includes(input.toLowerCase())
}

const items = ref<AssertionItem[]>(
  props.modelValue.map((a) => ({ ...a, expectedStr: JSON.stringify(a.expected) }))
)

watch(() => props.modelValue, (val) => {
  items.value = val.map((a) => ({ ...a, expectedStr: JSON.stringify(a.expected) }))
}, { deep: true })

function parseExpected(str: string): any {
  try { return JSON.parse(str) } catch { return str }
}

function onExpectedChange(index: number) {
  items.value[index].expected = parseExpected(items.value[index].expectedStr)
  emitChange()
}

function addItem() {
  items.value.push({ field: 'res.status', operator: 'eq', expected: 200, expectedStr: '200' })
  emitChange()
}

function removeItem(index: number) {
  items.value.splice(index, 1)
  emitChange()
}

function emitChange() {
  emit('update:modelValue', items.value.map(({ field, operator, expected }) => ({ field, operator, expected })))
}
</script>

<style scoped>
.assertion-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
</style>
