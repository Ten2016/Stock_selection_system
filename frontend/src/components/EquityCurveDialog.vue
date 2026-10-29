<template>
  <el-dialog
    :model-value="visible"
    :title="`${stat?.stock_code} ${stat?.stock_name} — 回测明细`"
    width="86%"
    top="5vh"
    destroy-on-close
    @update:model-value="$emit('update:visible', $event)"
    @opened="onOpened"
    @closed="destroyChart"
  >
    <div v-if="stat">
      <div class="metric-grid">
        <div v-for="m in metrics" :key="m.label" class="metric">
          <span class="metric__label">{{ m.label }}</span>
          <span class="metric__value" :class="m.tone">{{ m.value }}</span>
        </div>
      </div>

      <el-alert v-if="detail?.open_position" type="info" :closable="false" style="margin-bottom: 16px;">
        期末仍持有 {{ detail.open_position.shares }} 股，按收盘价估值，未计入已完成交易。
        <span v-if="detail.open_position.pending_exit">待卖出：{{ detail.open_position.pending_exit }}。</span>
      </el-alert>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="K线与买卖区间" name="kline">
          <div class="tab-hint">
            蓝色粗线段为持仓区间，箭头为买卖点，卖出点标注该笔净收益率。
          </div>
          <KlineChartPanel v-if="activeTab === 'kline'" :stock-code="stat.stock_code" :trades="trades" />
        </el-tab-pane>

        <el-tab-pane :label="`资金曲线`" name="equity">
          <div class="tab-hint">初始本金 {{ formatMoney(initialCapital) }}，虚线为本金基准。</div>
          <div ref="chartRef" class="equity-chart" />
        </el-tab-pane>

        <el-tab-pane :label="`交易明细 (${trades.length})`" name="trades">
          <el-table :data="trades" stripe size="small" max-height="420">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="entry_date" label="买入日" width="110" />
            <el-table-column prop="entry_price" label="买入价" width="90" />
            <el-table-column prop="exit_date" label="卖出日" width="110" />
            <el-table-column prop="exit_price" label="卖出价" width="90" />
            <el-table-column prop="bars_held" label="持有(日)" width="85" />
            <el-table-column label="净收益率" width="100" sortable :sort-by="r => r.pnl_pct">
              <template #default="{ row }">
                <span :class="row.pnl_pct >= 0 ? 'up' : 'down'">
                  {{ row.pnl_pct > 0 ? '+' : '' }}{{ row.pnl_pct }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column label="净盈亏" width="105">
              <template #default="{ row }">
                <span :class="row.pnl >= 0 ? 'up' : 'down'">{{ formatMoney(row.pnl) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="cost" label="费用" width="80" />
            <el-table-column prop="exit_reason" label="卖出原因" min-width="180" />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import { createChart, LineSeries, ColorType, LineStyle, CrosshairMode } from 'lightweight-charts'
import KlineChartPanel from './KlineChartPanel.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  stat: { type: Object, default: null },
  detail: { type: Object, default: null },
  initialCapital: { type: Number, default: 100000 },
})

defineEmits(['update:visible'])

const activeTab = ref('kline')
const chartRef = ref(null)
// 图表实例用普通变量：Vue 的 Proxy 会破坏 lightweight-charts 内部实例判等
let chart = null

const trades = computed(() => props.detail?.trades || [])

const fmt = (v, suffix = '') => (v == null ? '-' : `${v}${suffix}`)
const formatMoney = (v) =>
  v == null ? '-' : Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 0 })

const metrics = computed(() => {
  const s = props.stat
  if (!s) return []
  const tone = (v) => (v == null ? '' : v >= 0 ? 'up' : 'down')
  return [
    { label: '总收益', value: fmt(s.total_return_pct, '%'), tone: tone(s.total_return_pct) },
    { label: '买入持有基准', value: fmt(s.benchmark_return_pct, '%'), tone: tone(s.benchmark_return_pct) },
    { label: '超额收益', value: fmt(s.excess_return_pct, '%'), tone: tone(s.excess_return_pct) },
    { label: '最大回撤', value: fmt(s.max_drawdown_pct, '%'), tone: 'down' },
    { label: '交易笔数', value: fmt(s.trade_count) },
    { label: '胜率', value: fmt(s.win_rate, '%') },
    { label: '盈亏比', value: fmt(s.payoff_ratio) },
    { label: '盈利因子', value: fmt(s.profit_factor) },
    { label: 'SQN', value: fmt(s.sqn) },
    { label: '平均持仓', value: fmt(s.avg_hold_bars, ' 日') },
    { label: '最大连亏', value: fmt(s.max_consecutive_losses, ' 笔') },
    { label: '仓位暴露', value: fmt(s.exposure_pct, '%') },
    { label: '总费用', value: formatMoney(s.total_cost) },
    { label: '已实现盈亏', value: formatMoney(s.realized_pnl), tone: tone(s.realized_pnl) },
    { label: '持仓浮动盈亏', value: formatMoney(s.unrealized_pnl), tone: tone(s.unrealized_pnl) },
    { label: '期末权益', value: formatMoney(s.final_equity) },
  ]
})

const buildChart = () => {
  const curve = props.detail?.equity_curve || []
  if (!chartRef.value || !curve.length) return

  chart = createChart(chartRef.value, {
    autoSize: true,
    layout: {
      background: { type: ColorType.Solid, color: '#ffffff' },
      textColor: '#5c6270',
      attributionLogo: false,
    },
    grid: { vertLines: { color: '#f4f6fa' }, horzLines: { color: '#f4f6fa' } },
    rightPriceScale: { borderColor: '#e8ebf2' },
    timeScale: { borderColor: '#e8ebf2' },
    crosshair: {
      mode: CrosshairMode.Normal,
      vertLine: { style: LineStyle.Dashed },
      horzLine: { style: LineStyle.Dashed },
    },
    localization: { priceFormatter: (p) => p.toFixed(0) },
  })

  const equity = chart.addSeries(LineSeries, {
    color: '#409eff',
    lineWidth: 2,
    priceFormat: { type: 'price', precision: 0, minMove: 1 },
  }, 0)
  equity.setData(curve.map((d) => ({ time: d.date, value: d.equity })))

  // 本金基准线，一眼看出是赚是亏
  equity.createPriceLine({
    price: props.initialCapital,
    color: '#909399',
    lineWidth: 1,
    lineStyle: LineStyle.Dashed,
    axisLabelVisible: true,
    title: '本金',
  })

  chart.timeScale().fitContent()
}

const destroyChart = () => {
  chart?.remove()
  chart = null
}

const onOpened = async () => {
  activeTab.value = 'kline'
  destroyChart()
}

// 容器在 tab 激活后才有尺寸，autoSize 依赖这一点，否则高度会塌成 0
watch(activeTab, async (tab) => {
  destroyChart()
  if (tab !== 'equity' || !props.visible) return
  await nextTick()
  if (props.visible && activeTab.value === 'equity') buildChart()
})

onUnmounted(destroyChart)
</script>

<style scoped>
.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
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

.tab-hint {
  font-size: 12px;
  color: #9aa0ac;
  margin-bottom: 10px;
}

.equity-chart {
  width: 100%;
  height: 300px;
  border: 1px solid #eef0f5;
  border-radius: 8px;
}

.up {
  color: #ef5350;
}

.down {
  color: #26a69a;
}
</style>
