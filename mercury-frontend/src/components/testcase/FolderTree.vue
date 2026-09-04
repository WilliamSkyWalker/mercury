<template>
  <div class="pm-collection-tree">
    <div v-if="loading" class="pm-tree-loading">
      <a-spin size="small" />
    </div>
    <div v-else-if="!treeData.length" class="pm-empty">{{ t('testcase.noCollections') }}</div>
    <div v-else class="pm-tree-nodes">
      <CollectionNode
        v-for="node in treeData"
        :key="node.key"
        :node="node"
        :depth="0"
        :selected-key="selectedKey"
        @select="onNodeSelect"
        @right-click="onRightClick"
      />
    </div>

    <!-- Context menu -->
    <Teleport to="body">
      <div
        v-if="contextMenu.visible"
        class="pm-context-menu"
        :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
      >
        <template v-if="contextMenu.type === 'folder'">
          <div class="pm-context-item" @click="onContextAction({ key: 'add-folder' })">{{ t('testcase.addSubfolder') }}</div>
          <div class="pm-context-item" @click="onContextAction({ key: 'add-request' })">{{ t('testcase.addRequest') }}</div>
          <div class="pm-context-item" @click="onContextAction({ key: 'rename' })">{{ t('testcase.rename') }}</div>
          <div class="pm-context-item pm-context-danger" @click="onContextAction({ key: 'delete-folder' })">{{ t('common.delete') }}</div>
        </template>
        <template v-else>
          <div class="pm-context-item pm-context-danger" @click="onContextAction({ key: 'delete-request' })">{{ t('common.delete') }}</div>
        </template>
      </div>
    </Teleport>

    <!-- Folder modal -->
    <a-modal v-model:open="folderModal.visible" :title="t(folderModal.titleKey)" :confirm-loading="folderModalLoading" @ok="onFolderModalOk">
      <a-input v-model:value="folderModal.name" :placeholder="t('testcase.folderName')" @pressEnter="onFolderModalOk" />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, defineComponent, h } from 'vue'
import { useI18n } from 'vue-i18n'
import { message, Modal } from 'ant-design-vue'
import { folderApi, type Folder } from '../../api/folders.ts'
import { testcaseApi } from '../../api/testcases.ts'
import { useProjectStore } from '../../stores/project.ts'
import { useLoading } from '../../composables/useLoading.ts'

const projectStore = useProjectStore()
const { t } = useI18n()

interface TreeNode {
  key: string           // 'folder-1' or 'case-42'
  type: 'folder' | 'case'
  id: number
  name: string
  method?: string       // only for case
  children?: TreeNode[]
  expanded?: boolean
}

const emit = defineEmits<{
  select: [payload: { type: 'folder' | 'case' | null; id: number | null; folderId: number | null }]
}>()

const treeData = ref<TreeNode[]>([])
const selectedKey = ref<string>('')
const loading = ref(false)
const contextMenu = reactive({ visible: false, x: 0, y: 0, key: '', type: '' as 'folder' | 'case', id: 0, folderId: 0 })
const folderModal = reactive({ visible: false, titleKey: 'testcase.newCollection', name: '', parentId: null as number | null, editId: null as number | null })

async function loadTree() {
  loading.value = true
  try {
    const folders: Folder[] = await folderApi.tree({ project: projectStore.currentProjectId })
    const cases = await testcaseApi.list({ project: projectStore.currentProjectId })

    // Group cases by folder_id
    const casesByFolder: Record<number, any[]> = {}
    for (const c of cases) {
      const fid = c.folder || 0
      if (!casesByFolder[fid]) casesByFolder[fid] = []
      casesByFolder[fid].push(c)
    }

    // Build tree recursively
    function buildNodes(folders: Folder[]): TreeNode[] {
      return folders.map(f => {
        const folderChildren = buildNodes(f.children || [])
        const caseChildren: TreeNode[] = (casesByFolder[f.id] || []).map((c: any) => ({
          key: `case-${c.id}`,
          type: 'case' as const,
          id: c.id,
          name: c.case_name,
          method: c.method,
        }))
        return {
          key: `folder-${f.id}`,
          type: 'folder' as const,
          id: f.id,
          name: f.name,
          children: [...folderChildren, ...caseChildren],
          expanded: true,
        }
      })
    }

    treeData.value = buildNodes(folders)
  } finally {
    loading.value = false
  }
}

function onNodeSelect(node: TreeNode) {
  selectedKey.value = node.key
  if (node.type === 'case') {
    // Find parent folder
    const folderId = findParentFolderId(treeData.value, node.key)
    emit('select', { type: 'case', id: node.id, folderId })
  } else {
    emit('select', { type: 'folder', id: node.id, folderId: node.id })
  }
}

function findParentFolderId(nodes: TreeNode[], targetKey: string): number | null {
  for (const node of nodes) {
    if (node.children) {
      for (const child of node.children) {
        if (child.key === targetKey) return node.id
      }
      const found = findParentFolderId(node.children.filter(c => c.type === 'folder'), targetKey)
      if (found !== null) return found
    }
  }
  return null
}

function dismissContextMenu() {
  contextMenu.visible = false
}

function onRightClick(e: MouseEvent, node: TreeNode) {
  e.preventDefault()
  // Position menu, flip up if near bottom of viewport
  const menuHeight = node.type === 'folder' ? 160 : 40
  const y = (e.clientY + menuHeight > window.innerHeight) ? e.clientY - menuHeight : e.clientY
  contextMenu.x = e.clientX
  contextMenu.y = y
  contextMenu.key = node.key
  contextMenu.type = node.type
  contextMenu.id = node.id
  if (node.type === 'case') {
    contextMenu.folderId = findParentFolderId(treeData.value, node.key) || 0
  }
  contextMenu.visible = true
  setTimeout(() => document.addEventListener('click', dismissContextMenu, { once: true }), 0)
}

onBeforeUnmount(() => {
  document.removeEventListener('click', dismissContextMenu)
})

function onAddRoot() {
  folderModal.titleKey = 'testcase.newCollection'
  folderModal.name = ''
  folderModal.parentId = null
  folderModal.editId = null
  folderModal.visible = true
}

function onContextAction({ key }: { key: string }) {
  contextMenu.visible = false
  if (key === 'add-folder') {
    folderModal.titleKey = 'testcase.newSubfolder'
    folderModal.name = ''
    folderModal.parentId = contextMenu.id
    folderModal.editId = null
    folderModal.visible = true
  } else if (key === 'rename') {
    folderModal.titleKey = 'testcase.rename'
    folderModal.name = ''
    folderModal.parentId = null
    folderModal.editId = contextMenu.id
    folderModal.visible = true
  } else if (key === 'delete-folder') {
    const id = contextMenu.id
    Modal.confirm({
      title: t('testcase.deleteFolderTitle'),
      content: t('testcase.deleteFolderDescription'),
      okText: t('common.delete'),
      cancelText: t('common.cancel'),
      okType: 'danger',
      onOk: () => deleteFolder(id),
    })
  } else if (key === 'add-request') {
    selectedKey.value = ''
    emit('select', { type: 'new-case' as any, id: null, folderId: contextMenu.id })
  } else if (key === 'delete-request') {
    const id = contextMenu.id
    Modal.confirm({
      title: t('testcase.deleteRequestTitle'),
      content: t('testcase.cannotUndo'),
      okText: t('common.delete'),
      cancelText: t('common.cancel'),
      okType: 'danger',
      onOk: () => deleteRequest(id),
    })
  }
}

const [onFolderModalOk, folderModalLoading] = useLoading(async () => {
  if (!folderModal.name.trim()) {
    message.warning(t('testcase.enterName'))
    return
  }
  if (folderModal.editId) {
    await folderApi.update(folderModal.editId, { name: folderModal.name })
    message.success(t('testcase.renamed'))
  } else {
    await folderApi.create({ name: folderModal.name, parent: folderModal.parentId, project: projectStore.currentProjectId! })
    message.success(t('common.createdMessage'))
  }
  folderModal.visible = false
  await loadTree()
})

const [deleteFolder] = useLoading(async (id: number) => {
  await folderApi.delete(id)
  message.success(t('common.deleted'))
  if (selectedKey.value === `folder-${id}`) {
    selectedKey.value = ''
    emit('select', { type: null, id: null, folderId: null })
  }
  await loadTree()
})

const [deleteRequest] = useLoading(async (id: number) => {
  await testcaseApi.delete(id)
  message.success(t('common.deleted'))
  if (selectedKey.value === `case-${id}`) {
    selectedKey.value = ''
    emit('select', { type: null, id: null, folderId: null })
  }
  await loadTree()
})

onMounted(loadTree)

defineExpose({ loadTree, onAddRoot })
</script>

<script lang="ts">
// CollectionNode - renders a single tree node (folder or request)
const CollectionNode = defineComponent({
  name: 'CollectionNode',
  props: {
    node: { type: Object, required: true },
    depth: { type: Number, default: 0 },
    selectedKey: { type: String, default: '' },
  },
  emits: ['select', 'right-click'],
  setup(props, { emit }) {
    const expanded = ref(true)

    function toggle() {
      if (props.node.type === 'folder') {
        expanded.value = !expanded.value
      }
    }

    return () => {
      const node = props.node as any
      const isFolder = node.type === 'folder'
      const isSelected = props.selectedKey === node.key
      const indent = props.depth * 12

      const nodeEl = h('div', {
        class: ['pm-tree-node', { selected: isSelected }],
        style: { paddingLeft: `${indent + 8}px` },
        onClick: (e: MouseEvent) => {
          e.stopPropagation()
          if (isFolder) toggle()
          emit('select', node)
        },
        onContextmenu: (e: MouseEvent) => {
          e.preventDefault()
          e.stopPropagation()
          emit('right-click', e, node)
        },
      }, [
        // Arrow for folders
        isFolder
          ? h('span', {
              class: ['pm-tree-arrow', { expanded: expanded.value }],
            }, '▶')
          : h('span', { class: 'pm-tree-arrow-space' }),

        // Icon/method
        isFolder
          ? h('span', { class: 'pm-tree-folder-icon' }, expanded.value ? '📂' : '📁')
          : h('span', {
              class: ['pm-tree-method', `method-${(node.method || 'get').toLowerCase()}`],
            }, node.method || 'GET'),

        // Name
        h('span', { class: 'pm-tree-label', title: node.name }, node.name),
      ])

      // Children
      const children: any[] = [nodeEl]
      if (isFolder && expanded.value && node.children?.length) {
        for (const child of node.children) {
          children.push(
            h(CollectionNode, {
              node: child,
              depth: props.depth + 1,
              selectedKey: props.selectedKey,
              onSelect: (n: any) => emit('select', n),
              onRightClick: (e: MouseEvent, n: any) => emit('right-click', e, n),
            })
          )
        }
      }

      return h('div', { class: 'pm-tree-node-group' }, children)
    }
  },
})
</script>

<style scoped>
.pm-collection-tree {
  user-select: none;
}
.pm-tree-loading {
  text-align: center;
  padding: 20px;
}
.pm-empty {
  text-align: center;
  color: var(--text-3);
  font-size: 12px;
  padding: 16px 0;
}
</style>

<style>
/* Tree node styles (unscoped so they apply to render-function nodes) */
.pm-tree-node {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 3px 4px;
  cursor: pointer;
  border-radius: 3px;
  margin: 0 2px 0;
  transition: background 0.1s;
  min-height: 24px;
}
.pm-tree-node:hover {
  background: var(--bg-hover);
}
.pm-tree-node.selected {
  background: var(--bg-selected);
}
.pm-tree-arrow {
  font-size: 7px;
  color: var(--text-3);
  width: 10px;
  flex-shrink: 0;
  transition: transform 0.15s;
  display: inline-block;
  text-align: center;
}
.pm-tree-arrow.expanded {
  transform: rotate(90deg);
}
.pm-tree-arrow-space {
  width: 10px;
  flex-shrink: 0;
}
.pm-tree-folder-icon {
  font-size: 12px;
  flex-shrink: 0;
  width: 14px;
  text-align: center;
}
.pm-tree-method {
  font-size: 9px;
  font-weight: 800;
  min-width: 28px;
  flex-shrink: 0;
  text-align: left;
  font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
}
.pm-tree-method.method-get { color: var(--method-get); }
.pm-tree-method.method-post { color: var(--method-post); }
.pm-tree-method.method-put { color: var(--method-put); }
.pm-tree-method.method-delete { color: var(--method-delete); }
.pm-tree-method.method-patch { color: var(--method-patch); }
.pm-tree-method.method-head { color: var(--method-post); }
.pm-tree-method.method-options { color: var(--link); }
.pm-tree-label {
  font-size: 12px;
  line-height: 1.4;
  color: var(--text-2);
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
  flex: 1;
  min-width: 0;
}

/* Context menu */
.pm-context-menu {
  position: fixed;
  z-index: 1050;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 0;
  min-width: 140px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}
.pm-context-item {
  padding: 6px 16px;
  font-size: 13px;
  color: var(--text);
  cursor: pointer;
  transition: background 0.15s;
}
.pm-context-item:hover {
  background: var(--bg-hover);
}
.pm-context-danger {
  color: var(--error);
}

@media (max-width: 768px) {
  .pm-tree-node { padding: 3px 8px; font-size: 12px; }
  .pm-tree-empty { padding: 10px 0; font-size: 11px; }
}
</style>
