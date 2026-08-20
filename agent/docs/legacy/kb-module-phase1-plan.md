# RAG知识库模块一期实施方案（文件级CRUD + 条款检索 + Agent只读预留）

> 状态说明（2026-03-25）：
> 本文档最初是一期实施方案。当前代码已经完成大部分一期能力，本文保留为“方案 + 对照文档”。
> 若与代码冲突，以当前实现为准。当前实现状态见下方“已落地情况”和“与原方案差异”。

## 当前实现状态（代码对照）
1. 已落地：前端知识库管理页、详情页、上传预览、提交入库、整文替换、元数据修改、删除、原文件下载、条款检索、任务状态轮询。
2. 已落地：`agent/retrieval` 提供 `preview/commit/replace/file-download/list/get/retrieve/jobs` 等接口，并保留底层条款级接口。
3. 已落地：原文件临时存储与正式存储、`kb_ingest_previews` 预览会话、`kb_index_jobs` 异步索引任务、Qdrant 向量检索、worker 异步 embedding/upsert/delete。
4. 已落地：Agent 侧 `query_kb` 只读能力预留，支持 `retrieve/get_document/list_documents`。
5. 未完全落地：原方案中的“读接口登录可用、写接口 admin”尚未实现；当前 `/kb/*` 代理接口统一要求管理员。
6. 未完全落地：Agent 侧 `query_kb` 默认仍关闭，需显式打开 `KB_TOOL_ENABLED=true` 才会启用。

## 与原方案差异
1. 权限策略存在差异。原方案写的是“读登录可用、写 admin”，当前代码实际是“全部 `/kb/*` 需 admin”。
2. 前端页面本身也按管理员路由保护，普通登录用户当前无法访问知识库管理和详情页。
3. 一期“只读开放面”尚未做完，但“管理员运营面”已经具备可用主链路。
4. 本文后续章节保留原设计意图，适合做差距分析，不再视为当前实现说明书。

## 一、目标摘要
1. 在 `frtend-tsx` 的设置页新增“知识库”模块，完成文件级增删改查。
2. 上传流程覆盖 `TXT/MD/DOCX/PDF(文本层)`，自动条款切分，支持人工确认“切分位置与元数据”后入库。
3. 所有业务改动按“文件”组织，不提供条款级改删入口；检索支持“按文件阅读”和“按条目相似度检索”。
4. 通过 `/api/agent/kb/*` 网关统一转发到 `agent/retrieval`，隐藏底层头部鉴权细节。
5. 预留 Agent 侧 `query_kb` 工具函数接口（默认不启用、不联调）。

## 二、范围与边界
1. 一期包含：文件上传/预览切分/确认入库、文件替换、文件元数据修改、文件删除、文件阅读、条款检索、原文件下载。
2. 一期不包含：OCR、条款级独立改删、真实组织角色映射到四级权限、向量重排模型（rerank）。
3. ACL 一期目标策略：`/api/agent/kb/*` 写接口要求 `auth.role === admin`；读接口要求已登录（`user|admin`）。网关注入 `X-Caller-Level` 时优先使用 `auth.user.kb_level`（若已配置），否则按角色映射 `admin=>group`、`user=>company`；不再固定 `admin => group`。文件必须设置最小可见级别（`driver|fleet|company|group`）。
4. `kb_id` 一期固定单库（制度库），默认值 `regulations`（可通过配置覆盖）。

## 三、后端总体方案（agent/retrieval）
1. 保留现有文档/条款/检索主链路与异步向量任务。
2. 新增“文件解析与上传”能力，形成“两步式导入”：
3. 第一步 `preview`：上传文件并解析、切分，返回可编辑条款草稿，同时生成 `preview_id + preview_token + file_hash + expires_at`。
4. 第二步 `commit`：仅提交“确认后的条款草稿 + preview凭据”，由服务端使用 preview 阶段已落盘的原文件执行入库与向量任务创建。
5. 修改能力拆分为两类：元数据 PATCH；文件内容 replace（全量替换该文件全部条款）。
6. `commit/replace` 必须校验 `preview_id + preview_token + file_hash + TTL`，不一致返回 `PREVIEW_MISMATCH`，过期返回 `PREVIEW_EXPIRED`，已消费返回 `PREVIEW_ALREADY_USED`。
7. `replace` 语义显式化：同一 `docId` 下先写入旧条款 tombstone（`is_deleted=1, vector_status=deleted`）并创建 delete jobs，再写入新条款与 upsert jobs；返回 `deleted_clause_count/new_clause_count/delete_job_ids/upsert_job_ids`，确保旧条款与旧向量可追踪清理。
8. 条款级改删底层接口保留，但网关不暴露。

## 四、公共API与接口变更（重点）
### A. retrieval服务新增/调整接口
1. `POST /v1/documents/preview`（multipart）
2. 输入：`file`，`kb_id`，`title?`，`default_min_level`，`split_options?`，`idempotency_key?`
3. 输出：`preview`（文件元信息、解析警告、条款数组、建议字段路径、`preview_id`、`preview_token`、`file_hash`、`expires_at`）
4. `POST /v1/documents/commit`（json）
5. 输入：`preview_id`，`preview_token`，`payload`（含 `kb_id/title/default_min_level/clauses/file_hash`）
6. 输出：`document`，`job_ids`，`status=202`
7. `POST /v1/documents/:docId/replace`（json）
8. 输入：同 commit，语义为“替换该文件全部条款 + 更新原文件”；内部必须执行“旧条款删除任务 + 新条款入库任务”双任务链路
9. 输出：`document`，`delete_job_ids`，`upsert_job_ids`，`status=202`
10. `GET /v1/documents/:docId/file?kb_id=...`
11. 输出：原文件流（下载）
12. 错误码补充：`PREVIEW_MISMATCH`、`PREVIEW_EXPIRED`、`PREVIEW_ALREADY_USED`、`FILE_TOO_LARGE`、`TOO_MANY_CLAUSES`、`PDF_OCR_REQUIRED`
13. retrieval 后端保持现有接口（兼容保留，不代表全部经网关暴露）：`POST /v1/documents`、`GET /v1/documents`、`GET /v1/documents/:docId`、`PATCH /v1/documents/:docId`、`DELETE /v1/documents/:docId`、`POST /v1/documents/:docId/clauses:batchUpsert`、`DELETE /v1/documents/:docId/clauses/:clauseId`、`POST /v1/reindex`、`POST /v1/retrieve`、`GET /v1/jobs/:jobId`

### B. agent网关新增接口（前端统一调用）
1. 前缀：`/api/agent/kb/*`
2. 目标态：映射 retrieval 的读取与写入接口；读接口要求已登录；写接口校验 `auth.role === admin`。
3. 通过校验后网关注入头：`X-Tenant-Id`、`X-Caller-Level=<auth.user.kb_level|role映射>`、`X-Caller-Id=<auth.user.id|principal_id>`；`X-Caller-Company-Id` 在 `X-Caller-Level=company` 时透传/注入。
4. 网关不开放条款级改删路由（即不提供 `/clauses:batchUpsert` 和 `/clauses/:id DELETE`）
5. 网关通过 `KB_API_BASE_URL` 转发到 retrieval，支持 `multipart/form-data` 流式透传；超时由 `KB_API_TIMEOUT_MS`（可选）控制。

### C. 类型与模型变更
1. `kb_documents` 增加文件元字段：`file_name`、`file_mime`、`file_size`、`file_hash`、`file_storage_key`
2. `kb_clauses` 增加顺序字段：`order_index`（保证按文件阅读时条款顺序稳定）
3. 新增 `kb_ingest_previews`（或等价临时存储索引）：`preview_id`、`tenant_id`、`kb_id`、`file_hash`、`temp_file_key`、`preview_token_hash`、`status(pending|committed|expired)`、`expires_at`、`created_at`
4. `DocumentRecord`、`ClauseRecord`、`RetrieveItem.metadata` 扩展对应字段
5. 前端新增 `KnowledgeBaseClient` 类型与 DTO：`PreviewClause`、`DocumentFileMeta`、`KbRetrieveResult`、`PreviewSession`

## 五、切分与解析策略（决策落地）
1. 支持格式：`txt/md/docx/pdf(文本层)`。
2. PDF 一期规则：仅处理可提取文本的 PDF；扫描件返回明确错误码 `PDF_OCR_REQUIRED`。
3. 条款切分主规则：优先识别编号条款（`第X条`、`一、`、`（一）`、`1.`、`1.1`、`第X章`）。
4. 回退规则：当编号不明显时按段落聚合切分，控制最小/最大长度阈值。
5. 人工确认允许：调整切分位置（通过“拆分/合并相邻条款”操作）与元数据编辑（`field_path/tags`）。
6. 人工确认不提供：条款独立删除动作；任何变更最终以“文件一次性提交”生效。

## 六、文件存储与下载
1. retrieval 新增文件存储适配层，默认 `filesystem`。
2. 新增配置：`RAW_FILE_ROOT`（例如 `/data/kb-files`）。
3. 新增 preview 临时文件目录（例如 `RAW_PREVIEW_ROOT`）与 TTL 清理任务；preview 文件仅用于 `commit/replace` 校验与落库。
4. 上传 preview 时保存临时原文件；commit/replace 成功后迁移/写入正式 `file_storage_key` 并将 preview 标记为 `committed`。
5. 下载时按 `file_storage_key` 读取并流式返回。
6. docker-compose 增加持久卷挂载（`kb_files`）到 API 容器，并为 preview 临时目录提供可清理存储。
7. 后续可扩展 S3/MinIO 适配，但一期只实现本地文件系统适配。

## 七、前端页面方案（frtend-tsx）
1. 新增路由：`/settings/knowledge-base`（管理页），`/settings/knowledge-base/:docId`（文件详情）。
2. 在设置导航增加“知识库管理”入口。
3. 管理页功能：文件列表、按标题筛选、上传新文件、替换文件、改元数据、删除文件、查看向量任务状态、下载原文件。
4. 上传/替换弹窗流程：选择文件与权限 -> 预览切分 -> 人工调整切分位置和元数据 -> 提交入库。
5. 文件详情页：按 `order_index` 展示全部条款，支持“人类阅读模式”。
6. 检索面板：输入查询词，统一通过 `kbClient(baseURL=/api/agent/kb)` 调用 `/retrieve`，按相似度显示条款结果，可跳转来源文件对应条款。

## 八、Agent接入预留（不联调上线）
1. 在 `agent/src/app/runtime.ts` 预留 `query_kb` 工具函数签名与执行函数壳。
2. 新增 `QueryKbArgs`/`QueryKbResult` 类型定义，支持动作：`retrieve`、`get_document`、`list_documents`。
3. 默认通过环境开关关闭（例如 `KB_TOOL_ENABLED=false`），不加入当前工具列表。
4. 仅完成接口与调用骨架，确保后续可直接接只读检索。

## 九、实施步骤（按落地顺序）
1. retrieval：扩展 schema、repository、contracts、config、file storage service。
2. retrieval：实现 `preview/commit/replace/file-download` 接口、preview会话校验（`preview_id/token/hash/TTL`）与解析切分服务。
3. retrieval：实现 `order_index` 写入与按顺序读取。
4. agent网关：新增 `/api/agent/kb/*` 路由；目标态为读写分离权限（读登录可用、写admin）；注入真实 `X-Caller-Level`；`KB_API_BASE_URL` 转发与 multipart 透传。
5. 前端：新增 `kbClient`、设置路由与页面、上传预览确认流程、检索与详情展示。
6. Agent预留：添加 `query_kb` 类型与禁用态函数骨架。
7. 联调：上传->预览->确认->入库->任务轮询->文件阅读->条款检索->删除/替换。
8. 回归：已有 `/rules`、`/research`、`/chat` 路由不回归。

## 十、测试与验收场景
1. 上传 TXT/MD/DOCX/PDF(文本层) 各 1 份，预览切分成功。
2. 上传扫描版 PDF 返回 `PDF_OCR_REQUIRED`，前端提示“暂不支持OCR”。
3. 人工调整切分位置（拆分/合并）后提交，入库条款顺序正确；`commit` 必须携带有效 `preview_id/token/hash`。
4. 元数据 PATCH 生效，不触发内容重切分。
5. replace 后旧条款不可见、新条款可检索；delete/upsert 两类任务状态可追踪，且不再命中旧向量。
6. 删除文件后文件详情不可读、检索不再命中该文件条款。
7. 文件级最小权限字段写入成功，并在 retrieval 读过滤逻辑中可用。
8. 目标验收：未登录请求 `/api/agent/kb/*` 返回 401；非 admin 调用写接口返回 403；读接口按注入的 `X-Caller-Level` 生效过滤；网关不暴露条款级改删接口，请求返回 404/forbidden。
9. 原文件下载可用，MIME 与文件名正确。
10. `query_kb` 预留接口编译通过、默认不对外暴露。
11. retrieval 既有接口（如 `POST /v1/documents`、`POST /v1/reindex`）继续可用，避免兼容性回归。

## 十一、显式假设与默认值
1. `kb_id` 一期固定为制度库（默认 `regulations`），不做多库切换UI。
2. ACL 一期设计按“写admin、读登录可用”生效；`X-Caller-Level` 优先取 `auth.user.kb_level`，缺省按角色映射（`admin=>group`,`user=>company`），真实组织映射延后。当前代码实际仍为 `/kb/*` 全部 admin。
3. 单文件大小默认上限 20MB（可配），超限返回 `FILE_TOO_LARGE`。
4. 条款数量默认上限 2000 条/文件（可配），超限返回 `TOO_MANY_CLAUSES`。
5. OCR 不在一期实现，扫描件 PDF 仅给出可追踪错误码与提示。
6. 网关运行环境需提供 `KB_API_BASE_URL`；`KB_API_TIMEOUT_MS` 为可选配置。
