<template>
  <div>
    <a-table :data-source="items" :columns="columns" :pagination="false" size="small" row-key="key">
      <template #bodyCell="{ column, record, index }">
        <template v-if="column.dataIndex === 'enabled'">
          <a-checkbox v-model:checked="record.enabled" @change="emitChange" />
        </template>
        <template v-if="column.dataIndex === 'key'">
          <a-input v-model:value="record.key" size="small" placeholder="Key" @change="emitChange" />
        </template>
        <template v-if="column.dataIndex === 'value'">
          <a-input v-model:value="record.value" size="small" placeholder="Value" @change="emitChange" />
        </template>
        <template v-if="column.dataIndex === 'action'">
          <a-button type="link" danger size="small" @click="removeItem(index)">
            <DeleteOutlined />
          </a-button>
        </template>
      </template>
    </a-table>
    <a-button type="dashed" size="small" block style="margin-top: 8px" @click="addItem">
      <PlusOutlined /> Add {{ label }}
    </a-button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons-vue'

const props = defineProps<{
  modelValue: { key: string; value: string; enabled: boolean }[]
  label?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: { key: string; value: string; enabled: boolean }[]]
}>()

const items = ref([...props.modelValue])

watch(() => props.modelValue, (val) => {
  items.value = [...val]
}, { deep: true })

const columns = [
  { title: '', dataIndex: 'enabled', width: 40 },
  { title: 'Key', dataIndex: 'key' },
  { title: 'Value', dataIndex: 'value' },
  { title: '', dataIndex: 'action', width: 40 },
]

function addItem() {
  items.value.push({ key: '', value: '', enabled: true })
  emitChange()
}

function removeItem(index: number) {
  items.value.splice(index, 1)
  emitChange()
}

function emitChange() {
  emit('update:modelValue', [...items.value])
}
</script>
