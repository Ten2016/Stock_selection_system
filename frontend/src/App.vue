<template>
  <el-container style="height: 100vh;">
    <el-header style="background: #409EFF; color: #fff; padding: 0 20px;">
      <h2>Stock Selection System</h2>
    </el-header>
    <el-container>
      <el-aside width="200px" style="background: #f0f2f5;">
        <el-menu
          :default-active="activeMenu"
          router
          style="border-right: 0;"
        >
          <el-menu-item index="/">股票列表</el-menu-item>
          <el-menu-item index="/strategy">选股策略</el-menu-item>
          <el-menu-item index="/sync">数据同步</el-menu-item>
        </el-menu>
      </el-aside>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeMenu = computed(() => route.path)
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}
html, body, #app {
  height: 100%;
}
</style>
