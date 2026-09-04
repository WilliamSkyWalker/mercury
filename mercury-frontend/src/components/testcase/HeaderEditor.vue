<template>
  <div>
    <a-table :data-source="items" :columns="columns" :pagination="false" size="small" row-key="key">
      <template #bodyCell="{ column, record, index }">
        <template v-if="column.dataIndex === 'enabled'">
          <a-checkbox v-model:checked="record.enabled" @change="emitChange" />
        </template>
        <template v-if="column.dataIndex === 'key'">
          <a-input v-model:value="record.key" size="small" :placeholder="t('common.key')" @change="emitChange" />
        </template>
        <template v-if="column.dataIndex === 'value'">
          <a-input v-model:value="record.value" size="small" :placeholder="t('common.value')" @change="emitChange" />
        </template>
        <template v-if="column.dataIndex === 'action'">
          <a-button type="link" danger size="small" @click="removeItem(index)">
            <DeleteOutlined />
          </a-button>
        </template>
      </template>
    </a-table>
    <a-button type="dashed" size="small" block style="margin-top: 8px" @click="addItem">
      <PlusOutlined /> {{ t('testcase.addItem', { label: label || '' }) }}
    </a-button>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons-vue'

const props = defineProps<{
  modelValue: { key: string; value: string; enabled: boolean }[]
  label?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: { key: string; value: string; enabled: boolean }[]]
}>()

const { t } = useI18n()
const items = ref([...props.modelValue])

watch(() => props.modelValue, (val) => {
  items.value = [...val]
}, { deep: true })

const columns = computed(() => [
  { title: '', dataIndex: 'enabled', width: 40 },
  { title: t('common.key'), dataIndex: 'key' },
  { title: t('common.value'), dataIndex: 'value' },
  { title: '', dataIndex: 'action', width: 40 },
])

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
