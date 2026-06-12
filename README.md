# CausAI Platform

CausAI Platform 是一个面向数据准备、统计探索、因果发现与语义因果解释的数据分析平台。系统保留了适合数据分析工作台的紧凑页面风格与拖拽式交互，同时将后端拆分为 FastAPI 分层架构，使用 PostgreSQL 持久化用户、数据集、数据版本、分析任务和收藏内容。

## 核心能力

- 用户注册、登录、退出和当前登录态判断。
- CSV、TSV、TXT、JSON、JSONL、Excel 上传，历史数据集管理，当前数据集会话绑定。
- 数据准备：缺失值处理、字段启用/禁用、全局筛选、按列筛选、字段分布查看。
- 统计分析：字段列表、拖拽字段到 X/Y/颜色/大小/透明度参数区、自动绘图、图表类型切换和图表导出。
- 图表类型：散点图、条形图、折线图、箱线图、像素图。
- 数据驱动因果分析：变量选择、背景知识边编辑、PC/GIES 算法运行、因果边表格和因果图展示。
- 语义理解因果分析：变量关系解释、后门调整集、因果效应指标和大模型结果分析。
- 收藏夹：收藏统计图表、因果分析结果和语义分析结果，支持列表查看、快速跳转和删除。

## 技术栈

后端：

- FastAPI：应用入口、API 路由、模板页面和静态资源服务。
- SQLAlchemy 2.x：数据库模型和持久化访问。
- Alembic：数据库迁移。
- PostgreSQL：用户、数据集、版本、任务和收藏数据存储。
- Pydantic v2：请求、响应和算法输入校验。
- Pandas / NumPy / openpyxl / xlrd：多格式数据读取、清洗、统计和图表数据准备。
- causal-learn / gies / networkx：因果发现算法与图结构处理。
- OpenAI SDK 1.x：DeepSeek 兼容接口，用于语义因果能力。

前端：

- Jinja2 HTML 模板承载页面结构。
- 原生 JavaScript 管理页面状态、拖拽交互、接口请求和图表刷新。
- D3.js / ECharts / Plotly 等浏览器端图表库用于数据可视化和因果图展示。
- 全局 CSS 统一导航、表格、按钮、卡片、字段面板和状态提示风格。

## 系统架构

```text
CausAI Platform
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 应用入口
│   │   ├── api/v1/                  # 面向前后端分离场景的标准 REST API
│   │   ├── frontend/legacy.py       # 页面路由与工作台兼容 API
│   │   ├── core/                    # 配置、安全、通用基础设施
│   │   ├── db/                      # 数据库连接、Base、初始化逻辑
│   │   ├── models/                  # SQLAlchemy 数据模型
│   │   ├── schemas/                 # Pydantic 请求/响应模型
│   │   ├── services/                # 认证、数据集、数据处理、算法、大模型服务
│   │   ├── algorithms/              # PC、GIES、效应指标等算法封装
│   │   ├── templates/               # 数据分析工作台页面
│   │   ├── static/                  # CSS、图片、视频和静态前端资源
│   │   └── tests/                   # 后端单元测试
│   ├── alembic/                     # 数据库迁移脚本
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── requirements.txt
├── docker-compose.yml               # 本地 PostgreSQL
├── .env.example                     # 环境变量示例
└── README.md
```

### 后端分层

- `api/v1`：标准 REST API，负责请求参数解析、认证依赖和响应模型。
- `frontend/legacy.py`：服务数据分析工作台页面，提供页面路由和兼容旧页面交互的数据接口。
- `services`：承载业务逻辑，包括多格式数据上传、版本派生、统计计算、图表数据生成、因果任务运行和大模型调用。
- `models`：定义数据库实体，避免业务状态散落在文件或全局变量中。
- `schemas`：对变量列表、背景知识边、图表配置、认证参数等输入进行结构化校验。
- `algorithms`：隔离 PC、GIES、效应估计等算法实现，禁止使用不安全的字符串执行。

### 数据模型

主要数据表：

- `users`：用户账号、邮箱、密码哈希、角色、启用状态和时间戳。
- `datasets`：原始数据集、所属用户、存储路径、行列数和字段信息。
- `dataset_versions`：数据准备或筛选后的派生版本、操作记录、存储路径和字段信息。
- `analysis_jobs`：因果分析任务、算法类型、变量选择、背景知识、任务状态、结果边和结果路径。
- `favorites`：用户收藏的图表、因果结果和语义分析结果。

文件存储：

- 上传文件和分析结果写入 `backend/storage/`。
- 运行产物、缓存和本地环境文件不会进入 Git。
- 数据集与任务按用户和记录隔离，避免多用户覆盖同一个静态结果文件。

### 认证与安全

- 密码使用哈希存储，不保存明文密码。
- 登录态通过服务端签名会话 Cookie 管理。
- 业务接口统一检查当前用户。
- 数据集、数据版本、分析任务和收藏夹都按用户隔离访问。
- 上传文件使用安全文件名和 UUID 存储，限制文件类型和大小。
- DeepSeek API Key 通过环境变量配置，未配置时语义功能返回可理解的未配置状态。

## API 概览

标准 API：

- `POST /api/v1/auth/register`：注册用户。
- `POST /api/v1/auth/login`：登录。
- `POST /api/v1/auth/logout`：退出。
- `POST /api/v1/auth/token/refresh`：外部客户端刷新令牌。
- `GET /api/v1/auth/me`：当前用户。
- `GET /api/v1/datasets/supported-formats`：查询支持的数据文件格式。
- `POST /api/v1/datasets`：上传数据文件。
- `GET /api/v1/datasets`：数据集列表。
- `GET /api/v1/datasets/{id}`：数据集详情。
- `GET /api/v1/dataset-versions/{id}/rows`：数据预览。
- `POST /api/v1/dataset-versions/{id}/prepare`：数据准备。
- `GET /api/v1/dataset-versions/{id}/statistics`：统计信息。
- `GET /api/v1/dataset-versions/{id}/chart-suggestions`：图表推荐。
- `GET /api/v1/dataset-versions/{id}/correlation`：相关矩阵。
- `POST /api/v1/dataset-versions/{id}/groupby`：分组聚合。
- `POST /api/v1/dataset-versions/{id}/tests`：假设检验。
- `GET /api/v1/dataset-versions/{id}/outliers`：异常值检测。
- `POST /api/v1/dataset-versions/{id}/chart-data`：图表数据。
- `POST /api/v1/causal/jobs`：创建因果分析任务。
- `GET /api/v1/causal/jobs/{id}`：查询任务状态。
- `POST /api/v1/causal/jobs/{id}/retry`、`POST /api/v1/causal/jobs/{id}/cancel`：任务重试和取消。
- `GET /api/v1/causal/jobs/{id}/result`：获取因果结果。
- `POST /api/v1/llm/orient-edges`：语义辅助定向。
- `POST /api/v1/llm/backdoor-adjustment`：后门调整集分析。
- `POST /api/v1/llm/analyze-result`：大模型结果解释。
- `GET /api/v1/favorites`、`POST /api/v1/favorites`、`DELETE /api/v1/favorites/{id}`：收藏夹管理。
- `GET /api/v1/workflows`、`POST /api/v1/workflows`、`POST /api/v1/workflows/{id}/run`：可复现分析工作流。

工作台页面接口：

- `/api/upload-history`：历史上传列表。
- `/api/check-upload-status`：当前数据状态。
- `/api/get-statistics`：当前数据字段统计。
- `/api/generate-chart`：根据拖拽参数生成图表数据。
- `/api/plot-data`：字段分布数据。
- `/api/favorites`：收藏夹列表、创建和删除。

## 本地运行

### 1. 启动 PostgreSQL

```bash
docker compose up -d postgres
```

默认数据库连接：

```text
postgresql+psycopg://causai:causai@127.0.0.1:55432/causai
```

### 2. 安装后端依赖

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cd ..
cp .env.example .env
```

生产或共享环境中请修改 `.env` 内的 `JWT_SECRET`、`DATABASE_URL` 和可选的 `DEEPSEEK_API_KEY`。

### 3. 初始化数据库

```bash
cd backend
. .venv/bin/activate
alembic upgrade head
cd ..
```

应用启动时也会执行基础表初始化，推荐开发环境仍使用 Alembic 保持迁移一致。

### 4. 启动应用

```bash
. backend/.venv/bin/activate
uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 18100
```

访问：

```text
http://127.0.0.1:18100/
```

## 页面说明

- `/log-in.html`：登录与注册入口。
- `/index.html`：工作台首页，展示当前数据状态和功能入口。
- `/data-upload.html`：多格式数据上传与历史数据集选择。
- `/data-preparation.html`：缺失值处理、筛选、字段启用和字段分布。
- `/statistical-analysis.html`：字段拖拽、图表生成、导出和收藏。
- `/causal-analysis.html`：变量选择、算法执行、因果图和结果表。
- `/big-model-analysis.html`：语义因果解释、后门调整和效应分析。
- `/favorites.html`：收藏内容管理。
- `/profile.html`：账号信息、系统状态和快捷入口。

## 验证

后端静态检查与测试：

```bash
cd backend
PYTHONPYCACHEPREFIX=/tmp/causai_pycache python -m py_compile $(find app alembic -name '*.py')
pytest
```

手动验证建议：

1. 注册或登录账号。
2. 上传 CSV、TSV、JSONL 或 Excel 并确认进入数据准备页。
3. 检查字段列表、数据表、字段分布和缺失值处理。
4. 在统计分析页拖动字段到 X 轴和 Y 轴，确认图表自动生成。
5. 切换散点图、条形图、折线图、箱线图和像素图，确认图表刷新。
6. 收藏图表，进入收藏夹确认可查看和删除。
7. 进入因果分析页选择变量并运行算法，确认结果图和结果表正常。
8. 进入语义理解因果页，确认无 API Key 时展示未配置提示，有 API Key 时可生成解释。

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `ENVIRONMENT` | 运行环境，例如 `development` 或 `production` |
| `DATABASE_URL` | SQLAlchemy 数据库连接字符串 |
| `JWT_SECRET` | 会话和令牌签名密钥 |
| `JWT_ACCESS_TOKEN_MINUTES` | Access Token 有效分钟数 |
| `JWT_REFRESH_TOKEN_DAYS` | Refresh Token 有效天数 |
| `STORAGE_ROOT` | 上传文件和分析结果存储根目录 |
| `DEEPSEEK_API_KEY` | DeepSeek API Key，未配置时语义功能降级 |
| `DEEPSEEK_BASE_URL` | DeepSeek 兼容 OpenAI API 地址 |
| `DEEPSEEK_MODEL` | 语义分析使用的模型 |
| `ALLOWED_ORIGINS` | CORS 允许来源 |

## 扩展文档

- [API 调用文档](docs/API.md)：面向外部系统和脚本调用，包含认证、数据集、统计图表、因果任务和语义接口。
- [功能扩展设计](docs/FUNCTION_ROADMAP.md)：整理后续可实现的数据分析、协作、报告和因果能力。

## 部署建议

- 使用独立 PostgreSQL 实例，并定期备份数据库和 `STORAGE_ROOT`。
- 使用强随机 `JWT_SECRET`，不要提交真实 `.env`。
- 将上传目录与应用代码目录分离，设置文件大小限制和磁盘监控。
- 通过反向代理提供 HTTPS，并配置安全 Cookie。
- 生产环境建议使用 `uvicorn` worker 或 ASGI 进程管理器，并将静态资源交给 Nginx 等 Web 服务处理。
