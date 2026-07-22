<template>
  <el-dialog
    :model-value="visible"
    :title="`${stockCode} ${stockName}`"
    width="92%"
    top="4vh"
    destroy-on-close
    @update:model-value="$emit('update:visible', $event)"
  >
    <!-- 图表本体在 KlineChartPanel，本组件只负责弹窗外壳。
         destroy-on-close + v-if 保证每次打开都是全新实例，图表生命周期由面板自理。 -->
    <KlineChartPanel
      v-if="visible && stockCode"
      :stock-code="stockCode"
      :strategy-result="strategyResult"
      :backtest-signals="backtestSignals"
      :trades="trades"
      @loaded="stockName = $event.name"
    />
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import KlineChartPanel from './KlineChartPanel.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  stockCode: { type: String, default: '' },
  strategyResult: { type: Object, default: null },
  backtestSignals: { type: Array, default: () => [] },
  trades: { type: Array, default: () => [] },
})

defineEmits(['update:visible'])

// 股票名由面板加载完成后回传，用于弹窗标题
const stockName = ref('')
watch(() => props.stockCode, () => { stockName.value = '' })
</script>
