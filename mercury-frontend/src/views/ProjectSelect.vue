<template>
  <div class="project-select-page">
    <div class="project-select-container">
      <h1 class="title">Mercury</h1>
      <p class="subtitle">Select a project to continue</p>

      <a-spin :spinning="projectStore.loading">
        <div class="project-grid">
          <div
            v-for="p in projectStore.projects"
            :key="p.id"
            class="project-card"
            @click="onSelect(p)"
          >
            <div class="project-card-name">{{ p.name }}</div>
            <div class="project-card-desc">{{ p.description || 'No description' }}</div>
            <div class="project-card-stats">
              <span><ExperimentOutlined /> {{ p.testcase_count || 0 }} cases</span>
              <span><CloudServerOutlined /> {{ p.env_count || 0 }} envs</span>
              <span><OrderedListOutlined /> {{ p.testplan_count || 0 }} plans</span>
            </div>
          </div>

          <div class="project-card project-card-new" @click="showCreateModal = true">
            <PlusOutlined style="font-size: 32px; color: var(--text-3)" />
            <div style="color: var(--text-3); margin-top: 8px">New Project</div>
          </div>
        </div>
      </a-spin>

      <a-modal v-model:open="showCreateModal" title="Create Project" :confirm-loading="createLoading" @ok="onCreate">
        <a-form layout="vertical">
          <a-form-item label="Name">
            <a-input v-model:value="newProject.name" placeholder="Project name" />
          </a-form-item>
          <a-form-item label="Description">
            <a-textarea v-model:value="newProject.description" placeholder="Optional description" :rows="3" />
          </a-form-item>
        </a-form>
      </a-modal>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  PlusOutlined,
  ExperimentOutlined,
  CloudServerOutlined,
  OrderedListOutlined,
} from '@ant-design/icons-vue'
import { useProjectStore } from '../stores/project.ts'
import { projectApi, type Project } from '../api/projects.ts'
import { useLoading } from '../composables/useLoading.ts'

const router = useRouter()
const projectStore = useProjectStore()

const showCreateModal = ref(false)
const newProject = reactive({ name: '', description: '' })

function onSelect(p: Project) {
  projectStore.setCurrentProject(p.id)
  router.push('/testcases')
}

const [onCreate, createLoading] = useLoading(async () => {
  if (!newProject.name) { message.warning('Name is required'); return }
  const created = await projectApi.create(newProject)
  message.success('Project created')
  showCreateModal.value = false
  newProject.name = ''
  newProject.description = ''
  await projectStore.fetchProjects()
  onSelect(created)
})

onMounted(() => { projectStore.fetchProjects() })
</script>

<style scoped>
.project-select-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-deep);
}
.project-select-container {
  text-align: center;
  max-width: 800px;
  width: 100%;
  padding: 40px;
}
.title {
  font-size: 36px;
  font-weight: 700;
  margin-bottom: 4px;
  color: var(--accent);
}
.subtitle {
  font-size: 16px;
  color: var(--text-3);
  margin-bottom: 40px;
}
.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
  text-align: left;
}
.project-card {
  background: var(--bg-panel);
  border-radius: 8px;
  padding: 20px;
  cursor: pointer;
  border: 2px solid var(--border);
  transition: all 0.2s;
  min-height: 140px;
  display: flex;
  flex-direction: column;
}
.project-card:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 12px rgba(255, 108, 55, 0.15);
}
.project-card-new {
  align-items: center;
  justify-content: center;
  border: 2px dashed var(--border);
}
.project-card-new:hover {
  border-color: var(--accent);
}
.project-card-name {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--text);
}
.project-card-desc {
  color: var(--text-3);
  font-size: 13px;
  flex: 1;
  margin-bottom: 12px;
}
.project-card-stats {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-3);
}

@media (max-width: 768px) {
  .project-select-container { padding: 20px 16px; }
  .title { font-size: 28px; }
  .subtitle { font-size: 14px; margin-bottom: 24px; }
  .project-grid { grid-template-columns: 1fr; gap: 12px; }
  .project-card { min-height: 100px; padding: 16px; }
  .project-card-name { font-size: 16px; }
  .project-card-stats { flex-wrap: wrap; gap: 8px; }
}
</style>
