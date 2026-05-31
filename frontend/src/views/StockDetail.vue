<template>
  <div>
    <el-page-header @back="goBack" :content="stockCode + ' - ' + stockName + ' K线图'" />
    <el-card style="margin-top: 20px;">
      <div ref="chartRef" style="height: 600px; width: 100%;"></div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import * as echarts from 'echarts'
import api from '../api'

const router = useRouter()
const route = useRoute()
const chartRef = ref(null)
const stockCode = route.params.code
const stockName = ref('')
let chart = null
let allData = []

const goBack = () => {
  router.back()
}

const loadStockInfo = async () => {
  try {
    const res = await api.get(`/stocks/${stockCode}`)
    if (res.code === 0) {
      stockName.value = res.data.name || ''
    }
  } catch (error) {
    console.error(error)
  }
}

const loadKlineData = async () => {
  try {
    const res = await api.get(`/stocks/${stockCode}/kline`)
    if (res.code === 0 && res.data.klines && res.data.klines.length > 0) {
      allData = res.data.klines
      renderChart(allData)
    }
  } catch (error) {
    console.error(error)
  }
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

  chart = echarts.init(chartRef.value)

  const option = {
    title: {
      text: stockCode + ' ' + stockName.value + ' K线图',
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        crossStyle: {
          color: '#999'
        }
      },
      confine: true,
      position: function(point, params, dom, rect, size) {
        const tooltipWidth = 260
        const chartWidth = size.viewSize[0]
        const chartHeight = size.viewSize[1]
        const mouseX = point[0]
        const mouseY = point[1]

        let x
        if (mouseX > chartWidth / 2) {
          x = mouseX - tooltipWidth - 10
        } else {
          x = mouseX + 10
        }

        let y = mouseY - 30
        if (y + 300 > chartHeight) {
          y = chartHeight - 310
        }
        if (y < 10) {
          y = 10
        }

        return [x, y]
      },
      formatter: function(params) {
        if (!params || params.length === 0) return ''
        const date = params[0].axisValue
        const idx = dates.indexOf(date)
        const d = data[idx]
        if (!d) return ''
        let result = `<div style="padding:5px;min-width:200px;"><strong>${date}</strong><br/>`
        result += `<span style="color:#ef5350;">●</span> K线: 开 ${d.open.toFixed(2)} 收 ${d.close.toFixed(2)} 低 ${d.low.toFixed(2)} 高 ${d.high.toFixed(2)}<br/>`
        if (d.ma5 != null) result += `<span style="color:#5470c6;">●</span> MA5: ${d.ma5.toFixed(2)}<br/>`
        if (d.ma10 != null) result += `<span style="color:#91cc75;">●</span> MA10: ${d.ma10.toFixed(2)}<br/>`
        if (d.ma20 != null) result += `<span style="color:#fac858;">●</span> MA20: ${d.ma20.toFixed(2)}<br/>`
        if (d.ma30 != null) result += `<span style="color:#ee6666;">●</span> MA30: ${d.ma30.toFixed(2)}<br/>`
        if (d.ma60 != null) result += `<span style="color:#73c0de;">●</span> MA60: ${d.ma60.toFixed(2)}<br/>`
        if (d.ma120 != null) result += `<span style="color:#3ba272;">●</span> MA120: ${d.ma120.toFixed(2)}<br/>`
        if (d.boll_upper != null) result += `<span style="color:#fc8452;">●</span> 布林上轨: ${d.boll_upper.toFixed(2)}<br/>`
        if (d.boll_mid != null) result += `<span style="color:#9a60b4;">●</span> 布林中轨: ${d.boll_mid.toFixed(2)}<br/>`
        if (d.boll_lower != null) result += `<span style="color:#ea7ccc;">●</span> 布林下轨: ${d.boll_lower.toFixed(2)}<br/>`
        result += `</div>`
        return result
      }
    },
    legend: {
      data: ['K线', 'MA5', 'MA10', 'MA20', 'MA30', 'MA60', 'MA120', '布林上轨', '布林中轨', '布林下轨'],
    },
    grid: {
      left: '10%',
      right: '10%',
      bottom: '15%',
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
        start: 50,
        end: 100,
      },
      {
        start: 50,
        end: 100,
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
            }
          ]
        }
      },
      {
        name: 'MA5',
        type: 'line',
        data: ma5,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 1,
          opacity: 0.8,
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
        name: 'MA20',
        type: 'line',
        data: ma20,
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
        lineStyle: {
          width: 1,
          opacity: 0.8,
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

  chart.setOption(option)

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
                formatter: '最高\n' + maxVal.toFixed(2),
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
                formatter: '最低\n' + minVal.toFixed(2),
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

const handleResize = () => {
  chart && chart.resize && chart.resize()
}

onMounted(async () => {
  await nextTick()
  await loadStockInfo()
  await loadKlineData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (chart) {
    chart.dispose()
    chart = null
  }
})
</script>
