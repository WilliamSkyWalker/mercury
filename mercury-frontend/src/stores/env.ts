import { defineStore } from 'pinia'
import { ref } from 'vue'
import { envApi, type Env } from '../api/envs.ts'
import { useProjectStore } from './project.ts'

export const useEnvStore = defineStore('env', () => {
  const envs = ref<Env[]>([])
  const loading = ref(false)

  async function fetchEnvs() {
    loading.value = true
    try {
      const projectStore = useProjectStore()
      const params: Record<string, any> = { page_size: 100 }
      if (projectStore.currentProjectId) {
        params.project = projectStore.currentProjectId
      }
      const res = await envApi.list(params)
      envs.value = res.results || res
    } finally {
      loading.value = false
    }
  }

  return { envs, loading, fetchEnvs }
})
