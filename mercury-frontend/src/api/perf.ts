import request from './request.ts'

export interface Transaction {
  name: string
  weight: number
  sort_order: number
}

export interface PerfPlanCase {
  id: number
  testcase: number
  case_name: string
  role: 'setup' | 'transaction'
  transaction_name: string
  sort_order: number
  data_file_s3_key: string
  data_mode: 'round_robin' | 'random' | 'sequential_once'
  case_snapshot: Record<string, any>
  created_at: string
  updated_at: string
}

export interface PerfPlan {
  id: number
  project: number
  env: number | null
  env_name: string
  name: string
  description: string
  target_rate: number
  duration_secs: number
  max_vus: number
  transactions: Transaction[]
  account_data_file_s3_key: string
  notify_feishu_webhook: string
  notify_on_completion: boolean
  notify_on_failure: boolean
  plan_cases: PerfPlanCase[]
  created_at: string
  updated_at: string
}

export interface PerfPlanListItem {
  id: number
  project: number
  env: number | null
  env_name: string
  name: string
  description: string
  target_rate: number
  duration_secs: number
  max_vus: number
  transaction_count: number
  case_count: number
  created_at: string
  updated_at: string
}

export interface PerfRunSummary {
  total_reqs?: number
  success_count?: number
  error_count?: number
  dropped_count?: number
  active_vus?: number
  current_rps?: number
  latency_ms?: { p50: number; p95: number; p99: number; avg: number; min: number; max: number }
  per_transaction?: Record<string, { count: number; error_rate: number; p95_ms: number }>
}

export interface PerfRun {
  id: number
  perf_plan: number
  plan_name?: string
  target_rate: number
  duration_secs: number
  max_vus: number
  status: 'pending' | 'running' | 'completed' | 'failed' | 'aborting' | 'aborted' | 'setup_failed'
  started_at: string | null
  finished_at: string | null
  last_heartbeat_at: string | null
  summary_json: PerfRunSummary
  error_message: string
  total_reqs?: number
  error_rate?: number
  p95_ms?: number
  created_at: string
  updated_at?: string
}

export const perfApi = {
  // Plans
  listPlans: (params?: Record<string, any>) =>
    request.get<any, any>('/perf-plans/', { params }),
  getPlan: (id: number) => request.get<any, PerfPlan>(`/perf-plans/${id}/`),
  createPlan: (data: Partial<PerfPlan>) =>
    request.post<any, PerfPlan>('/perf-plans/', data),
  updatePlan: (id: number, data: Partial<PerfPlan>) =>
    request.patch<any, PerfPlan>(`/perf-plans/${id}/`, data),
  deletePlan: (id: number) => request.delete(`/perf-plans/${id}/`),

  // Cases
  listCases: (id: number, params?: Record<string, any>) =>
    request.get<any, PerfPlanCase[]>(`/perf-plans/${id}/cases/`, { params }),
  addCases: (id: number, payload: { role: 'setup' | 'transaction'; transaction_name?: string; case_ids: number[] }) =>
    request.post<any, PerfPlanCase[]>(`/perf-plans/${id}/cases/`, payload),
  updateCases: (id: number, payload: { ordering?: { id: number; sort_order: number }[]; data_bindings?: any[] }) =>
    request.put<any, any>(`/perf-plans/${id}/cases/`, payload),
  removeCases: (id: number, planCaseIds: number[]) =>
    request.delete<any, any>(`/perf-plans/${id}/cases/`, { data: { plan_case_ids: planCaseIds } }),
  syncSnapshots: (id: number) => request.post<any, any>(`/perf-plans/${id}/sync/`),

  // Run
  triggerRun: (id: number, overrides?: { target_rate?: number; duration_secs?: number; max_vus?: number }) =>
    request.post<any, PerfRun>(`/perf-plans/${id}/run/`, overrides || {}),
  listRuns: (id: number, limit = 50) =>
    request.get<any, PerfRun[]>(`/perf-plans/${id}/runs/`, { params: { limit } }),

  // Run detail / abort
  getRun: (id: number) => request.get<any, PerfRun>(`/perf-runs/${id}/`),
  abortRun: (id: number) => request.post<any, any>(`/perf-runs/${id}/abort/`),

  // Data file uploads
  uploadAccountPool: (id: number, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return request.post<any, { s3_key: string }>(
      `/perf-plans/${id}/upload-account-pool/`,
      fd,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
  },
  uploadCaseData: (planId: number, planCaseId: number, file: File, mode?: string) => {
    const fd = new FormData()
    fd.append('file', file)
    if (mode) fd.append('mode', mode)
    return request.post<any, { s3_key: string; mode: string }>(
      `/perf-plans/${planId}/cases/${planCaseId}/upload-data/`,
      fd,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
  },
}
