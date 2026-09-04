import request from './request.ts'

// Users
export function getUsers() {
  return request.get('/users/')
}

export function toggleWhitelistAdmin(id: number) {
  return request.post(`/whitelist/${id}/toggle-admin/`)
}

// Whitelist
export function getWhitelist() {
  return request.get('/whitelist/')
}

export function addWhitelist(data: { email: string; note?: string }) {
  return request.post('/whitelist/', data)
}

export function deleteWhitelist(id: number) {
  return request.delete(`/whitelist/${id}/`)
}

// Project Permissions
export function getPermissions(params?: { user?: number; project?: number }) {
  return request.get('/permissions/', { params })
}

export function addPermission(data: { user: number; project: number }) {
  return request.post('/permissions/', data)
}

export function deletePermission(id: number) {
  return request.delete(`/permissions/${id}/`)
}

// Audit Logs
export function getAuditLogs(params?: { page?: number; user_email?: string; action?: string; search?: string }) {
  return request.get('/audit-logs/', { params })
}
