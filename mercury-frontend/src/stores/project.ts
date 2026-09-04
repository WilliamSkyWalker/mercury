import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { projectApi, type Project } from '../api/projects.ts'

const STORAGE_KEY = 'mercury_current_project_id'

export const useProjectStore = defineStore('project', () => {
  const projects = ref<Project[]>([])
  const currentProjectId = ref<number | null>(getSavedProjectId())
  const loading = ref(false)

  const currentProject = computed(() =>
    projects.value.find(p => p.id === currentProjectId.value) || null
  )

  function getSavedProjectId(): number | null {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? Number(saved) : null
  }

  function setCurrentProject(id: number) {
    currentProjectId.value = id
    localStorage.setItem(STORAGE_KEY, String(id))
  }

  function clearCurrentProject() {
    currentProjectId.value = null
    localStorage.removeItem(STORAGE_KEY)
  }

  async function fetchProjects() {
    loading.value = true
    try {
      const res = await projectApi.list({ page_size: 100 })
      projects.value = res.results || res
    } catch {
      // Silently ignore (e.g. 401 on public pages)
    } finally {
      loading.value = false
    }
  }

  return {
    projects,
    currentProjectId,
    currentProject,
    loading,
    fetchProjects,
    setCurrentProject,
    clearCurrentProject,
  }
})
