import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { notification, Button } from 'ant-design-vue'
import { h } from 'vue'
import AppLayout from '../components/layout/AppLayout.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('../views/AdminManagement.vue'),
    meta: { skipProjectCheck: true },
  },
  {
    path: '/projects',
    name: 'ProjectSelect',
    component: () => import('../views/ProjectSelect.vue'),
    meta: { skipProjectCheck: true },
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
        meta: { title: 'Dashboard', icon: 'dashboard' },
      },
      {
        path: 'testcases',
        name: 'TestcaseManagement',
        component: () => import('../views/TestcaseManagement.vue'),
        meta: { title: 'Test Cases', icon: 'experiment' },
      },
      {
        path: 'testplans',
        name: 'TestplanManagement',
        component: () => import('../views/TestplanManagement.vue'),
        meta: { title: 'Test Plans', icon: 'ordered-list' },
      },
      {
        path: 'executions',
        name: 'ExecutionList',
        component: () => import('../views/ExecutionList.vue'),
        meta: { title: 'Executions', icon: 'history' },
      },
      {
        path: 'executions/:id',
        name: 'ExecutionDetail',
        component: () => import('../views/ExecutionDetail.vue'),
        meta: { title: 'Execution Detail', hidden: true, public: true, skipProjectCheck: true },
      },
      {
        path: 'schedules',
        name: 'ScheduleManagement',
        component: () => import('../views/ScheduleManagement.vue'),
        meta: { title: 'Schedules', icon: 'clock-circle' },
      },
      {
        path: 'perf',
        name: 'PerfPlanManagement',
        component: () => import('../views/PerfPlanManagement.vue'),
        meta: { title: 'Load Test', icon: 'thunderbolt' },
      },
      {
        path: 'perf/plans/:id/runs',
        name: 'PerfPlanHistory',
        component: () => import('../views/PerfPlanHistory.vue'),
        meta: { title: 'Run History' },
      },
      {
        path: 'perf/runs/:id',
        name: 'PerfRunDetail',
        component: () => import('../views/PerfRunDetail.vue'),
        meta: { title: 'Run Detail' },
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
        message: 'New Version Available',
        description: 'A new version has been deployed. Click to reload.',
        btn: () => h(Button, {
          type: 'primary',
          size: 'small',
          onClick: () => {
            notification.destroy()
            window.location.reload()
          },
        }, () => 'Reload Now'),
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

export default router
