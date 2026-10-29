<template>
  <div>
    <!-- ① 股票池 -->
    <el-card style="margin-bottom: 16px;">
      <template #header><span>① 选择股票（已选 {{ selected.length }} 只）</span></template>

      <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: center;">
        <el-select v-model="importStrategy" placeholder="从选股结果导入" style="width: 260px;">
          <el-option v-for="s in strategies" :key="s.name" :label="s.display_name" :value="s.name" />
        </el-select>
        <el-button :loading="importing" @click="importFromStrategy">导入选股结果</el-button>

        <el-divider direction="vertical" />

        <el-autocomplete
          v-model="searchKeyword"
          :fetch-suggestions="handleSearch"
          placeholder="或搜索代码/名称手动添加"
          style="width: 280px;"
          clearable
          @select="addStock"
        >
          <template #default="{ item }">
            <div style="display: flex; justify-content: space-between;">
              <span><strong>{{ item.code }}</strong> {{ item.name }}</span>
              <span style="color: #909399; font-size: 12px;">{{ toFixed(item.total_cap) }}亿</span>
            </div>
          </template>
        </el-autocomplete>

        <el-button v-if="selected.length" link type="danger" @click="selected = []">清空</el-button>
      </div>

      <div v-if="selected.length" style="margin-top: 12px; display: flex; flex-wrap: wrap; gap: 6px;">
        <el-tag
          v-for="s in selected"
          :key="s.code"
          closable
          size="small"
          @close="removeStock(s.code)"
        >{{ s.code }} {{ s.name }}</el-tag>
      </div>
      <el-empty v-else description="请先导入或添加股票" :image-size="60" />
    </el-card>

    <!-- ② 买入 + 卖出 -->
    <el-card style="margin-bottom: 16px;">
      <template #header><span>② 买入条件 × 卖出规则</span></template>

      <el-form :inline="true">
        <el-form-item label="买入条件">
          <el-select v-model="entryName" style="width: 260px;" @change="onEntryChange">
            <el-option v-for="r in entryRules" :key="r.name" :label="r.display_name" :value="r.name" />
          </el-select>
        </el-form-item>
        <el-form-item v-for="p in entryParams" :key="p.name" :label="p.label">
          <el-input-number
            v-model="entryValues[p.name]"
            :min="p.min ?? undefined" :max="p.max ?? undefined"
            :step="p.step || 1" :precision="p.type === 'float' ? 2 : 0"
            style="width: 110px;"
          />
          <span v-if="p.suffix" style="margin-left: 6px;">{{ p.suffix }}</span>
        </el-form-item>
      </el-form>

      <el-alert
        type="info" :closable="false" show-icon style="margin-bottom: 12px;"
        title="组内可选「任一满足」或「全部满足」，组与组之间恒为「任一满足」。同一天多条触发时按优先级取第一条：止损 > 移动止损 > 止盈 > MACD红柱连降 > 连续跌破均线 > 技术反转 > 时间到期。买卖信号均在次一交易日收盘成交。"
      />

      <div v-for="(group, gi) in exitGroups" :key="gi" class="group">
        <div class="group__head">
          <span class="group__title">条件组 {{ gi + 1 }}</span>
          <el-radio-group v-model="group.logic" size="small">
            <el-radio-button value="any">任一满足即卖出</el-radio-button>
            <el-radio-button value="all">全部满足才卖出</el-radio-button>
          </el-radio-group>
          <div style="flex: 1" />
          <el-button v-if="exitGroups.length > 1" link type="danger" @click="exitGroups.splice(gi, 1)">
            删除本组
          </el-button>
        </div>

        <div class="exit-list">
          <div
            v-for="r in exitRules" :key="r.name"
            class="exit-item" :class="{ 'exit-item--on': group.enabled[r.name] }"
          >
            <el-checkbox v-model="group.enabled[r.name]">
              <span class="exit-item__name">{{ r.display_name }}</span>
            </el-checkbox>
            <div class="exit-item__desc">{{ r.description }}</div>
            <div v-if="group.enabled[r.name] && r.params.length" class="exit-item__params">
              <div v-for="p in r.params" :key="p.name" class="exit-param">
                <span>{{ p.label }}</span>
                <el-input-number
                  v-model="group.values[r.name][p.name]"
                  :min="p.min ?? undefined" :max="p.max ?? undefined"
                  :step="p.step || 1" :precision="p.type === 'float' ? 2 : 0"
                  size="small" style="width: 100px;"
                />
                <span>{{ p.suffix }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <el-button style="margin-top: 12px;" @click="addGroup">+ 添加条件组（与上面各组是「或」关系）</el-button>

    </el-card>

    <!-- ③ 回测设置 -->
    <el-card style="margin-bottom: 16px;">
      <template #header><span>③ 回测设置</span></template>
      <el-form :inline="true">
        <el-form-item label="时间区间">
          <el-date-picker
            v-model="dateRange" type="daterange" value-format="YYYY-MM-DD"
            start-placeholder="开始" end-placeholder="结束" style="width: 260px;"
          />
        </el-form-item>
        <el-form-item label="初始本金">
          <el-input-number v-model="initialCapital" :min="10000" :step="10000" style="width: 150px;" />
          <span style="margin-left: 6px;">元</span>
        </el-form-item>
        <el-form-item label="买卖成交">
          <span>信号次一交易日收盘</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" :loading="running" @click="run">运行回测</el-button>
        </el-form-item>
      </el-form>
      <div class="hint">
        买入、卖出均按信号次一交易日收盘价撮合，并计入滑点；涨跌停受阻则顺延。
        期末未卖出持仓按收盘价估值，不强制平仓；胜率等交易指标只统计已完成交易。<br />
        全区间统一费率：佣金万2.5（最低 5 元）、卖出印花税万5、过户费 0.001%、滑点 0.1%。
      </div>
    </el-card>

    <!-- ④ 结果 -->
    <template v-if="result">
      <el-card style="margin-bottom: 16px;">
        <template #header><span>④ 聚合结果（{{ result.summary.stock_count }} 只股票）</span></template>

        <div class="section-label">
          交易池（所有股票的交易合并统计，衡量信号质量）
          <el-tag v-if="result.summary.pool.sample_warning" type="warning" size="small" effect="plain">
            样本不足 30 笔，无统计意义
          </el-tag>
        </div>
        <div class="metric-grid">
          <div v-for="m in poolMetrics" :key="m.label" class="metric">
            <span class="metric__label">{{ m.label }}</span>
            <span class="metric__value" :class="m.tone">{{ m.value }}</span>
          </div>
        </div>

        <div class="section-label">
          截面分布（个股收益右偏厚尾，中位数比均值更能代表典型表现）
        </div>
        <div class="metric-grid">
          <div v-for="m in crossMetrics" :key="m.label" class="metric">
            <span class="metric__label">{{ m.label }}</span>
            <span class="metric__value" :class="m.tone">{{ m.value }}</span>
          </div>
        </div>

        <el-alert
          type="info" :closable="false"
          title="刻意不提供跨股票的 Sharpe / 最大回撤平均值：各股回撤不同时发生，其平均值对应不到任何可执行的组合，没有可解释含义。"
          style="margin-top: 12px;"
        />
      </el-card>

      <el-card>
        <template #header><span>每只股票明细（点击行查看资金曲线与交易记录）</span></template>
        <el-table :data="result.per_stock" stripe @row-click="openDetail" style="cursor: pointer;">
          <el-table-column prop="stock_code" label="代码" width="100" />
          <el-table-column prop="stock_name" label="名称" width="120" />
          <el-table-column label="总收益" width="110" sortable :sort-by="r => r.total_return_pct">
            <template #default="{ row }">
              <span :class="row.total_return_pct >= 0 ? 'up' : 'down'">{{ row.total_return_pct }}%</span>
            </template>
          </el-table-column>
          <el-table-column label="基准" width="100">
            <template #default="{ row }">
              <span :class="row.benchmark_return_pct >= 0 ? 'up' : 'down'">{{ row.benchmark_return_pct }}%</span>
            </template>
          </el-table-column>
          <el-table-column label="超额" width="100" sortable :sort-by="r => r.excess_return_pct">
            <template #default="{ row }">
              <span :class="row.excess_return_pct >= 0 ? 'up' : 'down'">{{ row.excess_return_pct }}%</span>
            </template>
          </el-table-column>
          <el-table-column prop="trade_count" label="交易" width="80" />
          <el-table-column label="胜率" width="90">
            <template #default="{ row }">{{ row.win_rate == null ? '-' : row.win_rate + '%' }}</template>
          </el-table-column>
          <el-table-column prop="payoff_ratio" label="盈亏比" width="90" />
          <el-table-column label="最大回撤" width="100">
            <template #default="{ row }"><span class="down">{{ row.max_drawdown_pct }}%</span></template>
          </el-table-column>
          <el-table-column prop="avg_hold_bars" label="均持仓" width="90" />
          <el-table-column label="暴露" width="90">
            <template #default="{ row }">{{ row.exposure_pct }}%</template>
          </el-table-column>
        </el-table>

        <el-alert
          v-if="result.skipped.length"
          type="warning" :closable="false" style="margin-top: 12px;"
          :title="`${result.skipped.length} 只股票被跳过：${result.skipped.map(s => s.code + ' ' + s.reason).join('；')}`"
        />
      </el-card>
    </template>

    <EquityCurveDialog
      v-model:visible="detailVisible"
      :stat="detailStat"
      :detail="detailData"
      :initial-capital="result?.config.initial_capital ?? initialCapital"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getBacktestRules, runBacktest, getStrategies,
  getLatestStrategyResult, searchStocks,
} from '../api'
import EquityCurveDialog from '../components/EquityCurveDialog.vue'

const entryRules = ref([])
const exitRules = ref([])
const strategies = ref([])

const entryName = ref('')
const entryValues = reactive({})
// 卖出条件：多个条件组，组间 OR，组内 any/all
const exitGroups = ref([])

const selected = ref([])
const importStrategy = ref('')
const importing = ref(false)
const searchKeyword = ref('')

const dateRange = ref([])
const initialCapital = ref(100000)

const running = ref(false)
const result = ref(null)
const detailVisible = ref(false)
const detailStat = ref(null)
const detailData = ref(null)

const toFixed = (v, d = 2) => (v == null || Number.isNaN(Number(v)) ? '-' : Number(v).toFixed(d))
const fmt = (v, suffix = '') => (v == null ? '-' : `${v}${suffix}`)
const tone = (v) => (v == null ? '' : v >= 0 ? 'up' : 'down')

const currentEntry = computed(() => entryRules.value.find(r => r.name === entryName.value))
const entryParams = computed(() => currentEntry.value?.params || [])

const poolMetrics = computed(() => {
  const p = result.value?.summary.pool
  if (!p) return []
  return [
    { label: '总交易笔数', value: fmt(p.trade_count) },
    { label: '胜率', value: fmt(p.win_rate, '%') },
    { label: '盈亏比', value: fmt(p.payoff_ratio) },
    { label: '盈利因子', value: fmt(p.profit_factor) },
    { label: 'SQN', value: fmt(p.sqn) },
    { label: '每笔期望', value: fmt(p.expectancy_pct, '%'), tone: tone(p.expectancy_pct) },
    { label: '平均持仓', value: fmt(p.avg_hold_bars, ' 日') },
    { label: '最大连亏', value: fmt(p.max_consecutive_losses, ' 笔') },
    { label: '最佳单笔', value: fmt(p.best_trade_pct, '%'), tone: 'up' },
    { label: '最差单笔', value: fmt(p.worst_trade_pct, '%'), tone: 'down' },
    { label: '总费用', value: fmt(p.total_cost, ' 元') },
  ]
})

const crossMetrics = computed(() => {
  const c = result.value?.summary.cross_section
  if (!c?.best || !c?.worst) return []
  return [
    { label: '收益中位数', value: fmt(c.median_return_pct, '%'), tone: tone(c.median_return_pct) },
    { label: '收益均值', value: fmt(c.mean_return_pct, '%'), tone: tone(c.mean_return_pct) },
    { label: '25% 分位', value: fmt(c.p25_return_pct, '%'), tone: tone(c.p25_return_pct) },
    { label: '75% 分位', value: fmt(c.p75_return_pct, '%'), tone: tone(c.p75_return_pct) },
    { label: '正收益占比', value: fmt(c.positive_ratio, '%') },
    { label: '平均超额', value: fmt(c.mean_excess_pct, '%'), tone: tone(c.mean_excess_pct) },
    { label: '最佳', value: `${c.best.name} ${c.best.return_pct}%`, tone: 'up' },
    { label: '最差', value: `${c.worst.name} ${c.worst.return_pct}%`, tone: 'down' },
  ]
})

// 每个组独立持有自己的勾选状态与参数值
const makeGroup = (preset = {}) => ({
  logic: 'any',
  enabled: Object.fromEntries(exitRules.value.map(r => [r.name, !!preset[r.name]])),
  values: Object.fromEntries(
    exitRules.value.map(r => [r.name, Object.fromEntries(r.params.map(p => [p.name, p.default]))])
  ),
})

const addGroup = () => exitGroups.value.push(makeGroup())

const resetEntryParams = () => {
  for (const k of Object.keys(entryValues)) delete entryValues[k]
  for (const p of entryParams.value) entryValues[p.name] = p.default
}

const onEntryChange = () => resetEntryParams()

onMounted(async () => {
  try {
    const [rules, strats] = await Promise.all([getBacktestRules(), getStrategies()])
    entryRules.value = rules.data.entry_rules || []
    exitRules.value = rules.data.exit_rules || []
    strategies.value = strats.data || []

    if (entryRules.value.length) {
      entryName.value = entryRules.value[0].name
      resetEntryParams()
    }
    if (strategies.value.length) importStrategy.value = strategies.value[0].name

    // 默认给一个组，选中固定持有期做基准线
    exitGroups.value = [makeGroup({ fixed_days: true })]
  } catch (e) {
    console.error(e)
  }
})

const importFromStrategy = async () => {
  if (!importStrategy.value) return
  importing.value = true
  try {
    const res = await getLatestStrategyResult(importStrategy.value)
    const list = res.data?.selected_stocks || []
    if (!list.length) {
      return ElMessage.warning(res.data?.run_date
        ? '该策略最近一次选股未命中股票'
        : '该策略还没有选股结果，请先到「选股策略」页运行一次')
    }
    const seen = new Set(selected.value.map(s => s.code))
    for (const s of list) {
      if (!seen.has(s.code)) {
        selected.value.push({ code: s.code, name: s.name })
        seen.add(s.code)
      }
    }
    ElMessage.success(`已导入 ${list.length} 只股票`)
  } catch (e) {
    console.error(e)
  } finally {
    importing.value = false
  }
}

const handleSearch = (q, cb) => {
  if (!q) return cb([])
  searchStocks(q, 20)
    .then(res => cb((res.data?.list || []).map(s => ({
      value: `${s.code} ${s.name}`, code: s.code, name: s.name, total_cap: s.total_cap,
    }))))
    .catch(() => cb([]))
}

const addStock = (item) => {
  if (!selected.value.some(s => s.code === item.code)) {
    selected.value.push({ code: item.code, name: item.name })
  }
  searchKeyword.value = ''
}

const removeStock = (code) => {
  selected.value = selected.value.filter(s => s.code !== code)
}

const run = async () => {
  if (!selected.value.length) return ElMessage.warning('请先选择股票')
  if (selected.value.length > 100) return ElMessage.warning('单次最多回测 100 只股票，请减少股票数量')
  if (dateRange.value?.[0] > dateRange.value?.[1]) return ElMessage.warning('起始日期不能晚于结束日期')
  const groups = exitGroups.value
    .map(g => ({
      logic: g.logic,
      rules: exitRules.value.filter(r => g.enabled[r.name])
        .map(r => ({ name: r.name, params: g.values[r.name] })),
    }))
    .filter(g => g.rules.length)
  if (!groups.length) return ElMessage.warning('请至少选择一条卖出规则')

  running.value = true
  result.value = null
  try {
    const res = await runBacktest({
      stock_codes: selected.value.map(s => s.code),
      entry_name: entryName.value,
      entry_params: entryValues,
      exit_groups: groups,
      start_date: dateRange.value?.[0] || null,
      end_date: dateRange.value?.[1] || null,
      config: {
        initial_capital: initialCapital.value,
        execution: 'next_close',
        exit_timing: 'next_day',
      },
    })
    result.value = res.data
    ElMessage.success(`回测完成，共 ${res.data.summary.stock_count} 只股票`)
  } catch (e) {
    console.error(e)
  } finally {
    running.value = false
  }
}

const openDetail = (row) => {
  detailStat.value = row
  detailData.value = result.value?.details?.[row.stock_code] || null
  detailVisible.value = true
}
</script>

<style scoped>
.group {
  border: 1px solid #e8ebf2;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 12px;
  background: #fcfdff;
}

.group__head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.group__title {
  font-weight: 600;
  color: #303133;
}

.exit-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.exit-item {
  border: 1px solid #e8ebf2;
  border-radius: 8px;
  padding: 12px 14px;
  transition: all 0.2s;
}

.exit-item--on {
  border-color: #409eff;
  background: #f6fbff;
}

.exit-item__name {
  font-weight: 600;
  color: #303133;
}

.exit-item__desc {
  font-size: 12px;
  color: #9aa0ac;
  margin: 6px 0 0 24px;
}

.exit-item__params {
  margin: 10px 0 0 24px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.exit-param {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #606266;
}

.section-label {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin: 4px 0 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
  padding: 14px 16px;
  background: #fafbfd;
  border: 1px solid #eef0f5;
  border-radius: 8px;
  margin-bottom: 16px;
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.metric__label {
  font-size: 12px;
  color: #9aa0ac;
}

.metric__value {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.hint {
  font-size: 12px;
  color: #9aa0ac;
  line-height: 1.7;
}

.up {
  color: #ef5350;
}

.down {
  color: #26a69a;
}
</style>
