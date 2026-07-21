# A 股选股分析平台 — 项目规则

> 详细上下文见 [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md)，本文件只列开发时最容易踩坑的约束。

## 项目信息
- **项目名称**：A 股选股分析平台
- **部署模式**：单机单用户（无认证、无分布式）
- **项目定位**：面向个人投资者的 A 股数据同步与技术分析平台
- **平台**：代码本身平台无关；仅 `Makefile` 是 Windows 专用（`python.exe` / `npm.cmd`）

## 技术栈
- 前端：Vue 3 + Element Plus + lightweight-charts + Axios + Vite
- 后端：FastAPI + SQLAlchemy + Pandas + Uvicorn
- 数据库：SQLite（`backend/data/stock.db`）
- 数据源：腾讯财经 API（前复权 qfq）

## 核心功能
1. **K 线同步**：拉取前复权 K 线，线程池拉取 + 独立线程攒批 upsert
2. **技术指标**：MA5/10/20/30/60、布林带、MACD（DIF/DEA/MACD 柱，4 位小数，EMA 计算）
3. **K 线图**：lightweight-charts 单 chart 双 pane（主图 K 线+均线+布林带，副图 MACD），时间轴与十字光标原生联动
4. **选股与回测**：4 套策略，支持全市场筛选与单股历史回测
5. **股票管理**：列表搜索/排序、跳过列表、数据清理

## 关键约束

1. **统一响应**：`{ code, msg, data }`，code=0 成功。后端用 `success()` / `error()`；前端拦截器已在 `code !== 0` 时 reject，**业务代码不要再判 `res.code === 0`**。
2. **API 前缀**：`/api/v1`
3. **市值单位一律亿元**：`stock_basic.total_cap` 存亿元，所有市值筛选入参也是亿元，**两边都不要做单位换算**。
4. **空值判断必须用 `is not None` / `!= null`**：MACD、DIF、DEA、`change_pct`、`ytd_change_pct` 的 `0` 是合法值，用真值判断会把 0 变成 null，图上直接断线。
5. **同步状态在内存**：`backend/app/utils/sync_state.py` 的 `sync_status`，后端必须单进程。
6. **腾讯 K 线接口最多返回 `count` 条，超出时从 `end` 往回截断**（早期数据静默丢失，
   且不报错）。拉长区间必须用 `_fetch_kline_paged()` 自 end 向前翻页，
   **不要改回按固定日历窗口切页**；`KLINE_PAGE_SIZE=500` 也不要调大（实测 1000/2000 只回 640，3000+ 回空）。
7. **K 线必须前复权**：除权除息后腾讯会用新因子重算全部历史价，库里旧数据整体失效。
   同步只前推 `SYNC_BUFFER_DAYS`(10 天) 保证有重叠日，再逐日比对收盘价识别漂移，
   **只对真正除权的股票**做全量重拉（`sync.py::_need_full_resync`）。不要改回无差别前推一年。
8. **指标预加载**：在上述缓冲之外再预加载 120 天 close 作为计算上下文（不写库），确保 MA60/MACD 首日即正确。
9. **策略参数由 `ParamSpec` 单一定义**：后端校验、接口元数据、前端表单三者都从它生成。
   不要在 API 层或前端另写一份参数列表。
10. **策略只能读 `STRATEGY_COLUMNS` 里的列**：`services/strategies/common.py` 按列 SELECT，策略拿到的是 Row 不是 ORM 实体。用新字段前先把列加进去。
11. **图表实例不能放进 `ref()`/`reactive()`**：Vue 的 Proxy 会破坏 lightweight-charts 内部实例判等，`seriesData.get(series)` 会取不到值。用普通 `let`。
12. **单用户约束**：不引入分布式方案，不做多租户。

## 核心数据表
- **stock_basic**：股票基本信息（代码、名称、市值(亿元)、PE、PB）
- **stock_kline**：K 线数据（OHLC、成交量、均线、布林带、MACD），`stock_code + trade_date` 联合唯一
- **sync_record**：同步记录
- **strategy_result**：选股运行结果（只保留每个策略最新一次）

## 开发原则
- 新增 API：`app/api/` 加路由 → `app/services/` 加业务 → `main.py` 注册
- 新增指标：`indicator_service` 计算 → `stock_kline` 加字段 → `sync_service` UPSERT → 补算脚本 → `to_dict()` 的 `_FLOAT_FIELDS`
- 新增策略：**只需在 `services/strategies/` 新建一个文件**，继承 `BaseStrategy`、定义 `meta`/`check()`、
  末尾 `STRATEGY = XxxStrategy()`。注册表自动发现，API 与前端零改动（详见 PROJECT_CONTEXT §10.4）
- DB Session：API 层用 `Depends(get_db)`；后台任务用 `with SessionLocal() as db:`
- 全市场遍历务必用批量查询（`load_klines_bulk`），不要逐股 SELECT
- 所有指标与策略仅供学习研究，不构成投资建议
