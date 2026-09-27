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
      <label class="filter-item">
        <span>箱变编号</span>
        <input v-model="filters.keyword" placeholder="按箱变编号检索" />
      </label>
      <label class="filter-item">
        <span>箱变状态</span>
        <select v-model="filters.status">
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
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <button
              v-for="action in rowActions(row)"
              :key="action"
              class="link"
              type="button"
              @click="openAction(action, row)"
            >
              {{ action }}
            </button>
            <span v-if="!rowActions(row).length" class="muted">已归档，无可用动作</span>
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

    <div v-if="detail" class="modal-mask" @click.self="closeDetail">
      <div class="modal">
        <h3>箱式变压器详情</h3>
        <dl class="detail-grid">
          <template v-for="column in columns" :key="column">
            <dt>{{ column }}</dt>
            <dd>{{ detail[column] ?? '—' }}</dd>
          </template>
        </dl>
        <div class="modal-actions">
          <button
            v-for="action in rowActions(detail)"
            :key="action"
            class="btn primary"
            type="button"
            @click="openAction(action, detail)"
          >
            {{ action }}
          </button>
          <span v-if="!rowActions(detail).length" class="muted">已归档，无可用动作</span>
          <button class="btn ghost" type="button" @click="closeDetail">关闭</button>
        </div>
      </div>
    </div>

    <div v-if="pendingAction" class="modal-mask" @click.self="cancelAction">
      <div class="modal">
        <h3>{{ pendingAction.action }}</h3>
        <dl class="detail-grid">
          <dt>箱变编号</dt>
          <dd>{{ pendingAction.row['箱变编号'] ?? '—' }}</dd>
          <dt>额定容量</dt>
          <dd>{{ pendingAction.row['额定容量'] ?? '—' }}</dd>
          <dt>当前状态</dt>
          <dd>{{ pendingAction.row['箱变状态'] ?? '—' }}</dd>
        </dl>
        <p class="modal-tip">确认对这台箱式变压器执行「{{ pendingAction.action }}」吗？</p>
        <div class="modal-actions">
          <button class="btn primary" type="button" :disabled="acting" @click="confirmAction">
            {{ acting ? '执行中…' : '确认执行' }}
          </button>
          <button class="btn ghost" type="button" :disabled="acting" @click="cancelAction">取消</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null | string[]>

const ENDPOINT = '/api/transformer'
const columns = ["箱变编号", "箱变型号", "额定容量", "所属电站", "油温", "绕组温度", "上次检修日", "箱变状态"]
const statuses = ["运行", "轻瓦斯", "重瓦斯", "停机", "已归档"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref({ keyword: '', status: '' })
const detail = ref<Row | null>(null)
const pendingAction = ref<{ action: string; row: Row } | null>(null)
const acting = ref(false)

const stats = computed(() => [
  { label: '运行箱变', value: rows.value.filter((row) => row['箱变状态'] === '运行').length },
  { label: '告警箱变', value: rows.value.filter((row) => row['箱变状态'] === '轻瓦斯' || row['箱变状态'] === '重瓦斯').length },
  { label: '停机箱变', value: rows.value.filter((row) => row['箱变状态'] === '停机').length },
])

function rowActions(row: Row): string[] {
  return Array.isArray(row.available_actions) ? row.available_actions : []
}

function resetFilters() {
  filters.value = { keyword: '', status: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '箱式变压器登记入口尚未接入审批流'
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('箱式变压器详情读取失败')
    }
    detail.value = (await response.json()) as Row
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '箱变管理详情读取失败'
  }
}

function closeDetail() {
  detail.value = null
}

function openAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  pendingAction.value = { action, row }
}

function cancelAction() {
  pendingAction.value = null
}

async function confirmAction() {
  const pending = pendingAction.value
  if (!pending || acting.value) {
    return
  }
  acting.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${pending.row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: pending.action } }),
    })
    const payload = (await response.json()) as { ok: boolean; message?: string }
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || '箱变管理动作未生效，请稍后重试')
    }
    pendingAction.value = null
    noticeMessage.value = payload.message || '箱变管理操作已生效'
    await reload()
    if (detail.value && detail.value.id === pending.row.id) {
      await openDetail(pending.row)
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '箱变管理操作失败'
  } finally {
    acting.value = false
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.value.keyword) {
    query.set('keyword', filters.value.keyword)
  }
  if (filters.value.status) {
    query.set('status', filters.value.status)
  }
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
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
