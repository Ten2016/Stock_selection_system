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
          <el-input-number v-model="form.minMarketCap" :min="1" :max="1000000" placeholder="不填则不限制" style="width: 150px;" />
          <span style="margin-left: 8px;">亿元</span>
        </el-form-item>
        
        <!-- consecutive_ma5 策略参数 -->
        <template v-if="form.strategy === 'consecutive_ma5'">
          <el-form-item label="最近">
            <el-input-number v-model="form.xDays" :min="1" :max="1000000" style="width: 120px;" />
            <span style="margin-left: 8px;">天内跌破布林下轨</span>
          </el-form-item>
          <el-form-item label="之后">
            <el-input-number v-model="form.yDays" :min="1" :max="1000000" style="width: 120px;" />
            <span style="margin-left: 8px;">天内</span>
          </el-form-item>
          <el-form-item label="连续">
            <el-input-number v-model="form.zDays" :min="1" :max="1000000" style="width: 120px;" />
            <span style="margin-left: 8px;">天站上 5 日均线</span>
          </el-form-item>
        </template>
        
        <!-- rise_then_fall 策略参数 -->
        <template v-if="form.strategy === 'rise_then_fall'">
          <el-form-item label="往前">
            <el-input-number v-model="form.xDays" :min="1" :max="1000000" style="width: 120px;" />
            <span style="margin-left: 8px;">天</span>
          </el-form-item>
          <el-form-item label="涨幅大于">
            <el-input-number v-model="form.yPct" :min="1" :max="1000000" :step="0.5" style="width: 120px;" />
            <span style="margin-left: 8px;">%</span>
          </el-form-item>
          <el-form-item label="连续">
            <el-input-number v-model="form.zDays" :min="1" :max="1000000" style="width: 120px;" />
            <span style="margin-left: 8px;">天下跌</span>
          </el-form-item>
        </template>
        
        <!-- above_ma60 策略参数 -->
        <template v-if="form.strategy === 'above_ma60'">
          <el-form-item label="最近">
            <el-input-number v-model="form.yDays" :min="1" :max="1000000" style="width: 120px;" />
            <span style="margin-left: 8px;">天内</span>
          </el-form-item>
          <el-form-item label="站上60日均线">
            <el-input-number v-model="form.zDays" :min="1" :max="1000000" style="width: 120px;" />
            <span style="margin-left: 8px;">天</span>
          </el-form-item>
        </template>
        
        <!-- macd_green_pullback 策略参数 -->
        <template v-if="form.strategy === 'macd_green_pullback'">
          <el-form-item label="最近">
            <el-input-number v-model="form.yDays" :min="1" :max="1000000" style="width: 120px;" />
            <span style="margin-left: 8px;">天内出现绿柱拐点</span>
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

      <!-- 单股回测 -->
      <el-divider content-position="left">单股回测</el-divider>
      <div style="display: flex; align-items: flex-end; gap: 15px; flex-wrap: wrap;">
        <el-form-item label="选择股票" style="margin-bottom: 0;">
          <el-autocomplete
            v-model="searchKeyword"
            :fetch-suggestions="handleSearch"
            placeholder="输入代码或名称搜索"
            style="width: 320px;"
            @select="onSelectStock"
            clearable
          >
            <template #default="{ item }">
              <div style="display: flex; justify-content: space-between; width: 100%;">
                <span><strong>{{ item.code }}</strong> {{ item.name }}</span>
                <span style="color: #909399; font-size: 12px;">{{ toFixed(item.total_cap) }}亿</span>
              </div>
            </template>
          </el-autocomplete>
        </el-form-item>
        <el-button type="success" :loading="backtestLoading" @click="runBacktest">
          回测策略
        </el-button>
        <el-button v-if="backtestResult && backtestResult.signal_count > 0" @click="viewBacktestChart">
          查看K线
        </el-button>
      </div>

      <div v-if="backtestResult" style="margin-top: 20px; padding: 15px; background: #f6ffed; border: 1px solid #b7eb8f; border-radius: 4px;">
        <div style="margin-bottom: 10px;">
          <strong>{{ backtestResult.stock_code }} {{ backtestResult.stock_name }}</strong>
          <span style="margin-left: 15px; color: #52c41a;">共 {{ backtestResult.signal_count }} 个买点</span>
        </div>
        <div v-if="backtestResult.signals && backtestResult.signals.length > 0" style="display: flex; flex-wrap: wrap; gap: 8px;">
          <el-tag
            v-for="(signal, idx) in backtestResult.signals"
            :key="idx"
            type="success"
            effect="plain"
          >
            #{{ idx + 1 }} {{ signal.date }} (收{{ toFixed(signal.close) }})
          </el-tag>
        </div>
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
          
          <!-- above_ma60 策略结果 -->
          <template #default="{ row }" v-if="form.strategy === 'above_ma60'">
            <div v-if="row.result">
              <div style="margin-bottom: 8px;">
                <el-tag size="small" type="success">
                  站上60日线：{{ row.result.above_count }} 天
                </el-tag>
              </div>
              <div style="margin-bottom: 8px;">
                <el-tag size="small" type="info" style="margin-right: 4px;" v-for="(date, idx) in row.result.above_ma60_dates" :key="idx">
                  {{ date }}
                </el-tag>
              </div>
              <div style="font-size: 12px; color: #909399;">
                {{ row.result.strategy }}
              </div>
            </div>
          </template>
          
          <!-- macd_green_pullback 策略结果 -->
          <template #default="{ row }" v-if="form.strategy === 'macd_green_pullback'">
            <div v-if="row.result">
              <div style="margin-bottom: 8px;">
                <el-tag size="small" type="success">
                  拐点日期：{{ row.result.valley_date }}
                </el-tag>
                <el-tag size="small" type="warning" style="margin-left: 8px;">
                  已缩短 {{ row.result.shortening_days }} 天
                </el-tag>
              </div>
              <div style="margin-bottom: 8px; font-size: 12px;">
                <span style="color: #ef5350;">前低：{{ row.result.prev_min_low }}（{{ row.result.prev_min_low_date }}）</span>
                <span style="margin: 0 8px; color: #909399;">→</span>
                <span style="color: #26a69a;">现低：{{ row.result.current_min_low }}（{{ row.result.current_min_low_date }}）</span>
                <span style="margin-left: 8px; color: #26a69a;">（抬高 {{ row.result.low_diff_pct }}%）</span>
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
      :backtest-signals="backtestSignals"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getStrategies, selectStocks, getLatestStrategyResult, searchStocks, backtestStrategy } from '../api'
import KlineChartDialog from '../components/KlineChartDialog.vue'

const strategies = ref([])
const loading = ref(false)
const hasRun = ref(false)
const results = ref([])
const totalCount = ref(0)
const chartDialogVisible = ref(false)
const selectedStockCode = ref('')
const selectedStockResult = ref(null)
const backtestSignals = ref([])

// 股票搜索相关
const searchKeyword = ref('')
const searchSuggestions = ref([])
const selectedBacktestStock = ref(null)
const backtestLoading = ref(false)
const backtestResult = ref(null)

// 默认参数
const defaultParams = {
  consecutive_ma5: { minMarketCap: 300, xDays: 30, yDays: 10, zDays: 2 },
  rise_then_fall: { minMarketCap: 300, xDays: 30, yPct: 5.0, zDays: 3 },
  above_ma60: { minMarketCap: 300, yDays: 5, zDays: 3 },
  macd_green_pullback: { minMarketCap: 300, yDays: 5 }
}

const form = ref({ strategy: '', minMarketCap: 300, xDays: 30, yDays: 5, zDays: 3, yPct: 5.0 })

const selectedStrategy = computed(() => strategies.value.find(s => s.name === form.value.strategy))
const toFixed = (num, digits = 2) => (num == null || Number.isNaN(Number(num)) ? '-' : Number(num).toFixed(digits))

// 设置策略的默认参数
const setDefaultParams = (strategyName) => {
  const defaults = defaultParams[strategyName]
  if (defaults) {
    form.value.minMarketCap = defaults.minMarketCap
    if (defaults.xDays !== undefined) form.value.xDays = defaults.xDays
    if (defaults.yDays !== undefined) form.value.yDays = defaults.yDays
    if (defaults.zDays !== undefined) form.value.zDays = defaults.zDays
    if (defaults.yPct !== undefined) form.value.yPct = defaults.yPct
  }
}

const loadLatestResult = async (strategyName) => {
  if (!strategyName) return
  try {
    const res = await getLatestStrategyResult(strategyName)
    if (res.data?.selected_stocks?.length > 0) {
      results.value = res.data.selected_stocks
      totalCount.value = res.data.total_count || 0
      hasRun.value = true
      // 加载历史参数
      if (res.data.params) {
        form.value.minMarketCap = res.data.params.min_market_cap ?? 300
        if (res.data.params.x_days !== undefined) form.value.xDays = res.data.params.x_days
        if (res.data.params.y_days !== undefined) form.value.yDays = res.data.params.y_days
        if (res.data.params.z_days !== undefined) form.value.zDays = res.data.params.z_days
        if (res.data.params.y_pct !== undefined) form.value.yPct = res.data.params.y_pct
      }
    } else {
      // 没有历史结果，使用默认参数
      setDefaultParams(strategyName)
    }
  } catch (error) {
    console.error('加载最新结果失败:', error)
    setDefaultParams(strategyName)
  }
}

onMounted(async () => {
  try {
    const res = await getStrategies()
    strategies.value = Array.isArray(res.data) ? res.data : []
    if (strategies.value.length > 0) {
      form.value.strategy = strategies.value[0].name
      await loadLatestResult(form.value.strategy)
    }
  } catch (error) {
    console.error(error)
  }
})

const onStrategyChange = async () => {
  results.value = []; totalCount.value = 0; hasRun.value = false
  await loadLatestResult(form.value.strategy)
}

const runStrategy = async () => {
  if (!form.value.strategy) return ElMessage.warning('请选择策略')
  loading.value = true; hasRun.value = true
  try {
    const res = await selectStocks(form.value.strategy, form.value.minMarketCap, form.value.xDays, form.value.yDays, form.value.zDays, form.value.yPct)
    results.value = res.data.selected_stocks || []
    totalCount.value = res.data.total_count || 0
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

const viewStock = (row) => { selectedStockCode.value = row.code; selectedStockResult.value = row.result; backtestSignals.value = []; chartDialogVisible.value = true }

// 股票搜索
const handleSearch = async (keyword) => {
  if (!keyword || keyword.length < 1) {
    searchSuggestions.value = []
    return
  }
  try {
    const res = await searchStocks(keyword, 20)
    const list = res.data?.list || []
    searchSuggestions.value = list.map(s => ({
      value: `${s.code} ${s.name}`,
      code: s.code,
      name: s.name,
      total_cap: s.total_cap
    }))
  } catch (error) {
    console.error('搜索失败:', error)
    searchSuggestions.value = []
  }
}

const onSelectStock = (item) => {
  selectedBacktestStock.value = item
}

// 回测
const runBacktest = async () => {
  if (!selectedBacktestStock.value) return ElMessage.warning('请先选择股票')
  if (!form.value.strategy) return ElMessage.warning('请先选择策略')
  
  backtestLoading.value = true
  backtestResult.value = null
  try {
    const res = await backtestStrategy(
      form.value.strategy,
      selectedBacktestStock.value.code,
      2020,
      form.value.xDays,
      form.value.yDays,
      form.value.zDays,
      form.value.yPct
    )
    backtestResult.value = res.data
    backtestSignals.value = res.data?.signals || []
  } catch (error) {
    console.error('回测失败:', error)
  } finally {
    backtestLoading.value = false
  }
}

// 查看回测K线
const viewBacktestChart = () => {
  if (!selectedBacktestStock.value) return
  selectedStockCode.value = selectedBacktestStock.value.code
  selectedStockResult.value = null
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
