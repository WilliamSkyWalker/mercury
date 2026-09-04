import request from './request.ts'

export interface Project {
  id: number
  name: string
  description: string
  testcase_count?: number
  env_count?: number
  testplan_count?: number
  created_at: string
  updated_at: string
}

export const projectApi = {
  list: (params?: Record<string, any>) => request.get<any, any>('/projects/', { params }),
  get: (id: number) => request.get<any, Project>(`/projects/${id}/`),
  create: (data: Partial<Project>) => request.post<any, Project>('/projects/', data),
  update: (id: number, data: Partial<Project>) => request.patch<any, Project>(`/projects/${id}/`, data),
  delete: (id: number) => request.delete(`/projects/${id}/`),
}
