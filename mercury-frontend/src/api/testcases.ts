import request from './request.ts'

export interface HeaderItem {
  key: string
  value: string
  enabled: boolean
}

export interface ParamItem {
  key: string
  value: string
  enabled: boolean
}

export interface Assertion {
  field: string
  operator: string
  expected: any
}

export type WsStepKind = 'send' | 'recv' | 'wait' | 'close'

export interface WsStep {
  kind: WsStepKind
  // send
  payload_type?: 'text' | 'json' | 'binary_b64'
  payload?: any
  // recv
  timeout_ms?: number
  // wait
  duration_ms?: number
  // close
  code?: number
  reason?: string
}

export interface Testcase {
  id: number
  case_name: string
  method: string
  url: string
  headers: HeaderItem[]
  params: ParamItem[]
  body_type: string
  body: any
  assertions: Assertion[]
  pre_request_script: string
  post_request_script: string
  script_type: string
  timeout: number
  folder: number | null
  folder_name: string
  sort_order: number
  tags: string[]
  comment: string
  ws_steps: WsStep[] | null
  created_at: string
  updated_at: string
}

export interface RunResult {
  case_name: string
  status: string
  request: any
  response: any
  assertion_results: any[]
  extracted_variables: Record<string, any>
  error_message: string
  duration_ms: number
}

export const testcaseApi = {
  list: (params?: Record<string, any>) => request.get<any, any>('/testcases/', { params }),
  get: (id: number) => request.get<any, Testcase>(`/testcases/${id}/`),
  create: (data: Partial<Testcase> & { project?: number | null }) => request.post<any, Testcase>('/testcases/', data),
  update: (id: number, data: Partial<Testcase>) => request.patch<any, Testcase>(`/testcases/${id}/`, data),
  delete: (id: number) => request.delete(`/testcases/${id}/`),
  run: (id: number, envId?: number) => request.post<any, RunResult>(`/testcases/${id}/run/`, { env_id: envId }),
  batchRun: (caseIds: number[], envId?: number) =>
    request.post<any, any>('/testcases/batch-run/', { case_ids: caseIds, env_id: envId }),
  uploadFile: (id: number, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post<any, any>(`/testcases/${id}/upload-file/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  deleteFile: (id: number, fileName: string) =>
    request.delete<any, any>(`/testcases/${id}/delete-file/`, { data: { name: fileName } }),
}
