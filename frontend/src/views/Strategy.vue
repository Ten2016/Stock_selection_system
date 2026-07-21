<template>
  <div>
    <el-card style="margin-bottom: 20px;">
      <template #header>
        <div class="card-header">
          <span>选股策略</span>
        </div>
      </template>

      <el-form :inline="true" style="margin-bottom: 12px;">
        <el-form-item label="选择策略">
          <el-select v-model="strategyName" placeholder="请选择策略" style="width: 300px;" @change="onStrategyChange">
            <el-option
              v-for="s in strategies"
              :key="s.name"
              :label="s.display_name"
              :value="s.name"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="总市值大于">
          <el-input-number v-model="minMarketCap" :min="0" :max="1000000" style="width: 150px;" />
          <span style="margin-left: 8px;">亿元</span>
        </el-form-item>

        <!-- 参数表单由后端 /strategies 返回的 ParamSpec 驱动，新增策略无需改前端 -->
        <el-form-item v-for="p in currentParams" :key="p.name" :label="p.label">
          <el-input-number
            v-model="paramValues[p.name]"
            :min="p.min ?? undefined"
            :max="p.max ?? undefined"
            :step="p.step || 1"
            :precision="p.type === 'float' ? 2 : 0"
            style="width: 120px;"
          />
          <span v-if="p.suffix" style="margin-left: 8px;">{{ p.suffix }}</span>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="loading" @click="runStrategy">运行策略</el-button>
        </el-form-item>
      </el-form>

      <el-alert
        v-if="selectedStrategy"
        :title="selectedStrategy.display_name"
        :description="selectedStrategy.description"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 20px;"
      />

      <!-- 单股回测 -->
      <el-divider content-position="left">单股回测</el-divider>
      <div style="display: flex; align-items: center; gap: 15px; flex-wrap: wrap;">
        <el-autocomplete
          v-model="searchKeyword"
          :fetch-suggestions="handleSearch"
          placeholder="输入代码或名称搜索"
          style="width: 320px;"
          clearable
          @select="onSelectStock"
        >
          <template #default="{ item }">
            <div style="display: flex; justify-content: space-between; width: 100%;">
              <span><strong>{{ item.code }}</strong> {{ item.name }}</span>
              <span style="color: #909399; font-size: 12px;">{{ toFixed(item.total_cap) }}亿</span>
            </div>
          </template>
        </el-autocomplete>
        <el-input-number v-model="startYear" :min="2000" :max="2100" style="width: 130px;" />
        <span style="margin-left: -8px; color: #909399;">年起</span>
        <el-button type="success" :loading="backtestLoading" @click="runBacktest">回测策略</el-button>
        <el-button v-if="backtestResult && backtestResult.signal_count > 0" @click="viewBacktestChart">
          查看K线
        </el-button>
      </div>

      <div v-if="backtestResult" style="margin-top: 20px;">
        <el-alert
          :title="`${backtestResult.stock_code} ${backtestResult.stock_name} — 共 ${backtestResult.signal_count} 个买点`"
          :type="backtestResult.signal_count > 0 ? 'success' : 'warning'"
          :closable="false"
          show-icon
        />
        <div v-if="backtestResult.signals?.length" style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px;">
          <el-tag v-for="(signal, idx) in backtestResult.signals" :key="idx" type="success" effect="plain">
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
        <el-table-column prop="code" label="代码" width="110" />
        <el-table-column prop="name" label="名称" width="140" />
        <el-table-column label="总市值（亿）" width="130">
          <template #default="{ row }">{{ toFixed(row.total_cap) }}</template>
        </el-table-column>
        <!-- 结果详情统一按 result.tags 渲染，各策略自行决定展示哪些标签 -->
        <el-table-column label="策略详情" min-width="420">
          <template #default="{ row }">
            <div v-if="row.result">
              <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 6px;">
                <el-tag
                  v-for="(t, i) in (row.result.tags || [])"
                  :key="i"
                  :type="t.tone"
                  size="small"
                  effect="light"
                >{{ t.text }}</el-tag>
              </div>
              <div style="font-size: 12px; color: #909399;">{{ row.result.strategy }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewStock(row)">查看K线</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-empty v-else-if="hasRun" description="没有符合条件的股票" />

    <KlineChartDialog
      v-model:visible="chartDialogVisible"
      :stock-code="selectedStockCode"
      :strategy-result="selectedStockResult"
      :backtest-signals="backtestSignals"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getStrategies, selectStocks, getLatestStrategyResult, searchStocks, backtestStrategy } from '../api'
import KlineChartDialog from '../components/KlineChartDialog.vue'

const strategies = ref([])
const strategyName = ref('')
const minMarketCap = ref(300)
const paramValues = reactive({})

const loading = ref(false)
const hasRun = ref(false)
const results = ref([])
const totalCount = ref(0)

const chartDialogVisible = ref(false)
const selectedStockCode = ref('')
const selectedStockResult = ref(null)
const backtestSignals = ref([])

const searchKeyword = ref('')
const selectedBacktestStock = ref(null)
const backtestLoading = ref(false)
const backtestResult = ref(null)
const startYear = ref(2020)

const selectedStrategy = computed(() => strategies.value.find(s => s.name === strategyName.value))
const currentParams = computed(() => selectedStrategy.value?.params || [])

const toFixed = (num, digits = 2) => (num == null || Number.isNaN(Number(num)) ? '-' : Number(num).toFixed(digits))

// 用策略声明的默认值重置参数表单
const resetParams = () => {
  for (const key of Object.keys(paramValues)) delete paramValues[key]
  for (const p of currentParams.value) paramValues[p.name] = p.default
}

// 回填上次运行时用过的参数（仅接受当前策略声明过的字段）
const applySavedParams = (saved) => {
  if (!saved) return
  if (saved.min_market_cap != null) minMarketCap.value = saved.min_market_cap
  for (const p of currentParams.value) {
    if (saved[p.name] !== undefined) paramValues[p.name] = saved[p.name]
  }
}

const loadLatestResult = async () => {
  resetParams()
  results.value = []
  totalCount.value = 0
  hasRun.value = false
  try {
    const res = await getLatestStrategyResult(strategyName.value)
    if (res.data?.selected_stocks?.length > 0) {
      results.value = res.data.selected_stocks
      totalCount.value = res.data.total_count || 0
      hasRun.value = true
      applySavedParams(res.data.params)
    }
  } catch (error) {
    console.error('加载最新结果失败:', error)
  }
}

onMounted(async () => {
  try {
    const res = await getStrategies()
    strategies.value = Array.isArray(res.data) ? res.data : []
    if (strategies.value.length > 0) {
      strategyName.value = strategies.value[0].name
      await loadLatestResult()
    }
  } catch (error) {
    console.error(error)
  }
})

const onStrategyChange = () => {
  backtestResult.value = null
  backtestSignals.value = []
  loadLatestResult()
}

const runStrategy = async () => {
  if (!strategyName.value) return ElMessage.warning('请选择策略')
  loading.value = true
  hasRun.value = true
  try {
    const res = await selectStocks({
      strategyName: strategyName.value,
      minMarketCap: minMarketCap.value,
      params: paramValues,
    })
    results.value = res.data.selected_stocks || []
    totalCount.value = res.data.total_count || 0
    ElMessage.success(`筛选完成，命中 ${totalCount.value} 只`)
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

const viewStock = (row) => {
  selectedStockCode.value = row.code
  selectedStockResult.value = row.result
  backtestSignals.value = []
  chartDialogVisible.value = true
}

const handleSearch = (queryString, callback) => {
  if (!queryString) return callback([])
  searchStocks(queryString, 20)
    .then(res => callback((res.data?.list || []).map(s => ({
      value: `${s.code} ${s.name}`,
      code: s.code,
      name: s.name,
      total_cap: s.total_cap,
    }))))
    .catch(() => callback([]))
}

const onSelectStock = (item) => {
  selectedBacktestStock.value = item
}

const runBacktest = async () => {
  if (!selectedBacktestStock.value) return ElMessage.warning('请先选择股票')
  if (!strategyName.value) return ElMessage.warning('请先选择策略')

  backtestLoading.value = true
  backtestResult.value = null
  try {
    const res = await backtestStrategy({
      strategyName: strategyName.value,
      stockCode: selectedBacktestStock.value.code,
      startYear: startYear.value,
      params: paramValues,
    })
    backtestResult.value = res.data
    backtestSignals.value = res.data?.signals || []
  } catch (error) {
    console.error('回测失败:', error)
  } finally {
    backtestLoading.value = false
  }
}

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
