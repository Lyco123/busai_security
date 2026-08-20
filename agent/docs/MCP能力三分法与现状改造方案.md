# MCP 能力三分法与现状改造方案

## 1. 目标

本文档用于给当前 Agent 系统的能力面做统一分层，回答四个问题：

1. 哪些能力应继续直接继承 MCP 的动态性。
2. 哪些能力只需要做轻包装，不值得上升为高层业务工具。
3. 哪些能力已经出现明显语义断裂，应该收敛为少量稳定的领域视图或领域能力。
4. 各类能力当前对模型是否可见，可见到哪一层。

这里强调的不是“每个业务场景一个工具”，而是：

- 大部分能力仍然动态继承 MCP。
- `query_data` 仅作为当前阶段的 demo/兼容过渡层，不应被视为最终长期形态。
- 少量高频、复杂、易错、跨源的核心能力做稳定收口。
- 收口粒度按“稳定语义对象/动作”划分，不按用户问法划分。
- 能力分类和模型可见性是两张不同的表，必须同时维护。

---

## 2. 三分法定义

### A. 直接直出能力

定义：
- 能力职责单一。
- 输入输出边界清晰。
- 返回结果基本就是用户或上层 worker 需要的原子数据。
- 不需要跨多个数据源拼装。
- 不需要写很多 prompt 补丁规则兜底。

适合：
- 搜索类、读取类、列表类、统计类、单接口详情类。
- 长尾低频场景。
- 新接入 MCP 的通用能力。

策略：
- 由 runtime registry 动态发现并暴露。
- 只做命名、描述、权限、allow list 之类的薄控制。

### B. 轻包装能力

定义：
- 底层仍然是单一来源或近似单一来源。
- 但直接暴露给模型会产生轻度理解负担。
- 需要统一字段名、约束查询动作、规范返回格式。

适合：
- 抽象查询接口。
- 统一 schema 的 get/list/search/describe。
- 动态直出工具的轻量别名和轻量筛选。

策略：
- 保持动态能力面。
- 用少量代码把底层能力映射成更稳定的 agent 可消费接口。
- 不做复杂业务拼装，不承接跨源口径裁决。

### C. 高层领域视图 / 领域能力

定义：
- 同一业务对象分散在多个底层源。
- 一个任务经常要跨多个 MCP 才能稳定完成。
- 同一概念在不同源里字段命名或业务口径不一致。
- prompt 中已经堆了很多“优先用什么、不要误用什么、字段信谁”的补丁规则。
- 同类问题在不同链路中容易出现工具选择漂移、字段拼装不一致或误进报告流。

适合：
- 高频核心业务对象。
- 跨源且口径复杂的动作。
- 已经成为系统断裂点的能力。

策略：
- 只保留少量稳定视图，不按场景碎裂。
- 对外暴露的是稳定语义，不暴露底层源差异。
- 底层 MCP 的变化优先收敛在领域边界内，不向 prompt、router、worker 大面积扩散。

---

## 3. 当前系统现状概览

### 3.1 当前已经存在的三层雏形

1. 协议统一层
   - 文件：`agent/src/shared/mcp.ts`
   - 作用：统一 `initialize / tools/list / tools/call`，完成 MCP 协议适配。

2. 动态工具注册层
   - 文件：`agent/src/app/runtime.ts`
   - 作用：通过 `MCPToolProvider`、`HybridToolProvider` 动态发现并合并 MCP 与本地工具。

3. 过渡查询层
   - 文件：`agent/src/app/runtime.ts`
   - 作用：当前通过 `query_data` demo 一部分统一查询能力，后续应逐步由真实 MCP 接入替代或改为 MCP-backed facade。

4. 局部语义适配层
   - 文件：`agent/src/shared/vehicle-profile-mcp.ts`
   - 文件：`agent/src/domains/chat/structured-report-data-sources.ts`
   - 作用：针对少数任务做结果重整或数据源限制。

### 3.2 当前主要问题

当前问题不在“没有统一协议”，而在“业务语义层尚未按领域收口”。

具体表现：

- 车辆域语义分散在多个位置：
  - `query_data(vehicle)` schema：`agent/src/app/runtime.ts`
  - 车辆画像专用适配：`agent/src/shared/vehicle-profile-mcp.ts`
  - 车辆报告专用外部数据源约束：`agent/src/domains/chat/structured-report-data-sources.ts`
  - 车辆报告归一化：`agent/src/domains/chat/structured-report-normalizers.ts`
  - 车辆专家 prompt：`agent/skills/conversational/vehicle_expert/SKILL.md`
- 同一个业务对象没有单一 canonical view。
- prompt 正在承担一部分本应由代码承担的数据策略职责。
- 报告链路和问答链路对同一个对象的字段口径没有统一出口。
- 核心对象以外的能力边界尚未明确分层，后续继续加能力时容易扩散。
- `query_data` 当前承担了过多“未来会被真实 MCP 替代”的过渡职责，文档中不能把它误写成终局架构。

### 3.3 当前模型可见性现状

当前系统不是“一个模型看到全部工具”，而是至少存在三层工具面：

1. Router 顶层工具面
   - 用于路由和分发。
   - 当前可见：
     - `match_rules`
     - `generate_driver_report`
     - `generate_vehicle_report`
     - `generate_route_report`
     - `generate_accident_investigation_report`
     - `consult_omni`
     - `consult_vehicle_expert`
     - `rule_reply`
     - `request_further_info`

2. Worker 执行工具面
   - 由 `LocalToolProvider`、`MCPToolProvider`、`HybridToolProvider` 提供。
   - 本地固定可见：
     - `query_data`
     - `get_rule`
     - `get_rule_draft`
     - `update_rule_draft`
     - `submit_rule_turn`
     - `rule_exit`
     - `request_further_info`
   - 动态 MCP 工具由 provider 自动发现后加入。

3. Scoped worker 工具面
   - 某些 worker 实际看到的是 allow list 过滤后的子集。
   - `ScopedToolProvider` 会做工具收缩。
   - `request_further_info` 是例外，即使不在 allow list 中也会被保留。

### 3.4 当前容易混淆的点

- `generate_vehicle_report`、`consult_omni`、`consult_vehicle_expert`、`rule_reply` 是 Router 可调度的 worker 能力，不是 provider 数据工具。
- `rule_asker`、`rule_builder` 是 worker 类型，不是 `LocalToolProvider` 暴露出来的工具。
- `get_rule_draft`、`update_rule_draft`、`submit_rule_turn`、`rule_exit` 才是规则 worker 执行过程中真正调用的 provider 工具。
- `query_data` 是当前 demo/兼容查询层，不代表未来其他域不会像车辆一样改为真实 MCP 接入。

### 3.5 当前潜在故障点：工具暴露链路

除数据语义问题外，工具“如何被暴露给模型”本身也是潜在故障点。

典型风险：

- registry 注册遗漏，导致工具实际可用但模型不可见。
- visibility 或 allow list 配错，导致工具暴露过宽或过窄。
- scoped provider 配置错误，导致 worker 看不到关键工具，或看到了不该看到的工具。
- description、枚举、可见性元数据不一致，导致文档、代码、实际行为三者偏离。
- 新 MCP 接入后没有做暴露面校验，导致上线时才发现 Router/Worker 工具面异常。

结论：

- “工具暴露”应被视为一条独立的故障治理链路。
- 后续改造不只是整理能力分类，还要给工具暴露面加校验、测试和 fail-closed 机制。
- “能力三分法”描述的是语义层。
- “工具对模型的可见性”描述的是暴露层。
- 后续新增能力，必须同时回答“它属于哪一类”和“谁能看到它”。

---

## 4. 能力清单三分法归类

本文按“当前系统已实现 + 近期业务明确需要”的范围整理。

### 4.1 控制与编排类能力

这类能力不属于 MCP 语义收口问题，应继续保持系统内部能力。

#### 4.1.1 Router 顶层分发能力

| 能力 | 当前实现 | 分类 | 模型可见性 | 说明 |
| --- | --- | --- | --- | --- |
| 规则匹配 | `match_rules` | 内部控制能力 | Router 可见 | 用于规则命中，不属于数据接入层 |
| 驾驶员报告分发 | `generate_driver_report` | 内部控制能力 | Router 可见 | 顶层 worker 分发入口，不是 provider 数据工具 |
| 车辆报告分发 | `generate_vehicle_report` | 内部控制能力 | Router 可见 | 顶层 worker 分发入口，不是 provider 数据工具 |
| 线路报告分发 | `generate_route_report` | 内部控制能力 | Router 可见 | 顶层 worker 分发入口，不是 provider 数据工具 |
| 事故调查报告分发 | `generate_accident_investigation_report` | 内部控制能力 | Router 可见 | 顶层 worker 分发入口，不是 provider 数据工具 |
| 通用咨询分发 | `consult_omni` | 内部控制能力 | Router 可见 | 顶层 worker 分发入口 |
| 车辆专家分发 | `consult_vehicle_expert` | 内部控制能力 | Router 可见 | 顶层 worker 分发入口 |
| 规则回复分发 | `rule_reply` | 内部控制能力 | Router 可见 | 顶层规则执行入口 |
| 缺参续跑 | `request_further_info` | 内部控制能力 | Router 可见 | 用于挂起并等待下轮继续 |

#### 4.1.2 Worker 内部控制工具

| 能力 | 当前实现 | 分类 | 模型可见性 | 说明 |
| --- | --- | --- | --- | --- |
| 获取规则详情 | `get_rule` | 内部控制能力 | Worker 可见 | 规则执行期读取已保存规则详情 |
| 获取规则草稿 | `get_rule_draft` | 内部控制能力 | Worker 可见 | 规则配置流程读取草稿 |
| 更新规则草稿 | `update_rule_draft` | 内部控制能力 | Worker 可见 | 规则配置流程写回草稿 |
| 提交规则本轮提案 | `submit_rule_turn` | 内部控制能力 | Worker 可见 | 规则配置流程结构化提案 |
| 退出规则处理 | `rule_exit` | 内部控制能力 | Worker 可见 | 规则链路向 Router 回退 |
| 缺参续跑 | `request_further_info` | 内部控制能力 | Router 可见，Worker 可见 | 会话挂起和恢复控制工具 |
| 规则配置追问 worker | `rule_asker` | 内部控制能力 | 仅作为 worker 名称间接可见 | 它是 worker 类型，不是 provider 工具 |
| 规则编译 worker | `rule_builder` | 内部控制能力 | 仅作为 worker 名称间接可见 | 它是 worker 类型，不是 provider 工具 |

结论：

- 保持内部工具形态。
- 不纳入“高层领域视图”收口范围。
- 文档中必须区分“worker 名称”和“worker 可调用工具名称”。

### 4.2 通用查询层能力

#### 4.2.1 `query_data`（当前 demo/兼容层）

| 能力 | 当前实现 | 分类 | 模型可见性 | 说明 |
| --- | --- | --- | --- | --- |
| `query_data(describe/get/list/search)` | `agent/src/app/runtime.ts` | B. 轻包装能力 | Worker 可见；Router 不直接可见 | 当前是 demo/兼容查询层，后续应逐步改成 MCP-backed 或被真实 MCP 替代 |
| `driver` 抽象实体 | `DATA_SCHEMAS.driver` | B. 轻包装能力 | 通过 `query_data` 间接可见 | 当前由 `query_data` 承接，后续应补真实 MCP 接入 |
| `vehicle` 抽象实体 | `DATA_SCHEMAS.vehicle` | B. 轻包装能力 | 通过 `query_data` 间接可见 | 当前由 `query_data` 承接；车辆域会更早进入真实 MCP + 领域视图形态 |
| `route` 抽象实体 | `DATA_SCHEMAS.route` | B. 轻包装能力 | 通过 `query_data` 间接可见 | 当前由 `query_data` 承接，后续应补真实 MCP 接入 |
| `incident_case` 抽象实体 | `DATA_SCHEMAS.incident_case` | B. 轻包装能力 | 通过 `query_data` 间接可见 | 当前由 `query_data` 承接，后续应补真实 MCP 接入 |

结论：

- `query_data` 当前是系统可用的通用轻包装过渡层。
- 它不应被当成长期终局架构。
- 后续各域应逐步像车辆域一样接入真实 MCP，再决定是否仍保留一层 MCP-backed facade。
- 它不应承担复杂跨源口径统一。

#### 4.2.2 动态 MCP 直出

| 能力 | 当前实现 | 分类 | 模型可见性 | 说明 |
| --- | --- | --- | --- | --- |
| 车辆画像单车查询 | `get_mcp_base_absBusProfileMain_queryByNumberplate` | A. 直接直出能力 | 仅对特定 scoped worker 可见 | 单职责明确，但更适合作为底层源 |
| 车辆列表 | `get_mcp_base_odsJituanBsBus_list` | A. 直接直出能力 | 仅对命中 allow list 的 worker 可见 | 典型列表能力 |
| 车辆类型统计 | `get_mcp_base_odsJituanBsBus_vehicleTypelist` | A. 直接直出能力 | 仅对命中 allow list 的 worker 可见 | 单一统计能力 |
| 车辆使用性质统计 | `get_mcp_base_odsJituanBsBus_useNatureCount` | A. 直接直出能力 | 仅对命中 allow list 的 worker 可见 | 单一统计能力 |
| 其他动态 MCP 工具 | `MCPToolProvider` 动态发现 | A. 直接直出能力 | 默认 Worker 可见；可被 scoped allow list 限制 | 当前文档未逐个枚举，应补 registry 清单 |

结论：

- 这类能力继续保留在动态工具池中。
- 通过 allow list 和 prompt 描述控制使用边界。
- 不要全部都上升成高层工具。

### 4.3 车辆域

车辆域是当前系统最明显的断裂点，应作为第一优先级收口对象。

#### 4.3.1 继续直出或轻包装的车辆能力

| 能力 | 分类 | 模型可见性 | 原因 |
| --- | --- | --- | --- |
| 车辆列表查询 | A. 直接直出能力 | 仅对命中 allow list 的 worker 可见 | 列表能力边界清晰，低语义拼装 |
| 车辆类型统计 | A. 直接直出能力 | 仅对命中 allow list 的 worker 可见 | 单一统计，不需要跨源 |
| 车辆使用性质统计 | A. 直接直出能力 | 仅对命中 allow list 的 worker 可见 | 单一统计，不需要跨源 |
| 车辆通用详情 get/list/search | B. 轻包装能力 | Worker 可见；Router 不直接可见 | 当前由 `query_data(vehicle)` 承接；后续应逐步切到真实 MCP 接入后的统一查询面 |

#### 4.3.2 应收口为高层领域视图的车辆能力

| 稳定语义能力 | 分类 | 建议模型可见性 | 原因 |
| --- | --- | --- | --- |
| `vehicle.basic_info` | C. 高层领域视图 | 初期仅 Worker 内部复用；暂不直接暴露给 Router | 基础信息查询需要拼接档案字段与画像字段 |
| `vehicle.risk_snapshot` | C. 高层领域视图 | 初期仅 Worker 内部复用 | 风险分、风险等级、一级指标、核心风险因子口径应统一 |
| `vehicle.management_status` | C. 高层领域视图 | 初期仅 Worker 内部复用 | 管理闭环信息应统一出口 |
| `vehicle.report_source` | C. 高层领域视图 | 仅报告 Worker 内部复用 | 报告 worker 应读取统一报告源 |

#### 4.3.3 为什么车辆域必须收口

原因：

- 核心高频。
- 同一对象跨多个底层源。
- 已经出现“基础信息查询误进报告流”“报告链路与问答链路字段不一致”等问题。
- prompt 里已经出现较多工具选择补丁。
- 车辆专家和车辆报告都在重复承接同一批语义整理责任。

### 4.4 驾驶员域

| 能力 | 分类 | 建议模型可见性 | 说明 |
| --- | --- | --- | --- |
| 驾驶员详情查询 | B. 轻包装能力 | Worker 可见 | 当前由 `query_data(driver)` 承接，后续应接入真实 MCP |
| 驾驶员报告生成 | B. 轻包装能力 | Router 可见，Worker 内部依赖 `query_data` | 当前仍依赖 `query_data`，后续应迁移到真实 MCP 数据源 |
| 驾驶员基础信息视图 | C. 候选高层领域视图 | 初期仅 Worker 内部复用 | 若后续驾驶员画像话术要稳定落地，建议收口 |
| 驾驶员风险快照视图 | C. 候选高层领域视图 | 初期仅 Worker 内部复用 | 若驾驶员问答和报告开始共享大量口径，建议收口 |
| 驾驶员管理状态视图 | C. 候选高层领域视图 | 初期仅 Worker 内部复用 | 与管理效果话术强相关 |

结论：

- 驾驶员域当前断裂程度低于车辆域。
- 短期不必先做大范围高层视图。

### 4.5 线路域

| 能力 | 分类 | 建议模型可见性 | 说明 |
| --- | --- | --- | --- |
| 线路详情查询 | B. 轻包装能力 | Worker 可见 | 当前由 `query_data(route)` 承接，后续应接入真实 MCP |
| 线路报告生成 | B. 轻包装能力 | Router 可见，Worker 内部依赖 `query_data` | 当前仍依赖 `query_data`，后续应迁移到真实 MCP 数据源 |
| 线路基础信息视图 | C. 候选高层领域视图 | 初期仅 Worker 内部复用 | 若线路话术稳定化，需要统一线路基础信息 |
| 线路风险快照视图 | C. 候选高层领域视图 | 初期仅 Worker 内部复用 | 若问答与报告共用同一风险口径，应收口 |

结论：

- 线路域可作为车辆域之后的第二批收口对象。

### 4.6 事故域

| 能力 | 分类 | 建议模型可见性 | 说明 |
| --- | --- | --- | --- |
| 事故详情查询 | B. 轻包装能力 | Worker 可见 | 当前由 `query_data(incident_case)` 承接，后续应接入真实 MCP |
| 事故调查报告 | B. 轻包装能力 | Router 可见，Worker 内部依赖 `query_data` | 当前仍基于 `query_data` 组装，后续应迁移到真实 MCP 数据源 |
| 事故快照/事故管理视图 | A/B 保留 | 暂不新增独立可见工具 | 当前没有明显高频跨源断裂，暂不建议做高层视图 |

结论：

- 事故域当前不建议优先建设高层视图。

### 4.7 单位 / 组织 / 站场域

这些域在话术文档里已经存在，但当前代码里还不是一等实体。

| 能力 | 分类 | 建议模型可见性 | 说明 |
| --- | --- | --- | --- |
| 单位基础信息查询 | A/B 预留 | 当前先由 `query_data` 或轻包装 Worker 工具承接，后续应接入真实 MCP | 当前不急着做高层视图 |
| 单位画像快照 | C. 候选高层领域视图 | 仅在进入核心链路后再决定是否对模型暴露 | 仅当单位画像真正进入核心高频链路再收口 |
| 站场画像 / 站场基础信息 | A/B 预留 | 当前先由 `query_data` 或轻包装 Worker 工具承接，后续应接入真实 MCP | 当前尚不适合作为第一批高层视图 |

结论：

- 这些域先不要过早产品化为高层能力。

### 4.8 各工具对模型的可见性矩阵

下表描述的是“当前实际可见性”，不是“未来理想形态”。

| 工具/能力 | 类型 | Router 可见 | Worker 可见 | 动态/稳定 | 备注 |
| --- | --- | --- | --- | --- | --- |
| `match_rules` | 顶层控制工具 | 是 | 否 | 稳定 | 仅 Router 使用 |
| `generate_driver_report` | 顶层 worker 分发 | 是 | 间接，作为 worker 名称存在 | 稳定 | 不是 provider 数据工具 |
| `generate_vehicle_report` | 顶层 worker 分发 | 是 | 间接，作为 worker 名称存在 | 稳定 | 不是 provider 数据工具 |
| `generate_route_report` | 顶层 worker 分发 | 是 | 间接，作为 worker 名称存在 | 稳定 | 不是 provider 数据工具 |
| `generate_accident_investigation_report` | 顶层 worker 分发 | 是 | 间接，作为 worker 名称存在 | 稳定 | 不是 provider 数据工具 |
| `consult_omni` | 顶层 worker 分发 | 是 | 间接，作为 worker 名称存在 | 稳定 | 不是 provider 数据工具 |
| `consult_vehicle_expert` | 顶层 worker 分发 | 是 | 间接，作为 worker 名称存在 | 稳定 | 不是 provider 数据工具 |
| `rule_reply` | 顶层 worker 分发 | 是 | 间接，作为 worker 名称存在 | 稳定 | 规则执行入口 |
| `query_data` | 轻包装数据工具 | 否 | 是 | 过渡 | 当前是 Worker 的通用 demo/兼容查询入口 |
| `get_rule` | 内部控制工具 | 否 | 是 | 稳定 | 规则执行读取 |
| `get_rule_draft` | 内部控制工具 | 否 | 是 | 稳定 | 规则配置读取 |
| `update_rule_draft` | 内部控制工具 | 否 | 是 | 稳定 | 规则配置写入 |
| `submit_rule_turn` | 内部控制工具 | 否 | 是 | 稳定 | 规则配置提案 |
| `rule_exit` | 内部控制工具 | 否 | 是 | 稳定 | 从规则链路回退 |
| `request_further_info` | 内部控制工具 | 是 | 是 | 稳定 | Scoped provider 下也会保留 |
| 动态 MCP 工具 | 直出数据工具 | 否 | 视 allow list 而定 | 动态 | 由 `MCPToolProvider`/`HybridToolProvider` 暴露 |
| `vehicle.basic_info` 等候选领域视图 | 高层领域能力 | 当前无 | 当前无，建议仅内部复用 | 稳定 | 目前尚未正式落地为工具或 service 接口 |

结论：

- Router 看到的是“分发能力面”，不是完整数据工具面。
- Worker 看到的是“执行工具面”，其中包含本地工具和动态 MCP。
- 高层领域视图如果落地，初期应优先作为 Worker 内部能力或 service，而不是立即变成 Router 顶层工具。

---

## 5. 推荐的目标能力面

面向模型的能力面应同时存在两条轨道。

### 5.1 轨道 A：动态 MCP / 轻包装能力

保留：

- 动态注册的列表类、统计类、单接口详情类 MCP
- 低频、长尾、单职责清晰的能力
- `query_data` 作为迁移期兼容层暂时保留

目标：

- 保留 MCP 的动态性。
- 让各域最终都以真实 MCP 接入为主。
- `query_data` 只承担迁移期兼容职责，不继续无限扩张。

### 5.2 轨道 B：少量稳定领域视图

第一批建议只做车辆域：

- `vehicle.basic_info`
- `vehicle.risk_snapshot`
- `vehicle.management_status`
- `vehicle.report_source`

第二批可选：

- `driver.basic_info`
- `driver.risk_snapshot`
- `driver.management_status`
- `route.basic_info`
- `route.risk_snapshot`

原则：

- 只做少量视图。
- 一个视图对应一个稳定语义动作。
- 不按用户问法碎裂工具面。
- 初期优先作为 Worker 内部可复用能力，不急于全部提升为 Router 顶层可见工具。

### 5.3 推荐的可见性分层

建议把能力是否“对模型可见”也明确分层：

1. Router 顶层可见
   - 只保留分发型、会显著改变链路走向的能力。
   - 例如：`generate_*_report`、`consult_*`、`rule_reply`、`request_further_info`。

2. Worker 执行期可见
   - 包括迁移期兼容工具和允许直出的动态 MCP。
   - 例如：`query_data`、列表/统计型 MCP、必要的规则控制工具。

3. 仅内部复用，不直接暴露给模型
   - 优先放这里的是高层领域视图。
   - 例如：`vehicle.basic_info`、`vehicle.report_source` 初期更适合作为 service/view 被 worker 复用。

4. Scoped 可见
   - 对高风险 worker 强制收窄工具面。
   - 例如车辆报告 worker 只允许读取指定画像源；车辆元数据 worker 只允许访问车辆列表/统计工具与 `query_data(vehicle)`。

原则：

- 能力分类解决“它是什么”。
- 可见性分层解决“谁能看到它”。
- 未来新增工具必须同时回答这两个问题。

---

## 6. 对现状需要做的改动

本节按“必须改 / 建议改 / 暂缓改”划分。

### 6.1 必须改

#### 6.1.1 新增车辆域统一视图层

建议新增：

- `agent/src/domains/vehicle/vehicle-data-service.ts`

建议职责：

- 聚合车辆档案、车辆画像、车辆统计相关底层能力。
- 对外暴露少量稳定方法：
  - `getVehicleBasicInfo`
  - `getVehicleRiskSnapshot`
  - `getVehicleManagementStatus`
  - `getVehicleReportSource`

目标：

- 让车辆专家和车辆报告读取同一语义层。
- 把“字段信谁、缺字段怎么补、哪些字段来自哪个源”的逻辑从 prompt 中移到代码中。

#### 6.1.2 扩展车辆基础信息语义字段

当前问题：

- `agent/src/shared/vehicle-profile-mcp.ts` 只整理了少量字段。
- `agent/src/app/runtime.ts` 中 `DATA_SCHEMAS.vehicle` 的 `basic.*` 字段也过薄。

至少需要补齐的稳定字段：

- `plate_number`
- `vehicle_id`
- `route_name`
- `organization_name` 或 `fleet_name`
- `vehicle_type`
- `vehicle_length`
- `vehicle_brand`
- `energy_type`
- `vehicle_model`
- `risk_level`
- `risk_score`
- `rank_text`
- `updated_at`

说明：

- 这些字段不一定都来自同一个底层源。
- 这正是 `vehicle.basic_info` 视图存在的原因。

#### 6.1.3 让车辆专家复用车辆基础信息视图

需调整：

- `agent/skills/conversational/vehicle_expert/SKILL.md`

改动目标：

- 明确把“基础信息查询”从泛化的简单事实类中独立出来，作为车辆专家内部的稳定子模式。
- 查询时不再由 prompt 自己拼底层口径，而是优先使用统一车辆视图。

#### 6.1.4 让车辆报告链路复用统一报告源

需调整：

- `agent/src/domains/chat/structured-report-data-sources.ts`
- `agent/src/shared/vehicle-profile-mcp.ts`
- `agent/src/domains/chat/structured-report-normalizers.ts`

改动目标：

- 报告 worker 不再直接绑定某个原始 MCP 的形状。
- 统一切到 `vehicle.report_source` 视图上。

#### 6.1.5 为其他域补一条明确迁移路径

改动目标：

- 文档和代码都应明确：`driver`、`route`、`incident_case`、`unit/station` 当前只是暂由 `query_data` 承接。
- 后续这些域应与车辆域一致，逐步接入真实 MCP，而不是把 `query_data` 永久做大。
- 在迁移完成前，`query_data` 应被视为兼容层，不再继续吸收复杂业务语义。

### 6.2 建议改

#### 6.2.1 给工具 registry 增加“能力分层元数据”

建议位置：

- `agent/src/app/runtime.ts`

建议补充的元信息：

- `capability_layer`: `direct_mcp` / `light_wrapper` / `domain_view` / `internal_control`
- `domain`: `vehicle` / `driver` / `route` / `incident` / `rule`
- `stability`: `dynamic` / `stable`
- `visibility`: `router` / `worker` / `internal_only`
- `scope_policy`: `global` / `scoped_only`

目标：

- 让 router、worker、测试、观测都知道当前工具属于哪一层。
- 后续更容易控制哪些能力允许直出给模型，哪些只能内部调用。

#### 6.2.2 显式补一份“工具可见性注册表”

建议位置：

- `agent/src/app/runtime.ts`
- 或单独抽为 `agent/src/app/tool-registry-metadata.ts`

建议覆盖：

- Router 顶层工具清单
- Worker 本地工具清单
- 动态 MCP 默认可见策略
- Scoped allow list 的例外规则
- 候选领域视图是否仅内部复用

目标：

- 避免“文档知道，但代码没有显式表达”。
- 避免新增工具时只补 description，不补可见性边界。

#### 6.2.3 工具暴露链路单独做故障治理

建议位置：

- `agent/src/app/runtime.ts`
- `agent/src/domains/chat/router-service.ts`
- 工具注册和启动自检相关代码

建议补充：

- 启动期工具面快照校验：校验 Router 工具集、Worker 本地工具集、关键 scoped allow list。
- fail-closed 策略：未显式声明 visibility 的工具默认不暴露。
- registry 和 description 一致性校验：避免名字、枚举、描述、可见性元数据漂移。
- scoped provider 回归测试：关键 worker 的可见工具集合必须可断言。
- 观测项：记录“本轮可见工具集合”“scoped 后工具集合”“被过滤的工具集合”。

目标：

- 把“工具暴露出问题”从隐性故障点变成可测试、可观测、可回归的边界。
- 避免新 MCP 或新工具上线时，因为暴露面配置问题导致链路故障。

#### 6.2.4 路由与工具描述按三分法重写

需调整：

- `agent/skills/router/SKILL.md`
- `agent/skills/router/ab-y.SKILL.md`
- `agent/src/app/runtime.ts` 中工具 description

目标：

- 把“哪些是核心高层能力、哪些是统计/列表直出能力”说清楚。
- 把“哪些工具 Router 能看见、哪些只有 Worker 能看见”说清楚。
- 把“`query_data` 是当前迁移期 demo/兼容层”说清楚。
- 降低模型把基础查询误判成报告或把复杂问答误判成底层统计的概率。

#### 6.2.5 测试按三分法和可见性补齐

建议新增测试覆盖：

- 车辆基础信息查询：必须命中统一车辆基础信息视图。
- 车辆统计查询：必须继续命中直出统计 MCP。
- 车辆报告生成：必须继续命中统一车辆报告源。
- 车辆多轮补充查询：分析后补充基础信息时应复用当前车辆上下文。
- Router 顶层工具集合测试：确保不会把 `query_data`、动态 MCP 直接暴露给 Router。
- Worker scoped 工具集合测试：确保 `request_further_info` 之外的工具都受 allow list 约束。
- 规则链路工具集合测试：确保 `get_rule_draft`、`update_rule_draft`、`submit_rule_turn`、`rule_exit` 的可见性符合预期。
- 迁移期测试：确保各域在尚未接入真实 MCP 前，仍能由 `query_data` 兜底；接入后则切换到新数据源。

涉及文件：

- `agent/fixtures/assistant-reliability-cases.json`
- `agent/fixtures/assistant-ab-playwright-cases.json`
- 相关脚本和文档

### 6.3 暂缓改

以下能力先不要做高层视图：

- 事故域高层视图
- 单位域高层视图
- 站场域高层视图
- 所有列表和统计类直出 MCP

原因：

- 当前高频程度不足。
- 断裂点还不明确。
- 过早收口会把系统重新做成大而全的场景工具集合。

---

## 7. 推荐实施顺序

### 阶段 1：先止住车辆域扩散

1. 新增车辆统一视图层。
2. 让车辆基础信息查询和车辆报告都复用该层。
3. 补齐车辆基础字段映射。
4. 补测试。

### 阶段 2：让能力面显式分层

1. 在 runtime 工具元数据中标注三分法层级。
2. 同时标注 Router/Worker/Internal-only 可见性。
3. 给工具暴露链路加启动校验和 fail-closed 机制。
4. 重写 router 和 worker 的能力描述。
5. 明确哪些直出、哪些只能内部复用。

### 阶段 3：按真实断裂点继续收口

候选顺序：

1. 驾驶员域
2. 线路域
3. 其他画像域

原则：

- 没有明确断裂点，不做高层视图。
- 没有高频复用，不做高层视图。

---

## 8. 最终结论

当前系统不应走两种极端路线：

- 不是“所有业务场景都做一个高层工具”。
- 也不是“所有原始 MCP 都直接丢给模型自己理解”。

更稳的目标形态是：

1. 绝大多数能力保持动态 MCP 或轻包装直出。
2. 只有少量核心业务对象在出现明显断裂点时，才收敛成稳定领域视图。
3. 第一优先级应是车辆域，因为它已经同时影响查询、问答、报告和话术稳定性。
4. `query_data` 是当前迁移期兼容层，其他域后续也应像车辆域一样逐步接入真实 MCP。
5. 高层领域视图初期应优先作为 Worker 内部可复用能力，不必急着都变成 Router 顶层工具。
6. 工具暴露链路本身是潜在故障点，必须有独立的校验、测试和观测。

一句话总结：

> 动态 MCP 是目标主干，`query_data` 只是迁移期兼容层；少量高层领域视图负责稳住核心断裂点；Router 只看分发能力，Worker 才看执行工具，而工具暴露链路本身也要被当成故障点治理。
