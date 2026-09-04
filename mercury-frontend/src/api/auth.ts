import axios from 'axios'

const authRequest = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export interface LoginResponse {
  token: string
  user: {
    email: string
    display_name: string
    username: string
  }
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const res = await authRequest.post('/auth/login/', { email, password })
  return res.data
}
