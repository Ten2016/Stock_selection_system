# A 股选股分析平台 — 项目规则

## 项目信息
- **项目名称**：A 股选股分析平台
- **绝对路径**：h:\gitCode\Stock_selection_system
- **运行平台**：Windows 10（纯 Windows 项目，路径使用反斜杠）
- **部署模式**：单机单用户（无认证、无分布式）
- **项目定位**：面向个人投资者的 A 股数据同步与技术分析平台

## 技术栈
- 前端：Vue 3 + Element Plus + ECharts + Axios + Vite
- 后端：FastAPI + SQLAlchemy + Pandas + Uvicorn
- 数据库：SQLite（backend/data/stock.db）
- 数据源：腾讯财经 API（前复权 qfq）

## 核心功能
1. **K 线同步**：从腾讯 API 拉取前复权 K 线，批量写入 SQLite
2. **技术指标**：MA5/10/20/30/60、布林带、MACD（DIF/DEA/MACD柱，4位小数，EMA计算）
3. **K 线图**：ECharts 双 Grid（主图 K线+均线+布林带，副图 MACD），十字光标联动
5. **股票管理**：列表搜索/排序、单股详情、跳过列表、数据清理


## 关键约束
1. **统一响应**：`{ code, msg, data }`，code=0 成功；后端 success()/error()，前端拦截器已处理
2. **同步状态内存存储**：sync_status 存于 backend/app/api/sync.py 内存变量
3. **API 前缀**：/api/v1
6. **K 线必须前复权**：与实盘一致，除权除息后需重拉历史数据
7. **指标预加载**：增量同步前预加载 120 天历史数据，确保 MA60/MACD 正确
8. **单用户约束**：不引入分布式方案，不做多租户

## 核心数据表
- **stock_basic**：股票基本信息（代码、名称、市值、PE、PB、行业）
- **stock_kline**：K 线数据（OHLC、成交量、均线、布林带、MACD），stock_code + trade_date 联合唯一
- **sync_record**：同步记录
- **strategy_result**：选股运行结果

## 开发原则
- 新增 API：app/api/ 加路由 → app/services/ 加业务 → main.py 注册
- 新增指标：indicator_service 计算 → stock_kline 加字段 → sync_service UPSERT → 补算脚本
- 新增策略：strategy_service 实现 check 函数 → 注册到 run_strategy_for_stock
- DB Session：API 层用 Depends(get_db)；后台任务用 with SessionLocal() as db:
- 所有指标与策略仅供学习研究，不构成投资建议
