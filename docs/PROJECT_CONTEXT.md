# A 股选股分析平台 — 项目上下文文档

> **用途**：供开发者与 AI 助手快速理解仓库全貌，作为持久上下文参与后续开发。
> **最后更新**：2026-06-26
> **相关文档**：[`README.md`](../../README.md)（快速上手）、[`AGENTS.md`](../../AGENTS.md)（AI 开发指引）

---

## 1. 项目概览

| 维度 | 说明 |
|------|------|
| **定位** | 面向个人投资者的 A 股数据同步与技术分析平台 |
| **平台** | ⚠️ **纯 Windows 项目**，所有脚本、路径、工具均基于 Windows 设计 |
| **部署模式** | **单机、单用户** — 无认证、无多租户、无分布式 |
| **核心能力** | 腾讯财经 API 同步 K 线（前复权）、技术指标计算、ECharts K 线图、选股策略筛选 |
| **后端入口** | `http://127.0.0.1:8001`（`backend/run.py`） |
| **前端入口** | `http://localhost:5173`（Vite dev，代理 `/api` → 8001） |
| **数据库** | SQLite：`backend/data/stock.db`（git 忽略，首次启动自动创建） |

### 1.1 设计约束（开发时必须遵守）

1. **同步状态**存于内存全局变量 `sync_status`（`backend/app/api/sync.py`），仅适用于单进程单用户。
2. **SQLite** 不适合高并发写入；K 线同步已用批量写入（50 条一批）缓解锁竞争。
3. **跳过列表** `backend/skipped_stocks.csv` 无文件锁，同步启动时一次性读入内存。
4. **数据源** 腾讯 API 有频率限制；并发线程池 `max_workers=10`，请求间隔 50–150ms。
5. K 线同步 **必须** 同时提供 `start_date` 与 `end_date`，后端不接受默认值。
6. **路径风格**：统一使用 Windows 路径（反斜杠），脚本均为 PowerShell / Python 兼容。

---

## 2. 技术栈

| 层级 | 技术 | 版本参考 |
|------|------|----------|
| 前端框架 | Vue 3 + Vue Router | ^3.4 / ^4.3 |
| UI 组件 | Element Plus | ^2.6 |
| 图表 | Apache ECharts | ^5.5 |
| HTTP 客户端 | Axios | ^1.6 |
| 构建工具 | Vite | ^5.2 |
| 后端框架 | FastAPI | 0.104 |
| ORM | SQLAlchemy | 2.0 |
| 数据处理 | Pandas | 2.1 |
| 运行时 | Uvicorn | 0.24 |
| 数据库 | SQLite | 内置 |
| 外部数据 | 腾讯财经 API | `qt.gtimg.cn` / `web.ifzq.gtimg.cn` |

---

## 3. 仓库结构

```
Stock_selection_system/
├── AGENTS.md                    # AI 开发入口（指向本文档）
├── README.md                    # 项目门面（快速上手）
├── Makefile                     # 构建脚本（make bk / make fe）
├── docs/
│   └── PROJECT_CONTEXT.md       # 本文档
├── backend/                     # 后端服务
│   ├── run.py                   # uvicorn 启动入口（reload 模式）
│   ├── requirements.txt
│   ├── skipped_stocks.csv       # 同步跳过列表 {code,name}
│   ├── kill_backend.ps1         # Windows 杀后端进程脚本
│   ├── data/                    # SQLite 数据库目录（gitignore）
│   ├── app/
│   │   ├── main.py              # FastAPI 应用、路由注册、CORS
│   │   ├── api/                 # HTTP 路由层
│   │   │   ├── stocks.py        # 股票与 K 线 CRUD
│   │   │   ├── sync.py          # 同步任务、进度、跳过列表
│   │   │   └── strategies.py    # 选股策略
│   │   ├── core/
│   │   │   └── config.py        # Settings（pydantic-settings）
│   │   ├── models/              # SQLAlchemy ORM
│   │   ├── schemas/             # Pydantic schema
│   │   ├── services/            # 业务逻辑
│   │   └── utils/               # 数据库、响应、启动检查等
│   ├── scripts/                 # 一次性维护脚本（指标补算等）
│   ├── tools/                   # 调试与迁移工具
│   └── tests/                   # pytest 测试
└── frontend/                    # 前端应用
    ├── vite.config.js           # dev server + API 代理
    ├── package.json
    └── src/
        ├── main.js              # Vue 入口 + Element Plus 中文 locale
        ├── App.vue              # 布局：侧栏菜单 + router-view
        ├── api/index.js         # Axios 实例 + 策略/同步 API
        ├── router/index.js      # 路由表
        ├── views/               # 页面级组件
        └── components/          # 可复用组件（K 线图弹窗）
```

---

## 4. 系统架构

### 4.1 分层架构

```mermaid
flowchart TB
    subgraph Frontend["前端 Vue 3 SPA"]
        SL[StockList 股票列表]
        SD[StockDetail 个股详情]
        SP[SyncPage 数据同步]
        ST[Strategy 选股策略]
        KC[KlineChartDialog K线图弹窗]
    end

    subgraph Backend["后端 FastAPI"]
        API["API 路由层 app/api/"]
        SVC["业务层 app/services/"]
        ORM["ORM app/models/"]
    end

    subgraph External["外部"]
        TENCENT["腾讯财经 API"]
    end

    subgraph Storage["本地存储"]
        DB[(SQLite stock.db)]
        CSV[skipped_stocks.csv]
    end

    SL & SD & SP & ST --> API
    KC --> API
    API --> SVC
    SVC --> ORM
    ORM --> DB
    SVC --> TENCENT
    SVC --> CSV
```

### 4.2 请求与响应约定

**统一 JSON 格式**（前后端全局约定）：

```json
{
  "code": 0,
  "msg": "success",
  "data": { ... }
}
```

- `code === 0` 表示成功；非 0 为业务错误。
- 后端：`app/utils/response.py` 的 `success()` / `error()`。
- 前端：`frontend/src/api/index.js` 拦截器在 `code !== 0` 时 `ElMessage.error` 并 reject。
- 组件内使用：`const res = await api.get(...)` → `res.data` 为业务数据，`res.msg` 为消息。

### 4.3 配置项

`backend/app/core/config.py`（可通过 `.env` 覆盖）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `sqlite:///./data/stock.db` | 相对 backend 目录 |
| `API_V1_PREFIX` | `/api/v1` | 所有业务 API 前缀 |
| `HOST` | `127.0.0.1` | 后端监听地址 |
| `PORT` | `8001` | 后端端口 |

---

## 5. 数据模型

ORM 定义在 `backend/app/models/`，`init_db()` 通过 `Base.metadata.create_all` 建表。新增字段通过独立脚本 `ALTER TABLE` 升级。

### 5.1 `stock_basic` — 股票基本信息

| 字段 | 说明 |
|------|------|
| `code` | 股票代码（唯一） |
| `name` | 名称 |
| `market` | `SSE` / `SZSE` |
| `total_cap` | 总市值（亿元） |
| `industry`, `list_date` | 行业、上市日期 |
| `pe_ratio`, `pe_ratio_static`, `pb_ratio` | 市盈率、静态市盈率、市净率 |
| `ytd_change_pct` | 今年涨跌幅 |
| `is_active` | 是否活跃 |

### 5.2 `stock_kline` — K 线数据

| 字段分类 | 字段 | 说明 |
|---------|------|------|
| 基础 | `stock_code`, `trade_date` | 联合唯一索引 |
| 行情 | `open/high/low/close` | OHLC（前复权） |
| 成交 | `volume`, `amount` | 成交量、成交额（万元） |
| 涨跌 | `amplitude`, `change_pct`, `turnover_rate` | 振幅、涨跌幅、换手率 |
| 均线 | `ma5/10/20/30/60/120` | 简单移动平均线 |
| 布林带 | `boll_upper/mid/lower` | 20 日 MA ± 2 倍标准差 |
| MACD | `dif`, `dea`, `macd` | DIF、DEA、MACD 柱状图（2*(DIF-DEA)） |
| 分红 | `dividend_info` | JSON，除权除息信息 |

> **注意**：`ma120` 字段存在于数据库中，但当前同步流程的 `calculate_all_indicators` 未计算 ma120，以实际代码为准。

### 5.3 `sync_record` — 同步记录

记录每次同步的日期、状态、成功/跳过/失败/无数据计数及失败列表（JSON）。

### 5.4 `strategy` / `selection_result` — 策略元数据

`Strategy` 表定义策略配置；`SelectionResult` 关联策略的信号记录。当前选股结果主要存于 `strategy_result`。

### 5.5 `strategy_result` — 选股运行结果

| 字段 | 说明 |
|------|------|
| `strategy_name` | 策略标识 |
| `run_date` | 运行日期 |
| `params` | JSON 运行参数 |
| `total_count` | 命中数量 |
| `results` | JSON 选股结果列表 |

每次成功运行会 **删除该策略旧结果**，只保留最新一次。

---

## 6. API 接口清单

前缀：`/api/v1`

### 6.1 股票 `/stocks`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/stocks` | 分页列表；`search`, `min_market_cap`, `sort_by`, `sort_order` |
| GET | `/stocks/{code}` | 单只股票详情 |
| GET | `/stocks/{code}/kline` | K 线；可选 `start_date`, `end_date` |
| DELETE | `/stocks/{code}/kline` | 清空单股 K 线 |
| DELETE | `/stocks/all` | 清空全部 basic + kline |

### 6.2 同步 `/sync`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/sync/progress` | **轮询**实时进度（同步进行中） |
| GET | `/sync/history` | **一次性**上次同步历史 + 有 K 线股票总数 |
| POST | `/sync/start` | 启动 K 线同步；body: `{start_date, end_date}` |
| POST | `/sync/start-recent-days` | 同步近约 10 个交易日 |
| POST | `/sync/sync-basic-info` | 仅同步基本信息（市值、PE 等） |
| POST | `/sync/cancel` | 取消当前同步 |
| POST | `/sync/repair-indicators` | 重算所有股票的全部技术指标 |
| GET | `/sync/skipped-stocks` | 跳过列表 |
| POST | `/sync/skipped-stocks/add` | 批量添加；body: `{stocks: [{code,name}]}` |
| POST | `/sync/skipped-stocks/remove` | 移除；body: `{code}` |

**前端轮询约定**（`SyncPage.vue`）：

- `syncStatus` ← `/sync/history`（页面加载 + 同步结束后刷新）
- `realtimeProgress` ← `/sync/progress`（仅 `syncing` 时轮询）
- 两者 **不可混用**

### 6.3 策略 `/strategies`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/strategies` | 可用策略列表 |
| GET | `/strategies/latest-result` | 某策略最新结果；`strategy_name` 必填 |
| POST | `/strategies/select` | 运行选股；query: `strategy_name`, `min_market_cap`, `x_days`, `y_days`, `z_days`, `y_pct` |

---

## 7. 核心业务逻辑

### 7.1 数据同步流程（K 线）

```mermaid
sequenceDiagram
    participant UI as SyncPage
    participant API as sync.py
    participant Pool as ThreadPoolExecutor
    participant SVC as sync_service
    participant TX as 腾讯 API
    participant DB as SQLite

    UI->>API: POST /sync/start
    API->>API: background_tasks.run_sync_task
    API-->>UI: 任务已启动

    loop 轮询
        UI->>API: GET /sync/progress
        API-->>UI: sync_status
    end

    Note over API: 加载股票列表，过滤 0/3/6 开头且市值≥100亿
    Note over API: 预加载 sync 开始前 120 天历史 close（指标上下文）
    Pool->>SVC: fetch_one_stock_history（每股）
    SVC->>TX: fqkline/get（前复权 qfq）
    SVC->>SVC: calculate_all_indicators
    Pool-->>API: 批量结果
    API->>DB: save_kline_data（每 50 股一批）
    API->>DB: create_sync_record
```

**关键实现位置**：

- 任务编排：`backend/app/api/sync.py` → `run_sync_task()`
- 拉取与落库：`backend/app/services/sync_service.py`
- 指标计算：`backend/app/services/indicator_service.py`

**同步筛选规则**（`run_sync_task`）：

- 仅 `0/3/6` 开头 A 股
- `total_cap >= 100`（亿元）
- 按市值降序处理
- `skipped_stocks.csv` 中的代码跳过

**指标预加载机制**：

- 增量同步时，为了保证 MA60 / MACD 等指标的正确性，会预加载同步开始日期前 **120 个自然日**的历史 close 价格
- 与新拉取的数据合并后统一计算指标，再只写入新日期范围的数据

### 7.2 基本信息同步

`sync_service.run_basic_info_sync()`：批量请求 `qt.gtimg.cn`，解析沪市（600/601/603/605/688）与深市（000/001/002/003/300/301）代码，更新 `stock_basic`。

### 7.3 技术指标

`indicator_service.calculate_all_indicators(df)`：

| 指标 | 计算方式 | 精度 |
|------|---------|------|
| MA5/10/20/30/60 | 简单移动平均 | 2 位小数 |
| 布林带 | 基于 MA20，±2 倍标准差 | 2 位小数 |
| MACD (DIF/DEA/MACD) | EMA(12) - EMA(26) / signal EMA(9) / 2*(DIF-DEA) | 4 位小数 |

### 7.4 选股策略

定义于 `backend/app/services/strategy_service.py`：

| 标识 | 名称 | 逻辑摘要 |
|------|------|----------|
| `consecutive_ma5` | 跌破布林下轨后连续站上 5 日线 | 近 x 天内找跌破下轨日 → 之后 y 天内连续 z 天 close ≥ MA5 |
| `rise_then_fall` | 大涨后连续下跌 | 近 x 天内找涨幅 > y% 日 → 之后连续 z 天收盘价下跌 |
| `above_ma60` | 站上 60 日线策略 | 价格在 60 日均线之上运行 |

`run_strategy()` 遍历 `stock_basic`（可选市值过滤），逐股查 K 线并匹配；超时较长的请求前端设为 300s。

### 7.5 启动预检查

后端启动时（`main.py` → `on_event("startup")` → `init_db()`）执行：

| 步骤 | 说明 | 成本 |
|------|------|------|
| 1. 确保数据库目录存在 | 检查 `data/` 目录，不存在则创建 | 极低 |
| 2. `Base.metadata.create_all` | 基于 ORM 模型建表（IF NOT EXISTS） | 低 |
| 3. 表状态统计 | 查询 6 张核心表的存在性和行数，打印报告 | 低 |

> **历史**：早期版本还有 schema 修复（dividend_info 字段、唯一索引、重复行清理），随着项目稳定已移除。相关历史逻辑可在 git 记录中追溯。

---

## 8. 前端结构

### 8.1 路由

| 路径 | 组件 | 功能 |
|------|------|------|
| `/` | `StockList.vue` | 股票列表、搜索、排序、清空数据 |
| `/stock/:code` | `StockDetail.vue` | 个股详情页（K线 + 指标） |
| `/sync` | `SyncPage.vue` | 数据同步控制与进度 |
| `/strategy` | `Strategy.vue` | 选股策略运行与结果展示 |

### 8.2 关键组件

**`KlineChartDialog.vue`** — K 线图核心组件（弹窗模式）：

- ECharts 双 Grid 布局
  - **主图**（上）：蜡烛图 + MA 均线 + 布林带 + TD 序列标记
  - **副图**（下）：MACD（DIF 白线 + DEA 黄线 + 红绿柱状图）
- 缩放时动态更新最高/最低点标记
- 鼠标 hover 时副图左上角实时显示 MACD 当前值
- 支持展示选股策略命中信息（`strategyResult` prop）
- 十字光标跨图联动

**`StockDetail.vue`** — 个股详情页 K 线：

- 与 KlineChartDialog 相同的双图布局
- 右侧信息栏显示开高低收、成交量、均线、布林带、MACD 等

### 8.3 API 封装

`frontend/src/api/index.js`：

- 默认 `baseURL: '/api/v1'`
- 导出：`getStrategies`, `selectStocks`, `getLatestStrategyResult`, `syncBasicInfo`
- 其余接口通过默认 `api` 实例直接调用
- Axios 拦截器统一处理 `{code, msg, data}` 响应格式

---

## 9. 开发与运维

### 9.1 本地启动

**使用 Make：**

```bash
# 后端
make bk

# 前端（新开终端）
make fe
```

**手动：**

```bash
# 后端
cd backend
pip install -r requirements.txt
python run.py

# 前端
cd frontend
npm install
npm run dev
```

### 9.2 数据库初始化

首次启动后端时 `main.py` 的 `on_startup` 会自动调用 `init_db()`，创建所有表。无需手动操作。

### 9.3 维护脚本

| 路径 | 用途 |
|------|------|
| `backend/scripts/repair_macd.py` | 独立补算 MACD 指标（自动建字段 + 全量重算） |
| `backend/scripts/migrate_add_stock_fields.py` | 股票表字段迁移 |
| `backend/scripts/migrate_create_strategy_result.py` | 创建 strategy_result 表 |
| `backend/scripts/recalculate_indicators.py` | 重算指标 |
| `backend/scripts/repair_jsonish_data.py` | 修复 JSON 格式数据 |
| `backend/tools/migrate_db.py` | 通用迁移工具 |
| `backend/tools/backfill_ma30_ma120.py` | 回填 MA30/MA120 |
| `backend/tools/check_db.py` | 数据库检查 |
| `backend/tools/check_api_response.py` | API 响应调试 |

> 也可以通过 API `/sync/repair-indicators` 触发全量指标重算（需启动后端服务）。

### 9.4 测试

```bash
cd backend
pytest tests/
```

现有测试：`test_sync_service.py`, `test_kline_format.py`

### 9.5 生产部署建议

- 前端：`npm run build` → Nginx 托管 `dist`
- Nginx 将 `/api/v1` 反向代理到 `127.0.0.1:8001`
- 后端单进程运行（与 `sync_status` 内存状态一致）
- 数据库文件定期备份

---

## 10. 代码规范与扩展指南

### 10.1 新增 API

1. 在 `backend/app/api/` 添加路由函数
2. 业务逻辑放 `backend/app/services/`
3. 使用 `success()` / `error()` 返回
4. 在 `backend/app/main.py` 注册 `include_router`
5. 前端在 `api/index.js` 或页面内调用

### 10.2 新增数据库表 / 字段

**新表**：
1. `backend/app/models/` 定义模型
2. 在 `models/__init__.py` 导出
3. `services/` 实现 CRUD
4. `init_db()` 会自动 `create_all`

**新字段**：
1. 在模型定义中添加字段
2. 编写独立 `ALTER TABLE` 脚本（放 `scripts/`）
3. 同步更新 `KLINE_UPSERT_SQL` 和 `_df_to_rows()`
4. 更新 `indicator_service.calculate_all_indicators()`（如为指标字段）
5. 更新 `to_dict()` 方法

### 10.3 新增技术指标

1. `indicator_service.py` 新增计算函数
2. `calculate_all_indicators()` 中调用，生成新列
3. `stock_kline.py` 模型新增字段 + `to_dict()`
4. `sync_service.py` 的 UPSERT SQL 和 _df_to_rows 新增字段
5. `KlineData` schema 补充字段
6. 编写独立补算脚本（放 `scripts/`）
7. 前端 KlineChartDialog 和 StockDetail 同步展示

### 10.4 新增选股策略

1. 在 `strategy_service.py` 实现 `check_strategy_*` 函数
2. 在 `run_strategy_for_stock()` 注册策略名分支
3. 在 `get_available_strategies()` 注册元数据
4. 前端 `Strategy.vue` 添加参数表单项（如需要）

### 10.5 新增前端页面

1. `frontend/src/views/` 创建 Vue 组件
2. `router/index.js` 注册路由
3. `App.vue` 侧栏添加菜单项

### 10.6 数据库会话

- API 层：`Depends(get_db)` 注入 `Session`
- 后台任务 / 线程：使用 `with SessionLocal() as db:`
- 服务层接收 `db` 参数，不自行创建 Session

---

## 11. 已知限制与注意事项

| 类别 | 说明 |
|------|------|
| 平台 | 纯 Windows，不保证 Linux/macOS 兼容 |
| 并发 | 单用户；`sync_status` 非持久化 |
| 数据源 | 腾讯 API 限流；可能返回 `qfqday` 或 `day` 字段 |
| 特殊板块 | 科创板 688、北交所需额外关注 API 兼容性 |
| 增量同步 | 当前逻辑对时间段内数据抓取后 upsert |
| TD 序列 | K 线图中的 TD 为简化实现 |
| MA120 | 数据库有字段，但当前同步流程未计算 |
| 认证 | 无用户系统 |
| 投资建议 | 所有指标与策略仅供学习研究，不构成投资建议 |

---

## 12. 模块依赖关系速查

```
main.py
  ├── api/stocks.py      → stock_service
  ├── api/sync.py        → sync_service, stock_service, skipped_stocks
  └── api/strategies.py  → strategy_service, StrategyResult model

sync_service.py
  ├── indicator_service（指标计算：MA/布林带/MACD）
  ├── StockBasic, StockKline, SyncRecord
  └── 腾讯财经 API

strategy_service.py
  ├── StockBasic, StockKline
  └── check_strategy_* 纯函数

stock_service.py
  └── StockBasic, StockKline（查询与清理）

indicator_service.py
  └── pandas（纯计算，无副作用）
```

---

## 13. 文档维护

更新代码后，若涉及以下变更请同步更新本文档：

- 新增/删除 API 路由或请求参数
- 数据库表结构变更
- 新增选股策略或同步流程调整
- 前端路由或核心页面职责变化
- 部署方式或环境变量变更
- 新增/删除维护脚本
- 技术指标体系变化
