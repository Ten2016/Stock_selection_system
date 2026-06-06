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
            <div style="margin-bottom: 8px;" v-if="currentData.change_pct != null">
              <span :style="{color: currentData.change_pct >= 0 ? '#ef5350' : '#26a69a'}">●</span> 涨跌幅: {{ toFixed(currentData.change_pct) }}%
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
            <div v-if="currentData.ma120 != null" style="margin-bottom: 8px;">
              <span style="color:#3ba272;">●</span> MA120: {{ toFixed(currentData.ma120) }}
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
  const tdBuy = []
  const tdSell = []
  let buyCount = 0
  let sellCount = 0

  for (let i = 4; i < data.length; i++) {
    const curr = data[i]
    const prev4 = data[i - 4]

    if (curr.close > prev4.close) {
      sellCount++
      buyCount = 0
    } else if (curr.close < prev4.close) {
      buyCount++
      sellCount = 0
    } else {
      buyCount = 0
      sellCount = 0
    }

    if (buyCount > 0 && buyCount <= 9) {
      tdBuy.push({
        coord: [data[i].trade_date, data[i].low],
        value: buyCount,
        dataIndex: i
      })
    }

    if (sellCount > 0 && sellCount <= 9) {
      tdSell.push({
        coord: [data[i].trade_date, data[i].high],
        value: sellCount,
        dataIndex: i
      })
    }
  }

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
  const ma120 = data.map(item => item.ma120)
  const bollUpper = data.map(item => item.boll_upper)
  const bollMid = data.map(item => item.boll_mid)
  const bollLower = data.map(item => item.boll_lower)

  const { tdBuy, tdSell } = calcTDSequential(data)
  
  const strategyMarkPoints = []
  if (props.strategyResult) {
    // consecutive_ma5 策略：跌破布林下轨 + 站上5日线
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
    
    // rise_then_fall 策略：大涨 + 连续下跌
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

  chart = echarts.init(chartRef.value)

  const option = {
    animation: true,
    animationDuration: 300,
    animationDurationUpdate: 300,
    animationEasing: 'cubicOut',
    animationEasingUpdate: 'cubicOut',
    title: {
      text: props.stockCode + ' ' + stockName.value + ' K线图',
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        crossStyle: {
          color: '#999'
        }
      },
      show: false
    },
    legend: {
      data: ['K线', 'MA5', 'MA10', 'MA30', 'MA60', 'MA120', '布林上轨', '布林中轨', '布林下轨'],
    },
    grid: {
      left: '80',
      right: '60',
      bottom: '60',
      top: '60',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: { onZero: false },
      splitLine: { show: false },
      min: 'dataMin',
      max: 'dataMax',
    },
    yAxis: {
      scale: true,
      splitArea: {
        show: true,
      },
    },

    dataZoom: [
      {
        type: 'inside',
        start: 0,
        end: 100,
      },
      {
        type: 'slider',
        show: false,
      },
    ],

    series: [
      {
        name: 'K线',
        type: 'candlestick',
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
              type: 'max',
              name: '最高价',
              label: {
                formatter: '最高\n{c}',
                fontSize: 10,
              },
              itemStyle: {
                color: '#ef5350',
              }
            },
            {
              type: 'min',
              name: '最低价',
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
        data: ma5,
        smooth: true,
        symbol: 'none',
        animation: true,
        animationDuration: 300,
        animationDurationUpdate: 300,
        animationEasing: 'cubicOut',
        animationEasingUpdate: 'cubicOut',
        lineStyle: {
          width: 3,
          color: '#000',
          opacity: 1,
        },
      },
      {
        name: 'MA10',
        type: 'line',
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
        data: ma60,
        smooth: true,
        symbol: 'none',
        animation: true,
        animationDuration: 300,
        animationDurationUpdate: 300,
        animationEasing: 'cubicOut',
        animationEasingUpdate: 'cubicOut',
        lineStyle: {
          width: 2,
          color: '#ff6b6b',
          opacity: 1,
        },
      },
      {
        name: 'MA120',
        type: 'line',
        data: ma120,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 1,
          opacity: 0.8,
        },
      },
      {
        name: '布林上轨',
        type: 'line',
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
    ],
  }

  chart.setOption(option, true)

  if (data.length > 0) {
    const latestData = data[data.length - 1]
    currentDate.value = latestData.trade_date
    currentData.value = latestData
  }

  chart.getZr().on('mousemove', (event) => {
    const pointInPixel = [event.offsetX, event.offsetY]
    const pointInGrid = chart.convertFromPixel('grid', pointInPixel)
    
    if (pointInGrid && pointInGrid[0] != null) {
      const idx = Math.round(pointInGrid[0])
      if (idx >= 0 && idx < data.length) {
        const d = data[idx]
        currentDate.value = d.trade_date
        currentData.value = d
      }
    }
  })

  chart.on('dataZoom', () => {
    if (!chart) return
    const opt = chart.getOption()
    const start = opt.dataZoom[0].start / 100
    const end = opt.dataZoom[0].end / 100
    const startIdx = Math.floor(start * data.length)
    const endIdx = Math.ceil(end * data.length)
    const visibleData = data.slice(startIdx, endIdx)

    if (visibleData.length === 0) return

    let maxVal = -Infinity
    let minVal = Infinity
    let maxIdx = 0
    let minIdx = 0

    visibleData.forEach((item, idx) => {
      if (item.high > maxVal) {
        maxVal = item.high
        maxIdx = idx
      }
      if (item.low < minVal) {
        minVal = item.low
        minIdx = idx
      }
    })

    chart.setOption({
      series: [{
        markPoint: {
          data: [
            {
              coord: [visibleData[maxIdx].trade_date, maxVal],
              name: '最高价',
              label: {
                formatter: '最高\n' + toFixed(maxVal),
                fontSize: 10,
              },
              itemStyle: {
                color: '#ef5350',
              }
            },
            {
              coord: [visibleData[minIdx].trade_date, minVal],
              name: '最低价',
              label: {
                formatter: '最低\n' + toFixed(minVal),
                fontSize: 10,
              },
              itemStyle: {
                color: '#26a69a',
              }
            }
          ]
        }
      }]
    })
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
