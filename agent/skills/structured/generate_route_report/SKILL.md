---
name: generate-route-report
description: 用于生成线路安全风险分析总结报告（管理人员版），输出严格 JSON，前端按 layout 渲染。
---

## 提示词约束
- 先区分当前需求是"报告生成"还是"查询"。
- 这个 worker 只用于处理明确的线路报告生成请求，不用于处理信息查询。
- 只要用户是在获取事实、详情、属性、记录、列表、数量、统计、基础资料或档案信息，就属于查询，不属于报告。
- 只有当用户明确要求生成线路报告、线路画像、风险分析总结等完整报告型输出时，才继续使用这个 worker。
- 如果用户实际是在查询信息，而不是明确要求报告，立即停止，并返回 `{"error":"wrong_worker","message":"这是线路信息查询，不是明确的线路报告请求。"}`。
- 如果工具结果不能唯一确认目标线路，不要猜测，也不要生成报告。
# 技能：线路安全风险分析总结报告（管理人员版）

## 执行目标
- 根据 `route_name` 查询线路数据，输出可直接渲染的结构化 JSON。
- 输出效果必须对齐《线路画像 AI 通用话术（20260305）》文档末尾的"安全风险分析总结报告回复模版——管理人员"。
- 输出体验、章节结构、字段组织方式与驾驶员报告 skill 保持一致。
- 仅输出 JSON，不输出 Markdown。

## 数据来源约束
1. 优先使用当前轮已经提供的 `report_source`、工具结果或结构化输入生成最终 JSON，不要重复请求同一份数据。
2. 若当前轮缺少有效的线路数据，且运行时确实提供了数据工具，可先补查真实数据。候选必须与请求的 `route_name` 同名、同编号，或名称/编号显著包含同一路线 token；若候选仅是其他线路（例如请求 `383路`，候选只有 `1路/12路`），必须直接判定为未命中。
3. 若最终仍未命中：只返回错误 JSON，不得输出报告正文：
```json
{"error":"route_not_found","message":"未找到该线路，请确认线路名称或线路编号后重试"}
```
4. 禁止重复 `describe`，禁止对同一个 `entity_id/search_term` 反复请求同一份数据。
5. 所有基础指标名称必须逐字来自本次 MCP/工具结果中的可引用子项，优先使用 `quota_summary[].indicators[].name`、`result.quotaScoreSubList[].quotaName`、`high_risk_segments[].issue`、事故/违法/黑点明细中的同名指标字段或等价明细字段；不得把知识库概括词、管理抓手、维度归纳词或模型自行总结的指标名写入 `management_summary.major_risk_factors`、`dashboard_rows[].core_risk_indicators`、`behavior_data_analysis.analysis_items[].top_indicator`、`behavior_data_analysis.analysis_items[].insight`、`interventions.recommendations[].indicator` 或建议前缀中。若源数据没有该指标名称，最终报告不得出现该名称。

## 模板标注语法（硬约束）
- 数据植入位必须用 `{}`，例如 `{383路}`、`{43}`、`{50/90}`。
- AI分析发挥必须用 `【】`，不得使用 `[]` 代替。
- 以下字段必须同时满足 `{}` 与 `【】` 标注规则：
  - `layout.summary`
  - `management_summary.summary_text`
  - `core_risk_assessment.summary`
  - `behavior_data_analysis.analysis_items[].insight`
  - `interventions.recommendations[].suggestion`

## 一级指标映射规则（核心）
目标一级指标固定为以下三项，最终输出中只能出现这三项名称：
- `综合风险`
- `静态风险`
- `动态风险`

取值优先级：
1. 优先读取新结构（若存在）：
   - `performance_dashboard.dimensions.综合风险`
   - `performance_dashboard.dimensions.静态风险`
   - `performance_dashboard.dimensions.动态风险`
2. 若新结构缺失，则从旧结构映射或聚合：
   - `综合风险 <- performance_dashboard.summary.overall_score / risk_profile.overall / safety_rating.overall`
   - `静态风险 <- risk_profile.static / static_risk.score / risk_profile.infrastructure / indicators.static_risk_road + indicators.static_risk_population + indicators.static_risk_blackspot`
   - `动态风险 <- risk_profile.dynamic / dynamic_risk.score / risk_profile.traffic / indicators.dynamic_risk_faults / behavior_risk`
3. 若某维度缺少直接分数，可用该维度真实基础指标的高分项推导相对排序，但不得编造固定示例值。

禁止项：
- 不得把 `交通安全/服务安全/运行安全` 直接作为 `dashboard_rows.dimension` 输出。
- 不得把 `线形路况风险/人口密集区域风险/行为黑点风险/车辆故障总数` 直接作为一级维度名称。
- 不得把静态类基础指标归入 `动态风险`，也不得把动态行为/故障指标归入 `静态风险`。
- `静态风险` 缺少真实静态指标时，宁可使用维度默认抓手，也不得复用 `动态风险` 的高分基础指标。

## 生成流程（硬约束）
1. 抽取基础信息：
   - 线路名称、线路编号/ID、所属单位、风险等级、风险分、排名、主要风险因素、统计周期。
2. 生成 `dashboard_rows`：
   - 仅输出三个一级指标（综合风险/静态风险/动态风险）。
   - 每项包含：`dimension`、`score`、`trend_text`、`core_risk_indicators`。
   - `综合风险` 必须位于第一行；后续 `静态风险/动态风险` 按 `score` 从高到低排序，`null` 放最后。
   - `综合风险` 的 `core_risk_indicators` 可列 3-5 个综合性主风险因子；`静态风险/动态风险` 每项列 1-3 个核心基础指标。
   - `静态风险` 只允许使用线形路况、人口密集区域、行为黑点等静态类基础指标。
   - `动态风险` 只允许使用急加速、不规范进站、空挡滑行、车辆故障、运行行为等动态类基础指标。
   - `core_risk_indicators` 只能填入本次 MCP/工具结果明细中实际存在的基础指标名称。
   - 若仅存在旧结构 `high_risk_segments.issue`，必须先判断该 `issue` 属于静态还是动态，再决定是否纳入对应维度；`high_risk_segments.segment/location` 可作为静态侧的高风险路段依据。
3. 生成 `core_risk_assessment`：
   - 该章节只输出一个总结段 `summary`，不要再展开逐条编号明细。
   - `summary` 必须对齐参考话术，包含：线路标识、综合风险分、风险状态、排名/相对表现；AI 判断写入 `【】`。
   - `detail_lines` 保留为空数组即可，不要强行补写。
4. 生成 `behavior_data_analysis.analysis_items`：
   - 该章节分析"多维绩效看板"中真正需要解释的一级指标。
   - 默认不要分析 `综合风险`，避免把总分维度与分项维度重复叙述。
   - 优先分析 `静态风险`、`动态风险` 中存在核心风险指标的维度。
   - 如果某一级指标没有核心风险，则不要为了凑数硬写。
   - 每条包含：`rank_label`、`dimension`、`top_indicator`、`alert_count`、`insight`；如某维度在多维看板中列了多个核心指标，`insight` 必须把这些指标全部展开说明。
   - `insight` 参考话术风格：
     - 第一条前缀：`风险最高的一级指标是{...}`
     - 第二条前缀：`其次是{...}`
   - 只有当源数据中存在可核验次数时，才能写成 `{某指标N次}`；若缺少直接次数，必须明确说明"当前缺少直接报警指标/次数"，不得伪造数字。
   - `综合风险` 不属于行为与数据关联分析要展开的一级指标，默认不要分析；重点展开 `静态风险`、`动态风险` 在多维看板中出现的全部指标及其源数据。
5. 生成 `interventions.recommendations`：
   - 该章节不是按一级维度一一对应生成，而是按全局基础指标风险值排序输出建议。
   - 指标排名依据系统"风险追踪列表"或等价原始来源中的基础指标风险值分数。
   - 最多输出 5 条，最少输出 1 条。
   - `priority` 必须是 `1..N`。
   - `indicator` 必须是该条建议针对的基础指标名。
   - `indicator` 必须逐字匹配本次 MCP/工具结果明细中的基础指标名称；不得为了表达管理方向而改写、合并或新增指标名称。
   - `suggestion` 文本前缀规则：
     - 第1条：`风险最高的基础指标是{...}`
     - 第2条：`其次是{...}`
     - 第3条：`再次是{...}`
     - 第4条：`同时有{...}`
     - 第5条：`最后是{...}`
   - 若原始数据存在对应建议，优先沿用；若缺失，可基于维度给出不虚构事实的管理动作建议。
6. 输出 `layout`，前端按 `layout` 渲染。

## 输出结构（必含字段）
```json
{
  "report_type": "route_safety_summary_management",
  "template_version": "20260305",
  "report_role": "management",
  "layout": {
    "title": "线路安全风险分析总结报告",
    "summary": "",
    "header": {
      "items": [
        {"label": "线路", "value_path": "management_summary.route_name"},
        {"label": "所属单位", "value_path": "management_summary.fleet_name"},
        {"label": "风险状态", "value_path": "management_summary.risk_level", "highlight": true}
      ]
    },
    "sections": [
      {
        "title": "一、多维绩效看板",
        "blocks": [
          {
            "type": "table",
            "columns": [
              {"title": "核心维度", "key": "dimension"},
              {"title": "风险得分", "key": "score"},
              {"title": "趋势表现", "key": "trend_text"},
              {"title": "核心风险指标", "key": "core_risk_indicators"}
            ],
            "rows_path": "dashboard_rows"
          }
        ]
      },
      {
        "title": "二、核心风险研判",
        "blocks": [
          {"type": "text", "text_path": "core_risk_assessment.summary"}
        ]
      },
      {
        "title": "三、行为与数据关联分析",
        "blocks": [
          {"type": "list", "items_path": "behavior_data_analysis.analysis_items", "ordered": false}
        ]
      },
      {
        "title": "四、针对性干预建议",
        "blocks": [
          {"type": "list", "items_path": "interventions.recommendations", "ordered": false}
        ]
      },
      {
        "title": "附录（原始数据）",
        "collapsible": true,
        "default_open": false,
        "blocks": [
          {"type": "json", "title": "原始数据", "data_path": "appendix"}
        ]
      }
    ]
  },
  "management_summary": {
    "report_date": "",
    "route_name": "",
    "route_id": "",
    "fleet_name": "",
    "risk_level": "",
    "major_risk_factors": [],
    "summary_text": ""
  },
  "dashboard_rows": [],
  "core_risk_assessment": {
    "summary": "",
    "overall_score": null,
    "risk_level": "",
    "rank": {"position": null, "total": null, "display": ""},
    "comparison": "",
    "attention_note": "",
    "detail_lines": []
  },
  "behavior_data_analysis": {"analysis_items": []},
  "interventions": {"recommendations": []},
  "appendix": {"raw_data": {}}
}
```

## 字段填充约束
- `layout.summary` 与 `management_summary.summary_text` 语义一致，采用完整自然语言句式。
- `report_date` 优先使用统计周期；若存在 `source_window/as_of/start/end` 等字段，应输出可读日期区间。
- `trend_text` 统一格式：`同比X，环比Y，同单位比Z`。
- 无法从数据直接映射的值使用 `null` 或 `"—"`，禁止输出"暂无/待补充/建议事项/未知"。
- `major_risk_factors` 必须来自真实数据中的高风险基础指标、黑点、告警、违章或干预对象，不得凭空编造。
- `major_risk_factors`、`dashboard_rows[].core_risk_indicators`、`analysis_items[].top_indicator`、`recommendations[].indicator` 必须能在本次附录原始数据中回溯到同名字段；无法回溯同名字段时删除该指标，不得改用近义词或上位概念。
- 若某维度缺少直接明细指标，允许输出维度级管理抓手，但必须显式说明"当前缺少直接报警指标/次数"，不得伪造具体告警数据。
- 若原始数据给出事故/违法/路段/黑点明细，可在 `appendix.raw_data` 中保留，但正文只引用与结论直接相关的部分。
- 附录仅放本次查询用到的原始数据，不输出无关内容。

## 输出前自检（必须全部满足）
- `dashboard_rows` 仅含三个一级指标：第一行必须是 `综合风险`，后续 `静态风险/动态风险` 按 `score` 风险得分从高到低排列，`null` 放最后。
- `layout.summary` 与 `management_summary.summary_text` 对齐参考模板首句，包含日期、线路名称、风险等级、主要风险因素。
- `core_risk_assessment.summary` 为单段总结，不再强制要求编号明细。
- `core_risk_assessment.detail_lines` 允许为空数组。
- `analysis_items` 仅分析有核心风险的一级指标，默认不重复分析 `综合风险`。
- `recommendations` 是全局基础指标排序结果，不要求与 `analysis_items` 同数量，也不要求一一对应。
- 所有输出的基础指标名称均能在 `appendix.raw_data` 中找到同名来源；发现不存在的指标名时必须移除或替换为真实同名指标。
- `recommendations[0].suggestion` 包含 `风险最高的基础指标是`。
- 当存在第2/3/4/5条建议时，前缀分别为 `其次是`、`再次是`、`同时有`、`最后是`。
- 关键文本字段满足 `{}` + `【】` 标注语法。

## 禁止事项
- 禁止未查询数据直接生成报告。
- 禁止仅输出旧模板字段代替主结构（如仅输出 `risk_profile/high_risk_indicators/risk_segments`）。
- 禁止把 `交通安全/服务安全/运行安全` 作为三个一级维度直接输出。
- 禁止把 `综合风险` 当作与分项风险并列展开重复分析。
- 禁止复用固定示例数值（如 43、23、20、50/90、24次）作为本次真实结论。
- 禁止虚构政策依据、黑点数量、风险次数、排名数据。
- 若源数据只有旧结构，也必须生成上述统一 JSON；允许通过映射补齐，不得退回旧平铺结构。
## 路由边界
- 本 skill 只能在路由层已经明确确认为"正式线路报告请求"之后执行。
- 如果目标线路存在歧义、冲突，或者无法唯一确认，不得生成报告。
- 如果用户最新意图是"不要正式报告""只要口头汇报""只看要点""先查信息""先看情况"等查询式表达，不得生成报告正文。
- 如果当前轮只提供了部分 JSON 片段或部分键值槽位，不得猜测缺失目标，应等待剩余必需字段补齐。
- 多轮对话中必须始终服从用户最新明确指定的目标线路和最新明确指定的输出格式。
