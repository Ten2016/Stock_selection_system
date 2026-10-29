<template>
  <div v-loading="loading" class="kline-body">
    <!-- 基本信息 -->
    <div v-if="stockBasicInfo" class="basic-info">
      <div v-for="item in basicInfoItems" :key="item.label" class="basic-info__cell">
        <span class="basic-info__label">{{ item.label }}</span>
        <span class="basic-info__value" :class="item.tone">{{ item.value }}</span>
      </div>
    </div>

    <!-- 指标开关 -->
    <div class="toolbar">
      <el-checkbox-group v-model="visibleOverlays" size="small">
        <el-checkbox-button v-for="ma in MA_LINES" :key="ma.key" :value="ma.key">
          <span :style="{ color: ma.color }">●</span> {{ ma.label }}
        </el-checkbox-button>
        <el-checkbox-button value="boll">
          <span :style="{ color: BOLL_COLOR }">●</span> BOLL
        </el-checkbox-button>
      </el-checkbox-group>
      <div class="toolbar__spacer" />
      <el-radio-group v-model="rangeDays" size="small">
        <el-radio-button v-for="r in RANGE_PRESETS" :key="r.value" :value="r.value">
          {{ r.label }}
        </el-radio-button>
      </el-radio-group>
    </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  createSeriesMarkers,
  CrosshairMode,
  LineStyle,
  ColorType,
} from 'lightweight-charts'
import api from '../api'

const emit = defineEmits(['loaded'])

const props = defineProps({
  stockCode: { type: String, default: '' },
  strategyResult: { type: Object, default: null },
  backtestSignals: { type: Array, default: () => [] },
  // 回测交易记录：在图上标出买卖点，并把持仓区间高亮成粗线
  trades: { type: Array, default: () => [] },
})


// A 股惯例：红涨绿跌
const UP_COLOR = '#ef5350'
const DOWN_COLOR = '#26a69a'
const BOLL_COLOR = '#b37feb'
const DIF_COLOR = '#f5a623'
const DEA_COLOR = '#4a90e2'

const MA_LINES = [
  { key: 'ma5', label: 'MA5', color: '#f5a623' },
  { key: 'ma10', label: 'MA10', color: '#4a90e2' },
  { key: 'ma20', label: 'MA20', color: '#9c27b0' },
  { key: 'ma30', label: 'MA30', color: '#00bcd4' },
  { key: 'ma60', label: 'MA60', color: '#ff7043' },
]

const RANGE_PRESETS = [
  { label: '3月', value: 60 },
  { label: '6月', value: 120 },
  { label: '1年', value: 250 },
  { label: '全部', value: 0 },
]

const MACD_PANE = 1
const MACD_PANE_HEIGHT = 130
// 拉取窗口：覆盖最长预设(1年≈250交易日)并留出均线预热余量
const FETCH_DAYS = 600

const historyStart = computed(() => {
  const start = new Date()
  start.setDate(start.getDate() - FETCH_DAYS)
  const recent = `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`
  const dates = [
    recent,
    ...props.backtestSignals.map(signal => signal.date),
    ...props.trades.flatMap(trade => [trade.entry_date, trade.exit_date]),
    props.strategyResult?.breakdown_date,
    props.strategyResult?.rise_date,
    props.strategyResult?.valley_date,
    ...(props.strategyResult?.matching_dates || []),
    ...(props.strategyResult?.falling_dates || []),
  ].filter(Boolean)
  return dates.sort()[0]
})

const chartRef = ref(null)
const stockName = ref('')
const stockBasicInfo = ref(null)
const loading = ref(false)
const hasData = ref(false)
const visibleOverlays = ref(['ma5', 'ma10', 'ma20', 'ma60'])
const rangeDays = ref(120)
// 传入回测交易时默认看全部区间，否则早期的买卖点会落在可视区外

const emptyLegend = () => ({
  date: '-', open: '-', high: '-', low: '-', close: '-', changePct: '-',
  ma5: '-', ma10: '-', ma20: '-', ma30: '-', ma60: '-',
  dif: '-', dea: '-', macd: '-',
  tone: 'flat', macdTone: 'flat',
})
const legend = reactive(emptyLegend())

// 图表实例一律用普通变量：Vue 的响应式 Proxy 会破坏库内部的实例判等，
// 导致 param.seriesData.get(series) 永远取不到值。
let chart = null
let candleSeries = null
let maSeries = {}
let bollSeries = {}
let macdHist = null
let difSeries = null
let deaSeries = null
let markersPlugin = null
let holdingSeries = null
let resizeObserver = null
let allData = []

const toFixed = (num, digits = 2) => {
  if (num == null) return '-'
  const n = Number(num)
  return Number.isNaN(n) ? '-' : n.toFixed(digits)
}

const basicInfoItems = computed(() => {
  const info = stockBasicInfo.value || {}
  const ytd = info.ytd_change_pct
  return [
    { label: '总市值', value: info.total_cap != null ? `${toFixed(info.total_cap)} 亿` : '-' },
    { label: '动态市盈率', value: toFixed(info.pe_ratio) },
    { label: '静态市盈率', value: toFixed(info.pe_ratio_static) },
    { label: '市净率', value: toFixed(info.pb_ratio) },
    {
      label: '今年涨跌幅',
      value: ytd != null ? `${toFixed(ytd)}%` : '-',
      tone: ytd == null ? '' : ytd >= 0 ? 'up' : 'down',
    },
    { label: '行业', value: info.industry || '-' },
  ]
})

const strategyTags = computed(() => {
  const result = props.strategyResult
  if (!result) return []
  // 后端策略统一返回 tags；兼容旧结果则退回按字段拼装
  if (Array.isArray(result.tags)) return result.tags
  const fallback = []
  if (result.breakdown_date) fallback.push({ text: `跌破 ${result.breakdown_date}`, tone: 'warning' })
  if (result.rise_date) fallback.push({ text: `大涨 ${result.rise_date}`, tone: 'danger' })
  if (result.valley_date) fallback.push({ text: `拐点 ${result.valley_date}`, tone: 'success' })
  return fallback
})

// ---------- 主题 ----------
const chartTheme = () => ({
  layout: {
    background: { type: ColorType.Solid, color: '#ffffff' },
    textColor: '#5c6270',
    fontSize: 12,
    attributionLogo: false,
    panes: { separatorColor: '#e8ebf2', separatorHoverColor: 'rgba(64,158,255,0.25)', enableResize: true },
  },
  grid: {
    vertLines: { color: '#f4f6fa' },
    horzLines: { color: '#f4f6fa' },
  },
  rightPriceScale: {
    borderColor: '#e8ebf2',
    scaleMargins: { top: 0.12, bottom: 0.08 },
  },
  timeScale: {
    borderColor: '#e8ebf2',
    rightOffset: 6,
    barSpacing: 8,
    minBarSpacing: 1,
  },
  crosshair: {
    mode: CrosshairMode.Normal,
    vertLine: { color: '#9aa0ac', width: 1, style: LineStyle.Dashed, labelBackgroundColor: '#5c6270' },
    horzLine: { color: '#9aa0ac', width: 1, style: LineStyle.Dashed, labelBackgroundColor: '#5c6270' },
  },
})

// 日线的 time 直接用后端的 'YYYY-MM-DD'，避开时区换算
const formatDate = (t) => {
  if (typeof t === 'string') return t
  if (t && typeof t === 'object' && 'year' in t) {
    return `${t.year}-${String(t.month).padStart(2, '0')}-${String(t.day).padStart(2, '0')}`
  }
  return String(t ?? '-')
}

// 指标为 null 时给 whitespace（只有 time），让线断开而不是错误连线
const lineData = (rows, key) =>
  rows.map(d => (d[key] == null ? { time: d.trade_date } : { time: d.trade_date, value: d[key] }))

// ---------- 构建图表 ----------
const buildChart = () => {
  if (!chartRef.value) return

  chart = createChart(chartRef.value, { autoSize: true, ...chartTheme() })

  candleSeries = chart.addSeries(CandlestickSeries, {
    upColor: UP_COLOR,
    downColor: DOWN_COLOR,
    borderUpColor: UP_COLOR,
    borderDownColor: DOWN_COLOR,
    wickUpColor: UP_COLOR,
    wickDownColor: DOWN_COLOR,
    borderVisible: false,
    priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
  }, 0)

  const overlayOpts = (color, extra = {}) => ({
    color,
    lineWidth: 1,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
    ...extra,
  })

  for (const ma of MA_LINES) {
    maSeries[ma.key] = chart.addSeries(LineSeries, overlayOpts(ma.color), 0)
  }
  for (const key of ['boll_upper', 'boll_mid', 'boll_lower']) {
    bollSeries[key] = chart.addSeries(
      LineSeries,
      overlayOpts(BOLL_COLOR, { lineStyle: LineStyle.Dotted }),
      0,
    )
  }

  // 持仓区间高亮：只在持仓期有值的粗线，非持仓期给 whitespace 断开
  holdingSeries = chart.addSeries(LineSeries, overlayOpts('#409eff', { lineWidth: 4 }), 0)

  macdHist = chart.addSeries(HistogramSeries, {
    priceFormat: { type: 'price', precision: 4, minMove: 0.0001 },
    priceLineVisible: false,
    lastValueVisible: false,
    base: 0,
  }, MACD_PANE)
  difSeries = chart.addSeries(LineSeries, overlayOpts(DIF_COLOR), MACD_PANE)
  deaSeries = chart.addSeries(LineSeries, overlayOpts(DEA_COLOR), MACD_PANE)

  chart.panes()[MACD_PANE].setHeight(MACD_PANE_HEIGHT)
  chart.subscribeCrosshairMove(onCrosshairMove)
}

const applyData = () => {
  if (!chart || !allData.length) return

  candleSeries.setData(allData.map(d => ({
    time: d.trade_date,
    open: d.open,
    high: d.high,
    low: d.low,
    close: d.close,
  })))

  for (const ma of MA_LINES) {
    maSeries[ma.key].setData(lineData(allData, ma.key))
  }
  for (const key of ['boll_upper', 'boll_mid', 'boll_lower']) {
    bollSeries[key].setData(lineData(allData, key))
  }

  // 逐柱染色写在数据点上，不要为红绿柱建两个 series
  macdHist.setData(allData.map(d => (
    d.macd == null
      ? { time: d.trade_date }
      : { time: d.trade_date, value: d.macd, color: d.macd >= 0 ? UP_COLOR : DOWN_COLOR }
  )))
  difSeries.setData(lineData(allData, 'dif'))
  deaSeries.setData(lineData(allData, 'dea'))

  applyHoldingHighlight()
  applyOverlayVisibility()
  applyMarkers()
  applyRange()
  updateLegend(allData[allData.length - 1])
}

// 把每笔交易的持仓区间画成粗线覆盖在 K 线上，一眼看出「哪几段是持有的」
const applyHoldingHighlight = () => {
  if (!holdingSeries) return
  const held = new Set()
  for (const t of props.trades) {
    for (const d of allData) {
      if (d.trade_date >= t.entry_date && d.trade_date <= t.exit_date) held.add(d.trade_date)
    }
  }
  holdingSeries.setData(
    allData.map(d => (held.has(d.trade_date) ? { time: d.trade_date, value: d.close } : { time: d.trade_date }))
  )
  holdingSeries.applyOptions({ visible: held.size > 0 })
}

const applyOverlayVisibility = () => {
  if (!chart) return
  const selected = visibleOverlays.value
  for (const ma of MA_LINES) {
    maSeries[ma.key]?.applyOptions({ visible: selected.includes(ma.key) })
  }
  const showBoll = selected.includes('boll')
  for (const key of ['boll_upper', 'boll_mid', 'boll_lower']) {
    bollSeries[key]?.applyOptions({ visible: showBoll })
  }
}

const applyMarkers = () => {
  if (!candleSeries) return

  // marker 的 time 必须与 K 线上已有的时间点完全一致，否则会被静默丢弃
  const validDates = new Set(allData.map(d => d.trade_date))
  const markers = []

  const push = (date, opts) => {
    if (date && validDates.has(date)) markers.push({ time: date, ...opts })
  }

  const result = props.strategyResult
  if (result) {
    push(result.breakdown_date, { position: 'belowBar', color: '#faad14', shape: 'arrowUp', text: '跌破' })
    push(result.rise_date, { position: 'aboveBar', color: UP_COLOR, shape: 'arrowDown', text: '大涨' })
    push(result.valley_date, { position: 'belowBar', color: DOWN_COLOR, shape: 'circle', text: '拐点' })
    for (const d of result.matching_dates || []) {
      push(d, { position: 'belowBar', color: DOWN_COLOR, shape: 'arrowUp', text: '站上MA5' })
    }
    for (const d of result.falling_dates || []) {
      push(d, { position: 'aboveBar', color: '#909399', shape: 'arrowDown', text: '' })
    }
  }

  props.backtestSignals.forEach((s, i) => {
    push(s.date, { position: 'belowBar', color: '#409eff', shape: 'arrowUp', text: `B${i + 1}` })
  })

  // 回测交易：买卖点各打一个标记，卖出点标出该笔的净收益率
  props.trades.forEach((t, i) => {
    const win = t.pnl_pct >= 0
    push(t.entry_date, {
      position: 'belowBar', color: '#409eff', shape: 'arrowUp', text: `买${i + 1}`,
    })
    push(t.exit_date, {
      position: 'aboveBar',
      color: win ? UP_COLOR : DOWN_COLOR,
      shape: 'arrowDown',
      text: `卖${i + 1} ${t.pnl_pct > 0 ? '+' : ''}${t.pnl_pct}%`,
    })
  })

  markers.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0))

  if (markersPlugin) {
    markersPlugin.setMarkers(markers)
  } else {
    markersPlugin = createSeriesMarkers(candleSeries, markers)
  }
}

const applyRange = () => {
  if (!chart || !allData.length) return
  const days = props.trades.length || props.backtestSignals.length ? 0 : rangeDays.value
  if (!days || days >= allData.length) {
    chart.timeScale().fitContent()
    return
  }
  chart.timeScale().setVisibleLogicalRange({
    from: allData.length - days,
    to: allData.length - 1 + 6,
  })
}

const onCrosshairMove = (param) => {
  // 鼠标移出数据范围时 time 为 undefined
  if (!param || param.time === undefined || !param.point) {
    updateLegend(allData[allData.length - 1])
    return
  }

  const bar = param.seriesData.get(candleSeries)
  const row = bar ? { ...bar, trade_date: formatDate(param.time) } : null
  if (!row) return

  legend.date = row.trade_date
  legend.open = toFixed(row.open)
  legend.high = toFixed(row.high)
  legend.low = toFixed(row.low)
  legend.close = toFixed(row.close)
  legend.tone = row.close >= row.open ? 'up' : 'down'

  const source = allData.find(d => d.trade_date === row.trade_date)
  legend.changePct = source?.change_pct != null ? `${toFixed(source.change_pct)}%` : '-'

  for (const ma of MA_LINES) {
    legend[ma.key] = toFixed(param.seriesData.get(maSeries[ma.key])?.value)
  }
  legend.dif = toFixed(param.seriesData.get(difSeries)?.value, 4)
  legend.dea = toFixed(param.seriesData.get(deaSeries)?.value, 4)
  const macdVal = param.seriesData.get(macdHist)?.value
  legend.macd = toFixed(macdVal, 4)
  legend.macdTone = macdVal == null ? 'flat' : macdVal >= 0 ? 'up' : 'down'
}

const updateLegend = (row) => {
  if (!row) return
  legend.date = row.trade_date
  legend.open = toFixed(row.open)
  legend.high = toFixed(row.high)
  legend.low = toFixed(row.low)
  legend.close = toFixed(row.close)
  legend.changePct = row.change_pct != null ? `${toFixed(row.change_pct)}%` : '-'
  legend.tone = row.close >= row.open ? 'up' : 'down'
  for (const ma of MA_LINES) legend[ma.key] = toFixed(row[ma.key])
  legend.dif = toFixed(row.dif, 4)
  legend.dea = toFixed(row.dea, 4)
  legend.macd = toFixed(row.macd, 4)
  legend.macdTone = row.macd == null ? 'flat' : row.macd >= 0 ? 'up' : 'down'
}

// ---------- 数据加载 ----------
// 数据到达与容器挂载的先后顺序不确定，两边都调用 renderIfReady，
// 由它判断「容器已挂载 且 数据已就绪」才真正建图。
const mounted = ref(false)
let loadVersion = 0

const renderIfReady = () => {
  if (!mounted.value || !allData.length || !chartRef.value) return
  if (!chart) buildChart()
  applyData()
}

const loadAll = async () => {
  const requestedCode = props.stockCode
  const version = ++loadVersion
  allData = []
  stockBasicInfo.value = null
  Object.assign(legend, emptyLegend())
  loading.value = true
  hasData.value = false
  try {
    const [infoRes, klineRes] = await Promise.all([
      api.get(`/stocks/${requestedCode}`),
      api.get(`/stocks/${requestedCode}/kline`, {
        params: { start_date: historyStart.value },
      }),
    ])

    // 请求返回时可能已切换股票
    if (!mounted.value || version !== loadVersion) return

    stockName.value = infoRes.data?.name || ''
    stockBasicInfo.value = infoRes.data || null
    emit('loaded', { code: requestedCode, name: stockName.value })

    // lightweight-charts 要求数据按时间严格升序
    allData = (klineRes.data?.klines || [])
      .slice()
      .sort((a, b) => (a.trade_date < b.trade_date ? -1 : a.trade_date > b.trade_date ? 1 : 0))

    hasData.value = allData.length > 0
    await nextTick()
    if (!mounted.value || version !== loadVersion) return
    renderIfReady()
  } catch (error) {
    console.error('加载 K 线失败:', error)
  } finally {
    if (mounted.value && version === loadVersion) loading.value = false
  }
}

const destroyChart = () => {
  resizeObserver?.disconnect()
  resizeObserver = null
  if (chart) {
    chart.unsubscribeCrosshairMove(onCrosshairMove)
    chart.remove()
  }
  chart = null
  candleSeries = null
  maSeries = {}
  bollSeries = {}
  macdHist = null
  difSeries = null
  deaSeries = null
  markersPlugin = null
  holdingSeries = null
}

onMounted(async () => {
  mounted.value = true
  await nextTick()
  if (props.stockCode) loadAll()
})

watch([() => props.stockCode, historyStart], ([code]) => {
  if (!code) return
  destroyChart()
  loadAll()
})


// 策略结果 / 回测信号变化时刷新标记，无需重建图表
watch(() => [props.strategyResult, props.backtestSignals, props.trades], () => {
  if (!chart || !allData.length) return
  applyHoldingHighlight()
  applyMarkers()
  applyRange()
})

watch(visibleOverlays, applyOverlayVisibility)
watch(rangeDays, applyRange)

onUnmounted(() => {
  mounted.value = false
  loadVersion += 1
  destroyChart()
})
</script>

<style scoped>
.kline-body {
  min-height: 200px;
}

.basic-info {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  padding: 12px 16px;
  background: #fafbfd;
  border: 1px solid #eef0f5;
  border-radius: 8px;
  margin-bottom: 12px;
}

.basic-info__cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.basic-info__label {
  font-size: 12px;
  color: #9aa0ac;
}

.basic-info__value {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.toolbar__spacer {
  flex: 1;
}

.chart-wrap {
  position: relative;
  width: 100%;
  height: 560px;
  border: 1px solid #eef0f5;
  border-radius: 8px;
  overflow: hidden;
}

.chart {
  width: 100%;
  height: 100%;
}

.chart-empty {
  position: absolute;
  inset: 0;
  background: #fff;
}

.legend {
  position: absolute;
  top: 8px;
  left: 12px;
  z-index: 3;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  line-height: 18px;
  pointer-events: none;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

/* 副图读数固定在 MACD 面板左上角 */
.legend--macd {
  top: auto;
  bottom: 148px;
}

.legend__date {
  font-weight: 600;
  color: #303133;
}

.legend__title {
  color: #9aa0ac;
}

.up {
  color: #ef5350;
}

.down {
  color: #26a69a;
}

.flat {
  color: #9aa0ac;
}

.strategy-panel {
  margin-top: 12px;
  padding: 12px 16px;
  background: #f6fbff;
  border: 1px solid #e3f0fb;
  border-radius: 8px;
}

.strategy-panel__title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.strategy-panel__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.strategy-panel__desc {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}
</style>
