<template>
  <div class="pm-dashboard">
    <a-spin :spinning="loading">
      <!-- Top summary stats -->
      <a-row :gutter="[16, 12]" class="pm-stats-row">
        <a-col :xs="12" :sm="4">
          <a-statistic :title="t('dashboard.testCases')" :value="data?.summary.total_cases || 0" />
        </a-col>
        <a-col :xs="12" :sm="4">
          <a-statistic :title="t('dashboard.testPlans')" :value="data?.summary.total_plans || 0" />
        </a-col>
        <a-col :xs="12" :sm="4">
          <a-statistic :title="t('dashboard.environments')" :value="data?.summary.total_envs || 0" />
        </a-col>
        <a-col :xs="12" :sm="4">
          <a-statistic :title="t('dashboard.runs7d')" :value="data?.summary.total_runs_7d || 0" />
        </a-col>
        <a-col :xs="24" :sm="8">
          <a-statistic :title="t('dashboard.avgPassRate7d')" :suffix="'%'">
            <template #formatter>
              <span :style="{ color: (data?.summary.avg_pass_rate_7d || 0) >= 90 ? '#52c41a' : '#ff4d4f' }">
                {{ data?.summary.avg_pass_rate_7d || 0 }}
              </span>
            </template>
          </a-statistic>
        </a-col>
      </a-row>

      <!-- Monitor Health + Top Failures -->
      <a-row :gutter="[16, 16]" class="pm-row">
        <a-col :xs="24" :lg="14">
          <a-card :title="t('dashboard.monitorHealth')" size="small">
            <template #extra>
              <span class="pm-card-hint">{{ t('dashboard.activeCount', { count: monitors.length }) }}</span>
            </template>
            <a-empty v-if="!monitorsLoading && monitors.length === 0" :description="t('dashboard.noActiveMonitors')" />
            <a-spin v-else :spinning="monitorsLoading">
              <table class="pm-table">
                <thead>
                  <tr>
                    <th>{{ t('dashboard.monitor') }}</th>
                    <th>{{ t('dashboard.cadence') }}</th>
                    <th>{{ t('dashboard.lastRun') }}</th>
                    <th>{{ t('dashboard.passRate') }}</th>
                    <th>{{ t('dashboard.nextRun') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="m in monitors" :key="m.id">
                    <td>
                      <span :class="['pm-pill', `pm-pill-${m.health}`]">{{ healthLabel(m.health) }}</span>
                      <span class="pm-monitor-name">{{ m.name }}</span>
                      <span v-if="m.env_name" class="pm-monitor-env">{{ m.env_name }}</span>
                    </td>
                    <td class="pm-mono">{{ m.cadence }}</td>
                    <td>
                      <router-link
                        v-if="m.last_execution_id"
                        :to="`/executions/${m.last_execution_id}`"
                        class="pm-link"
                      >
                        {{ formatAge(m.age_seconds) }}
                      </router-link>
                      <span v-else class="pm-text-dim">{{ t('common.never') }}</span>
                    </td>
                    <td>
                      <span v-if="m.last_pass_rate !== null" :style="{ color: passRateColor(m.last_pass_rate) }">
                        {{ m.last_pass_rate }}%
                      </span>
                      <span v-else class="pm-text-dim">—</span>
                    </td>
                    <td class="pm-text-dim pm-mono">{{ formatNextRun(m.next_run_at) }}</td>
                  </tr>
                </tbody>
              </table>
            </a-spin>
          </a-card>
        </a-col>

        <a-col :xs="24" :lg="10">
          <a-card :title="t('dashboard.topFailingCases')" size="small">
            <template #extra>
              <span class="pm-card-hint">{{ t('dashboard.minimumRuns') }}</span>
            </template>
            <a-empty v-if="!topFailuresLoading && topFailures.length === 0" :description="t('dashboard.noFailures')" />
            <a-spin v-else :spinning="topFailuresLoading">
              <table class="pm-table">
                <thead>
                  <tr>
                    <th>{{ t('dashboard.case') }}</th>
                    <th class="pm-th-num">{{ t('dashboard.fails') }}</th>
                    <th class="pm-th-num">{{ t('dashboard.rate') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="r in topFailures" :key="r.testcase_id">
                    <td>
                      <router-link
                        v-if="r.last_execution_id"
                        :to="`/executions/${r.last_execution_id}`"
                        class="pm-link"
                      >
                        {{ r.name }}
                      </router-link>
                      <span v-else>{{ r.name }}</span>
                      <div v-if="r.last_error" class="pm-error-line" :title="r.last_error">{{ r.last_error }}</div>
                    </td>
                    <td class="pm-mono pm-text-dim pm-th-num">{{ r.failed_count }}/{{ r.total_runs }}</td>
                    <td class="pm-th-num">
                      <span :style="{ color: failRateColor(r.fail_rate) }" class="pm-mono">{{ r.fail_rate }}%</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </a-spin>
          </a-card>
        </a-col>
      </a-row>

      <!-- Pass rate by plan -->
      <a-row :gutter="[16, 16]" class="pm-row">
        <a-col :span="24">
          <a-card :title="t('dashboard.passRateByPlan')" size="small">
            <a-empty v-if="!planTrendsLoading && plans.length === 0" :description="t('dashboard.noExecutions')" />
            <a-spin v-else :spinning="planTrendsLoading">
              <div class="pm-plan-grid">
                <div v-for="p in plans" :key="p.testplan_id" class="pm-plan-row">
                  <div class="pm-plan-name">{{ p.name }}</div>
                  <div class="pm-plan-spark">
                    <Sparkline :values="sparkValues(p.daily)" />
                  </div>
                  <div class="pm-plan-meta">
                    <span :style="{ color: passRateColor(p.avg_pass_rate_7d) }" class="pm-mono">{{ p.avg_pass_rate_7d }}%</span>
                    <span class="pm-text-dim pm-mono">{{ t('dashboard.runsCount', { count: p.total_runs_7d }) }}</span>
                  </div>
                </div>
              </div>
            </a-spin>
          </a-card>
        </a-col>
      </a-row>

      <!-- Recent failures -->
      <a-row :gutter="[16, 16]" class="pm-row">
        <a-col :span="24">
          <a-card :title="t('dashboard.recentFailures')" size="small">
            <a-list :data-source="data?.recent_failures || []" size="small">
              <template #renderItem="{ item }">
                <a-list-item>
                  <a-list-item-meta>
                    <template #title>
                      <router-link :to="`/executions/${item.id}`">{{ item.task_id }}</router-link>
                    </template>
                    <template #description>
                      {{ item.env_name }} | {{ item.pass_rate }}% | {{ item.created_at?.substring(0, 16) }}
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
          </a-card>
        </a-col>
      </a-row>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, h, watch, defineComponent } from 'vue'
import { useI18n } from 'vue-i18n'
import { statsApi, type DashboardData, type MonitorRow, type TopFailureRow, type PlanTrendRow } from '../api/stats.ts'
import { useProjectStore } from '../stores/project.ts'

const projectStore = useProjectStore()
const { t } = useI18n()

const data = ref<DashboardData | null>(null)
const monitors = ref<MonitorRow[]>([])
const topFailures = ref<TopFailureRow[]>([])
const plans = ref<PlanTrendRow[]>([])

const loading = ref(false)
const monitorsLoading = ref(false)
const topFailuresLoading = ref(false)
const planTrendsLoading = ref(false)

async function loadAll() {
  const project = projectStore.currentProjectId
  loading.value = true
  monitorsLoading.value = true
  topFailuresLoading.value = true
  planTrendsLoading.value = true

  const dashP = statsApi.dashboard({ project }).then((d) => { data.value = d }).finally(() => { loading.value = false })
  const monP = statsApi.monitors({ project }).then((d) => { monitors.value = d.monitors }).finally(() => { monitorsLoading.value = false })
  const topP = statsApi.topFailures({ project }).then((d) => { topFailures.value = d.top_failures }).finally(() => { topFailuresLoading.value = false })
  const planP = statsApi.planTrends({ project }).then((d) => { plans.value = d.plans }).finally(() => { planTrendsLoading.value = false })

  await Promise.allSettled([dashP, monP, topP, planP])
}

watch(() => projectStore.currentProjectId, () => { loadAll() }, { immediate: true })

function healthLabel(h: string) {
  return {
    ok: t('dashboard.healthOk'),
    stale: t('dashboard.healthStale'),
    dead: t('dashboard.healthDead'),
  }[h] || h
}

function passRateColor(rate: number) {
  if (rate >= 95) return '#52c41a'
  if (rate >= 80) return '#faad14'
  return '#ff4d4f'
}

function failRateColor(rate: number) {
  if (rate >= 50) return '#ff4d4f'
  if (rate >= 20) return '#faad14'
  return '#888'
}

function formatAge(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return t('common.never')
  if (seconds < 60) return t('dashboard.secondsAgo', { count: seconds })
  if (seconds < 3600) return t('dashboard.minutesAgo', { count: Math.floor(seconds / 60) })
  if (seconds < 86400) return t('dashboard.hoursAgo', { count: Math.floor(seconds / 3600) })
  return t('dashboard.daysAgo', { count: Math.floor(seconds / 86400) })
}

function formatNextRun(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  const diffMs = d.getTime() - Date.now()
  if (diffMs < 0) return t('dashboard.pending')
  const sec = Math.floor(diffMs / 1000)
  if (sec < 60) return t('dashboard.inSeconds', { count: sec })
  if (sec < 3600) return t('dashboard.inMinutes', { count: Math.floor(sec / 60) })
  if (sec < 86400) return t('dashboard.inHours', { count: Math.floor(sec / 3600) })
  return d.toISOString().substring(0, 16).replace('T', ' ')
}

function sparkValues(daily: PlanTrendRow['daily']): (number | null)[] {
  return daily.map((d) => d.avg_pass_rate)
}

const Sparkline = defineComponent({
  name: 'Sparkline',
  props: {
    values: { type: Array as () => (number | null)[], required: true },
  },
  setup(props) {
    return () => {
      const W = 140
      const H = 28
      const PAD = 2
      const xs = props.values.map((_, i) => PAD + (i * (W - PAD * 2)) / Math.max(props.values.length - 1, 1))
      // y-axis: pass rate 0–100, with null treated as gap
      const yFor = (v: number | null) => {
        if (v === null) return null
        return PAD + (1 - v / 100) * (H - PAD * 2)
      }
      const ys = props.values.map(yFor)

      // Build path with gaps where null
      const segments: string[] = []
      let cur: string[] = []
      ys.forEach((y, i) => {
        if (y === null) {
          if (cur.length) { segments.push(cur.join(' ')); cur = [] }
        } else {
          cur.push(`${cur.length === 0 ? 'M' : 'L'} ${xs[i].toFixed(1)} ${y.toFixed(1)}`)
        }
      })
      if (cur.length) segments.push(cur.join(' '))

      const dots = ys.map((y, i) => y === null ? null : h('circle', {
        cx: xs[i].toFixed(1),
        cy: y.toFixed(1),
        r: 1.5,
        fill: '#1890ff',
      }))

      return h('svg', {
        width: W, height: H,
        viewBox: `0 0 ${W} ${H}`,
        style: 'display:block;overflow:visible',
      }, [
        // Baseline at 90%
        h('line', {
          x1: 0, x2: W,
          y1: yFor(90), y2: yFor(90),
          stroke: 'rgba(82,196,26,0.25)',
          'stroke-dasharray': '2 2',
        }),
        ...segments.map((d) => h('path', {
          d, fill: 'none', stroke: '#1890ff', 'stroke-width': 1.5, 'stroke-linejoin': 'round',
        })),
        ...dots.filter(Boolean),
      ])
    }
  },
})
</script>

<style scoped>
.pm-dashboard { padding: 20px; color: var(--text); overflow-y: auto; height: 100%; }
.pm-stats-row { margin-bottom: 16px; }
.pm-row { margin-bottom: 16px; }

.pm-card-hint { font-size: 11px; color: var(--text-3); }

/* Common table styling */
.pm-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.pm-table th {
  text-align: left;
  padding: 6px 8px;
  font-weight: 500;
  color: var(--text-3);
  border-bottom: 1px solid var(--border);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.pm-table td {
  padding: 8px;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
  color: var(--text-2);
}
.pm-table tr:last-child td { border-bottom: none; }
.pm-th-num { text-align: right; }
.pm-mono { font-family: 'SF Mono', Monaco, Menlo, Consolas, monospace; font-size: 11px; }
.pm-text-dim { color: var(--text-3); }
.pm-link { color: var(--accent); }
.pm-link:hover { text-decoration: underline; }

/* Status pills */
.pm-pill {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.4px;
  margin-right: 8px;
  vertical-align: middle;
}
.pm-pill-ok { background: rgba(82,196,26,0.15); color: #52c41a; }
.pm-pill-stale { background: rgba(250,173,20,0.15); color: #faad14; }
.pm-pill-dead { background: rgba(255,77,79,0.15); color: #ff4d4f; }

.pm-monitor-name { font-weight: 500; color: var(--text); }
.pm-monitor-env {
  margin-left: 8px;
  font-size: 11px;
  color: var(--text-3);
  padding: 0 4px;
  border-radius: 2px;
  background: var(--bg-deep);
}

.pm-error-line {
  font-size: 11px;
  color: var(--text-3);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 280px;
}

/* Plan sparklines */
.pm-plan-grid { display: flex; flex-direction: column; }
.pm-plan-row {
  display: grid;
  grid-template-columns: 1fr 160px 160px;
  gap: 16px;
  align-items: center;
  padding: 8px 4px;
  border-bottom: 1px solid var(--border);
}
.pm-plan-row:last-child { border-bottom: none; }
.pm-plan-name { font-size: 13px; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pm-plan-spark { display: flex; align-items: center; }
.pm-plan-meta { display: flex; gap: 12px; justify-content: flex-end; align-items: baseline; font-size: 12px; }

@media (max-width: 768px) {
  .pm-dashboard { padding: 12px; }
  .pm-plan-row { grid-template-columns: 1fr; gap: 4px; }
  .pm-plan-meta { justify-content: flex-start; }
  .pm-error-line { max-width: 200px; }
}
</style>
