import request from './request.ts'

export interface CaseResult {
  id: number
  testcase: number | null
  case_name: string
  status: string
  request_method: string
  request_url: string
  request_headers: Record<string, string>
  request_body: string
  response_status: number
  response_headers: Record<string, string>
  response_body: string
  duration_ms: number
  assertion_results: any[]
  extracted_variables: Record<string, any>
  error_message: string
  stream_metrics?: {
    first_token_ms: number
    last_token_ms: number
    token_count: number
    tokens_per_sec: number | null
  } | null
  created_at: string
}

export interface Execution {
  id: number
  task_id: string
  testplan: number | null
  testplan_name: string
  env: number | null
  env_name: string
  trigger_type: string
  status: string
  total_cases: number
  passed_cases: number
  failed_cases: number
  error_cases: number
  skipped_cases: number
  pass_rate: number
  duration_ms: number
  report_url: string
  case_results?: CaseResult[]
  created_at: string
  updated_at: string
}

export const executionApi = {
  list: (params?: Record<string, any>) => request.get<any, any>('/executions/', { params }),
  get: (id: number) => request.get<any, Execution>(`/executions/${id}/`),
  listCaseResults: (executionId: number, params?: Record<string, any>) =>
    request.get<any, any>(`/executions/${executionId}/case-results/`, { params }),
  getCaseResult: (executionId: number, resultId: number) =>
    request.get<any, CaseResult>(`/executions/${executionId}/case-results/${resultId}/`),
  report: (id: number) => request.get<any, any>(`/executions/${id}/report/`),
}
