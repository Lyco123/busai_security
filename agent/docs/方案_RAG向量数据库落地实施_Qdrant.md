# 方案：RAG + 向量数据库落地实施（Qdrant，精简版）
## 1. 目标
- 用向量数据库替换当前 `D1 全量加载 + 内存相似度计算`。
- 保持现有 `Strong Router + precomputed match` 架构不变。
- 在 1-2 周内上线可灰度、可回滚的生产版本。
## 2. 现状与问题
- 向量存储在 D1 文本字段，检索时需要全量拉取后计算。
- D1 无 ANN 索引，规则规模增长后时延和成本快速上升。
- Workers 存在执行时长与内存限制，稳定性风险高。
- 冲突检测与在线检索共用低效路径，写入链路被拖慢。
## 3. 选型结论
### 3.1 主方案
- 选型：`Qdrant`（Docker 自建）作为向量检索底座。
### 3.2 选择理由
- 轻量部署，适合当前团队和体量。
- HNSW + payload filter 能满足多租户、启停、版本过滤。
- 快照与恢复简单，便于生产运维。
- TS/Python 接入成本低，便于过渡。
### 3.3 不选说明
- `Milvus`：能力强但运维复杂度更高。
- `pgvector`：可复用数据库，但 ANN 场景下性能弹性不足。
- 托管向量库：便捷但成本与内网控制不如自建。
## 4. 目标架构
### 4.1 组件
1. `Rule Store`：规则事实存储（D1/后续 PostgreSQL）。
2. `Embedding Service`：统一向量化、模型版本管理。
3. `Vector Search Service`：检索、聚合、冲突检测。
4. `Qdrant`：向量索引与过滤。
5. `Runtime/Router`：使用预计算结果做最终决策。
### 4.2 在线读链路
1. Runtime 收到 query。
2. Runtime 调 `Vector Search Service.match_rules`。
3. Service 生成 query embedding。
4. Service 检索 Qdrant，按 `rule_id` 聚合分数。
5. 返回 TopK，Runtime 注入 `[RULE_MATCH_RESULTS]`。
6. Router 按既有策略决策并派单。
### 4.3 写入链路
1. `rule_builder` 产出/更新 `rule_json`。
2. Rule Store 落库成功后触发异步向量任务。
3. Embedding Service 生成 anchor/examples 向量。
4. Vector Service upsert 到 Qdrant。
5. 更新规则向量状态（`ready/pending/failed`）。
## 5. 数据模型
### 5.1 Collection
- 主集合：`agent_rule_segments`
### 5.2 Point 拆分
- 每条规则拆为：1 个 anchor（`match_text`）+ N 个 example（`examples[i]`）。
- `point_id`：
  - `rule:{rule_id}:anchor`
  - `rule:{rule_id}:ex:{idx}`
### 5.3 Payload 字段
- `rule_id` string
- `segment_type` enum(`anchor`,`example`)
- `segment_index` int
- `tenant_id` string
- `enabled` bool
- `priority` int
- `rule_version` int
- `embedding_model` string
- `updated_at` RFC3339
### 5.4 Qdrant 参数建议
- Distance: `Cosine`
- HNSW: `m=32`, `ef_construct=256`
- Search: `ef=128`（按延迟再调到 256）
- 首发不启用量化
## 6. 检索与打分
### 6.1 召回
- 先检索 `topN=50`。
- 过滤条件：`tenant_id`、`enabled=true`。
### 6.2 聚合
- 同 `rule_id` 采用 Max Fusion：
```text
rule_score = max(score(anchor), max(score(examples)))
```
### 6.3 阈值
- `>= 0.72`：高置信，Router 优先 `rule_reply`。
- `0.60 ~ 0.72`：候选，交 Router 二次判断。
- `< 0.60`：未命中。
### 6.4 冲突检测（写入前）
- 自检索排除自身 rule_id：
  - `> 0.92`：阻断保存。
  - `0.82 ~ 0.92`：告警并要求确认。
  - `< 0.82`：允许保存。
## 7. 接口契约
### 7.1 `POST /vector/match_rules`
请求：
```json
{
  "tenant_id": "bus-prod",
  "query": "我想查司机张三的违规记录",
  "top_k": 5,
  "min_score": 0.6
}
```
响应：
```json
{
  "success": true,
  "data": {
    "matches": [
      {"rule_id": "rule-violation-001", "score": 0.81, "best_segment_type": "example"}
    ],
    "latency_ms": 47
  }
}
```
### 7.2 `POST /vector/upsert_rule`
- 输入：`rule_id + match_text + examples + metadata`
- 输出：upsert 成功/失败与错误详情
### 7.3 `POST /vector/rebuild`
- 支持按租户/时间窗口/全量重建
- 支持 dry-run 和并发限制
## 8. 系统改造点
### 8.1 Runtime
- 新增开关：`VECTOR_SEARCH_ENABLED`
- `match_rules` 改为 HTTP 调向量服务
- 失败自动回退旧逻辑
### 8.2 Rule Builder / 管理端
- 规则保存后触发向量更新任务
- 展示 `vector_status`
- 支持手动重建向量
### 8.3 规则表新增字段
- `embedding_model` TEXT
- `embedding_version` INTEGER
- `vector_status` TEXT
- `vector_updated_at` TEXT
- `vector_error` TEXT
## 9. 发布计划
### Phase 0（1 天）
- 部署 Qdrant + Vector Service
- 建 collection 和基础索引
### Phase 1（1-2 天）
- 离线回填历史规则向量
- 输出回填报告
### Phase 2（1 天）
- 开启双写（旧存储 + Qdrant）
- 读路径仍走旧逻辑
### Phase 3（2-3 天）
- 灰度双读（10% -> 50% -> 100%）
- 评估时延、命中率、新旧差异
### Phase 4（1 天）
- 切主到新读路径
- 保留旧开关 2 周
## 10. 验收标准
- 性能：`match_rules` P95 < 120ms，P99 < 200ms
- 稳定性：向量写入成功率 >= 99.9%
- 可用性：服务可用性 >= 99.9%
- 质量：`Recall@5 >= 0.95`，Top1 命中率不低于旧方案
## 11. 监控与运维
- 指标：检索时延/QPS/错误率、upsert 成功率、embedding 时延、Qdrant 时延
- 日志：仅记录 query hash、topK、最终命中，不落原始敏感文本
- 备份：每日 snapshot（保留 7 天），每周冷备（保留 4 周）
- 演练：每月一次恢复演练
## 12. 安全
- Qdrant 与 Vector Service 仅内网访问
- 服务间 token 鉴权
- 强制 `tenant_id` 过滤，防跨租户命中
- API Key 走环境变量/密钥管理，不入库
## 13. 回滚策略
触发条件（任一满足）：
- 15 分钟错误率 > 2%
- P95 > 300ms 且持续
- Top1 命中率较基线下降 > 10%
回滚步骤：
1. 关闭 `VECTOR_SEARCH_ENABLED`
2. Runtime 切回旧检索路径
3. 保留双写，暂停新读流量
4. 修复后再灰度恢复
## 14. 默认配置
```env
VECTOR_SEARCH_ENABLED=true
VECTOR_SHADOW_COMPARE_ENABLED=true
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_EMBEDDING_MODEL=text-embedding-v1
OPENAI_API_KEY=***
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION_RULES=agent_rule_segments
QDRANT_SEARCH_TOPN=50
QDRANT_MIN_SCORE=0.60
QDRANT_HIGH_SCORE=0.72
```
## 15. 落地任务清单
1. 新建 `vector-service`（可先 TS 后 Python）。
2. 实现 `match_rules/upsert_rule/rebuild/detect_conflict`。
3. Runtime 接入并加 fallback。
4. 管理端加向量状态与重建入口。
5. 完成压测、评估、监控、告警。
## 16. 知识库设计（新增）
- 结论：不建议“索引管理替代向量化”，建议“向量检索 + 索引管理 + Git 式版本管理”三层并行。
- 数据层：文档原文存对象存储（MinIO/S3），元数据入库（doc_id、tenant_id、acl、source、hash、version）。
- 版本层（Git 式）：知识库按 `branch/tag/commit` 管理，支持灰度分支、回滚、审计；可落地 `lakeFS` 或 `DVC`。
- 索引层：同一知识版本同时构建 `dense`（语义）+ `sparse/BM25`（关键词）索引。
- 发布层：采用“新索引构建完成 -> alias 原子切换（蓝绿）-> 老索引延迟下线”。
- 检索层：`Hybrid Retrieval (dense+sparse) -> Rerank -> 上下文组装 -> LLM`。
- 权限层：检索时强制 `tenant_id + acl` filter，禁止跨租户召回。
- 质量层：离线评估 `Recall@k/NDCG@k`，在线看 `Top1 命中率/人工纠错率`。
- 运维层：索引快照与知识版本绑定（可一键回滚“数据+索引”到同一版本）。
- 实施顺序：先上向量库替换（本方案），再补 Git 式版本层，最后上线 hybrid 与 rerank。
结论：按本精简方案执行，可在低风险前提下完成向量库生产替换，并为后续知识库 RAG 扩展保留空间。
