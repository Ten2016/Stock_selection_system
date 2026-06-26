# A 股选股分析平台

> ⚠️ **重要声明**：本项目为**纯 Windows 平台**项目，所有脚本、路径、工具均基于 Windows 环境设计与测试，不保证 Linux / macOS 兼容性。

一个面向个人投资者的 A 股数据同步与技术分析平台，支持 K 线图展示、多维度技术指标计算、选股策略筛选。

## ✨ 核心功能

| 功能模块 | 说明 |
|---------|------|
| **数据同步** | 从腾讯财经 API 同步全市场 A 股前复权 K 线数据，支持线程池并发 |
| **技术指标** | MA 均线（5/10/20/30/60/120）、布林带、MACD（DIF/DEA/柱状图） |
| **K 线图** | 基于 ECharts 的交互式 K 线图，支持缩放、高低点标记、TD 序列 |
| **选股策略** | 内置多套选股策略，可自定义参数，一键筛选符合条件的股票 |
| **数据管理** | 支持单股 / 全量数据清理，跳过列表管理，独立补算脚本 |

## 🛠 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 前端框架 | Vue 3 + Vue Router | ^3.4 / ^4.3 |
| UI 组件库 | Element Plus | ^2.6 |
| 图表库 | Apache ECharts | ^5.5 |
| 构建工具 | Vite | ^5.2 |
| 后端框架 | FastAPI | 0.104 |
| ORM | SQLAlchemy | 2.0 |
| 数据处理 | Pandas | 2.1 |
| 数据库 | SQLite | 内置 |
| 数据源 | 腾讯财经 API | 免费行情接口 |

## 🚀 快速开始

### 环境要求

- **操作系统**：Windows 10 / 11
- **Python**：3.8 及以上
- **Node.js**：16 及以上
- **Make**：（可选）推荐安装 MinGW 或 GnuWin32 Make

### 启动方式

**使用 Make：**

```bash
# 启动后端（新开一个终端）
make bk

# 启动前端（新开一个终端）
make fe
```

**手动启动：**

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

### 访问地址

- **前端页面**：http://localhost:5173
- **后端 API**：http://127.0.0.1:8001
- **API 文档**：http://127.0.0.1:8001/docs

### 首次使用

1. 打开前端页面，进入「数据同步」页面
2. 点击「同步基本信息」同步股票基本资料
3. 选择日期范围，点击「开始同步」下载 K 线数据
4. 同步完成后，进入「股票列表」查看和筛选股票
5. 点击「详情」或「K线」查看个股技术分析图表

## 📁 项目结构

```
Stock_selection_system/
├── AGENTS.md                    # AI 开发指引
├── README.md                    # 本文档
├── Makefile                     # 构建脚本（Windows）
├── docs/
│   └── PROJECT_CONTEXT.md       # 完整项目上下文（开发者必读）
├── backend/                     # 后端服务（FastAPI）
│   ├── run.py                   # 启动入口
│   ├── requirements.txt         # Python 依赖
│   ├── skipped_stocks.csv       # 同步跳过列表
│   ├── data/                    # SQLite 数据库目录
│   ├── scripts/                 # 维护脚本（指标补算等）
│   └── app/
│       ├── main.py              # FastAPI 应用入口
│       ├── api/                 # API 路由层
│       ├── core/                # 配置管理
│       ├── models/              # SQLAlchemy ORM 模型
│       ├── schemas/             # Pydantic 数据模型
│       ├── services/            # 业务逻辑层
│       └── utils/               # 工具函数
└── frontend/                    # 前端应用（Vue 3）
    ├── vite.config.js           # Vite 配置
    ├── package.json
    └── src/
        ├── main.js              # 入口文件
        ├── App.vue              # 根组件
        ├── api/                 # API 封装
        ├── router/              # 路由配置
        ├── views/               # 页面组件
        └── components/          # 可复用组件
```

## 📊 技术指标说明

| 指标 | 参数 | 说明 |
|------|------|------|
| MA 均线 | 5/10/20/30/60/120 日 | 简单移动平均线 |
| 布林带 | 20 日，±2 倍标准差 | 基于 MA20 的通道指标 |
| MACD | 12, 26, 9 | 指数平滑异同移动平均线 |

## ⚠️ 注意事项

1. **单机单用户**：本项目为个人使用设计，无用户认证、无分布式支持
2. **数据源限制**：腾讯财经 API 有频率限制，同步已内置节流控制
3. **数据仅供参考**：所有指标与策略仅供学习研究，不构成投资建议
4. **数据库文件**：SQLite 数据库位于 `backend/data/stock.db`，建议定期备份

## 📚 更多文档

- 完整项目上下文与开发指南：[docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md)
- AI 开发指引：[AGENTS.md](AGENTS.md)
