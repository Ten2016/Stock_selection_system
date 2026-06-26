# AGENTS.md — AI 开发指引

> ⚠️ **重要声明**：本项目为**纯 Windows 平台**项目，所有脚本、路径、工具均基于 Windows 环境设计。

本仓库为 **单机单用户** A 股选股分析平台（FastAPI + Vue 3 + SQLite）。

## 必读文档

完整项目上下文见 **[docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md)**，包含架构、数据模型、API、业务逻辑与扩展指南。

## 开发前牢记

1. **单用户约束**：同步状态在 `backend/app/api/sync.py` 的内存变量 `sync_status` 中，勿引入分布式方案。
2. **统一响应**：`{ code, msg, data }`；后端 `success()/error()`，前端 Axios 拦截器已处理。
3. **同步 API 分离**：`/sync/history`（历史，查一次）与 `/sync/progress`（轮询，仅同步中）不可混用。
4. **工作目录**：后端命令在 `backend/` 下执行；数据库路径相对 `backend/data/stock.db`。
5. **Windows 平台**：路径使用反斜杠，脚本为 PowerShell / Python 兼容，不保证 Linux/macOS 可用。

## 快速启动

```bash
# 后端
make bk

# 前端（新开终端）
make fe
```

## 关键路径

| 用途 | 路径 |
|------|------|
| API 路由 | `backend/app/api/` |
| 业务逻辑 | `backend/app/services/` |
| ORM 模型 | `backend/app/models/` |
| 工具函数 | `backend/app/utils/` |
| 指标计算 | `backend/app/services/indicator_service.py` |
| 策略服务 | `backend/app/services/strategy_service.py` |
| 前端页面 | `frontend/src/views/` |
| K 线图组件 | `frontend/src/components/KlineChartDialog.vue` |
| 个股详情页 | `frontend/src/views/StockDetail.vue` |
| 跳过列表 | `backend/skipped_stocks.csv` |
| 维护脚本 | `backend/scripts/` |
