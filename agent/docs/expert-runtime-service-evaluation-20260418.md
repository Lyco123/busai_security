# 专家体系方案评估与取舍

日期：2026-04-18

## 1. 评估结论

当前系统只有 5 个主要 domain：

- 驾驶员
- 车辆
- 单位
- 线路
- 事故

在这个规模下，不建议做重型通用 agent 平台。

更合适的是：

- 保留按 domain 组织的现有结构
- 只新增：
  - `Expert Registry`
  - `Shared Context Builder`

## 2. 为什么不建议上重方案

前一版方案包含：

- `Task Descriptor`
- `Expert Runtime Service`
- `Context Provider Framework`
- `Skill Pack`

这些抽象对大规模系统是成立的，但对当前系统偏重。

主要原因：

- domain 数量有限
- 任务形态有限
- 当前已有可复用主链路
- 过度抽象会抬高 prompt 和 runtime 的维护成本

## 3. 当前系统真正的问题

当前更实际的问题不是“没有框架”，而是：

- expert 配置散落
- 上下文注入散落
- deep COT 等策略没有集中管理

因此优先级应是“小收口”，不是“大平台化”。

## 4. 为什么保留 domain

对于当前系统，没有证据表明“去 domain 化”会更好。

保留 domain 的好处：

- 业务直观
- prompt 边界清晰
- router 和 worker 语义稳定
- 便于新增同类 expert

更合理的方向不是废弃 domain，而是：

- 保留 domain
- 减少重复实现

## 5. 联网调研结论

基于 2026-04-18 调研，官方资料整体都支持：

- 先用简单 workflow / manager pattern
- 不要过早做复杂多 agent 编排
- 把 context engineering 作为稳定性的重点

主要参考：

- Anthropic, *Building Effective AI Agents*  
  <https://www.anthropic.com/engineering/building-effective-agents>
- OpenAI, *A practical guide to building agents*  
  <https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/>
- LangChain, *Multi-agent*  
  <https://docs.langchain.com/oss/python/langchain/multi-agent>
- LangChain, *Context engineering in agents*  
  <https://docs.langchain.com/oss/python/langchain/context-engineering>
- LlamaIndex, *Routing*  
  <https://docs.llamaindex.ai/en/stable/module_guides/querying/router/>
- MCP Resources  
  <https://modelcontextprotocol.io/docs/concepts/resources>
- MCP Prompts  
  <https://modelcontextprotocol.io/specification/2025-06-18/server/prompts>

## 6. 取舍结果

### 本轮建议做

- `Expert Registry`
- `Shared Context Builder`
- deep COT 统一入口

### 本轮不建议做

- 完整 `Task Descriptor` 体系
- Skill Pack 拆分
- Context Provider 插件框架
- 多 agent handoff
- 通用 agent 平台化重构

## 7. 推荐路线

短期：

- 做轻量收口

中期：

- 如果后续真的增加更多 expert 和上下文来源，再考虑继续抽象

长期：

- 只有在 domain、任务类型、维护人数都明显增长后，再评估是否升级为重型运行时框架

