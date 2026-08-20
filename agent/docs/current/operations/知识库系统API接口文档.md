# 知识库系统 API 接口文档

本文档是当前知识库/RAG 检索服务与 Agent 知识库代理接口的业务契约。

最后对齐代码日期：2026-08-10。

## 1. 文档范围

知识库系统当前有两层接口：

- Agent Worker 代理层：`/api/agent/kb/*`，实现位置：`agent/src/infra/kb-proxy.ts`。
- Retrieval 检索服务层：`/v1/*`，实现位置：`agent/retrieval/src/index.ts` 和 `agent/retrieval/src/services/kb-service.ts`。

前端通常应调用 Agent Worker 代理层。直接调用 Retrieval 服务主要用于服务间调用、本地调试和部署检查。

### 1.1 代理路径与底层路径映射

代理层会转发到对应的 Retrieval 服务路径，映射关系如下：

| 前端/Agent 代理路径                       | Retrieval 服务路径              | 说明                 |
| ----------------------------------------- | ------------------------------- | -------------------- |
| `/api/agent/kb/retrieve`                  | `/v1/retrieve`                  | 检索条款             |
| `/api/agent/kb/reindex`                   | `/v1/reindex`                   | 触发重建索引         |
| `/api/agent/kb/documents/preview`         | `/v1/documents/preview`         | 上传并解析预览       |
| `/api/agent/kb/documents/commit`          | `/v1/documents/commit`          | 确认入库             |
| `/api/agent/kb/documents/{docId}/replace` | `/v1/documents/{docId}/replace` | 替换文档             |
| `/api/agent/kb/documents`                 | `/v1/documents`                 | 文档列表或直接创建   |
| `/api/agent/kb/documents/{docId}`         | `/v1/documents/{docId}`         | 文档详情、更新、删除 |
| `/api/agent/kb/documents/{docId}/file`    | `/v1/documents/{docId}/file`    | 下载原始文件         |
| `/api/agent/kb/jobs/{jobId}`              | `/v1/jobs/{jobId}`              | 查询索引任务         |

注意：底层 Retrieval 服务支持 `/v1/documents/{docId}/clauses:batchUpsert` 和 `/v1/documents/{docId}/clauses/{clauseId}`，但 Agent Worker 代理层当前不开放 `/api/agent/kb/documents/{docId}/clauses*`。

> 第 7 节接口详情中的示例路径均为 Retrieval 服务路径（上表右列）。前端实际请求时改用上表左列的代理前缀 `/api/agent/kb` + 对应路径，且不传任何 KB header（见 2.1）。

## 2. 鉴权与请求头

### 2.1 Agent Worker 代理层

当前实现下，所有 `/api/agent/kb/*` 接口要求调用方已登录。未登录（anon）请求返回 `403`；登录用户即可访问，不要求管理员身份。真正的读写权限由 Retrieval 服务按 `X-Caller-Level` 判定（见 2.3 与 8.1）。

前端调用 `/api/agent/kb/*` 时无需自行设置以下 header，只要保持登录态、用 `credentials: "include"` 发请求即可（浏览器会自动携带登录 cookie，代理层据此识别当前登录用户并生成下表 header）。下表 header 均由代理层附加，前端不传：

| 请求头                | 来源                                                           |
| --------------------- | -------------------------------------------------------------- |
| `X-Tenant-Id`         | `KB_TENANT_ID`，默认 `default`                                 |
| `X-Caller-Level`      | 登录用户 `kb_level`，无值时默认 `driver`；管理员缺省为 `group` |
| `X-Caller-Id`         | 用户 id 或 principal id                                        |
| `X-Request-Id`        | 入站请求头或新生成的请求 id                                    |
| `X-Caller-Company-Id` | 用户已配置 `company_id` 时附加（不强制）                       |

### 2.2 Retrieval 服务层

直接调用 `/v1/*` 时按需提供以下 header：

| 请求头                | 必填 | 说明                                         |
| --------------------- | ---: | -------------------------------------------- |
| `X-Tenant-Id`         |   否 | 租户 id，缺省 `default`                      |
| `X-Caller-Level`      |   是 | `driver`、`fleet`、`company`、`group`        |
| `X-Caller-Id`         |   是 | 调用方 id                                    |
| `X-Caller-Company-Id` |   否 | 当前不参与权限判定，预留给将来的公司维度隔离 |

权限等级顺序：

```text
driver < fleet < company < group
```

### 2.3 集中权限模型

KB 权限由两条轴共同决定：

- 调用方等级：`X-Caller-Level`，Agent Worker 代理层从登录用户的 `agent_users.kb_level` 派生；没有配置 `kb_level` 时，管理员缺省为 `group`，普通用户缺省为 `driver`。
- 资源最小等级：文档级 `default_min_level` 和条款级 `min_level`；条款未显式设置 `min_level` 时继承文档默认权限。

各等级的业务语义：

| 等级      | 语义                                 | 典型权限                                               |
| --------- | ------------------------------------ | ------------------------------------------------------ |
| `driver`  | 驾驶员、一线个人或最低可见范围       | 只能读取 `driver` 级资源                               |
| `fleet`   | 车队、线路队或基层管理单元           | 可读取 `driver`、`fleet` 级资源                        |
| `company` | 公司、分子公司或专业公司管理人员     | 可读取 `company` 及以下资源；可写不高于自身等级的资源  |
| `group`   | 集团、总部或平台超级管理范围         | 可读取和写入全部等级资源；`reindex scope=all` 仅此级可用 |

当前实现只按等级 rank 判定，不按 `company_id`、车队 id 或驾驶员 id 做数据隔离。`X-Caller-Company-Id` 只在代理层能拿到 `company_id` 时透传，当前 Retrieval 服务不参与权限判定。

读规则：

- 通用判定为 `caller_rank >= resource_min_rank`。
- 文档列表按文档 `default_min_rank` 静默过滤，调用方只看到可见文档。
- 单文档详情、原始文件下载、条款级接口等遇到不可见资源时返回 `404 DOCUMENT_NOT_FOUND` 或 `404 CLAUSE_NOT_FOUND`，不暴露资源是否真实存在。
- 检索接口按条款 `min_rank` 静默过滤，返回结果不会包含高于调用方等级的条款。

写规则：

- 写入操作要求调用方至少为 `company` 级。
- 调用方不能写入高于自身等级的资源，例如 `company` 可写 `driver/fleet/company`，不能写 `group`。
- 更新已有文档或条款时，调用方还必须能看见并写入当前资源等级；修改 `default_min_level` 时，新等级也不能高于调用方等级。

调用方等级管理：

- `kb_level` 和 `company_id` 存放在 Agent Worker 使用的 `agent_users` 表中，读取位置为 `agent/src/infra/auth/session-store.ts`，代理注入位置为 `agent/src/infra/kb-proxy.ts`。
- 当前没有 admin API 或前端页面可以维护 `kb_level/company_id`。如需给用户开通 KB 等级，只能由运维或数据库管理员直接改库。
- 若部署库缺少列，需先补列；示例 SQL：

```sql
ALTER TABLE agent_users ADD COLUMN kb_level TEXT;
ALTER TABLE agent_users ADD COLUMN company_id TEXT;
```

给某用户开通 company 级 KB 写权限示例：

```sql
UPDATE agent_users
SET kb_level = 'company',
    company_id = 'company_xxx',
    updated_at = datetime('now')
WHERE id = 'user_xxx';
```

`kb_level` 允许值为 `driver/fleet/company/group`。设为空或非法值时，代理层会按缺省规则派生调用方等级。

## 3. 支持的文件格式

`POST /v1/documents/preview` 支持以下扩展名：

- `.txt`
- `.md`
- `.markdown`
- `.docx`
- `.pdf`

支持的 MIME 类型：

| MIME                                                                      | 说明                         |
| ------------------------------------------------------------------------- | ---------------------------- |
| `text/plain`                                                              | 纯文本                       |
| `text/markdown`                                                           | Markdown                     |
| `text/x-markdown`                                                         | 会归一化为 `text/markdown`   |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | DOCX                         |
| `application/pdf`                                                         | PDF                          |
| `application/x-pdf`                                                       | 会归一化为 `application/pdf` |

如果 MIME 缺失或为 `application/octet-stream`，服务会根据文件扩展名兜底判断。

PDF 行为：

- 有可提取文本层的 PDF 直接解析。
- 文本层不可提取（文本长度不足 20 字符或解析失败）时尝试 OCR；OCR 仅在 `OCR_ENABLED=true` 且 `OCR_BASE_URL` 已配置时实际执行。
- `OCR_ENABLED=false` 时返回 `PDF_OCR_REQUIRED`（422），前端可据此提示用户上传带文本层的 PDF 或联系管理员。
- OCR 已启用但调用失败时，Retrieval 会返回 `OCR_*` 系列诊断码（超时、网络失败、空文本、上游业务错误等），完整列表与 HTTP 状态见 8.1。上游业务错误会被包装成 `OCR_{上游error_code}`，未提供 `error_code` 时返回兜底码 `OCR_FAILED`。

当前默认限制：

| 配置                       |     默认值 | 说明             |
| -------------------------- | ---------: | ---------------- |
| `MAX_FILE_SIZE_BYTES`      | `20971520` | 20 MB            |
| `MAX_CLAUSES_PER_DOCUMENT` |     `2000` | 单文档最大条款数 |
| `PREVIEW_TTL_SECONDS`      |     `3600` | 预览会话有效期   |

## 4. 文件存储语义

常规上传流程不接受客户端传入物理文件路径。

预览阶段将原始文件临时保存到：

```text
RAW_PREVIEW_ROOT/{preview_id}/{timestamp}_{safeFileName}
```

确认入库或替换时，将临时文件移动到正式文件目录：

```text
RAW_FILE_ROOT/{kb_id}/{docId}/{timestamp}_{safeFileName}
```

正式相对路径会保存到文档记录的 `file_storage_key`。

示例：

```text
RAW_FILE_ROOT=/data/kb-files
kb_id=regulations
docId=doc_abc
file_storage_key=regulations/doc_abc/1720000000000_safety.pdf
物理文件=/data/kb-files/regulations/doc_abc/1720000000000_safety.pdf
```

删除是逻辑删除。`DELETE /v1/documents/{docId}` 会将文档和条款标记为删除，并创建向量删除任务；当前不会从 `RAW_FILE_ROOT` 删除原始物理文件。

`POST /v1/documents` 是特殊的直接创建入口。它允许在 JSON 中传 `file_storage_key`，但不会上传、校验或移动原始文件。这个接口应视为内部迁移或补数据入口，不是前端常规上传入口。

## 5. 通用数据结构

### 5.1 AccessLevel

```json
"driver" | "fleet" | "company" | "group"
```

### 5.2 ClauseInput

```json
{
  "clause_id": "可选条款 id",
  "field_path": "section/1",
  "content": "条款正文",
  "heading_path": ["可选", "标题", "路径"],
  "min_level": "company",
  "tags": ["事故", "上报"],
  "order_index": 1
}
```

`field_path` 和 `content` 必填，其余字段可选。

### 5.3 DocumentResponse

```json
{
  "tenant_id": "default",
  "kb_id": "regulations",
  "doc_id": "doc_xxx",
  "title": "事故调查规范",
  "source_uri": "",
  "file_name": "sample.md",
  "file_mime": "text/markdown",
  "file_size": 12345,
  "file_hash": "sha256...",
  "file_storage_key": "regulations/doc_xxx/1720000000000_sample.md",
  "default_min_level": "company",
  "status": "active",
  "version": 1,
  "created_at": "2026-07-21T00:00:00.000Z",
  "updated_at": "2026-07-21T00:00:00.000Z"
}
```

## 6. 标准入库流程

前端常规上传使用：

```text
preview -> 用户校对条款 -> commit
```

替换已有文档使用：

```text
preview -> 用户校对条款 -> replace
```

`preview_id`、`preview_token`、`file_hash` 和预览 TTL 用来绑定预览结果与最终提交/替换请求。

## 7. 接口详情

### 7.1 `POST /v1/documents/preview`

解析文件并创建临时预览会话。

Content-Type：`multipart/form-data`

请求字段：

| 字段                | 必填 | 说明                                                                       |
| ------------------- | ---: | -------------------------------------------------------------------------- |
| `file`              |   是 | 上传的源文件                                                               |
| `kb_id`             |   否 | 知识库 id，默认 `KB_DEFAULT_ID`                                            |
| `title`             |   否 | 建议文档标题                                                               |
| `default_min_level` |   否 | `driver`、`fleet`、`company`、`group`，默认 `driver`                       |
| `split_options`     |   否 | JSON 字符串，`min_clause_chars`（20–5000）、`max_clause_chars`（50–10000） |

响应状态码：`200`

响应：

```json
{
  "success": true,
  "data": {
    "preview": {
      "file_name": "sample.md",
      "file_mime": "text/markdown",
      "file_size": 12345,
      "warnings": [],
      "clauses": [
        {
          "clause_id": "preview_clause_1",
          "field_path": "section/1",
          "heading_path": ["section/1"],
          "content": "条款正文",
          "min_level": "company",
          "tags": [],
          "order_index": 1
        }
      ],
      "preview_id": "preview_xxx",
      "preview_token": "preview_token_xxx",
      "file_hash": "sha256...",
      "expires_at": "2026-07-21T01:00:00.000Z"
    }
  }
}
```

### 7.2 `POST /v1/documents/commit`

基于预览会话创建新文档。

请求：

```json
{
  "preview_id": "preview_xxx",
  "preview_token": "preview_token_xxx",
  "payload": {
    "kb_id": "regulations",
    "title": "事故调查规范",
    "source_uri": "",
    "default_min_level": "company",
    "file_hash": "sha256...",
    "clauses": [
      {
        "field_path": "section/1",
        "content": "事故发生后，应在规定时限内完成上报。",
        "tags": ["事故", "上报"]
      }
    ]
  }
}
```

请求字段：

| 字段            | 必填 | 说明                                      |
| --------------- | ---: | ----------------------------------------- |
| `preview_id`    |   是 | `preview` 接口返回的预览会话 id           |
| `preview_token` |   是 | `preview` 接口返回的预览提交 token        |
| `payload`       |   是 | 用户校对后的最终入库内容                  |

`payload` 字段：

| 字段                | 必填 | 说明                                                                 |
| ------------------- | ---: | -------------------------------------------------------------------- |
| `kb_id`             |   是 | 知识库 id，必须与 `preview` 会话中的 `kb_id` 一致                    |
| `title`             |   是 | 入库后的文档标题                                                     |
| `source_uri`        |   否 | 原始来源地址或外部来源标识；无来源时可传空字符串或不传               |
| `default_min_level` |   是 | 文档默认最小访问等级：`driver`、`fleet`、`company`、`group`           |
| `file_hash`         |   是 | `preview` 接口返回的文件 hash，用于确认提交文件与预览文件一致        |
| `clauses`           |   是 | 用户确认后的条款数组，至少 1 条；每项结构见 [5.2 ClauseInput](#52-clauseinput) |

必传字段为：`preview_id`、`preview_token`、`payload.kb_id`、`payload.title`、`payload.default_min_level`、`payload.file_hash`、`payload.clauses`。`clauses` 内每条至少要传 `field_path` 和 `content`。

响应状态码：`202`

响应：

```json
{
  "success": true,
  "data": {
    "document": { "...": "DocumentResponse" },
    "job_ids": ["job_xxx"]
  }
}
```

行为：

- 校验预览 id、token、文件 hash、`kb_id` 和 TTL。
- 创建新的 `doc_id`。
- 写入文档元数据。
- 写入条款。
- 将预览临时文件移动到 `RAW_FILE_ROOT`。
- 创建向量 upsert 任务。

### 7.3 `POST /v1/documents/{docId}/replace`

使用预览会话替换已有文档的源文件和条款。

请求体与 `POST /v1/documents/commit` 相同，`docId` 来自路径。

响应状态码：`202`

响应：

```json
{
  "success": true,
  "data": {
    "document": { "...": "DocumentResponse" },
    "deleted_clause_count": 12,
    "new_clause_count": 10,
    "delete_job_ids": ["job_delete_xxx"],
    "upsert_job_ids": ["job_upsert_xxx"]
  }
}
```

行为：

- 校验目标文档可见且可写。
- 将旧 active 条款标记为删除。
- 为旧条款创建向量 delete 任务。
- 插入新条款。
- 为新条款创建向量 upsert 任务。
- 将预览临时文件移动到 `RAW_FILE_ROOT`。

### 7.4 `POST /v1/documents`

直接创建文档和条款，不走上传预览流程。

请求：

```json
{
  "kb_id": "regulations",
  "doc_id": "optional-doc-id",
  "title": "事故调查规范",
  "source_uri": "",
  "file_name": "sample.md",
  "file_mime": "text/markdown",
  "file_size": 12345,
  "file_hash": "sha256...",
  "file_storage_key": "regulations/doc_xxx/1720000000000_sample.md",
  "default_min_level": "company",
  "status": "active",
  "clauses": [
    {
      "field_path": "section/1",
      "content": "条款正文",
      "min_level": "company",
      "tags": []
    }
  ]
}
```

请求字段：

| 字段                | 必填 | 说明                                                               |
| ------------------- | ---: | ------------------------------------------------------------------ |
| `kb_id`             |   是 | 知识库 id                                                          |
| `doc_id`            |   否 | 指定文档 id；不传时服务端自动生成                                  |
| `title`             |   是 | 文档标题                                                           |
| `source_uri`        |   否 | 原始来源地址或外部来源标识；默认空字符串                           |
| `file_name`         |   否 | 原始文件名；默认空字符串                                           |
| `file_mime`         |   否 | 原始文件 MIME；默认 `application/octet-stream`                     |
| `file_size`         |   否 | 原始文件大小，非负整数；默认 `0`                                   |
| `file_hash`         |   否 | 原始文件 hash；默认空字符串                                        |
| `file_storage_key`  |   否 | 已存在的原始文件存储 key；服务端信任该值，不上传、不移动文件        |
| `default_min_level` |   否 | 文档默认最小访问等级；默认 `driver`                                |
| `status`            |   否 | 文档状态；默认 `active`                                            |
| `clauses`           |   否 | 初始条款数组；默认空数组。每项结构见 [5.2 ClauseInput](#52-clauseinput) |

必传字段为：`kb_id`、`title`。如传 `clauses`，每条至少要传 `field_path` 和 `content`。

响应状态码：`202`

响应：

```json
{
  "success": true,
  "data": {
    "document": { "...": "DocumentResponse" },
    "clause_ids": ["clause_xxx"],
    "job_ids": ["job_xxx"]
  }
}
```

注意：该接口信任 `file_storage_key`，不会上传或移动文件。产品上传应优先使用 `preview -> commit`。

### 7.5 `GET /v1/documents`

查询当前调用方可见的文档列表。

Query 参数：

| 参数     | 必填 | 说明                    |
| -------- | ---: | ----------------------- |
| `kb_id`  |   是 | 知识库 id               |
| `limit`  |   否 | 默认 `20`，范围 `1–100` |
| `offset` |   否 | 默认 `0`                |

响应状态码：`200`

响应：

```json
{
  "success": true,
  "data": {
    "items": [{ "...": "DocumentResponse" }],
    "total": 1,
    "limit": 20,
    "offset": 0
  }
}
```

### 7.6 `GET /v1/documents/{docId}`

查询当前调用方可见的单个文档。

Query 参数：

| 参数              | 必填 | 说明                                 |
| ----------------- | ---: | ------------------------------------ |
| `kb_id`           |   是 | 知识库 id                            |
| `include_clauses` |   否 | 默认 `true`；传 `false` 时不返回条款 |

响应状态码：`200`

响应：

```json
{
  "success": true,
  "data": {
    "...": "DocumentResponse",
    "clauses": [
      {
        "clause_id": "clause_xxx",
        "field_path": "section/1",
        "heading_path": ["section", "1"],
        "content": "条款正文",
        "min_level": "company",
        "tags": [],
        "order_index": 1,
        "version": 1
      }
    ]
  }
}
```

### 7.7 `PATCH /v1/documents/{docId}`

更新文档元数据。

请求：

```json
{
  "kb_id": "regulations",
  "title": "新标题",
  "source_uri": "",
  "default_min_level": "company",
  "status": "active"
}
```

请求字段：

| 字段                | 必填 | 说明                                                       |
| ------------------- | ---: | ---------------------------------------------------------- |
| `kb_id`             |   是 | 知识库 id，用于定位路径中的 `docId`                        |
| `title`             |   否 | 新文档标题                                                 |
| `source_uri`        |   否 | 新原始来源地址或外部来源标识                               |
| `default_min_level` |   否 | 新文档默认最小访问等级：`driver`、`fleet`、`company`、`group` |
| `status`            |   否 | 新文档状态                                                 |

必传字段为：`kb_id`。其余字段可选；未传字段保持原值。

响应状态码：`202`

响应：

```json
{
  "success": true,
  "data": {
    "document": { "...": "DocumentResponse" },
    "job_ids": ["job_xxx"]
  }
}
```

权限继承行为：

- 修改 `default_min_level` 时，服务只重写 active 且 `inherits_default=1` 的条款。
- 已显式设置 `min_level` 的条款不会被文档默认权限覆盖。

当前实现注意点：前端上传提交时常给每条 clause 都带上 `min_level`（即使等于文档默认权限），这会使该条款被后端视为显式权限而非继承默认权限，后续修改文档默认权限时不会同步覆盖。若需“按文件设权限、改文件权限时同步影响默认条款”，前端对继承默认权限的条款不应传 `min_level`，或后端在 commit 时把 `clause.min_level === default_min_level` 视为继承。

### 7.8 `DELETE /v1/documents/{docId}`

逻辑删除文档。

Query 参数：

| 参数    | 必填 | 说明      |
| ------- | ---: | --------- |
| `kb_id` |   是 | 知识库 id |

响应状态码：`202`

响应：

```json
{
  "success": true,
  "data": {
    "deleted": true,
    "job_ids": ["job_xxx"]
  }
}
```

行为：

- 插入新的 deleted 文档版本。
- 将 active 条款标记为删除。
- 创建向量 delete 任务。

### 7.9 `GET /v1/documents/{docId}/file`

下载文档原始源文件。

Query 参数：

| 参数    | 必填 | 说明      |
| ------- | ---: | --------- |
| `kb_id` |   是 | 知识库 id |

响应：

- 状态码：`200`
- Body：二进制文件内容
- `Content-Type`：存储的 `file_mime`
- `Content-Disposition`：`attachment; filename="{encoded file_name}"`

### 7.10 `POST /v1/retrieve`

检索相关条款。

请求：

```json
{
  "kb_id": "regulations",
  "query": "事故发生后多久上报",
  "top_k": 5,
  "filters": {
    "doc_ids": ["doc_xxx"],
    "field_paths": ["section/1"],
    "tags": ["事故"]
  }
}
```

请求字段：

| 字段                  | 必填 | 说明                                      |
| --------------------- | ---: | ----------------------------------------- |
| `kb_id`               |   是 | 知识库 id                                 |
| `query`               |   是 | 检索问题或关键词                          |
| `top_k`               |   否 | 返回条数，默认 `8`，范围 `1–50`           |
| `filters`             |   否 | 检索过滤条件                              |
| `filters.doc_ids`     |   否 | 只检索指定文档 id                         |
| `filters.field_paths` |   否 | 只检索指定条款路径                        |
| `filters.tags`        |   否 | 只检索带指定标签的条款                    |

必传字段为：`kb_id`、`query`。

响应状态码：`200`

响应：

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "doc_id": "doc_xxx",
        "clause_id": "clause_xxx",
        "field_path": "section/1",
        "heading_path": ["section", "1"],
        "content": "条款正文",
        "score": 0.92,
        "min_level": "company",
        "metadata": {
          "title": "事故调查规范",
          "source_uri": "",
          "tags": ["事故"],
          "file_name": "sample.md",
          "order_index": 1
        }
      }
    ]
  }
}
```

行为：

- 按调用方权限等级静默过滤。
- 支持文档标题快速路径。
- 使用 Qdrant 向量召回和 ClickHouse 词法兜底。
- query rewrite 和 rerank 是否启用取决于 Retrieval 服务环境变量。

### 7.11 `POST /v1/reindex`

为已有范围创建向量 upsert 任务。

请求：

```json
{
  "scope": "kb",
  "kb_id": "regulations",
  "doc_id": "doc_xxx",
  "clause_id": "clause_xxx"
}
```

请求字段：

| 字段        | 必填 | 说明                                                        |
| ----------- | ---: | ----------------------------------------------------------- |
| `scope`     |   是 | 重建范围：`all`、`kb`、`document`、`clause`                 |
| `kb_id`     | 按范围 | `scope=kb/document/clause` 时必填                           |
| `doc_id`    | 按范围 | `scope=document/clause` 时必填                              |
| `clause_id` | 按范围 | `scope=clause` 时必填                                      |

范围规则：

| scope      | 必填字段                       |
| ---------- | ------------------------------ |
| `all`      | 无；仅 `group` 调用方可执行    |
| `kb`       | `kb_id`                        |
| `document` | `kb_id`、`doc_id`              |
| `clause`   | `kb_id`、`doc_id`、`clause_id` |

响应状态码：`202`

响应：

```json
{
  "success": true,
  "data": {
    "scope": "kb",
    "selected_clauses": 10,
    "job_ids": ["job_xxx"]
  }
}
```

### 7.12 `GET /v1/jobs/{jobId}`

查询索引任务最新状态。

`job_type` 取值：`upsert`、`delete`、`rebuild`。`status` 取值：`pending`、`running`、`success`、`failed`。

响应状态码：`200`

响应：

```json
{
  "success": true,
  "data": {
    "job_id": "job_xxx",
    "job_type": "upsert",
    "status": "pending",
    "retry_count": 0,
    "next_run_at": "2026-07-21T00:00:00.000Z",
    "last_error": "",
    "updated_at": "2026-07-21T00:00:00.000Z"
  }
}
```

### 7.13 `POST /v1/documents/{docId}/clauses:batchUpsert`

仅 Retrieval 服务层支持。Agent Worker `/kb/*` 代理层不开放条款接口。

请求：

```json
{
  "kb_id": "regulations",
  "clauses": [
    {
      "clause_id": "optional",
      "field_path": "section/1",
      "content": "条款正文",
      "min_level": "company",
      "tags": []
    }
  ]
}
```

请求字段：

| 字段      | 必填 | 说明                                                               |
| --------- | ---: | ------------------------------------------------------------------ |
| `kb_id`   |   是 | 知识库 id，用于定位路径中的 `docId`                                |
| `clauses` |   是 | 要新增或更新的条款数组，至少 1 条；每项结构见 [5.2 ClauseInput](#52-clauseinput) |

必传字段为：`kb_id`、`clauses`。`clauses` 内每条至少要传 `field_path` 和 `content`；传 `clause_id` 表示更新指定条款，不传则新增条款。

响应状态码：`202`

响应：

```json
{
  "success": true,
  "data": {
    "clause_ids": ["clause_xxx"],
    "job_ids": ["job_xxx"]
  }
}
```

### 7.14 `DELETE /v1/documents/{docId}/clauses/{clauseId}`

同 7.13，仅 Retrieval 服务层支持，Agent Worker 代理层不开放条款接口。

Query 参数：

| 参数    | 必填 | 说明      |
| ------- | ---: | --------- |
| `kb_id` |   是 | 知识库 id |

响应状态码：`202`

响应：

```json
{
  "success": true,
  "data": {
    "deleted": true,
    "job_ids": ["job_xxx"]
  }
}
```

## 8. 错误码

### 8.1 Retrieval 服务错误码

|  HTTP | Code                      | 含义                                                                                                  |
| ----: | ------------------------- | ----------------------------------------------------------------------------------------------------- |
| `400` | `INVALID_CALLER_LEVEL`    | 缺少或非法 `X-Caller-Level`                                                                           |
| `400` | `MISSING_CALLER_ID`       | 缺少 `X-Caller-Id`                                                                                    |
| `400` | `MISSING_FILE`            | 缺少 multipart `file` 字段                                                                            |
| `400` | `INVALID_DEFAULT_LEVEL`   | `default_min_level` 非法                                                                              |
| `400` | `INVALID_SPLIT_OPTIONS`   | `split_options` 不是合法 JSON                                                                         |
| `400` | `INVALID_PAYLOAD`         | 请求体未通过 Zod 校验（字段缺失、类型错误或超界）                                                     |
| `400` | `UNSUPPORTED_FILE_TYPE`   | 文件类型不是 TXT/MD/DOCX/PDF                                                                          |
| `400` | `EMPTY_DOCUMENT`          | 解析后没有可读文本或条款                                                                              |
| `400` | `TOO_MANY_CLAUSES`        | 条款数超过 `MAX_CLAUSES_PER_DOCUMENT`                                                                 |
| `400` | `FILE_TOO_LARGE`          | 文件超过 `MAX_FILE_SIZE_BYTES`                                                                        |
| `400` | `PREVIEW_MISMATCH`        | 预览 id、token、hash、tenant 或 `kb_id` 不匹配                                                        |
| `400` | `MISSING_KB_ID`           | 缺少必填 `kb_id`                                                                                      |
| `400` | `MISSING_DOC_SCOPE`       | reindex `scope=document` 缺少 `kb_id` 或 `doc_id`                                                     |
| `400` | `MISSING_CLAUSE_SCOPE`    | reindex `scope=clause` 缺少 `kb_id`、`doc_id` 或 `clause_id`                                          |
| `403` | `WRITE_FORBIDDEN`         | 调用方权限低于写入要求                                                                                |
| `403` | `WRITE_LEVEL_FORBIDDEN`   | 调用方试图写入高于自身等级的资源                                                                      |
| `403` | `REINDEX_SCOPE_FORBIDDEN` | 非 `group` 调用方请求 `scope=all`                                                                     |
| `404` | `DOCUMENT_NOT_FOUND`      | 文档不存在、已删除或对调用方不可见                                                                    |
| `404` | `CLAUSE_NOT_FOUND`        | 条款不存在、已删除或对调用方不可见                                                                    |
| `404` | `FILE_NOT_FOUND`          | 文档没有存储的原始文件 key                                                                            |
| `404` | `JOB_NOT_FOUND`           | 索引任务不存在或属于其他租户                                                                          |
| `409` | `DOCUMENT_EXISTS`         | 直接创建时指定了已存在的 active `doc_id`                                                              |
| `409` | `PREVIEW_ALREADY_USED`    | 预览会话已提交                                                                                        |
| `409` | `PREVIEW_EXPIRED`         | 预览会话已过期                                                                                        |
| `422` | `PDF_OCR_REQUIRED`        | PDF 没有文本层且 `OCR_ENABLED=false`                                                                  |
| `422` | `OCR_EMPTY_TEXT`          | OCR 服务成功响应，但返回空文本                                                                        |
| `422` | `OCR_FAILED`              | OCR 服务返回 `success=false` 且未提供 `error_code` 时的兜底码                                         |
| `422` | `OCR_{上游error_code}`    | OCR 服务返回 `success=false` 时的业务错误映射，例如 `OCR_INVALID_PAGE_RANGE`、`OCR_OCR_PROCESS_ERROR` |
| `500` | `INTERNAL_ERROR`          | 未捕获的服务端异常                                                                                    |
| `500` | `OCR_NOT_CONFIGURED`      | `OCR_ENABLED=true` 但 `OCR_BASE_URL` 为空                                                             |
| `502` | `OCR_REQUEST_FAILED`      | Retrieval 无法请求 OCR 服务                                                                           |
| `504` | `OCR_TIMEOUT`             | Retrieval 调用 OCR 服务的 HTTP 请求超时                                                               |

OCR HTTP 异常返回 `OCR_HTTP_ERROR`，状态码与上游一致。这个错误表示 OCR 服务 HTTP 响应不是 2xx；它不同于 OCR 服务返回 `success=false` 的业务错误。

### 8.2 Agent Worker 代理错误

|  HTTP | 含义                                                      |
| ----: | --------------------------------------------------------- |
| `403` | 未登录（anon）访问 `/api/agent/kb/*`                      |
| `404` | 代理层未开放该路由，包括 `/kb/documents/{docId}/clauses*` |
| `500` | 未配置 `KB_API_BASE_URL`                                  |
| `502` | 上游 Retrieval 请求失败或超时                             |

## 9. 文档边界

- 本文档用于 KB/RAG API 契约。
- `agent/docs/Agent系统API接口文档.md` 保留 Agent 总接口索引和 `/kb/*` 代理路由说明。
- `agent/retrieval/README.md` 用于 Retrieval 服务启动、部署和快速 curl 检查。
