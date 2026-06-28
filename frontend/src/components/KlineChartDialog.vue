<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="stockCode + ' - ' + stockName + ' K线图'"
    width="80%"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div style="display: flex;">
      <div style="flex: 1; margin-right: 10px;">
        <el-card style="margin-bottom: 10px;">
          <div ref="chartRef" style="height: 600px; width: 100%;"></div>
        </el-card>
        <!-- 股票基本信息 -->
        <el-card v-if="stockBasicInfo">
          <template #header>
            <span style="font-weight: bold;">{{ stockCode }} {{ stockName }} 基本信息</span>
          </template>
          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
            <div>
              <div style="color: #909399; font-size: 12px; margin-bottom: 4px;">总市值</div>
              <div style="font-size: 16px; font-weight: bold;">{{ stockBasicInfo.total_cap ? stockBasicInfo.total_cap.toFixed(2) + ' 亿' : '-' }}</div>
            </div>
            <div>
              <div style="color: #909399; font-size: 12px; margin-bottom: 4px;">动态市盈率 (TTM)</div>
              <div style="font-size: 16px; font-weight: bold;">{{ stockBasicInfo.pe_ratio ? stockBasicInfo.pe_ratio.toFixed(2) : '-' }}</div>
            </div>
            <div>
              <div style="color: #909399; font-size: 12px; margin-bottom: 4px;">静态市盈率</div>
              <div style="font-size: 16px; font-weight: bold;">{{ stockBasicInfo.pe_ratio_static ? stockBasicInfo.pe_ratio_static.toFixed(2) : '-' }}</div>
            </div>
            <div>
              <div style="color: #909399; font-size: 12px; margin-bottom: 4px;">市净率</div>
              <div style="font-size: 16px; font-weight: bold;">{{ stockBasicInfo.pb_ratio ? stockBasicInfo.pb_ratio.toFixed(2) : '-' }}</div>
            </div>
            <div>
              <div style="color: #909399; font-size: 12px; margin-bottom: 4px;">今年涨跌幅</div>
              <div v-if="stockBasicInfo.ytd_change_pct != null" :style="{fontSize: '16px', fontWeight: 'bold', color: stockBasicInfo.ytd_change_pct >= 0 ? '#ef5350' : '#26a69a'}">
                {{ stockBasicInfo.ytd_change_pct.toFixed(2) }}%
              </div>
              <div v-else style="font-size: 16px; font-weight: bold;">-</div>
            </div>
            <div>
              <div style="color: #909399; font-size: 12px; margin-bottom: 4px;">行业</div>
              <div style="font-size: 16px; font-weight: bold;">{{ stockBasicInfo.industry || '-' }}</div>
            </div>
          </div>
        </el-card>
      </div>
      <el-card style="width: 280px;">
        <div style="padding: 10px;">
          <div v-if="strategyResult" style="margin-bottom: 15px; padding: 10px; background: #e6f7ff; border: 1px solid #91d5ff; border-radius: 4px;">
            <h4 style="margin: 0 0 8px 0; font-size: 14px; color: #1890ff;">
              🎯 {{ strategyResult.strategy }}
            </h4>
            <!-- consecutive_ma5 策略信息 -->
            <div v-if="strategyResult.breakdown_date" style="margin-bottom: 8px;">
              <el-tag size="small" type="warning">
                跌破：{{ strategyResult.breakdown_date }}
              </el-tag>
            </div>
            <div v-if="strategyResult.matching_dates && strategyResult.matching_dates.length >= 2" style="margin-bottom: 8px;">
              <el-tag size="small" type="success" style="margin-right: 4px;">
                {{ strategyResult.matching_dates[0] }}
              </el-tag>
              <el-tag size="small" type="success">
                {{ strategyResult.matching_dates[1] }}
              </el-tag>
            </div>
            <div v-if="strategyResult.details && strategyResult.breakdown_close" style="margin-top: 8px; font-size: 12px; color: #606266;">
              <div>跌破日: 收{{ toFixed(strategyResult.breakdown_close) }} / 下轨{{ toFixed(strategyResult.boll_lower) }}</div>
              <div style="margin-top: 4px;" v-if="strategyResult.details.day1_close">第一天: 收{{ toFixed(strategyResult.details.day1_close) }} / MA5{{ toFixed(strategyResult.details.day1_ma5) }}</div>
              <div style="margin-top: 4px;" v-if="strategyResult.details.day2_close">第二天: 收{{ toFixed(strategyResult.details.day2_close) }} / MA5{{ toFixed(strategyResult.details.day2_ma5) }}</div>
            </div>
            
            <!-- rise_then_fall 策略信息 -->
            <div v-if="strategyResult.rise_date" style="margin-bottom: 8px;">
              <el-tag size="small" type="danger">
                大涨：{{ strategyResult.rise_date }} ({{ strategyResult.rise_pct }}%)
              </el-tag>
            </div>
            <div v-if="strategyResult.falling_dates && strategyResult.falling_dates.length > 0" style="margin-bottom: 8px;">
              <el-tag size="small" type="info" style="margin-right: 4px;" v-for="(date, idx) in strategyResult.falling_dates" :key="idx">
                {{ date }}
              </el-tag>
            </div>
            <div v-if="strategyResult.details && strategyResult.rise_close" style="margin-top: 8px; font-size: 12px; color: #606266;">
              <div>大涨日: 收{{ toFixed(strategyResult.rise_close) }}</div>
              <div style="margin-top: 4px;" v-for="(date, idx) in strategyResult.falling_dates" :key="idx">
                跌{{ idx + 1 }}: 收{{ toFixed(strategyResult.details['fall_day' + (idx + 1) + '_close']) }}
              </div>
            </div>
          </div>
          <h4 style="margin: 0 0 15px 0; font-size: 16px;">{{ currentDate }}</h4>
          <div v-if="currentData">
            <div style="margin-bottom: 8px;">
              <span style="color:#ef5350;">●</span> 开盘: {{ toFixed(currentData.open) }}
            </div>
            <div style="margin-bottom: 8px;">
              <span style="color:#ef5350;">●</span> 收盘: {{ toFixed(currentData.close) }}
            </div>
            <div style="margin-bottom: 8px;">
              <span :style="{color: (currentData.change_pct != null ? currentData.change_pct : 0) >= 0 ? '#ef5350' : '#26a69a'}">●</span> 涨跌幅: {{ toFixed(currentData.change_pct != null ? currentData.change_pct : 0) }}%
            </div>
            <div style="margin-bottom: 8px;">
              <span style="color:#ef5350;">●</span> 最高: {{ toFixed(currentData.high) }}
            </div>
            <div style="margin-bottom: 8px;">
              <span style="color:#ef5350;">●</span> 最低: {{ toFixed(currentData.low) }}
            </div>
            <div style="margin-top: 12px; padding-top: 8px; border-top: 1px solid #eee;"></div>
            <div v-if="currentData.ma5 != null" style="margin-bottom: 8px;">
              <span style="color:#000;">●</span> MA5: {{ toFixed(currentData.ma5) }}
            </div>
            <div v-if="currentData.ma10 != null" style="margin-bottom: 8px;">
              <span style="color:#91cc75;">●</span> MA10: {{ toFixed(currentData.ma10) }}
            </div>
            <div v-if="currentData.ma30 != null" style="margin-bottom: 8px;">
              <span style="color:#ee6666;">●</span> MA30: {{ toFixed(currentData.ma30) }}
            </div>
            <div v-if="currentData.ma60 != null" style="margin-bottom: 8px;">
              <span style="color:#ff6b6b;">●</span> MA60: {{ toFixed(currentData.ma60) }}
            </div>
            <div style="margin-top: 12px; padding-top: 8px; border-top: 1px solid #eee;"></div>
            <div v-if="currentData.boll_upper != null" style="margin-bottom: 8px;">
              <span style="color:#fc8452;">●</span> 布林上轨: {{ toFixed(currentData.boll_upper) }}
            </div>
            <div v-if="currentData.boll_mid != null" style="margin-bottom: 8px;">
              <span style="color:#9a60b4;">●</span> 布林中轨: {{ toFixed(currentData.boll_mid) }}
            </div>
            <div v-if="currentData.boll_lower != null" style="margin-bottom: 8px;">
              <span style="color:#ea7ccc;">●</span> 布林下轨: {{ toFixed(currentData.boll_lower) }}
            </div>
            <div style="margin-top: 12px; padding-top: 8px; border-top: 1px solid #eee;"></div>
            <div style="margin-bottom: 8px; font-weight: bold; font-size: 13px;">MACD (12,26,9)</div>
            <div v-if="currentData.dif != null" style="margin-bottom: 8px;">
              <span style="color:#1890ff;">●</span> DIF: {{ toFixed(currentData.dif, 4) }}
            </div>
            <div v-if="currentData.dea != null" style="margin-bottom: 8px;">
              <span style="color:#fa8c16;">●</span> DEA: {{ toFixed(currentData.dea, 4) }}
            </div>
            <div v-if="currentData.macd != null" style="margin-bottom: 8px;">
              <span :style="{color: currentData.macd >= 0 ? '#ef5350' : '#26a69a'}">●</span>
              MACD: {{ toFixed(currentData.macd, 4) }}
            </div>
          </div>
        </div>
      </el-card>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch, nextTick, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import api from '../api'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  stockCode: {
    type: String,
    default: ''
  },
  strategyResult: {
    type: Object,
    default: null
  },
  backtestSignals: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:visible'])

const chartRef = ref(null)
const stockName = ref('')
const stockBasicInfo = ref(null)
const currentDate = ref('')
const currentData = ref(null)
let chart = null
let allData = []

const toFixed = (num, digits = 2) => {
  if (num == null) return '-'
  const n = Number(num)
  if (isNaN(n)) return '-'
  return n.toFixed(digits)
}

const calcTDSequential = (data) => {
  const buySequences = []
  const sellSequences = []
  let buyCount = 0
  let sellCount = 0
  let currentBuySeq = []
  let currentSellSeq = []

  for (let i = 4; i < data.length; i++) {
    const curr = data[i]
    const prev4 = data[i - 4]

    if (curr.close > prev4.close) {
      if (buyCount > 0) {
        buySequences.push(currentBuySeq)
        currentBuySeq = []
        buyCount = 0
      }
      sellCount++
      currentSellSeq.push({
        coord: [data[i].trade_date, data[i].high],
        value: sellCount,
        dataIndex: i
      })
    } else if (curr.close < prev4.close) {
      if (sellCount > 0) {
        sellSequences.push(currentSellSeq)
        currentSellSeq = []
        sellCount = 0
      }
      buyCount++
      currentBuySeq.push({
        coord: [data[i].trade_date, data[i].low],
        value: buyCount,
        dataIndex: i
      })
    } else {
      if (buyCount > 0) {
        buySequences.push(currentBuySeq)
        currentBuySeq = []
        buyCount = 0
      }
      if (sellCount > 0) {
        sellSequences.push(currentSellSeq)
        currentSellSeq = []
        sellCount = 0
      }
    }

    if (sellCount >= 9) {
      sellSequences.push(currentSellSeq)
      currentSellSeq = []
      sellCount = 0
    }
    if (buyCount >= 9) {
      buySequences.push(currentBuySeq)
      currentBuySeq = []
      buyCount = 0
    }
  }

  if (currentBuySeq.length > 0) {
    buySequences.push(currentBuySeq)
  }
  if (currentSellSeq.length > 0) {
    sellSequences.push(currentSellSeq)
  }

  const tdBuy = []
  const tdSell = []

  buySequences.forEach((seq, idx) => {
    const isLast = idx === buySequences.length - 1
    if (isLast || seq.length >= 8) {
      tdBuy.push(...seq)
    }
  })

  sellSequences.forEach((seq, idx) => {
    const isLast = idx === sellSequences.length - 1
    if (isLast || seq.length >= 8) {
      tdSell.push(...seq)
    }
  })

  return { tdBuy, tdSell }
}

const renderChart = (data) => {
  if (chart) {
    chart.dispose()
    chart = null
  }

  if (!chartRef.value) return

  const dates = data.map(item => item.trade_date)
  const values = data.map(item => [
    item.open, item.close, item.low, item.high
  ])
  const ma5 = data.map(item => item.ma5)
  const ma10 = data.map(item => item.ma10)
  const ma20 = data.map(item => item.ma20)
  const ma30 = data.map(item => item.ma30)
  const ma60 = data.map(item => item.ma60)
  const bollUpper = data.map(item => item.boll_upper)
  const bollMid = data.map(item => item.boll_mid)
  const bollLower = data.map(item => item.boll_lower)
  const difData = data.map(item => item.dif)
  const deaData = data.map(item => item.dea)
  const macdData = data.map(item => item.macd)

  const { tdBuy, tdSell } = calcTDSequential(data)
  
  const strategyMarkPoints = []
  if (props.strategyResult) {
    if (props.strategyResult.breakdown_date) {
      const item = data.find(d => d.trade_date === props.strategyResult.breakdown_date)
      if (item) {
        strategyMarkPoints.push({
          coord: [props.strategyResult.breakdown_date, item.low],
          name: '跌破布林下轨',
          symbol: 'pin',
          symbolSize: 20,
          label: {
            show: true,
            formatter: '跌破',
            position: 'inside',
            fontSize: 10,
            color: '#fff',
            fontWeight: 'bold',
          },
          itemStyle: {
            color: '#faad14',
          }
        })
      }
    }
    
    if (props.strategyResult.matching_dates && Array.isArray(props.strategyResult.matching_dates)) {
      props.strategyResult.matching_dates.forEach((date, idx) => {
        const item = data.find(d => d.trade_date === date)
        if (item) {
          strategyMarkPoints.push({
            coord: [date, item.high],
            name: '站上5日线',
            symbol: 'pin',
            symbolSize: 20,
            label: {
              show: true,
              formatter: `${idx + 1}`,
              position: 'inside',
              fontSize: 10,
              color: '#fff',
              fontWeight: 'bold',
            },
            itemStyle: {
              color: '#52c41a',
            }
          })
        }
      })
    }
    
    if (props.strategyResult.rise_date) {
      const item = data.find(d => d.trade_date === props.strategyResult.rise_date)
      if (item) {
        strategyMarkPoints.push({
          coord: [props.strategyResult.rise_date, item.high],
          name: '大涨',
          symbol: 'pin',
          symbolSize: 20,
          label: {
            show: true,
            formatter: '涨',
            position: 'inside',
            fontSize: 10,
            color: '#fff',
            fontWeight: 'bold',
          },
          itemStyle: {
            color: '#f5222d',
          }
        })
      }
    }
    
    if (props.strategyResult.falling_dates && Array.isArray(props.strategyResult.falling_dates)) {
      props.strategyResult.falling_dates.forEach((date, idx) => {
        const item = data.find(d => d.trade_date === date)
        if (item) {
          strategyMarkPoints.push({
            coord: [date, item.low],
            name: '下跌',
            symbol: 'pin',
            symbolSize: 20,
            label: {
              show: true,
              formatter: `${idx + 1}`,
              position: 'inside',
              fontSize: 10,
              color: '#fff',
              fontWeight: 'bold',
            },
            itemStyle: {
              color: '#26a69a',
            }
          })
        }
      })
    }
  }

  // 回测信号标记
  if (props.backtestSignals && props.backtestSignals.length > 0) {
    props.backtestSignals.forEach((signal, idx) => {
      const item = data.find(d => d.trade_date === signal.date)
      if (item) {
        strategyMarkPoints.push({
          coord: [signal.date, item.low],
          name: '买点' + (idx + 1),
          symbol: 'triangle',
          symbolSize: 14,
          symbolRotate: 180,
          label: {
            show: true,
            formatter: '买',
            position: 'bottom',
            fontSize: 11,
            color: '#eb2f96',
            fontWeight: 'bold',
          },
          itemStyle: {
            color: '#eb2f96',
          }
        })
      }
    })
  }

  chart = echarts.init(chartRef.value)

  const defaultShowCount = 200
  const totalBars = data.length
  const dataZoomStart = totalBars > defaultShowCount ? ((totalBars - defaultShowCount) / totalBars) * 100 : 0

  // 计算指定索引范围内的最高/最低点
  const calcExtremeInRange = (startIdx, endIdx) => {
    let maxPrice = -Infinity
    let maxDate = ''
    let minPrice = Infinity
    let minDate = ''
    for (let i = Math.max(0, startIdx); i <= Math.min(data.length - 1, endIdx); i++) {
      const item = data[i]
      if (item.high > maxPrice) {
        maxPrice = item.high
        maxDate = item.trade_date
      }
      if (item.low < minPrice) {
        minPrice = item.low
        minDate = item.trade_date
      }
    }
    return { maxDate, maxPrice, minDate, minPrice }
  }

  // 初始显示范围的最高/最低点
  const initialStart = Math.floor(dataZoomStart / 100 * totalBars)
  const initialEnd = totalBars - 1
  const { maxDate: initMaxDate, maxPrice: initMaxPrice, minDate: initMinDate, minPrice: initMinPrice } = calcExtremeInRange(initialStart, initialEnd)

  const latestMacd = data.length > 0 ? data[data.length - 1] : null

  const option = {
    animation: true,
    animationDuration: 300,
    animationDurationUpdate: 300,
    animationEasing: 'cubicOut',
    animationEasingUpdate: 'cubicOut',
    title: {
      text: props.stockCode + ' ' + stockName.value + ' K线图',
      left: 0,
      top: 0,
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        link: [{ xAxisIndex: 'all' }],
        lineStyle: {
          color: '#999',
          width: 1,
          type: 'dashed',
        },
        crossStyle: {
          color: '#999',
          width: 1,
          type: 'dashed',
        }
      },
      show: true,
      showContent: false,
    },
    legend: {
      data: ['K线', 'MA5', 'MA10', 'MA30', 'MA60', '布林上轨', '布林中轨', '布林下轨', 'DIF', 'DEA', 'MACD'],
      top: 25,
    },
    axisPointer: {
      link: [{ xAxisIndex: 'all' }],
      lineStyle: {
        color: '#999',
        width: 1,
        type: 'dashed',
      },
      crossStyle: {
        color: '#999',
        width: 1,
        type: 'dashed',
      }
    },
    grid: [
      {
        left: '80',
        right: '60',
        top: '70',
        height: '55%',
        containLabel: true,
      },
      {
        left: '80',
        right: '60',
        top: '72%',
        height: '18%',
        containLabel: true,
      }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        boundaryGap: false,
        axisLine: { onZero: false },
        splitLine: { show: false },
        min: 'dataMin',
        max: 'dataMax',
        gridIndex: 0,
        axisLabel: { show: false },
      },
      {
        type: 'category',
        data: dates,
        boundaryGap: false,
        axisLine: { onZero: false },
        splitLine: { show: false },
        min: 'dataMin',
        max: 'dataMax',
        gridIndex: 1,
        axisLabel: { show: true, fontSize: 10 },
      }
    ],
    yAxis: [
      {
        scale: true,
        gridIndex: 0,
        splitArea: {
          show: true,
        },
      },
      {
        scale: true,
        gridIndex: 1,
        splitArea: {
          show: false,
        },
        axisLabel: { fontSize: 10 },
      }
    ],

    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: dataZoomStart,
        end: 100,
      },
      {
        type: 'slider',
        xAxisIndex: [0, 1],
        show: false,
      },
    ],

    series: [
      {
        name: 'K线',
        type: 'candlestick',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: values,
        itemStyle: {
          color: '#ef5350',
          color0: '#26a69a',
          borderColor: '#ef5350',
          borderColor0: '#26a69a',
        },
        markPoint: {
          data: [
            {
              coord: [initMaxDate, initMaxPrice],
              name: '最高价',
              value: initMaxPrice,
              label: {
                formatter: '最高\n{c}',
                fontSize: 10,
              },
              itemStyle: {
                color: '#ef5350',
              }
            },
            {
              coord: [initMinDate, initMinPrice],
              name: '最低价',
              value: initMinPrice,
              label: {
                formatter: '最低\n{c}',
                fontSize: 10,
              },
              itemStyle: {
                color: '#26a69a',
              }
            },
            ...strategyMarkPoints
          ]
        }
      },
      {
        name: 'MA5',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: ma5,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 1,
          color: '#000',
          opacity: 0.8,
        },
      },
      {
        name: 'MA10',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: ma10,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 1,
          opacity: 0.8,
        },
      },

      {
        name: 'MA30',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: ma30,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 1,
          opacity: 0.8,
        },
      },
      {
        name: 'MA60',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: ma60,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 2,
          color: '#ff6b6b',
          opacity: 1,
        },
      },
      {
        name: '布林上轨',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: bollUpper,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 2,
          type: 'dashed',
          color: '#fc8452',
          opacity: 0.9,
        },
      },
      {
        name: '布林中轨',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: bollMid,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 2,
          type: 'dotted',
          color: '#9a60b4',
          opacity: 0.9,
        },
      },
      {
        name: '布林下轨',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: bollLower,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 2,
          type: 'dashed',
          color: '#ea7ccc',
          opacity: 0.9,
        },
      },
      {
        name: 'TD买9',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: tdBuy.map(item => ({
          value: [item.coord[0], item.coord[1]],
          label: {
            show: true,
            formatter: item.value === 9 ? '低9' : item.value.toString(),
            position: 'bottom',
            fontSize: item.value === 9 ? 18 : 14,
            color: item.value === 9 ? '#ff0000' : '#00b894',
            fontWeight: item.value === 9 ? 'bold' : 'bold',
            backgroundColor: item.value === 9 ? '#fff3cd' : 'transparent',
            padding: item.value === 9 ? [3, 6] : 0,
            borderRadius: item.value === 9 ? 4 : 0,
          }
        })),
        symbol: 'circle',
        symbolSize: 1,
        itemStyle: {
          color: 'transparent',
        },
      },
      {
        name: 'TD卖9',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: tdSell.map(item => ({
          value: [item.coord[0], item.coord[1]],
          label: {
            show: true,
            formatter: item.value === 9 ? '高9' : item.value.toString(),
            position: 'top',
            fontSize: item.value === 9 ? 18 : 14,
            color: item.value === 9 ? '#ff0000' : '#e17055',
            fontWeight: item.value === 9 ? 'bold' : 'bold',
            backgroundColor: item.value === 9 ? '#fff3cd' : 'transparent',
            padding: item.value === 9 ? [3, 6] : 0,
            borderRadius: item.value === 9 ? 4 : 0,
          }
        })),
        symbol: 'circle',
        symbolSize: 1,
        itemStyle: {
          color: 'transparent',
        },
      },
      {
        name: 'DIF',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: difData,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 1.5,
          color: '#1890ff',
        },
      },
      {
        name: 'DEA',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: deaData,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 1.5,
          color: '#fa8c16',
        },
      },
      {
        name: 'MACD',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: macdData.map((val, idx) => ({
          value: val,
          itemStyle: {
            color: val != null && val >= 0 ? '#ef5350' : '#26a69a',
          }
        })),
        barWidth: '25%',
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: {
            color: '#666',
            width: 1,
            type: 'solid',
          },
          data: [
            { yAxis: 0 }
          ]
        }
      },
    ],
    graphic: [
      {
        type: 'text',
        left: 80,
        top: '72%',
        style: {
          text: 'MACD(12,26,9)  ',
          fontSize: 12,
          fill: '#333',
          fontWeight: 'bold',
        },
        z: 100,
      },
      {
        type: 'text',
        left: 80 + 85,
        top: '72%',
        style: {
          text: latestMacd && latestMacd.macd != null ? `MACD:${latestMacd.macd.toFixed(4)}  ` : '',
          fontSize: 12,
          fill: latestMacd && latestMacd.macd != null && latestMacd.macd >= 0 ? '#ef5350' : '#26a69a',
        },
        z: 100,
      },
      {
        type: 'text',
        left: 80 + 175,
        top: '72%',
        style: {
          text: latestMacd && latestMacd.dif != null ? `DIF:${latestMacd.dif.toFixed(4)}  ` : '',
          fontSize: 12,
          fill: '#1890ff',
        },
        z: 100,
      },
      {
        type: 'text',
        left: 80 + 250,
        top: '72%',
        style: {
          text: latestMacd && latestMacd.dea != null ? `DEA:${latestMacd.dea.toFixed(4)}` : '',
          fontSize: 12,
          fill: '#fa8c16',
        },
        z: 100,
      }
    ]
  }

  chart.setOption(option, true)

  if (data.length > 0) {
    const latestData = data[data.length - 1]
    currentDate.value = latestData.trade_date
    currentData.value = latestData
  }

  // dataZoom时更新最高/最低点标记
  chart.on('dataZoom', () => {
    const opt = chart.getOption()
    const start = opt.dataZoom[0].start
    const end = opt.dataZoom[0].end
    const startIdx = Math.floor(start / 100 * totalBars)
    const endIdx = Math.floor(end / 100 * totalBars) - 1
    const { maxDate, maxPrice, minDate, minPrice } = calcExtremeInRange(startIdx, endIdx)

    chart.setOption({
      series: [{
        name: 'K线',
        markPoint: {
          data: [
            { coord: [maxDate, maxPrice], value: maxPrice, name: '最高价', label: { formatter: '最高\n{c}', fontSize: 10 }, itemStyle: { color: '#ef5350' } },
            { coord: [minDate, minPrice], value: minPrice, name: '最低价', label: { formatter: '最低\n{c}', fontSize: 10 }, itemStyle: { color: '#26a69a' } },
            ...strategyMarkPoints
          ]
        }
      }]
    })
  })

  chart.getZr().on('mousemove', (event) => {
    const pointInPixel = [event.offsetX, event.offsetY]
    const pointInGrid = chart.convertFromPixel({ xAxisIndex: 0, yAxisIndex: 0 }, pointInPixel)
    
    if (pointInGrid && pointInGrid[0] != null) {
      const idx = Math.round(pointInGrid[0])
      if (idx >= 0 && idx < data.length) {
        const d = data[idx]
        currentDate.value = d.trade_date
        currentData.value = d

        if (d.dif != null && d.dea != null && d.macd != null) {
          chart.setOption({
            graphic: [
              {
                left: 80,
                top: '72%',
                style: { text: 'MACD(12,26,9)  ' }
              },
              {
                left: 80 + 85,
                top: '72%',
                style: { 
                  text: `MACD:${d.macd.toFixed(4)}  `,
                  fill: d.macd >= 0 ? '#ef5350' : '#26a69a',
                }
              },
              {
                left: 80 + 175,
                top: '72%',
                style: { 
                  text: `DIF:${d.dif.toFixed(4)}  `,
                  fill: '#1890ff',
                }
              },
              {
                left: 80 + 250,
                top: '72%',
                style: { 
                  text: `DEA:${d.dea.toFixed(4)}`,
                  fill: '#fa8c16',
                }
              }
            ]
          })
        }
      }
    }
  })
}

const loadStockInfo = async () => {
  try {
    const res = await api.get(`/stocks/${props.stockCode}`)
    if (res.code === 0) {
      stockName.value = res.data.name || ''
      stockBasicInfo.value = res.data
    }
  } catch (error) {
    console.error(error)
  }
}

const loadKlineData = async () => {
  try {
    const res = await api.get(`/stocks/${props.stockCode}/kline`)
    if (res.code === 0 && res.data.klines && res.data.klines.length > 0) {
      allData = res.data.klines
      await nextTick()
      renderChart(allData)
    }
  } catch (error) {
    console.error(error)
  }
}

const handleClose = () => {
  if (chart) {
    chart.dispose()
    chart = null
  }
  stockName.value = ''
  stockBasicInfo.value = null
  currentDate.value = ''
  currentData.value = null
  allData = []
}

const handleResize = () => {
  chart && chart.resize && chart.resize()
}

watch(() => props.visible, async (newVal) => {
  if (newVal && props.stockCode) {
    await nextTick()
    await loadStockInfo()
    await loadKlineData()
    window.addEventListener('resize', handleResize)
  } else {
    window.removeEventListener('resize', handleResize)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (chart) {
    chart.dispose()
    chart = null
  }
})
</script>
