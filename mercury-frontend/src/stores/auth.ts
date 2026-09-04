import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const TOKEN_KEY = 'mercury_token'
const USER_KEY = 'mercury_user'

export interface UserInfo {
  email: string
  display_name: string
  username: string
  is_admin?: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY) || '')
  const user = ref<UserInfo | null>(
    (() => {
      try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null') }
      catch { return null }
    })()
  )

  const isLoggedIn = computed(() => !!token.value)

  function setAuth(t: string, u: UserInfo) {
    token.value = t
    user.value = u
    localStorage.setItem(TOKEN_KEY, t)
    localStorage.setItem(USER_KEY, JSON.stringify(u))
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  return { token, user, isLoggedIn, setAuth, logout }
})
