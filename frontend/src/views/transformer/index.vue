<template>
  <section class="page" data-module="transformer">
    <header class="page-head">
      <div>
        <h2>箱变管理管理</h2>
        <p class="page-desc">维护箱式变压器，围绕箱变编号、箱变型号、额定容量、所属电站做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记箱式变压器</button>
        <button class="btn" type="button" @click="exportRows">导出箱变管理清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <label class="filter-item">
        <span>箱变状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in rowActions(row)"
              :key="action"
              class="link"
              type="button"
              @click="askAction(action, row)"
            >
              {{ action }}
            </button>
            <span v-if="!rowActions(row).length" class="muted-text">无可用动作</span>
            <button class="link" type="button" @click="openDetail(row)">详情</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无箱变管理数据，可先登记箱式变压器</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条箱变管理记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="detailEntry || detailLoading" class="modal-mask" @click.self="closeDetail">
      <div class="modal" role="dialog" aria-label="箱式变压器详情">
        <header class="modal-head">
          <h3>箱式变压器详情</h3>
          <button class="link" type="button" @click="closeDetail">关闭</button>
        </header>
        <p v-if="detailLoading" class="muted-text">正在读取最新状态…</p>
        <template v-else-if="detailEntry">
          <dl class="detail-grid">
            <template v-for="column in columns" :key="column">
              <dt>{{ column }}</dt>
              <dd>{{ detailEntry[column] ?? '—' }}</dd>
            </template>
          </dl>
          <footer class="modal-foot">
            <span class="muted-text">当前环节：{{ detailEntry['箱变状态'] ?? '—' }}</span>
            <span class="row-actions">
              <button
                v-for="action in rowActions(detailEntry)"
                :key="action"
                class="btn"
                type="button"
                @click="askAction(action, detailEntry)"
              >
                {{ action }}
              </button>
              <span v-if="!rowActions(detailEntry).length" class="muted-text">无可用动作</span>
            </span>
          </footer>
        </template>
      </div>
    </div>

    <div v-if="pendingAction" class="modal-mask" @click.self="cancelAction">
      <div class="modal" role="dialog" aria-label="箱变操作确认">
        <header class="modal-head">
          <h3>确认执行「{{ pendingAction.action }}」</h3>
          <button class="link" type="button" @click="cancelAction">取消</button>
        </header>
        <dl class="detail-grid">
          <dt>箱变编号</dt>
          <dd>{{ pendingAction.row['箱变编号'] ?? '—' }}</dd>
          <dt>额定容量</dt>
          <dd>{{ pendingAction.row['额定容量'] ?? '—' }}</dd>
          <dt>当前状态</dt>
          <dd>{{ pendingAction.row['箱变状态'] ?? '—' }}</dd>
          <dt>目标状态</dt>
          <dd>{{ actionTarget(pendingAction) }}</dd>
        </dl>
        <footer class="modal-foot">
          <span class="muted-text">执行后列表、详情与弹窗将同步进入下一环节</span>
          <span class="row-actions">
            <button class="btn ghost" type="button" :disabled="submitting" @click="cancelAction">再想想</button>
            <button class="btn primary" type="button" :disabled="submitting" @click="confirmAction">
              {{ submitting ? '执行中…' : '确认执行' }}
            </button>
          </span>
        </footer>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null> & {
  id?: string | number
  available_actions?: string[]
  action_targets?: Record<string, string>
}

const ENDPOINT = '/api/transformer'
const columns = ["箱变编号", "箱变型号", "额定容量", "所属电站", "油温", "绕组温度", "上次检修日", "箱变状态"]
const statuses = ["运行", "轻瓦斯", "重瓦斯", "停机"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const statusFilter = ref('')
const filterFields = columns.slice(0, 3)

// 统计卡片跟着当前列表数据走，不再写死
const stats = computed(() => [
  { label: '运行箱变', value: rows.value.filter((row) => row['箱变状态'] === '运行').length },
  { label: '告警箱变', value: rows.value.filter((row) => ['轻瓦斯', '重瓦斯'].includes(String(row['箱变状态']))).length },
  { label: '停机箱变', value: rows.value.filter((row) => row['箱变状态'] === '停机').length },
])

// 详情弹窗：每次打开都重新拉取，避免残留旧值
const detailEntry = ref<Row | null>(null)
const detailLoading = ref(false)

// 操作确认弹窗：一次只允许一条待确认动作，提交中禁止重复点击
const pendingAction = ref<{ action: string; row: Row } | null>(null)
const submitting = ref(false)

function rowActions(row: Row): string[] {
  return Array.isArray(row.available_actions) ? row.available_actions : []
}

function actionTarget(pending: { action: string; row: Row }): string {
  return pending.row.action_targets?.[pending.action] ?? '—'
}

function buildQuery(): string {
  const query = new URLSearchParams()
  if (filters.value['箱变编号']) query.set('keyword', filters.value['箱变编号'])
  if (filters.value['箱变型号']) query.set('箱变型号', filters.value['箱变型号'])
  if (filters.value['额定容量']) query.set('额定容量', filters.value['额定容量'])
  if (statusFilter.value) query.set('status', statusFilter.value)
  return query.toString()
}

function resetFilters() {
  filters.value = {}
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '箱式变压器登记入口尚未接入审批流'
}

async function openDetail(row: Row) {
  detailEntry.value = null
  detailLoading.value = true
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('箱式变压器详情读取失败')
    }
    detailEntry.value = (await response.json()) as Row
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '箱式变压器详情读取失败'
    detailEntry.value = null
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  detailEntry.value = null
  detailLoading.value = false
}

function askAction(action: string, row: Row) {
  noticeMessage.value = ''
  errorMessage.value = ''
  pendingAction.value = { action, row }
}

function cancelAction() {
  if (!submitting.value) {
    pendingAction.value = null
  }
}

async function confirmAction() {
  const pending = pendingAction.value
  if (!pending || submitting.value) {
    return
  }
  submitting.value = true
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${pending.row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action: pending.action }),
    })
    const payload = (await response.json()) as { ok: boolean; message?: string }
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || '箱变管理动作未生效，请稍后重试')
    }
    noticeMessage.value = payload.message ?? '箱变管理操作已完成'
    pendingAction.value = null
    await reload()
    if (detailEntry.value && detailEntry.value.id === pending.row.id) {
      await openDetail(pending.row)
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '箱变管理操作失败'
    pendingAction.value = null
    await reload()
  } finally {
    submitting.value = false
  }
}

async function reload() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}?${buildQuery()}`)
    if (!response.ok) {
      throw new Error('箱式变压器列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '箱变管理列表读取失败'
  }
}

onMounted(reload)
</script>
