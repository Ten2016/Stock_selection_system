<template>
  <div>
    <el-card style="margin-bottom: 20px;">
      <template #header>
        <div class="card-header">
          <span>选股策略</span>
        </div>
      </template>
      
      <el-form :inline="true" :model="form" style="margin-bottom: 20px;">
        <el-form-item label="选择策略">
          <el-select v-model="form.strategy" placeholder="请选择策略" style="width: 300px;" @change="onStrategyChange">
            <el-option
              v-for="strategy in strategies"
              :key="strategy.name"
              :label="strategy.display_name"
              :value="strategy.name"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="总市值大于">
          <el-input-number v-model="form.minMarketCap" :min="0" placeholder="不填则不限制" style="width: 150px;" />
          <span style="margin-left: 8px;">亿元</span>
        </el-form-item>
        
        <!-- consecutive_ma5 策略参数 -->
        <template v-if="form.strategy === 'consecutive_ma5'">
          <el-form-item label="最近">
            <el-input-number v-model="form.xDays" :min="5" :max="100" style="width: 120px;" />
            <span style="margin-left: 8px;">天内跌破布林下轨</span>
          </el-form-item>
          <el-form-item label="之后">
            <el-input-number v-model="form.yDays" :min="3" :max="60" style="width: 120px;" />
            <span style="margin-left: 8px;">天内</span>
          </el-form-item>
          <el-form-item label="连续">
            <el-input-number v-model="form.zDays" :min="1" :max="10" style="width: 120px;" />
            <span style="margin-left: 8px;">天站上 5 日均线</span>
          </el-form-item>
        </template>
        
        <!-- rise_then_fall 策略参数 -->
        <template v-if="form.strategy === 'rise_then_fall'">
          <el-form-item label="往前">
            <el-input-number v-model="form.xDays" :min="5" :max="100" style="width: 120px;" />
            <span style="margin-left: 8px;">天</span>
          </el-form-item>
          <el-form-item label="涨幅大于">
            <el-input-number v-model="form.yPct" :min="0" :max="20" :step="0.5" style="width: 120px;" />
            <span style="margin-left: 8px;">%</span>
          </el-form-item>
          <el-form-item label="连续">
            <el-input-number v-model="form.zDays" :min="1" :max="10" style="width: 120px;" />
            <span style="margin-left: 8px;">天下跌</span>
          </el-form-item>
        </template>
        
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="runStrategy">
            运行策略
          </el-button>
        </el-form-item>
      </el-form>

      <div v-if="selectedStrategy" style="margin-bottom: 20px; padding: 15px; background: #f5f7fa; border-radius: 4px;">
        <strong>{{ selectedStrategy.display_name }}</strong>
        <p style="margin-top: 8px; color: #606266;">{{ selectedStrategy.description }}</p>
      </div>
    </el-card>

    <el-card v-if="results.length > 0">
      <template #header>
        <div class="card-header">
          <span>筛选结果（共 {{ totalCount }} 只股票）</span>
        </div>
      </template>

      <el-table :data="results" stripe>
        <el-table-column prop="code" label="代码" width="120" />
        <el-table-column prop="name" label="名称" width="150" />
        <el-table-column prop="total_cap" label="总市值（亿）" width="150">
          <template #default="{ row }">
            {{ toFixed(row.total_cap) }}
          </template>
        </el-table-column>
        <el-table-column prop="result" label="策略详情" min-width="400">
          <!-- consecutive_ma5 策略结果 -->
          <template #default="{ row }" v-if="form.strategy === 'consecutive_ma5'">
            <div v-if="row.result">
              <div style="margin-bottom: 8px;">
                <el-tag size="small" type="warning">
                  跌破：{{ row.result.breakdown_date }}
                </el-tag>
              </div>
              <div style="margin-bottom: 8px;">
                <el-tag size="small" type="success" style="margin-right: 4px;" v-for="(date, idx) in row.result.matching_dates" :key="idx">
                  {{ date }}
                </el-tag>
              </div>
              <div style="font-size: 12px; color: #909399;">
                {{ row.result.strategy }}
              </div>
            </div>
          </template>
          
          <!-- rise_then_fall 策略结果 -->
          <template #default="{ row }" v-if="form.strategy === 'rise_then_fall'">
            <div v-if="row.result">
              <div style="margin-bottom: 8px;">
                <el-tag size="small" type="danger">
                  大涨：{{ row.result.rise_date }} ({{ row.result.rise_pct }}%)
                </el-tag>
              </div>
              <div style="margin-bottom: 8px;">
                <el-tag size="small" type="info" style="margin-right: 4px;" v-for="(date, idx) in row.result.falling_dates" :key="idx">
                  {{ date }}
                </el-tag>
              </div>
              <div style="font-size: 12px; color: #909399;">
                {{ row.result.strategy }}
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewStock(row)">查看K线</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-empty v-else-if="hasRun" description="没有符合条件的股票" />

    <!-- K线图弹窗 -->
    <KlineChartDialog
      v-model:visible="chartDialogVisible"
      :stock-code="selectedStockCode"
      :strategy-result="selectedStockResult"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { getStrategies, selectStocks, getLatestStrategyResult } from '../api'
import KlineChartDialog from '../components/KlineChartDialog.vue'

const strategies = ref([])
const loading = ref(false)
const hasRun = ref(false)
const results = ref([])
const totalCount = ref(0)
const chartDialogVisible = ref(false)
const selectedStockCode = ref('')
const selectedStockResult = ref(null)
const form = ref({
  strategy: '',
  minMarketCap: null,
  xDays: 30,
  yDays: 10,
  zDays: 2,
  yPct: 5.0
})

const selectedStrategy = computed(() => {
  return strategies.value.find(s => s.name === form.value.strategy)
})

const toFixed = (num, digits = 2) => {
  if (num == null) return '-'
  const n = Number(num)
  if (isNaN(n)) return '-'
  return n.toFixed(digits)
}

// 加载策略的最新结果
const loadLatestResult = async (strategyName) => {
  if (!strategyName) return
  try {
    const res = await getLatestStrategyResult(strategyName)
    if (res.data && res.data.selected_stocks && res.data.selected_stocks.length > 0) {
      results.value = res.data.selected_stocks
      totalCount.value = res.data.total_count
      hasRun.value = true
      // 恢复参数
      if (res.data.params) {
        form.value.minMarketCap = res.data.params.min_market_cap
        form.value.xDays = res.data.params.x_days || form.value.xDays
        form.value.yDays = res.data.params.y_days || form.value.yDays
        form.value.zDays = res.data.params.z_days || form.value.zDays
        form.value.yPct = res.data.params.y_pct || form.value.yPct
      }
    }
  } catch (error) {
    console.error('加载最新结果失败:', error)
  }
}

onMounted(async () => {
  try {
    const res = await getStrategies()
    strategies.value = res.data
    if (strategies.value.length > 0) {
      form.value.strategy = strategies.value[0].name
      // 加载默认策略的最新结果
      await loadLatestResult(form.value.strategy)
    }
  } catch (error) {
    console.error(error)
  }
})

const onStrategyChange = () => {
  // 切换策略时重置参数
  if (form.value.strategy === 'consecutive_ma5') {
    form.value.xDays = 30
    form.value.yDays = 10
    form.value.zDays = 2
  } else if (form.value.strategy === 'rise_then_fall') {
    form.value.xDays = 30
    form.value.yPct = 5.0
    form.value.zDays = 3
  }
  // 加载新策略的最新结果
  results.value = []
  totalCount.value = 0
  hasRun.value = false
  loadLatestResult(form.value.strategy)
}

const runStrategy = async () => {
  if (!form.value.strategy) {
    alert('请选择策略')
    return
  }

  loading.value = true
  hasRun.value = true
  try {
    const res = await selectStocks(
      form.value.strategy,
      form.value.minMarketCap,
      form.value.xDays,
      form.value.yDays,
      form.value.zDays,
      form.value.yPct
    )
    console.log('策略结果:', res.data)
    results.value = res.data.selected_stocks
    totalCount.value = res.data.total_count
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

const viewStock = (row) => {
  selectedStockCode.value = row.code
  selectedStockResult.value = row.result
  chartDialogVisible.value = true
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
