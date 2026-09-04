import request from './request.ts'

export interface Folder {
  id: number
  project: number
  name: string
  parent: number | null
  sort_order: number
  children?: Folder[]
  testcase_count?: number
  created_at: string
  updated_at: string
}

export const folderApi = {
  tree: (params?: Record<string, any>) => request.get<any, Folder[]>('/folders/tree/', { params }),
  list: (params?: Record<string, any>) => request.get<any, any>('/folders/', { params }),
  get: (id: number) => request.get<any, Folder>(`/folders/${id}/`),
  create: (data: Partial<Folder>) => request.post<any, Folder>('/folders/', data),
  update: (id: number, data: Partial<Folder>) => request.patch<any, Folder>(`/folders/${id}/`, data),
  delete: (id: number) => request.delete(`/folders/${id}/`),
}
