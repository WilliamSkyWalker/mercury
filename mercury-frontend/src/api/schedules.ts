import request from './request.ts'

export interface ScheduledTask {
  id: number
  name: string
  testplan: number
  testplan_name: string
  env: number | null
  env_name: string
  trigger_type: string
  cron_expression: string
  interval_seconds: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export const scheduleApi = {
  list: (params?: Record<string, any>) => request.get<any, any>('/schedules/', { params }),
  get: (id: number) => request.get<any, ScheduledTask>(`/schedules/${id}/`),
  create: (data: Partial<ScheduledTask>) => request.post<any, ScheduledTask>('/schedules/', data),
  update: (id: number, data: Partial<ScheduledTask>) =>
    request.patch<any, ScheduledTask>(`/schedules/${id}/`, data),
  delete: (id: number) => request.delete(`/schedules/${id}/`),
  toggle: (id: number) => request.post<any, any>(`/schedules/${id}/toggle/`),
}
