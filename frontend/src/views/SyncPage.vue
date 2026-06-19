<template>
  <div>
    <el-card style="margin-bottom: 20px;">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>数据同步</span>
          <div>
            <el-button type="primary" @click="startSync" :disabled="syncing">开始同步</el-button>
            <div style="display: inline-flex; align-items: center; margin-left: 10px;">
              <span style="margin-right: 5px; font-size: 14px;">同步近</span>
              <el-input-number v-model="recentDays" :min="1" :max="365" size="small" style="width: 100px;" />
              <span style="margin-left: 5px; margin-right: 10px; font-size: 14px;">天</span>
              <el-button type="success" @click="startSyncRecentDays" :disabled="syncing">开始同步</el-button>
            </div>
            <el-button type="warning" @click="startSyncBasicInfo" :disabled="syncing">同步基本信息</el-button>
            <el-button type="info" @click="startRepairIndicators" :disabled="syncing">数据修复</el-button>
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
          <el-descriptions-item label="跳过（已有数据）">
            <el-tag type="info">{{ syncStatus.skipped_count || 0 }}</el-tag>
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
const syncStatus = ref(null)
const skippedStocks = ref([])
const realtimeProgress = ref(null)
const recentDays = ref(10)
const today = new Date().toISOString().split('T')[0]
const syncForm = ref({ startDate: '2024-01-01', endDate: today })
let timer = null

const loadSyncHistory = async () => { try { const res = await api.get('/sync/history'); syncStatus.value = res.data } catch (error) { console.error(error) } }
const loadSkippedStocks = async () => { try { const res = await api.get('/sync/skipped-stocks'); skippedStocks.value = res.data.stocks || [] } catch (error) { console.error(error) } }
const pollSyncProgress = async () => { try { const res = await api.get('/sync/progress'); realtimeProgress.value = res.data; if (!res.data.is_syncing && syncing.value) { syncing.value = false; stopPolling(); await loadSyncHistory(); await loadSkippedStocks(); realtimeProgress.value = null } } catch (error) { console.error(error) } }
const startPolling = () => { stopPolling(); timer = setInterval(pollSyncProgress, 2000) }
const stopPolling = () => { if (timer) { clearInterval(timer); timer = null } }

const startSync = async () => {
  if (!syncForm.value.startDate || !syncForm.value.endDate) return ElMessage.error('请选择起始日期和结束日期')
  try { const res = await api.post('/sync/start', { start_date: syncForm.value.startDate, end_date: syncForm.value.endDate }); ElMessage.success(res.msg); syncing.value = true; realtimeProgress.value = null; startPolling() } catch (error) { console.error(error) }
}
const startSyncRecentDays = async () => { try { const res = await api.post('/sync/start-recent-days', { days: recentDays.value }); ElMessage.success(res.msg); syncing.value = true; realtimeProgress.value = null; startPolling() } catch (error) { console.error(error) } }
const startRepairIndicators = async () => { try { const res = await api.post('/sync/repair-indicators'); ElMessage.success(res.msg); syncing.value = true; realtimeProgress.value = null; startPolling() } catch (error) { console.error(error) } }
const startSyncBasicInfo = async () => { try { const res = await syncBasicInfo(); ElMessage.success(res.msg); syncing.value = true; realtimeProgress.value = null; startPolling() } catch (error) { console.error(error) } }
const cancelSync = async () => { try { const res = await api.post('/sync/cancel'); ElMessage.success(res.msg) } catch (error) { console.error(error) } }
const addOneToSkip = async (stock) => { try { await api.post('/sync/skipped-stocks/add', { stocks: [stock] }); ElMessage.success('已加入跳过列表'); await loadSkippedStocks() } catch (error) { console.error(error) } }
const addAllFailedToSkip = async () => { try { if (!syncStatus.value?.failed_stocks?.length) return; await api.post('/sync/skipped-stocks/add', { stocks: syncStatus.value.failed_stocks }); ElMessage.success('全部加入跳过列表'); await loadSkippedStocks() } catch (error) { console.error(error) } }
const addAllNoDataToSkip = async () => { try { if (!syncStatus.value?.no_data_stocks?.length) return; await api.post('/sync/skipped-stocks/add', { stocks: syncStatus.value.no_data_stocks }); ElMessage.success('全部加入跳过列表'); await loadSkippedStocks() } catch (error) { console.error(error) } }
const removeFromSkip = async (code) => { try { await api.post('/sync/skipped-stocks/remove', { code }); ElMessage.success('已从跳过列表移除'); await loadSkippedStocks() } catch (error) { console.error(error) } }

onMounted(async () => { await loadSyncHistory(); await loadSkippedStocks() })
onUnmounted(stopPolling)
</script>
