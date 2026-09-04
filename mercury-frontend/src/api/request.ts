import axios from 'axios'
import { message } from 'ant-design-vue'
import router from '../router'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('mercury_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      // Don't redirect to login on public pages (e.g. shared execution reports)
      const isPublicPage = router.currentRoute.value.meta?.public
      if (!isPublicPage) {
        localStorage.removeItem('mercury_token')
        localStorage.removeItem('mercury_user')
        router.replace({ name: 'Login' })
      }
      return Promise.reject(error)
    }
    const data = error.response?.data
    let msg = ''
    if (data) {
      if (typeof data.detail === 'string') {
        msg = data.detail
      } else if (typeof data === 'object') {
        // DRF validation errors: { field: [errors] }
        const errs = Object.entries(data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
        msg = errs.join('; ')
      }
    }
    msg = msg || error.message || 'Request failed'
    message.error(msg)
    return Promise.reject(error)
  }
)

export default request
