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
      <a-input v-model:value="item.expectedStr" placeholder="Expected" style="flex: 1" size="small" @change="onExpectedChange(index)" />
      <a-button type="link" danger size="small" @click="removeItem(index)">
        <DeleteOutlined />
      </a-button>
    </div>
    <a-button type="dashed" size="small" block style="margin-top: 8px" @click="addItem">
      <PlusOutlined /> Add Assertion
    </a-button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
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

const operators = [
  { value: 'eq', label: 'equals (==)' },
  { value: 'neq', label: 'not equals (!=)' },
  { value: 'gt', label: '>' },
  { value: 'gte', label: '>=' },
  { value: 'lt', label: '<' },
  { value: 'lte', label: '<=' },
  { value: 'in', label: 'in' },
  { value: 'nin', label: 'not in' },
  { value: 'contains', label: 'contains' },
  { value: 'notContains', label: 'not contains' },
  { value: 'isNull', label: 'is None' },
  { value: 'isNotNull', label: 'is not None' },
  { value: 'isEmpty', label: 'is empty' },
  { value: 'isNotEmpty', label: 'is not empty' },
  { value: 'matches', label: 'regex matches' },
]

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
