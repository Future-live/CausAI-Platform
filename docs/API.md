# CausAI Platform API

本文档面向需要通过程序调用 CausAI Platform 的外部系统、脚本和自动化任务。所有标准接口默认以 `/api/v1` 为前缀。

## 认证方式

系统支持两种认证方式：

1. 浏览器页面使用 HttpOnly Cookie。
2. 外部调用方使用 Bearer Token。

登录后响应体会返回 `access_token` 和 `refresh_token`，同时也会写入 Cookie。

### 注册

```http
POST /api/v1/auth/register
Content-Type: application/json
```

```json
{
  "username": "analyst",
  "email": "analyst@example.com",
  "password": "strong-password"
}
```

### 登录

```http
POST /api/v1/auth/login
Content-Type: application/json
```

```json
{
  "username": "analyst",
  "password": "strong-password"
}
```

响应：

```json
{
  "user": {
    "id": "uuid",
    "username": "analyst",
    "email": "analyst@example.com",
    "role": "user"
  },
  "access_token": "jwt-access-token",
  "refresh_token": "jwt-refresh-token",
  "token_type": "bearer"
}
```

后续请求：

```http
Authorization: Bearer <access_token>
```

### 刷新令牌

```http
POST /api/v1/auth/refresh
```

浏览器调用会读取 refresh Cookie。外部调用方可以使用请求体刷新：

```http
POST /api/v1/auth/token/refresh
Content-Type: application/json
```

```json
{
  "refresh_token": "jwt-refresh-token"
}
```

## 支持的数据文件

查询系统支持的文件类型：

```http
GET /api/v1/datasets/supported-formats
```

当前支持：

- `.csv`：逗号分隔文本。
- `.tsv`：制表符分隔文本。
- `.txt`：常见分隔文本，自动尝试识别分隔符。
- `.json`：JSON 数组或对象结构。
- `.jsonl`：每行一个 JSON 对象。
- `.xlsx`：Excel 工作簿，读取第一个 Sheet。
- `.xls`：旧版 Excel 工作簿，读取第一个 Sheet。

内部准备、筛选后的派生版本会统一保存为 CSV，保证统计、图表和因果算法链路稳定。

## 推荐调用流程

```text
注册/登录
  -> 上传数据集
  -> 获取 latest_version.id
  -> 预览行数据与字段信息
  -> 数据准备/筛选/字段启用
  -> 统计信息或图表数据
  -> 创建因果分析任务
  -> 查询任务状态
  -> 获取因果结果
  -> 语义解释或效应分析
```

## 数据集接口

### 上传数据集

```http
POST /api/v1/datasets
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

字段：

- `file`：数据文件，支持 CSV、TSV、TXT、JSON、JSONL、XLSX、XLS。

响应：

```json
{
  "id": "dataset-id",
  "original_filename": "sample.xlsx",
  "row_count": 4177,
  "column_count": 8,
  "columns": [
    {
      "name": "Length",
      "dtype": "float64",
      "analysis_type": "measure",
      "semantic_type": "numeric",
      "enabled": true,
      "missing_count": 0,
      "unique_count": 134
    }
  ],
  "latest_version": {
    "id": "version-id",
    "dataset_id": "dataset-id",
    "kind": "original",
    "row_count": 4177,
    "columns": [],
    "created_at": "2026-06-12T10:00:00"
  },
  "created_at": "2026-06-12T10:00:00"
}
```

### 数据集列表

```http
GET /api/v1/datasets
Authorization: Bearer <access_token>
```

### 数据集详情

```http
GET /api/v1/datasets/{dataset_id}
Authorization: Bearer <access_token>
```

### 数据预览

```http
GET /api/v1/dataset-versions/{version_id}/rows?limit=100&offset=0
Authorization: Bearer <access_token>
```

## 数据准备接口

### 缺失值处理

```http
POST /api/v1/dataset-versions/{version_id}/prepare
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "fill_na": "median",
  "drop_na": false
}
```

`fill_na` 支持：

- `none`
- `mean`
- `median`
- `mode`

数值列按均值/中位数/众数处理；非数值列在均值或中位数模式下使用众数兜底。

### 筛选数据

```http
POST /api/v1/dataset-versions/{version_id}/filter
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "global_low": 0.01,
  "global_high": 0.99,
  "quantile_filters": [
    {"column": "Length", "low": 0.05, "high": 0.95}
  ],
  "value_filters": [
    {"column": "Sex", "values": ["M", "F"]}
  ]
}
```

### 启用字段

```http
PATCH /api/v1/dataset-versions/{version_id}/columns
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "enabled_columns": ["Length", "Diameter", "Rings"]
}
```

## 统计与图表接口

### 统计信息

```http
GET /api/v1/dataset-versions/{version_id}/statistics
Authorization: Bearer <access_token>
```

返回每个启用字段的均值、标准差、中位数、缺失数、唯一值数量等信息。

### 字段分布

```http
GET /api/v1/dataset-versions/{version_id}/columns/{column}/distribution
Authorization: Bearer <access_token>
```

### 字段可选值

```http
GET /api/v1/dataset-versions/{version_id}/columns/{column}/values?limit=500
Authorization: Bearer <access_token>
```

### 图表数据

```http
POST /api/v1/dataset-versions/{version_id}/chart-data
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "chart_type": "scatter",
  "x": "Length",
  "y": "Rings",
  "color": "Sex",
  "size": "Whole weight",
  "opacity": null,
  "limit": 5000
}
```

`chart_type` 支持：

- `scatter`
- `bar`
- `line`
- `boxplot`
- `pixel`

接口返回结构化行数据，调用方可以用 ECharts、D3、Plotly 或自己的可视化引擎渲染。

### 图表推荐

```http
GET /api/v1/dataset-versions/{version_id}/chart-suggestions
Authorization: Bearer <access_token>
```

系统会根据字段类型返回适合的散点图、箱线图、条形图、折线图或像素图配置建议。

### 相关矩阵

```http
GET /api/v1/dataset-versions/{version_id}/correlation?method=pearson
Authorization: Bearer <access_token>
```

`method` 支持 `pearson`、`spearman`、`kendall`。

### 分组聚合

```http
POST /api/v1/dataset-versions/{version_id}/groupby
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "group_by": ["Sex"],
  "metrics": [
    {"column": "Length", "agg": "mean", "alias": "avg_length"},
    {"column": "Rings", "agg": "median"}
  ],
  "limit": 500
}
```

### 假设检验

```http
POST /api/v1/dataset-versions/{version_id}/tests
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "test_type": "anova",
  "group_column": "Sex",
  "value_column": "Length"
}
```

`test_type` 支持 `t_test`、`anova`、`chi_square`。

### 异常值检测

```http
GET /api/v1/dataset-versions/{version_id}/outliers?columns=Length&columns=Rings
Authorization: Bearer <access_token>
```

当前使用 IQR 方法返回各数值字段异常值数量、比例和上下界。

## 因果分析接口

### 创建任务

```http
POST /api/v1/causal/jobs
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "dataset_version_id": "version-id",
  "algorithm": "pc",
  "selected_variables": ["Length", "Diameter", "Rings"],
  "background_edges": [
    {"source": "Length", "target": "Rings"}
  ],
  "algorithm_params": {
    "alpha": 0.05
  }
}
```

`algorithm` 支持：

- `pc`
- `gies`

### 查询任务列表

```http
GET /api/v1/causal/jobs?dataset_version_id=version-id
Authorization: Bearer <access_token>
```

### 查询任务状态

```http
GET /api/v1/causal/jobs/{job_id}
Authorization: Bearer <access_token>
```

`status` 常见值：

- `pending`
- `running`
- `completed`
- `failed`
- `canceled`

任务响应会包含 `progress`、`started_at` 和 `worker_id`，页面或第三方系统可以轮询任务详情展示进度。

### 重试和取消

```http
POST /api/v1/causal/jobs/{job_id}/retry
POST /api/v1/causal/jobs/{job_id}/cancel
Authorization: Bearer <access_token>
```

### 获取任务结果

```http
GET /api/v1/causal/jobs/{job_id}/result
Authorization: Bearer <access_token>
```

返回：

- `nodes`：变量节点。
- `edges`：因果边。
- `job`：任务元信息。

### 因果效应指标

```http
POST /api/v1/causal/effect
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "job_id": "job-id",
  "cause_var": "Length",
  "effect_var": "Rings"
}
```

返回 KL、JS、Total Variation、Wasserstein、Hellinger 等距离指标。

## 语义因果接口

语义接口依赖 `DEEPSEEK_API_KEY`。未配置时接口会返回明确的未配置提示，不会导致系统崩溃。

### 语义辅助定向

```http
POST /api/v1/llm/orient-edges
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "job_id": "job-id"
}
```

### 后门调整集

```http
POST /api/v1/llm/backdoor-adjustment
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "nodes": ["Length", "Diameter", "Rings"],
  "edges": [
    {"source": "Length", "target": "Rings"}
  ],
  "cause_var": "Length",
  "effect_var": "Rings"
}
```

### 大模型结果解释

```http
POST /api/v1/llm/analyze-result
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "job_id": "job-id",
  "question": "请解释这个因果图中最重要的变量关系"
}
```

## 收藏夹接口

标准收藏夹接口：

```http
GET /api/v1/favorites
POST /api/v1/favorites
DELETE /api/v1/favorites/{item_id}
```

兼容页面仍保留 `/api/favorites`，外部系统建议使用 `/api/v1/favorites`。

创建收藏：

```http
POST /api/v1/favorites
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "kind": "chart",
  "title": "Length 与 Rings 散点图",
  "description": "统计分析页生成的散点图",
  "dataset_id": "dataset-id",
  "group_name": "探索分析",
  "sort_order": 10,
  "payload": {
    "dataset_version_id": "version-id",
    "chart_type": "scatter",
    "x": "Length",
    "y": "Rings"
  },
  "snapshot": {
    "columns": ["Length", "Rings"],
    "summary": "保存时的轻量快照，便于复现"
  }
}
```

列表接口支持 `kind`、`dataset_id`、`group_name`、`keyword`、`created_from`、`created_to`、`sort` 查询参数。

## 工作流接口

工作流用于保存可复现的数据准备步骤，并套用到新的数据版本。

```http
POST /api/v1/workflows
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "name": "基础清洗流程",
  "description": "缺失值处理 + 分位数筛选",
  "steps": [
    {"type": "prepare", "payload": {"fill_na": "median", "drop_na": false}},
    {"type": "filter", "payload": {"global_low": 0.01, "global_high": 0.99}},
    {"type": "columns", "payload": {"enabled_columns": ["Length", "Rings"]}}
  ]
}
```

运行工作流：

```http
POST /api/v1/workflows/{workflow_id}/run
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "dataset_version_id": "version-id"
}
```

当前可执行步骤包括 `prepare`、`filter`、`columns`。`chart` 和 `causal` 步骤会被保留在工作流中，但运行时跳过，便于后续扩展为完整自动分析流程。

## 错误处理

常见 HTTP 状态：

- `400`：请求参数错误、字段不存在、文件格式无法解析。
- `401`：未登录或 token 无效。
- `404`：数据集、数据版本、任务或收藏不存在，或不属于当前用户。
- `413`：上传文件超过大小限制。
- `422`：请求体不符合 Pydantic schema。
- `500`：未预期服务端错误。

错误响应通常包含：

```json
{
  "detail": "错误说明"
}
```

## 调用示例

```bash
BASE_URL="http://127.0.0.1:18100/api/v1"

TOKEN=$(curl -sS -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"analyst","password":"strong-password"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -sS -X POST "$BASE_URL/datasets" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample.xlsx"
```
