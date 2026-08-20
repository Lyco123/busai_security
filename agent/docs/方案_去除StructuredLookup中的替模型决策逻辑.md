# 方案：去除 `structured-lookup.ts` 中的“替模型决策”逻辑

## 1. 背景

当前链路中，`structured-lookup.ts` 承担了两类职责：

1. 解析和维护结构化报告所需的对象查找状态
2. 在 Router 之前，基于规则和本地匹配结果，替大模型提前做部分决策

第二类职责的典型表现包括：

- 用硬编码关键词判断某条消息是不是“车辆报告 / 驾驶员报告 / 线路报告 / 事故调查”
- 在进入 Router LLM 之前，直接决定是否走 `generate_*_report`
- 在部分场景下，优先走本地对象解析，而不是让模型结合当前可用工具自行判断

这会带来两个问题：

- 决策边界逐渐写死，新表达方式容易被误判
- 问题被前置短路后，模型失去利用工具和上下文自行修正的机会

本方案的目标是：**把“替模型做决定”的部分尽量移除，先做 Prompt-first 的路由实验；如果效果不达标，再按最小范围加回确定性保护。**

## 2. 总体结论

结论不是“删除整个 `structured-lookup.ts`”，而是：

- **删除其中替模型决策的逻辑**
- **保留其中纯状态管理和纯工具性能力**

换句话说，目标是把 `structured-lookup.ts` 从“半个规则路由器”收缩成“结构化状态与对象解析工具箱”。

这是可行的，但必须分阶段进行，不能一步到位直接删除全部能力。

## 3. 什么叫“替模型做决定”

本次要去掉的，是下面这类逻辑：

- `looksLikeDriverReportRequest()`
- `looksLikeVehicleReportRequest()`
- `looksLikeRouteReportRequest()`
- `looksLikeAccidentInvestigationReportRequest()`
- Router 中基于这些布尔值直接进入 `handle*ReportResolution()` 或直接返回“缺少对象信息”的前置短路
- 任何“只要命中若干关键词，就跳过 Router LLM 直接决定 worker”的逻辑

这些逻辑的共同特点是：

- 输入是自然语言
- 输出是高层决策
- 决策本应由模型结合工具能力、当前提示词、历史上下文共同完成

## 4. 哪些能力不建议删除

以下能力不属于“替模型做决定”，不建议在第一阶段删除：

### 4.1 多轮澄清状态

例如：

- `pending_structured_lookup`
- follow-up rewrite
- “是这个 / 就这个 / 不是 / 第三个” 这类确认态的续接

原因：

- 这部分更像会话状态机，不是高层语义路由
- 仅靠模型记忆做这类续接，稳定性通常明显更差

### 4.2 已解析对象的结构化表示

例如：

- `DriverLookupResolution`
- `VehicleLookupResolution`
- `RouteLookupResolution`
- `IncidentLookupResolution`

原因：

- 它们是中间数据结构，不是决策本身
- 即便后续仍需要对象查找，这种结构化表示仍然有价值

### 4.3 纯查找函数本身

例如：

- `resolveDriverLookup()`
- `resolveVehicleLookup()`
- `resolveRouteLookup()`
- `resolveIncidentLookup()`

原因：

- 这些函数可以从“前置强制执行”改为“模型触发后调用”
- 它们本身是能力，不一定是约束

真正要删除的是“谁来决定什么时候用这些函数”。

## 5. 目标架构

目标架构应当是：

1. 用户消息进入 `router-service.ts`
2. Router LLM 先结合提示词、场景、可用工具列表做决策
3. 模型自行决定：
   - 走 `consult_omni`
   - 走 `consult_vehicle_expert`
   - 走 `generate_*_report`
   - 或先调用对象查找 / MCP 工具
4. 只有在出现明确的多轮澄清状态时，才使用 `structured-lookup` 的状态能力辅助续接

即：

- `structured-lookup` 不再主导“是否进入某类 worker”
- `structured-lookup` 只在“模型已经决定需要结构化对象查找”时提供能力

## 6. 推荐技术路线

建议分三阶段推进。

### 阶段 A：Prompt-first，移除前置报告判断

目标：

- 去掉 Router 中基于 `looksLike*ReportRequest()` 的前置判定和短路
- 保留 `pending_structured_lookup` follow-up 能力
- 保留对象解析函数，但不再由 Router 默认调用

具体做法：

1. 删除或停用以下“高层判定”函数的调用：
   - `looksLikeDriverReportRequest()`
   - `looksLikeVehicleReportRequest()`
   - `looksLikeRouteReportRequest()`
   - `looksLikeAccidentInvestigationReportRequest()`
2. 删除 Router 中这几类前置分支：
   - “像报告请求但缺对象，直接返回缺信息提示”
   - “像报告请求，直接进入 `handle*ReportResolution()`”
3. 保留：
   - `extractDirectStructuredToolCall`
   - follow-up rewrite
   - `pending_structured_lookup` 解析与恢复

这一阶段的核心思想是：

- 模型先决定“这是报告还是普通查询”
- 而不是代码先决定

### 阶段 B：把对象查找从“前置自动执行”改成“可调用工具”

目标：

- 让模型在需要时主动调用对象查找能力
- 而不是由 Router 帮它先查

推荐实现方式：

1. 把 driver / vehicle / route / incident lookup 封装成显式工具
2. 在 Router/Worker 的 tool list 中暴露，例如：
   - `resolve_driver_candidate`
   - `resolve_vehicle_candidate`
   - `resolve_route_candidate`
   - `resolve_incident_candidate`
3. 工具返回：
   - `resolved`
   - `ambiguous`
   - `not_found`
   - 候选列表
4. 由模型根据返回结果决定：
   - 继续澄清
   - 继续报告生成
   - 改走基础信息查询工具

这样做的价值是：

- 能力还在
- 但决策权回到模型

### 阶段 C：仅按需要恢复最小保护

如果阶段 A/B 表现退化，再加回“最小必要保护”，而不是恢复原有整套前置逻辑。

只建议恢复两类保护：

1. 明确格式化 follow-up 保护
2. 明确对象歧义保护

不建议恢复：

- 大而泛的关键词报告判断
- Router 前置强制分流
- “像某类请求”就提前替模型决定 worker

## 7. Prompt-first 方案应如何设计

如果要把决策权交还给模型，提示词必须更强，不然只是简单撤防。

## 7A. 删除项与提示词接管项映射

这一节回答的不是“删什么”，而是“删掉之后，提示词具体接什么”。

### 7A.1 删除 `looksLike*ReportRequest()` 后，由 Router Prompt 接管的判断

代码里被删除的判断包括：

- `looksLikeDriverReportRequest()`
- `looksLikeVehicleReportRequest()`
- `looksLikeRouteReportRequest()`
- `looksLikeAccidentInvestigationReportRequest()`

这些判断删掉之后，Router Prompt 必须显式接管下面四个问题：

1. 当前请求是“普通查询”还是“结构化报告”
2. 如果是结构化报告，对象是否已经足够明确
3. 如果对象不明确，是先澄清还是先调用对象解析工具
4. 如果不是结构化报告，应优先走哪个具体工具

Router Prompt 里需要补的关键指令应包括：

- 先判断用户目标是“查询事实 / 查询统计 / 查询列表 / 查询基础信息 / 生成报告”中的哪一种
- “信息 / 详情 / 属性 / 明细 / 列表 / 统计”默认不是报告
- “报告 / 画像 / 风险分析 / 调查报告 / 整改报告”才优先视为报告
- 若请求同时包含对象词和查询词，不得仅凭“车辆 / 司机 / 线路 / 事故”这些实体名就直接进入报告 worker
- 若存在专用 MCP 工具，优先选 MCP，不要默认回退 `query_data`

对应效果：

- 以前代码在做“这是不是报告”
- 改成 Prompt 让模型自己做“任务类型判别”

### 7A.2 删除“缺对象就直接返回补充提示”后，由 Router Prompt 接管的判断

当前被移除的典型行为是：

- 像报告请求，但没有对象
- Router 直接返回“请提供车牌号 / 驾驶员姓名 / 线路名”这类固定回复

这部分删掉之后，Router Prompt 需要接管：

1. 是否真的缺少关键对象
2. 缺少时该直接澄清，还是能先用工具搜候选
3. 澄清时应该问最小必要问题，而不是泛泛追问

Router Prompt 需要新增明确要求：

- 只有当当前工具无法可靠定位对象时，才向用户追问
- 如果消息里已经出现车牌号、工号、线路名、事故编号等标识，优先尝试工具定位，不要先追问
- 追问必须只问最小必要字段，不要一次把所有字段都要一遍
- 若候选可枚举，应优先给出候选而不是只说“信息不足”

对应效果：

- 以前代码在做“是否缺参数”
- 改成 Prompt 让模型自己做“是否需要澄清”的判断

### 7A.3 删除 `handle*ReportResolution()` 的前置进入逻辑后，由 Router Prompt 接管的判断

当前被移除的行为是：

- 命中特定模式后，Router 不再让模型选 worker
- 而是直接进入 `handleDriverReportResolution()` / `handleVehicleReportResolution()` / `handleRouteReportResolution()` / `handleIncidentReportResolution()`

这部分删掉之后，Router Prompt 需要接管：

1. 该不该进入 `generate_*_report`
2. 进入前是否应先做对象解析
3. 是否其实应该走 `consult_omni` 或 `consult_vehicle_expert`

Router Prompt 里应写清楚：

- 只有用户明确要“报告 / 画像 / 调查 / 风险分析结果”时，才考虑 `generate_*_report`
- 基础信息查询、统计查询、列表查询，不要进入报告 worker
- 如果对象不明确，先做对象确认，再进入报告 worker
- 若请求可以由一个更具体的 MCP 工具直接完成，不要绕到报告生成

对应效果：

- 以前代码在做“选哪个 worker”
- 改成 Prompt 让模型自己做“worker 选择”

### 7A.4 删除“本地对象解析优先于模型判断”后，由 Tool-aware Prompt 接管的判断

当前被弱化或移除的行为是：

- Router 先用本地对象解析函数查人、查车、查线路、查事故
- 模型只能接收解析后的结果，不能主导是否先查对象

这部分调整后，提示词需要接管：

1. 什么时候应该先查对象
2. 什么时候应该直接查 MCP
3. 查对象失败后下一步是什么

这里需要两类提示词配合：

- Router Prompt：决定是否先调用对象解析工具
- Worker Prompt：如果要生成报告，但对象尚未确认，禁止直接继续生成

Router Prompt 应补：

- 需要唯一对象的任务，若对象尚不唯一，应先解析对象或先澄清
- 只做事实查询时，如果 MCP 工具能直接按车牌/工号/线路查明细，则优先直接查业务数据

Worker Prompt 应补：

- 对象未唯一确认时，不得直接生成报告
- 如果当前只有模糊候选，先要求调用对象解析工具或要求澄清

### 7A.5 删除“基础查询误入报告流”的保护后，由 Prompt 明确边界

这是当前最容易出问题的一类。

需要在 Router Prompt 明确写成硬边界的内容：

- “车辆信息 / 车辆详情 / 车辆属性 / 车辆基础信息”不是车辆报告
- “每种车型数量 / 使用性质统计 / 车辆列表”不是车辆报告
- “驾驶员基础信息 / 驾驶员明细”不是驾驶员报告
- “线路明细 / 线路列表 / 线路统计”不是线路报告
- “事故详情 / 事故记录查询”不是事故调查报告

同时补充正向定义：

- 明确出现“报告 / 画像 / 风险分析 / 调查报告 / 整改报告 / 总结报告”时，优先考虑报告 worker

对应效果：

- 以前这类边界靠代码里的关键词函数
- 改成在 Router Prompt 中显式声明任务边界

### 7A.6 哪些内容不交给提示词，而是继续保留在代码里

为了防止方案失控，需要明确：不是所有内容都交给提示词。

仍建议保留在代码中的包括：

- `pending_structured_lookup` 状态结构
- follow-up rewrite
- 候选对象的结构化表示
- 对象解析函数本身
- feature flag 与 shadow 评估埋点

原因是：

- 这些是基础设施或能力模块
- 它们不直接替模型做高层语义决策
- 它们只是让模型有状态、有工具可用

### 7.1 Router Prompt 要补的内容

Router 提示词里应明确要求模型先做以下区分：

1. 这是普通问答、统计查询、基础信息查询，还是结构化报告请求
2. 如果是结构化报告，是否已经具备明确对象标识
3. 如果对象不明确，是先澄清，还是先调用对象查找工具
4. 如果有更具体的 MCP 工具，优先使用 MCP，而不是走泛化 `query_data`

尤其要写清楚以下边界：

- “车辆信息 / 基础信息 / 详情 / 属性”不等于“车辆报告”
- “每种车型数量 / 使用性质统计”不等于“单车报告”
- 只有用户明确要求“报告 / 画像 / 风险分析 / 调查报告”时，才优先考虑 `generate_*_report`

除此之外，Router Prompt 还应补上动作顺序：

1. 先判别任务类型
2. 再判别对象是否明确
3. 再决定是直接查 MCP、先解析对象、还是先澄清
4. 最后才决定进入哪个 worker

也就是把原来散落在代码中的“先验判断顺序”转移到 Prompt 中显式写给模型。

### 7.2 Worker Prompt 要补的内容

报告类 worker 的提示词里应强调：

- 不能在对象未确认时直接生成报告
- 如果只有模糊对象，必须先澄清或调用对象解析工具
- 不能把基础信息查询误当成报告生成

除此之外，还应按 worker 类型补充禁止项：

- `generate_vehicle_report`：不得把“车辆信息 / 车辆详情 / 车牌查明细”当成车辆报告
- `generate_driver_report`：不得把“驾驶员信息 / 工号查人”当成驾驶员画像
- `generate_route_report`：不得把“线路详情 / 线路统计”当成线路报告
- `generate_accident_investigation_report`：不得把“事故记录查询 / 事故详情”当成调查报告

也就是说，Worker Prompt 不只负责“怎么写报告”，还要负责“什么时候不该写报告”。

### 7.3 Tool Description 要补的内容

如果不再靠前置规则兜底，工具描述必须更清楚。

重点是：

- 某个工具解决什么问题
- 什么时候该用它
- 什么时候不该用它
- 参数是业务含义，不只是字段名

具体需要补到工具描述里的内容包括：

- `get_mcp_base_odsJituanBsBus_list`：
  - 用于单车基础信息、车辆列表、按车牌/自编号筛选
  - 不用于生成车辆风险报告
- `get_mcp_base_odsJituanBsBus_vehicleTypelist`：
  - 用于车辆类型统计/分类
  - 不用于单车明细查询
- `get_mcp_base_odsJituanBsBus_useNatureCount`：
  - 用于使用性质统计
  - 不用于单车信息查询
- 对象解析类工具（如果后续引入）：
  - 用于“从模糊对象到唯一对象”
  - 不直接返回业务结论

这样做的目的，是把原先隐含在代码里的“工具使用边界”，显式前移到工具描述中。

这点在 [mcp-tool-description-guide.md](/d:/BUS/agent/docs/mcp-tool-description-guide.md) 中已有方向，但需要进一步针对“单车基础信息查询”和“结构化报告生成”做更明确区分。

## 8. 对表现的预期影响

### 8.1 可能提升的部分

- 自然表达覆盖率更高
- 不容易被硬编码关键词误伤
- 普通查询更容易走对 MCP 工具
- 新增工具后更容易被模型自然利用

### 8.2 可能下降的部分

- 报告类请求的对象确认精度
- 多轮确认稳定性
- 同名对象、模糊车牌、模糊线路时的保守性
- 一些边缘 case 的可解释性

### 8.3 最可能出现的退化形式

1. 该澄清时不澄清，直接用错对象
2. 把基础信息查询误当报告
3. 把报告请求误当普通问答
4. 多轮确认丢状态
5. 工具调用路径发散，出现不必要的 `query_data`

## 9. 实验设计

这个方案应按实验推进，而不是直接全量切换。

### 9.1 建议开关

增加独立 feature flag，例如：

- `prompt_first_structured_lookup_routing`

控制粒度：

- `off`: 保持现状
- `shadow`: 新链路只记录决策，不生效
- `partial`: 仅车辆域生效
- `on`: 全量生效

### 9.2 建议先做 shadow 模式

shadow 模式下：

- 现网仍走旧链路
- 同时记录“如果按新策略，模型会怎么选”

要记录：

- 新旧链路选中的 worker 是否一致
- 新旧链路是否都调用了工具
- 新旧链路是否都命中了正确对象
- 新旧链路最终回复质量差异

### 9.3 建议先在车辆域试点

原因：

- 当前车辆域已经暴露出“前置判定过强”的问题
- MCP 工具更完整
- case 量通常更大，便于观察

但报告类对象确认风险也高，因此应只先去掉“车辆报告前置判定”，不要同时删除 follow-up 状态能力。

## 10. 评估指标

至少看以下指标：

### 10.1 路由正确率

- 普通查询是否进入正确 worker / 工具链
- 报告请求是否进入正确报告 worker

### 10.2 对象确认正确率

- 司机 / 车辆 / 线路 / 事故对象是否命中正确目标

### 10.3 澄清质量

- 该澄清时是否澄清
- 不该澄清时是否过度澄清

### 10.4 工具效率

- 平均工具调用次数
- 无效调用次数
- `query_data` 被错误兜底的比例

### 10.5 最终回答可用率

- 用户是否一次拿到想要的结果
- 是否出现“没查到，但其实工具能查到”的情况

## 11. 回滚策略

如果出现以下任一情况，应立即回滚到上一阶段：

- 报告类对象误命中显著上升
- 多轮确认成功率显著下降
- 正确工具命中率明显下降
- “基础信息查询误进报告流”问题没有改善，反而更散
- 客诉样本中出现明显幻觉增多

回滚顺序建议如下：

1. 先回滚“模型自主决定对象解析”
2. 再回滚“前置报告判断”
3. 最后保留 Prompt 改造部分

这样能最大限度保留已经验证有效的提示词优化。

## 12. 推荐落地顺序

推荐按以下顺序实施：

1. 先写清 Router Prompt 和 Worker Prompt 的新边界
2. 增加 feature flag
3. 去掉 `looksLike*ReportRequest()` 在 Router 的前置强决策作用
4. 保留 follow-up 状态能力不动
5. 观察车辆域表现
6. 需要时再把对象解析封装成显式工具
7. 最后再考虑是否继续削薄 `structured-lookup.ts`

## 13. 最终建议

建议采用的不是“删除 `structured-lookup.ts`”，而是：

- **先删除它替模型做决定的部分**
- **把对象解析降级为可被模型调用的能力**
- **把状态续接保留为基础设施**

这样更符合目标，也更容易验证：

- 如果 Prompt-first 能达到目标，就继续收缩规则
- 如果 Prompt-first 不够稳定，只加回最小必要保护

这条路线的关键不是“去规则化”，而是：

- 让规则从“替模型决策”退回到“提供状态和能力”
