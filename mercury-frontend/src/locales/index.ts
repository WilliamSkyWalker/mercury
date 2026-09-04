import { createI18n } from 'vue-i18n'
import dayjs from 'dayjs'
import 'dayjs/locale/en'
import 'dayjs/locale/zh-cn'
import enUS from './en-US.ts'
import zhCN from './zh-CN.ts'

export type AppLocale = 'zh-CN' | 'en-US'

const STORAGE_KEY = 'mercury_locale'
const supportedLocales: AppLocale[] = ['zh-CN', 'en-US']

function isSupportedLocale(value: string | null): value is AppLocale {
  return !!value && supportedLocales.includes(value as AppLocale)
}

function detectBrowserLocale(): AppLocale {
  const primaryLocale = navigator.languages?.[0] || navigator.language || ''
  return primaryLocale.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en-US'
}

export function getInitialLocale(): AppLocale {
  const saved = localStorage.getItem(STORAGE_KEY)
  return isSupportedLocale(saved) ? saved : detectBrowserLocale()
}

export const i18n = createI18n({
  legacy: false,
  locale: getInitialLocale(),
  fallbackLocale: 'en-US',
  messages: {
    'en-US': enUS,
    'zh-CN': zhCN,
  },
})

function applyDocumentLocale(locale: AppLocale) {
  document.documentElement.lang = locale
  dayjs.locale(locale === 'zh-CN' ? 'zh-cn' : 'en')
}

export function setAppLocale(locale: AppLocale) {
  i18n.global.locale.value = locale
  localStorage.setItem(STORAGE_KEY, locale)
  applyDocumentLocale(locale)
}

applyDocumentLocale(i18n.global.locale.value)
