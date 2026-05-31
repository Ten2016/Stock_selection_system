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
          <el-select v-model="form.strategy" placeholder="请选择策略" style="width: 300px;">
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
          <template #default="{ row }">
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
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewStock(row)">查看K线</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-empty v-else-if="hasRun" description="没有符合条件的股票" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getStrategies, selectStocks } from '../api'

const router = useRouter()

const strategies = ref([])
const loading = ref(false)
const hasRun = ref(false)
const results = ref([])
const totalCount = ref(0)
const form = ref({
  strategy: '',
  minMarketCap: null,
  xDays: 30,
  yDays: 10,
  zDays: 2
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

onMounted(async () => {
  try {
    const res = await getStrategies()
    strategies.value = res.data
    if (strategies.value.length > 0) {
      form.value.strategy = strategies.value[0].name
    }
  } catch (error) {
    console.error(error)
  }
})

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
      form.value.zDays
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
  router.push({
    path: `/stock/${row.code}`,
    query: {
      strategyResult: JSON.stringify(row.result)
    }
  })
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
