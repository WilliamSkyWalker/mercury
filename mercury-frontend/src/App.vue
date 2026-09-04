<template>
  <a-config-provider :locale="antdLocale">
    <router-view />
  </a-config-provider>
</template>

<script setup lang="ts">
import { computed, watchEffect } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import enUS from 'ant-design-vue/es/locale/en_US'
import zhCN from 'ant-design-vue/es/locale/zh_CN'

const route = useRoute()
const { locale, t } = useI18n({ useScope: 'global' })
const antdLocale = computed(() => locale.value === 'zh-CN' ? zhCN : enUS)

watchEffect(() => {
  const titleKey = route.meta.titleKey as string | undefined
  document.title = titleKey ? `Mercury · ${t(titleKey)}` : 'Mercury'
})
</script>
