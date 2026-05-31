# 股票选股系统 - 项目方案与实现文档

> **重要声明：本系统为单机部署、单用户服务，开发时无需考虑多节点、多用户并发问题。**

---

## 一、项目概述

### 1.1 系统定位
一个面向个人投资者的股票数据同步与技术分析系统，核心功能包括：
- 从腾讯财经API同步A股K线数据（前复权）
- 技术指标计算（均线、布林线等）
- K线图可视化（支持TD序列、高低点标记）
- 股票筛选与策略回测（预留）

### 1.2 技术栈
| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Vue 3 + Element Plus + ECharts | SPA单页应用 |
| 后端 | FastAPI (Python) | RESTful API |
| 数据库 | SQLite | 本地文件存储 |
| 数据源 | 腾讯财经API | 免费A股行情数据 |

---

## 二、项目架构

### 2.1 目录结构
```
Stock_selection_system/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── api/               # API路由层
│   │   │   ├── stocks.py      # 股票数据接口
│   │   │   ├── sync.py        # 数据同步接口
│   │   │   └── strategies.py  # 策略接口（预留）
│   │   ├── core/
│   │   │   └── config.py      # 配置管理
│   │   ├── models/            # SQLAlchemy ORM模型
│   │   │   ├── stock.py       # 股票基本信息
│   │   │   ├── stock_kline.py # K线数据
│   │   │   └── sync_record.py # 同步记录
│   │   ├── schemas/           # Pydantic数据校验
│   │   ├── services/          # 业务逻辑层
│   │   │   ├── stock_service.py       # 股票CRUD
│   │   │   ├── sync_service.py        # 数据同步/指标计算
│   │   │   └── indicator_service.py   # 技术指标计算
│   │   └── utils/             # 工具类
│   │       ├── database.py    # 数据库连接
│   │       ├── response.py    # 统一响应格式
│   │       └── skipped_stocks.py  # 跳过股票管理
│   ├── data/                  # SQLite数据库文件
│   ├── tests/                 # 单元测试
│   ├── tools/                 # 维护工具脚本
│   ├── requirements.txt       # Python依赖
│   └── run.py                 # 启动入口
├── frontend/                  # 前端应用
│   ├── src/
│   │   ├── api/
│   │   │   └── index.js       # Axios封装（统一响应拦截）
│   │   ├── router/
│   │   │   └── index.js       # 路由配置
│   │   ├── views/
│   │   │   ├── StockList.vue  # 股票列表页
│   │   │   ├── StockDetail.vue # K线图详情页
│   │   │   └── SyncPage.vue   # 数据同步页
│   │   ├── App.vue
│   │   └── main.js            # 入口（Element Plus中文locale）
│   ├── index.html
│   └── vite.config.js
├── skipped_stocks.csv         # 跳过同步的股票列表（后端根目录）
└── src/                      # 历史遗留代码（废弃）
```

### 2.2 架构分层

```
┌─────────────────────────────────────────┐
│              前端 Vue 3                  │
│  StockList / StockDetail / SyncPage     │
──────────────┬──────────────────────────
               │ HTTP REST API
┌──────────────▼──────────────────────────┐
│           后端 FastAPI                   │
─────────────────────────────────────────┤
│  API路由层 (app/api/)                   │
│  ├─ /api/v1/stocks/*    股票数据接口    │
│  ├─ /api/v1/sync/*      同步管理接口    │
│  └─ /api/v1/strategies/* 策略接口(预留) │
├─────────────────────────────────────────┤
│  业务逻辑层 (app/services/)             │
│  ├─ stock_service.py     股票CRUD       │
│  ├─ sync_service.py      同步/指标计算  │
│  └─ indicator_service.py 技术指标       │
├─────────────────────────────────────────┤
│  数据访问层 (app/models/)               │
│  ├─ StockBasic           股票基本信息   │
│  ├─ StockKline           K线数据        │
│  └─ SyncRecord           同步记录       │
├─────────────────────────────────────────┤
│  数据存储 (SQLite)                      │
│  └─ data/stock.db                       │
└─────────────────────────────────────────┘
```

---

## 三、数据库设计

### 3.1 表结构

#### stock_basic（股票基本信息）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| code | VARCHAR(10) UNIQUE | 股票代码 |
| name | VARCHAR(100) | 股票名称 |
| market | VARCHAR(10) | SSE/SZSE |
| total_cap | DECIMAL(18,2) | 总市值（亿） |
| industry | VARCHAR(100) | 行业 |
| list_date | DATE | 上市日期 |
| is_active | BOOLEAN | 是否活跃 |

#### stock_kline（K线数据）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| stock_code | VARCHAR(10) | 股票代码（外键） |
| trade_date | DATE | 交易日期 |
| open/close/high/low | DECIMAL(10,2) | 开/收/高/低 |
| volume | DECIMAL(18,0) | 成交量 |
| amount | DECIMAL(18,2) | 成交额（万元） |
| ma5/ma10/ma20/ma30/ma60/ma120 | DECIMAL(10,2) | 均线 |
| boll_upper/mid/lower | DECIMAL(10,2) | 布林线 |

#### sync_record（同步记录）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| sync_date | DATE UNIQUE | 同步日期 |
| stock_count | INTEGER | 股票总数 |
| status | VARCHAR(20) | 状态 |
| success_count | INTEGER | 成功数 |
| skipped_count | INTEGER | 跳过数 |
| failed_count | INTEGER | 失败数 |
| no_data_count | INTEGER | 无数据数 |
| failed_stocks | TEXT(JSON) | 失败股票列表 |
| no_data_stocks | TEXT(JSON) | 无数据股票列表 |

---

## 四、API接口规范

### 4.1 统一响应格式

所有接口返回统一JSON结构：
```json
{
  "code": 0,        // 0表示成功，非0表示错误码
  "msg": "描述信息",
  "data": {}        // 业务数据（可选）
}
```

### 4.2 接口清单

#### 股票数据 (/api/v1/stocks)
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /stocks | 分页查询股票列表（支持搜索） |
| GET | /stocks/{code} | 获取单只股票信息 |
| GET | /stocks/{code}/kline | 获取K线数据 |
| DELETE | /stocks/{code}/kline | 清空单只股票K线 |
| DELETE | /stocks/all | 清空所有数据 |

#### 数据同步 (/api/v1/sync)
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /sync/progress | 实时同步进度（轮询用） |
| GET | /sync/history | 上次同步历史记录（查一次） |
| POST | /sync/start | 启动同步任务（start_date、end_date必填） |
| POST | /sync/cancel | 取消同步任务 |
| GET | /sync/skipped-stocks | 获取跳过股票列表 |
| POST | /sync/skipped-stocks/add | 添加跳过股票 |
| POST | /sync/skipped-stocks/remove | 移除跳过股票 |

##### POST /sync/start 请求示例
```json
{
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}
```

#### 策略 (/api/v1/strategies)
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /strategies | 获取策略列表（预留） |
| POST | /strategies/select | 选股（预留） |

---

## 五、前端开发规范

### 5.1 响应数据处理

API拦截器已统一处理 `{ code, msg, data }` 格式，组件内直接使用：

```javascript
// 正确用法
const res = await api.get('/stocks')
stocks.value = res.data.list      // 业务数据在 res.data 中
ElMessage.success(res.msg)        // 消息在 res.msg 中
```

### 5.2 同步页面轮询逻辑

- **历史数据**：`/sync/history` 只在页面加载时调用一次
- **实时进度**：只在同步进行中通过 `/sync/progress` 轮询
- **同步结束**：自动停止轮询，重新加载历史数据
- **禁止混用**：实时数据(`realtimeProgress`)和历史数据(`syncStatus`)严格分离

### 5.3 K线图组件规范

- 使用 ECharts 渲染
- 支持缩放时动态更新最高/最低点标记
- TD序列（高低9）标记逻辑遵循 Tom DeMark 标准
- Tooltip 位置根据鼠标位置自动调整，避免遮挡

---

## 六、后端开发规范

### 6.1 统一响应格式

所有接口使用 `success()` 和 `error()` 函数返回：

```python
from app.utils.response import success, error

@router.get("/example")
async def example():
    return success(data={"key": "value"}, msg="操作成功")
    # 或
    return error(code=1, msg="操作失败")
```

### 6.2 数据库会话管理

- 使用 `with SessionLocal() as db:` 上下文管理器自动关闭会话
- 不要在服务层创建新的 SessionLocal，应通过依赖注入传入
- `get_db` 依赖注入用于 API 层

### 6.3 跳过股票机制

- `skipped_stocks.csv` 为增量操作：添加时重复代码会被覆盖，删除时只移除指定代码
- 同步任务启动时**只读一次** CSV 到内存集合，避免每次循环都读文件
- `is_skipped(code, cached_codes=skipped_codes)` 优先使用传入的缓存集合

### 6.4 同步任务要求

- `start_date` 和 `end_date` 必须同时提供，缺一不可，不接受默认值
- 同步取消时需保存当时的进度到同步记录
- 内存 `sync_status` 变量仅用于单机单用户场景
- 所有变量需在函数最开始初始化，避免作用域问题

---

## 七、部署说明

### 7.1 环境要求
- Python 3.8+
- Node.js 16+
- SQLite（内置）

### 7.2 后端启动
```bash
cd backend
pip install -r requirements.txt
python run.py
```
服务运行在 `http://127.0.0.1:8001`

### 7.3 前端开发
```bash
cd frontend
npm install
npm run dev
```
前端运行在 `http://localhost:5173`，通过 Vite proxy 代理到后端

### 7.4 生产部署
使用 Nginx 静态托管前端 dist 目录，同时代理 `/api/v1` 到后端 8001 端口。

---

## 八、注意事项

### 8.1 单机单用户约束
以下设计基于**单机部署、单用户**前提：
- 内存全局变量 `sync_status` 存储同步状态
- SQLite 作为数据库，不支持高并发写入
- `skipped_stocks.csv` 文件读写不考虑并发锁
- 无用户认证/权限控制

### 8.2 数据源限制
- 腾讯财经API有频率限制，同步时需控制请求间隔（0.3-1.0秒）
- API可能返回不同格式（`qfqday` vs `day`），代码已做兼容
- 科创板(688)、北交所股票需特殊处理

### 8.3 已知限制
- 不支持增量更新（已有数据的股票直接跳过）
- 不支持实时行情推送，仅定时同步
- TD序列算法为简化版，未处理完美/不完美序列

---

## 九、后续开发指南

### 9.1 新增API接口
1. 在 `app/api/` 下创建/修改路由文件
2. 使用 `success()` / `error()` 返回统一格式
3. 在 `app/main.py` 注册路由

### 9.2 新增数据库表
1. 在 `app/models/` 下定义 SQLAlchemy 模型
2. 在 `app/services/` 下实现 CRUD 方法
3. 运行数据库迁移（tools/migrate_db.py）

### 9.3 新增前端页面
1. 在 `frontend/src/views/` 下创建 Vue 组件
2. 在 `frontend/src/router/index.js` 注册路由
3. 使用 `api` 实例调用后端接口

---

*文档最后更新: 2026-05-31*
