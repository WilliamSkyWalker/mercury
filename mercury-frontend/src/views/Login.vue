<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <h1>Mercury</h1>
        <p class="subtitle">{{ t('auth.subtitle') }}</p>
      </div>
      <a-form layout="vertical" @finish="handleLogin">
        <a-form-item :label="t('auth.email')">
          <a-input
            v-model:value="email"
            :placeholder="t('auth.emailPlaceholder')"
            size="large"
            @pressEnter="handleLogin"
          />
        </a-form-item>
        <a-form-item :label="t('auth.password')">
          <a-input-password
            v-model:value="password"
            :placeholder="t('auth.password')"
            size="large"
            @pressEnter="handleLogin"
          />
        </a-form-item>
        <a-button
          type="primary"
          size="large"
          block
          :loading="loading"
          @click="handleLogin"
        >
          {{ t('auth.login') }}
        </a-button>
        <a-alert
          v-if="errorMsg"
          :message="errorMsg"
          type="error"
          show-icon
          style="margin-top: 16px"
        />
      </a-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { login } from '../api/auth.ts'
import { useAuthStore } from '../stores/auth.ts'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useI18n()

const email = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

async function handleLogin() {
  if (!email.value || !password.value) {
    errorMsg.value = t('auth.missingCredentials')
    return
  }
  errorMsg.value = ''
  loading.value = true
  try {
    const res = await login(email.value, password.value)
    authStore.setAuth(res.token, res.user)
    router.replace('/')
  } catch (e: any) {
    errorMsg.value = e.response?.data?.detail || e.message || t('auth.loginFailed')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-deep);
}
.login-card {
  width: 380px;
  padding: 40px;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 12px;
}
.login-header {
  text-align: center;
  margin-bottom: 32px;
}
.login-header h1 {
  margin: 8px 0 4px;
  font-size: 28px;
  color: var(--text);
}
.subtitle {
  color: var(--text-3);
  margin: 0;
}

@media (max-width: 768px) {
  .login-card { width: 90%; max-width: 380px; padding: 24px; }
  .login-header h1 { font-size: 24px; }
}
</style>
