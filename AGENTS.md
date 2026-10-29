# Repository Guidelines

## 项目结构

本项目是基于 FastAPI、SQLite 与 Vue 3 的 A 股选股分析平台。详细架构见 `docs/PROJECT_CONTEXT.md`。

- `backend/app/api/`：路由；`services/`：同步、指标、选股与回测；`models/`：ORM；`utils/`：数据库、限流等公共能力。
- `backend/app/services/strategies/`：选股插件；`backtest/exits/`：回测出场规则。
- `backend/tests/`：测试；`backend/scripts/`：数据修复；`backend/tools/`：诊断工具。
- `frontend/src/views/`：页面；`components/`：共享组件；`api/`：接口封装；`router/`：路由。样式主要随 Vue 组件维护。

## 安装、开发与构建

以下命令供开发者手动执行，前后端分别启动终端：

| 工作目录 | 命令 | 用途 |
| --- | --- | --- |
| `backend/` | `pip install -r requirements.txt` | 安装后端依赖 |
| `backend/` | `python run.py` | 启动后端，默认端口 8001 |
| `frontend/` | `npm install` | 安装前端依赖 |
| `frontend/` | `npm run dev` | 启动 Vite，默认端口 5173 |
| `frontend/` | `npm run build` | 生成生产资源，仅由用户执行 |
| `frontend/` | `npm run preview` | 预览已有构建产物 |

按本机环境选择 `python` 或 `python3`。根目录 `make bk`、`make fe` 使用 Windows 可执行文件名；其他平台使用上述命令。Vite 将 `/api` 代理至后端。

## 代码风格与扩展

Python 使用四空格缩进，函数与模块采用 `snake_case`，类采用 `PascalCase`。Vue、JavaScript 使用两空格缩进，组件采用 `PascalCase.vue`；沿用现有单引号、无分号风格。当前未配置统一格式化或 lint 工具，避免无关格式调整。

新增选股策略复用 `BaseStrategy`、`StrategyMeta` 和 `ParamSpec`，在独立模块导出 `STRATEGY` 实例供自动发现。优先复用现有工具，仅修改任务相关代码。

## 测试与验证

后端使用标准库 `unittest`，文件命名为 `test_*.py`，方法以 `test_` 开头。开发者可在 `backend/` 执行 `python -m unittest discover -s tests -v`。现有腾讯接口可用性测试会访问外网，新增逻辑测试优先使用 `unittest.mock` 隔离网络。

当前没有覆盖率门槛或前端自动化测试配置。策略改动应验证截断数据下的历史信号一致性；界面改动需手动检查相关页面、接口与图表交互。

## 提交与合并请求

历史提交以简短中文描述为主，例如“策略拆分”，未采用固定前缀规范。提交说明应明确改动对象和行为，避免笼统的“优化”。合并请求说明问题、改动范围、验证结果与未验证项；有工单时关联，界面变更附截图。

## 配置与协作约束

- 配置入口为 `backend/app/core/config.py`，支持 `.env`；勿提交密钥、数据库或生成产物。
- SQLite 默认位于 `backend/data/stock.db`；修复数据前备份。后端保持单进程，同步状态存于内存；市值字段与筛选参数统一使用亿元。
- AI 助手修改后仅做静态检查，不运行编译、构建或启动服务，并列出用户需验证的重点。
- Git 默认只读；未经明确要求，不执行提交、切换分支、拉取等改变仓库状态的操作。
