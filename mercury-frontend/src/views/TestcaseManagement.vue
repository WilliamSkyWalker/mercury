<template>
  <div class="pm-workspace">
    <!-- Left sidebar: unified collection tree -->
    <div class="pm-sidebar">
      <div class="pm-sidebar-header">
        <span class="pm-sidebar-title">{{ t('testcase.collections') }}</span>
        <a-button type="text" size="small" class="pm-icon-btn" @click="onNewFolder">
          <FolderAddOutlined />
        </a-button>
      </div>
      <div class="pm-sidebar-content">
        <FolderTree ref="folderTreeRef" @select="onTreeSelect" />
      </div>
    </div>

    <!-- Right: editor area -->
    <div class="pm-editor-area">
      <CaseEditor
        :case-id="selectedCaseId"
        :folder-id="selectedFolderId"
        @saved="onCaseSaved"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { FolderAddOutlined } from '@ant-design/icons-vue'
import FolderTree from '../components/testcase/FolderTree.vue'
import CaseEditor from '../components/testcase/CaseEditor.vue'

const { t } = useI18n()
const folderTreeRef = ref()
const selectedFolderId = ref<number | null>(null)
const selectedCaseId = ref<number | null>(null)

function onTreeSelect(payload: { type: string | null; id: number | null; folderId: number | null }) {
  if (payload.type === 'case') {
    selectedCaseId.value = payload.id
    selectedFolderId.value = payload.folderId
  } else if (payload.type === 'folder') {
    selectedFolderId.value = payload.folderId
    selectedCaseId.value = null
  } else if (payload.type === 'new-case') {
    selectedFolderId.value = payload.folderId
    selectedCaseId.value = null
  } else {
    selectedFolderId.value = null
    selectedCaseId.value = null
  }
}

function onCaseSaved() {
  folderTreeRef.value?.loadTree()
}

function onNewFolder() {
  folderTreeRef.value?.onAddRoot?.()
}
</script>

<style scoped>
.pm-workspace {
  display: flex;
  height: 100%;
  overflow: hidden;
}

/* Sidebar */
.pm-sidebar {
  width: 240px;
  flex-shrink: 0;
  background: var(--bg-panel);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.pm-sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 12px 8px;
  border-bottom: 1px solid var(--border);
}
.pm-sidebar-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-2);
}
.pm-icon-btn {
  color: var(--text-3) !important;
  font-size: 14px;
}
.pm-icon-btn:hover {
  color: var(--accent) !important;
}
.pm-sidebar-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 4px 0;
}

/* Editor area */
.pm-editor-area {
  flex: 1;
  overflow: hidden;
  min-width: 0;
}

/* Mobile: sidebar becomes collapsible top panel */
@media (max-width: 768px) {
  .pm-workspace { flex-direction: column; }
  .pm-sidebar { width: 100%; max-height: 40vh; border-right: none; border-bottom: 1px solid var(--border); }
  .pm-editor-area { flex: 1; min-height: 0; }
}
</style>
