<template>
  <div class="script-editor">
    <a-textarea
      :value="modelValue"
      :rows="12"
      :placeholder="placeholder"
      style="font-family: monospace; font-size: 13px;"
      @update:value="$emit('update:modelValue', $event)"
    />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: string
  placeholder?: string
}>()

defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<style scoped>
.script-editor {
  width: 100%;
}
</style>
