import request from './request.ts'

export interface Env {
  id: number
  name: string
  variables: Record<string, string>
  created_at: string
  updated_at: string
}

export const envApi = {
  list: (params?: Record<string, any>) => request.get<any, any>('/envs/', { params }),
  get: (id: number) => request.get<any, Env>(`/envs/${id}/`),
  create: (data: Partial<Env>) => request.post<any, Env>('/envs/', data),
  update: (id: number, data: Partial<Env>) => request.patch<any, Env>(`/envs/${id}/`, data),
  delete: (id: number) => request.delete(`/envs/${id}/`),
}
