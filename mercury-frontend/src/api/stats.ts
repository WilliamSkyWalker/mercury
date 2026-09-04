import request from './request.ts'

export interface DashboardData {
  summary: {
    total_cases: number
    total_plans: number
    total_envs: number
    total_runs_7d: number
    avg_pass_rate_7d: number
  }
  daily_stats: {
    date: string
    executions: number
    avg_pass_rate: number
  }[]
  recent_failures: any[]
}

export interface MonitorRow {
  id: number
  name: string
  testplan_id: number
  testplan_name: string
  env_name: string
  trigger_type: 'interval' | 'cron'
  cadence: string
  is_active: boolean
  last_status: string | null
  last_pass_rate: number | null
  last_run_at: string | null
  last_execution_id: number | null
  age_seconds: number | null
  expected_seconds: number
  next_run_at: string | null
  health: 'ok' | 'stale' | 'dead'
}

export interface TopFailureRow {
  testcase_id: number
  name: string
  method: string
  url: string
  total_runs: number
  failed_count: number
  fail_rate: number
  last_error: string
  last_execution_id: number | null
}

export interface PlanTrendRow {
  testplan_id: number
  name: string
  total_runs_7d: number
  avg_pass_rate_7d: number
  daily: {
    date: string
    executions: number
    avg_pass_rate: number | null
  }[]
}

export const statsApi = {
  dashboard: (params?: Record<string, any>) =>
    request.get<any, DashboardData>('/stats/dashboard/', { params }),
  monitors: (params?: Record<string, any>) =>
    request.get<any, { monitors: MonitorRow[] }>('/stats/monitors/', { params }),
  topFailures: (params?: Record<string, any>) =>
    request.get<any, { top_failures: TopFailureRow[] }>('/stats/top-failures/', { params }),
  planTrends: (params?: Record<string, any>) =>
    request.get<any, { plans: PlanTrendRow[] }>('/stats/plan-trends/', { params }),
}
