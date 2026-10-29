<template>
  <div>
    <el-card style="margin-bottom: 20px;">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>数据同步</span>
          <div>
            <el-button type="primary" @click="startSync" :disabled="syncing || starting">开始同步</el-button>
            <div style="display: inline-flex; align-items: center; margin-left: 10px;">
              <span style="margin-right: 5px; font-size: 14px;">同步近</span>
              <el-input-number v-model="recentDays" :min="1" :max="365" size="small" style="width: 100px;" />
              <span style="margin-left: 5px; margin-right: 10px; font-size: 14px;">天</span>
              <el-button type="success" @click="startSyncRecentDays" :disabled="syncing || starting">开始同步</el-button>
            </div>
            <el-button type="warning" @click="startSyncBasicInfo" :disabled="syncing || starting">同步基本信息</el-button>
            <el-button type="info" @click="startRepairIndicators" :disabled="syncing || starting">数据修复</el-button>
            <el-button type="danger" @click="cancelSync" :disabled="!syncing">取消同步</el-button>
          </div>
        </div>
      </template>

      <el-form :model="syncForm" style="margin-bottom: 20px;">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="起始日期">
              <el-date-picker v-model="syncForm.startDate" type="date" value-format="YYYY-MM-DD" placeholder="选择起始日期" style="width: 100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期">
              <el-date-picker v-model="syncForm.endDate" type="date" value-format="YYYY-MM-DD" placeholder="选择结束日期" style="width: 100%;" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <el-alert type="info" :closable="false" style="margin-bottom: 20px;">
        近 N 天按自然日计算；精确同步最近 3 个月请使用日期区间。仅同步已收盘日线。
        系统会补齐与已有数据的断档；首次同步会额外拉取一年用于指标计算。
        复权变化时会重拉该股票全部已存历史；重刷旧区间会更新至该股票已有的最新日期。
      </el-alert>

      <el-descriptions v-if="!syncing && syncStatus" title="上次同步信息" :column="2" border style="margin-bottom: 20px;">
        <el-descriptions-item label="同步日期">
          {{ syncStatus.sync_date || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="同步股票数">
          <el-tag type="success">{{ syncStatus.stock_count || 0 }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="syncStatus.status === 'success' ? 'success' : 'danger'">{{ syncStatus.status || '-' }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="已有K线股票数">
          <el-tag type="info">{{ syncStatus.total_stocks_with_kline || 0 }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <el-alert v-if="realtimeProgress?.error_msg" :title="realtimeProgress.error_msg" type="error" :closable="false" style="margin-top: 20px;" />
      <el-alert v-else-if="!syncing && syncStatus?.error_msg" :title="syncStatus.error_msg" type="error" :closable="false" style="margin-top: 20px;" />

      <div v-if="syncing && realtimeProgress" style="margin-top: 20px;">
        <el-progress :percentage="realtimeProgress.progress" :status="realtimeProgress.progress === 100 ? 'success' : undefined" />
      </div>

      <div v-if="syncing && realtimeProgress" style="margin-top: 20px;">
        <el-descriptions title="实时同步进度" :column="2" border>
          <el-descriptions-item label="成功">
            <el-tag type="success">{{ realtimeProgress.success_count || 0 }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="跳过（在跳过列表中）">
            <el-tag type="info">{{ realtimeProgress.skipped_count || 0 }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="失败">
            <el-tag type="danger">{{ realtimeProgress.failed_count || 0 }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="未获取到数据">
            <el-tag type="warning">{{ realtimeProgress.no_data_count || 0 }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <div v-if="!syncing && syncStatus && (syncStatus.success_count || syncStatus.failed_count || syncStatus.no_data_count)" style="margin-top: 20px;">
        <el-descriptions title="上次同步结果" :column="2" border>
          <el-descriptions-item label="成功">
            <el-tag type="success">{{ syncStatus.success_count || 0 }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="未获取到数据">
            <el-tag type="warning">{{ syncStatus.no_data_count || 0 }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="失败">
            <el-tag type="danger">{{ syncStatus.failed_count || 0 }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="跳过（在跳过列表中）">
            <el-tag type="info">{{ syncStatus.skipped_count || 0 }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <div v-if="!syncing && syncStatus && syncStatus.failed_stocks && syncStatus.failed_stocks.length > 0" style="margin-top: 20px;">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span style="color: #f56c6c;">失败股票列表 ({{ syncStatus.failed_stocks.length }})</span>
              <el-button type="primary" size="small" @click="addAllFailedToSkip">全部加入跳过列表</el-button>
            </div>
          </template>
          <el-table :data="syncStatus.failed_stocks" size="small" max-height="300">
            <el-table-column prop="code" label="代码" width="120" />
            <el-table-column prop="name" label="名称" width="150" />
            <el-table-column prop="reason" label="失败原因" min-width="260" />
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button type="primary" size="small" @click="addOneToSkip(row)">加入跳过列表</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>

      <div v-if="!syncing && syncStatus && syncStatus.no_data_stocks && syncStatus.no_data_stocks.length > 0" style="margin-top: 20px;">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span style="color: #e6a23c;">未获取到数据股票列表 ({{ syncStatus.no_data_stocks.length }})</span>
              <el-button type="primary" size="small" @click="addAllNoDataToSkip">全部加入跳过列表</el-button>
            </div>
          </template>
          <el-table :data="syncStatus.no_data_stocks" size="small" max-height="300">
            <el-table-column prop="code" label="代码" width="120" />
            <el-table-column prop="name" label="名称" width="150" />
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button type="primary" size="small" @click="addOneToSkip(row)">加入跳过列表</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>

      <div style="margin-top: 20px;">
        <el-card>
          <template #header>
            <span style="color: #909399;">跳过股票列表 ({{ skippedStocks.length }}) - 这些股票会在同步时自动跳过</span>
          </template>
          <el-table :data="skippedStocks" size="small" max-height="300">
            <el-table-column prop="code" label="代码" width="120" />
            <el-table-column prop="name" label="名称" width="150" />
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button type="danger" size="small" @click="removeFromSkip(row.code)">移除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>

    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import api, { syncBasicInfo } from '../api'

const syncing = ref(false)
const starting = ref(false)
const syncStatus = ref(null)
const skippedStocks = ref([])
const realtimeProgress = ref(null)
const recentDays = ref(10)
const now = new Date()
const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
const syncForm = ref({ startDate: '2024-01-01', endDate: today })
let timer = null
let pollVersion = 0
let disposed = false

const loadSyncHistory = async () => { try { const res = await api.get('/sync/history'); syncStatus.value = res.data } catch (error) { console.error(error) } }
const loadSkippedStocks = async () => { try { const res = await api.get('/sync/skipped-stocks'); skippedStocks.value = res.data.stocks || [] } catch (error) { console.error(error) } }
const pollSyncProgress = async (version) => {
  let again = true
  try {
    const res = await api.get('/sync/progress')
    if (disposed || version !== pollVersion) return
    const wasSyncing = syncing.value
    realtimeProgress.value = res.data
    syncing.value = res.data.is_syncing
    again = syncing.value
    if (!syncing.value && wasSyncing) {
      await Promise.all([loadSyncHistory(), loadSkippedStocks()])
      if (res.data.status === 'cancelled') ElMessage.info('同步已取消')
      if (res.data.status === 'partial') ElMessage.warning('同步结束，部分股票失败，请查看结果')
    }
  } catch (error) {
    console.error(error)
  } finally {
    if (!disposed && version === pollVersion && again) {
      timer = setTimeout(() => pollSyncProgress(version), 2000)
    }
  }
}
const stopPolling = () => {
  pollVersion += 1
  if (timer) clearTimeout(timer)
  timer = null
}
const startPolling = () => {
  stopPolling()
  pollSyncProgress(pollVersion)
}

const startTask = async (request) => {
  if (starting.value || syncing.value) return
  starting.value = true
  try {
    const res = await request()
    ElMessage.success(res.msg)
    syncing.value = true
    realtimeProgress.value = null
    if (!disposed) startPolling()
  } catch (error) {
    console.error(error)
  } finally {
    starting.value = false
  }
}

const startSync = () => {
  if (!syncForm.value.startDate || !syncForm.value.endDate) return ElMessage.error('请选择起始日期和结束日期')
  if (syncForm.value.startDate > syncForm.value.endDate) return ElMessage.error('起始日期不能晚于结束日期')
  return startTask(() => api.post('/sync/start', { start_date: syncForm.value.startDate, end_date: syncForm.value.endDate }))
}
const startSyncRecentDays = () => startTask(() => api.post('/sync/start-recent-days', { days: recentDays.value }))
const startRepairIndicators = () => startTask(() => api.post('/sync/repair-indicators'))
const startSyncBasicInfo = () => startTask(syncBasicInfo)
const cancelSync = async () => { try { const res = await api.post('/sync/cancel'); ElMessage.success(res.msg) } catch (error) { console.error(error) } }
const addOneToSkip = async (stock) => { try { await api.post('/sync/skipped-stocks/add', { stocks: [stock] }); ElMessage.success('已加入跳过列表'); await loadSkippedStocks() } catch (error) { console.error(error) } }
const addAllFailedToSkip = async () => { try { if (!syncStatus.value?.failed_stocks?.length) return; await api.post('/sync/skipped-stocks/add', { stocks: syncStatus.value.failed_stocks }); ElMessage.success('全部加入跳过列表'); await loadSkippedStocks() } catch (error) { console.error(error) } }
const addAllNoDataToSkip = async () => { try { if (!syncStatus.value?.no_data_stocks?.length) return; await api.post('/sync/skipped-stocks/add', { stocks: syncStatus.value.no_data_stocks }); ElMessage.success('全部加入跳过列表'); await loadSkippedStocks() } catch (error) { console.error(error) } }
const removeFromSkip = async (code) => { try { await api.post('/sync/skipped-stocks/remove', { code }); ElMessage.success('已从跳过列表移除'); await loadSkippedStocks() } catch (error) { console.error(error) } }

onMounted(() => {
  loadSyncHistory()
  loadSkippedStocks()
  startPolling()
})
onUnmounted(() => {
  disposed = true
  stopPolling()
})
</script>
