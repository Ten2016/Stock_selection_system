<template>
  <div>
    <el-card style="margin-bottom: 20px;">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>股票列表 (共 {{ total }} 只)</span>
          <div>
            <el-input
              v-model="searchKeyword"
              placeholder="搜索代码/名称"
              style="width: 200px; margin-right: 10px;"
              clearable
              @keyup.enter="handleSearch"
            />
            <el-button type="primary" @click="handleSearch">查询</el-button>
            <el-popconfirm
              title="确定要清空所有股票数据吗？此操作不可恢复！"
              confirm-button-text="确定清空"
              cancel-button-text="取消"
              confirm-button-type="danger"
              @confirm="clearAllStockData"
            >
              <template #reference>
                <el-button type="danger" :loading="clearingAll">清空所有数据</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </template>
      <el-table :data="stocks" style="width: 100%" @sort-change="handleSortChange" :default-sort="{prop: 'total_cap', order: 'descending'}" v-loading="loading">
        <el-table-column label="序号" width="60">
          <template #default="{ $index }">
            {{ (currentPage - 1) * pageSize + $index + 1 }}
          </template>
        </el-table-column>
        <el-table-column prop="code" label="代码" width="100" />
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column prop="total_cap" label="总市值(亿)" width="110" sortable="custom">
          <template #default="{ row }">
            {{ formatNumber(row.total_cap) }}
          </template>
        </el-table-column>
        <el-table-column prop="pe_ratio" label="动态市盈率" width="110" sortable="custom">
          <template #default="{ row }">
            {{ formatNumber(row.pe_ratio) }}
          </template>
        </el-table-column>
        <el-table-column prop="pe_ratio_static" label="静态市盈率" width="110">
          <template #default="{ row }">
            {{ formatNumber(row.pe_ratio_static) }}
          </template>
        </el-table-column>
        <el-table-column prop="pb_ratio" label="市净率" width="100" sortable="custom">
          <template #default="{ row }">
            {{ formatNumber(row.pb_ratio) }}
          </template>
        </el-table-column>
        <el-table-column prop="ytd_change_pct" label="今年涨跌幅" width="110" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.ytd_change_pct != null" :style="{color: row.ytd_change_pct >= 0 ? '#ef5350' : '#26a69a'}">
              {{ formatNumber(row.ytd_change_pct) }}%
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="K线数据" width="180">
          <template #default="{ row }">
            <span v-if="row.kline_date_range">
              {{ row.kline_date_range.min_date }} ~ {{ row.kline_date_range.max_date }}
              <br/>
              <el-tag size="small" type="success">{{ row.kline_date_range.count }}条</el-tag>
            </span>
            <span v-else style="color: #999;">无数据</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewStock(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 20px; display: flex; justify-content: center;">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next, jumper"
          @current-change="handlePageChange"
          :prev-text="'上一页'"
          :next-text="'下一页'"
        />
      </div>
    </el-card>

    <!-- K线图弹窗 -->
    <KlineChartDialog
      v-model:visible="chartDialogVisible"
      :stock-code="selectedStockCode"
      :strategy-result="null"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import KlineChartDialog from '../components/KlineChartDialog.vue'

const stocks = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(50)
const searchKeyword = ref('')
const clearingAll = ref(false)
const loading = ref(false)
const chartDialogVisible = ref(false)
const selectedStockCode = ref('')
const sortBy = ref('total_cap')
const sortOrder = ref('desc')

const formatNumber = (value, digits = 2) => {
  if (value == null || value === '') return '-'
  const n = Number(value)
  return Number.isFinite(n) ? n.toFixed(digits) : '-'
}

const loadStocks = async () => {
  loading.value = true
  try {
    const params = {
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
    }
    if (searchKeyword.value) params.search = searchKeyword.value
    const res = await api.get('/stocks', { params })
    stocks.value = res.data.list || []
    total.value = res.data.total || 0
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => { currentPage.value = 1; loadStocks() }
const handleSortChange = ({ prop, order }) => { sortBy.value = prop || 'total_cap'; sortOrder.value = order === 'ascending' ? 'asc' : 'desc'; currentPage.value = 1; loadStocks() }
const handlePageChange = (page) => { currentPage.value = page; loadStocks() }
const viewStock = (row) => { selectedStockCode.value = row.code; chartDialogVisible.value = true }

const clearAllStockData = async () => {
  try {
    clearingAll.value = true
    const res = await api.delete('/stocks/all')
    ElMessage.success(res.msg)
    await loadStocks()
  } catch (error) {
    console.error(error)
  } finally {
    clearingAll.value = false
  }
}

onMounted(loadStocks)
</script>
