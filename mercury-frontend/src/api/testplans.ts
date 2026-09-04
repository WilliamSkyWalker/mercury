import request from './request.ts'

export interface PlanCase {
  id: number
  testcase: number
  case_name: string
  method: string
  url: string
  sort_order: number
}

export interface Testplan {
  id: number
  name: string
  folder: number | null
  env: number | null
  env_name: string
  is_serial: boolean
  retry_count: number
  feishu_webhook: string
  notify_on_failure: boolean
  plan_cases: PlanCase[]
  case_count?: number
  created_at: string
  updated_at: string
}

export const testplanApi = {
  list: (params?: Record<string, any>) => request.get<any, any>('/testplans/', { params }),
  get: (id: number) => request.get<any, Testplan>(`/testplans/${id}/`),
  create: (data: Partial<Testplan>) => request.post<any, Testplan>('/testplans/', data),
  update: (id: number, data: Partial<Testplan>) => request.patch<any, Testplan>(`/testplans/${id}/`, data),
  delete: (id: number) => request.delete(`/testplans/${id}/`),
  run: (id: number, envId?: number) => request.post<any, any>(`/testplans/${id}/run/`, { env_id: envId }),
  getCases: (id: number) => request.get<any, PlanCase[]>(`/testplans/${id}/cases/`),
  addCases: (id: number, caseIds: number[]) =>
    request.post<any, any>(`/testplans/${id}/cases/`, { case_ids: caseIds }),
  removeCases: (id: number, planCaseIds: number[]) =>
    request.delete<any, any>(`/testplans/${id}/cases/`, { data: { plan_case_ids: planCaseIds } }),
  updateCaseOrder: (id: number, ordering: { id: number; sort_order: number }[]) =>
    request.put<any, any>(`/testplans/${id}/cases/`, { ordering }),
  getSyncDiff: (id: number) => request.get<any, any>(`/testplans/${id}/sync/`),
  applySync: (id: number, planCaseIds: number[]) =>
    request.post<any, any>(`/testplans/${id}/sync/`, { plan_case_ids: planCaseIds }),
}
