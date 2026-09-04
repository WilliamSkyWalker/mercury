import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { notification, Button } from 'ant-design-vue'
import { h } from 'vue'
import AppLayout from '../components/layout/AppLayout.vue'
import { i18n } from '../locales'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { public: true, titleKey: 'auth.login' },
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('../views/AdminManagement.vue'),
    meta: { skipProjectCheck: true, titleKey: 'common.admin' },
  },
  {
    path: '/projects',
    name: 'ProjectSelect',
    component: () => import('../views/ProjectSelect.vue'),
    meta: { skipProjectCheck: true, titleKey: 'nav.manageProjects' },
  },
  {
    path: '/',
    component: AppLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue'),
        meta: { titleKey: 'nav.dashboard', icon: 'dashboard' },
      },
      {
        path: 'testcases',
        name: 'TestcaseManagement',
        component: () => import('../views/TestcaseManagement.vue'),
        meta: { titleKey: 'dashboard.testCases', icon: 'experiment' },
      },
      {
        path: 'testplans',
        name: 'TestplanManagement',
        component: () => import('../views/TestplanManagement.vue'),
        meta: { titleKey: 'dashboard.testPlans', icon: 'ordered-list' },
      },
      {
        path: 'executions',
        name: 'ExecutionList',
        component: () => import('../views/ExecutionList.vue'),
        meta: { titleKey: 'nav.tasks', icon: 'history' },
      },
      {
        path: 'executions/:id',
        name: 'ExecutionDetail',
        component: () => import('../views/ExecutionDetail.vue'),
        meta: { titleKey: 'common.detail', hidden: true, public: true, skipProjectCheck: true },
      },
      {
        path: 'schedules',
        name: 'ScheduleManagement',
        component: () => import('../views/ScheduleManagement.vue'),
        meta: { titleKey: 'nav.schedules', icon: 'clock-circle' },
      },
      {
        path: 'perf',
        name: 'PerfPlanManagement',
        component: () => import('../views/PerfPlanManagement.vue'),
        meta: { titleKey: 'nav.loadTest', icon: 'thunderbolt' },
      },
      {
        path: 'perf/plans/:id/runs',
        name: 'PerfPlanHistory',
        component: () => import('../views/PerfPlanHistory.vue'),
        meta: { titleKey: 'common.history' },
      },
      {
        path: 'perf/runs/:id',
        name: 'PerfRunDetail',
        component: () => import('../views/PerfRunDetail.vue'),
        meta: { titleKey: 'common.detail' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Version check: detect new deployments on route change
let currentScriptHash = ''
const scriptHashRe = /src="\/static\/assets\/index-([^"]+)\.js"/

function extractScriptHash(html: string): string {
  const match = html.match(scriptHashRe)
  return match ? match[1] : ''
}

// Capture initial hash from current page
const initialScript = document.querySelector('script[src*="/static/assets/index-"]')
if (initialScript) {
  const src = initialScript.getAttribute('src') || ''
  const m = src.match(/index-([^.]+)\.js/)
  if (m) currentScriptHash = m[1]
}

let checking = false
async function checkForUpdate() {
  if (checking || !currentScriptHash) return
  checking = true
  try {
    const resp = await fetch('/?_t=' + Date.now(), { cache: 'no-store' })
    const html = await resp.text()
    const newHash = extractScriptHash(html)
    if (newHash && newHash !== currentScriptHash) {
      currentScriptHash = newHash
      notification.info({
        message: i18n.global.t('update.title'),
        description: i18n.global.t('update.description'),
        btn: () => h(Button, {
          type: 'primary',
          size: 'small',
          onClick: () => {
            notification.destroy()
            window.location.reload()
          },
        }, () => i18n.global.t('update.reload')),
        duration: 0,
        placement: 'topRight',
      })
    }
  } catch { /* ignore */ }
  checking = false
}

router.beforeEach((to) => {
  // Allow public routes (login)
  if (to.meta.public) return true

  // Check authentication
  const token = localStorage.getItem('mercury_token')
  if (!token) {
    return { name: 'Login' }
  }

  // Check project selection
  if (to.meta.skipProjectCheck) return true
  const savedId = localStorage.getItem('mercury_current_project_id')
  if (!savedId) {
    return { name: 'ProjectSelect' }
  }

  // Check for new version (non-blocking)
  checkForUpdate()

  return true
})

router.afterEach((to) => {
  const titleKey = to.meta.titleKey as string | undefined
  document.title = titleKey ? `Mercury · ${i18n.global.t(titleKey)}` : 'Mercury'
})

export default router
