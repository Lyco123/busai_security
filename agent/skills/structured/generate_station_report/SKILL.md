---
name: generate-station-report
description: 用于生成站场安全风险分析总结报告（管理人员版），输出严格 JSON，前端按 layout 渲染。
---

## 提示词约束
- 先区分当前需求是"报告生成"还是"查询"。
- 这个 worker 只用于处理明确的站场报告生成请求，不用于处理信息查询。
- 只要用户是在获取事实、详情、属性、记录、列表、数量、统计、基础资料、档案信息、评分或分数，就属于查询，不属于报告。
- 只有当用户明确要求生成站场报告、站场画像、风险分析总结等完整报告型输出时，才继续使用这个 worker。
- 如果用户实际是在查询信息，而不是明确要求报告，立即停止，并返回 `{"error":"wrong_worker","message":"这是站场信息查询，不是明确的站场报告请求。"}`。
- 如果工具结果不能唯一确认目标站场，不要猜测，也不要生成报告。
# 技能：站场安全风险分析总结报告（管理人员版）

## 执行目标

- 根据 `busStationName` / `station_name` 查询站场画像数据，输出可直接渲染的结构化 JSON。
- 输出效果必须对齐《站场画像AI通用话术（20260305）》文档末尾的"安全风险分析总结报告回复模版——管理人员"。
- 输出体验、章节结构、字段组织方式与驾驶员报告 skill 保持一致。
- 仅输出 JSON，不输出 Markdown。

## 数据来源约束

1. 优先使用当前轮已经提供的 `report_source`、工具结果或结构化输入生成最终 JSON，不要重复请求同一份数据。
2. 若当前轮缺少有效的站场画像数据，且运行时确实提供了数据工具，可先补查真实数据。候选必须与请求的 `station_name` 同名，或名称显著包含同一站场 token；若候选仅是其他站场，必须直接判定为未命中。
3. 若最终仍未命中：只返回错误 JSON，不得输出报告正文：
```json
{"error":"station_not_found","message":"未找到该站场画像数据，请确认站场名称后重试"}
```
4. 禁止重复 `describe`，禁止对同一个 `entity_id/search_term` 反复请求同一份数据。
5. 所有基础指标名称必须逐字来自本次 MCP/工具结果中的可引用子项，优先使用 `quota_summary[].indicators[].name`、`quota_items[].quota_name`、`suggestions[].indicator` 或等价明细字段；不得把知识库概括词、管理抓手、维度归纳词或模型自行总结的指标名写入 `management_summary.major_risk_factors`、`dashboard_rows[].core_risk_indicators`、`behavior_data_analysis.analysis_items[].top_indicator`、`behavior_data_analysis.analysis_items[].insight`、`interventions.recommendations[].indicator` 或建议前缀中。若源数据没有该指标名称，最终报告不得出现该名称。

## 模板标注语法（硬约束）
- 数据植入位必须用 `{}`，例如 `{文化公园总站}`、`{16}`、`{2026年6月8日-6月14日}`。
- AI分析发挥必须用 `【】`，不得使用 `[]` 代替。
- 以下字段必须同时满足 `{}` 与 `【】` 标注规则：
  - `layout.summary`
  - `management_summary.summary_text`
  - `core_risk_assessment.summary`
  - `behavior_data_analysis.analysis_items[].insight`
  - `interventions.recommendations[].suggestion`

## 一级指标映射规则（核心）
目标一级指标固定为以下四项，最终输出中只能出现这四项名称：
- `综合风险`
- `交通安全`
- `三防安全`
- `消防安全`

取值优先级：
1. 优先读取新结构（若存在）：
   - `performance_dashboard.summary.overall_score`
   - `performance_dashboard.dimensions.综合风险`
   - `performance_dashboard.dimensions.交通安全`
   - `performance_dashboard.dimensions.三防安全`
   - `performance_dashboard.dimensions.消防安全`
2. 若新结构缺失，则从站场画像明细中按真实字段映射或聚合：
   - `综合风险 <- performance_dashboard.summary.overall_score / risk_profile.overall / safety_rating.overall`
   - `交通安全 <- risk_profile.traffic / traffic_safety.score / 交通安全类 quota_summary`
   - `三防安全 <- risk_profile.three_defense / three_defense_safety.score / 三防安全类 quota_summary`
   - `消防安全 <- risk_profile.fire / fire_safety.score / 消防安全类 quota_summary`
3. 若某维度缺少直接分数，可用该维度真实基础指标的高分项推导相对排序，但不得编造固定示例值。

禁止项：
- 不得把基础指标名称直接作为 `dashboard_rows.dimension` 输出。
- 不得把站场、总站、车站别名当成风险维度输出。
- 不得把交通安全类基础指标归入 `三防安全` 或 `消防安全`，也不得跨维度复用高分基础指标。
- 某个一级维度缺少真实基础指标时，宁可保留空指标或说明缺少直接指标，也不得复用其他维度的指标。

## 生成流程（硬约束）
1. 抽取基础信息：
   - 站场名称、站场 ID、所属单位、风险等级、风险分、排名、主要风险因素、统计周期。
2. 生成 `dashboard_rows`：
   - 仅输出四个一级指标（综合风险/交通安全/三防安全/消防安全）。
   - 每项包含：`dimension`、`score`、`trend_text`、`core_risk_indicators`。
   - `综合风险` 必须位于第一行；后续 `交通安全/三防安全/消防安全` 按 `score` 从高到低排序，`null` 放最后。
   - `综合风险` 的 `core_risk_indicators` 可列 3-5 个综合性主风险因子；其他维度每项列 1-3 个核心基础指标。
   - `core_risk_indicators` 只能填入本次 MCP/工具结果明细中实际存在的基础指标名称。
3. 生成 `core_risk_assessment`：
   - 该章节只输出一个总结段 `summary`，不要再展开逐条编号明细。
   - `summary` 必须对齐参考话术，包含：站场标识、综合风险分、风险状态、排名/相对表现；AI 判断写入 `【】`。
   - `risk_factors` 保留为空数组即可，不要强行补写。
4. 生成 `behavior_data_analysis.analysis_items`：
   - 该章节分析"多维绩效看板"中真正需要解释的一级指标。
   - 默认不要分析 `综合风险`，避免把总分维度与分项维度重复叙述。
   - 优先分析 `交通安全`、`三防安全`、`消防安全` 中存在核心风险指标的维度。
   - 如果某一级指标没有核心风险，则不要为了凑数硬写。
   - 每条包含：`rank_label`、`dimension`、`top_indicator`、`alert_count`、`insight`；如某维度在多维看板中列了多个核心指标，`insight` 必须把这些指标全部展开说明。
   - `insight` 参考话术风格：
     - 第一条前缀：`风险最高的一级指标是{...}`
     - 第二条前缀：`其次是{...}`
     - 第三条前缀：`最后是{...}`
   - 只有当源数据中存在可核验次数时，才能写成 `{某指标N次}`；若缺少直接次数，必须明确说明"当前缺少直接报警指标/次数"，不得伪造数字。
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
  "report_type": "station_safety_summary_management",
  "template_version": "20260305",
  "report_role": "management",
  "layout": {
    "title": "站场安全风险分析总结报告",
    "summary": "",
    "header": {
      "items": [
        {"label": "站场", "value_path": "management_summary.station_name"},
        {"label": "所属单位", "value_path": "management_summary.organ_name"},
        {"label": "风险状态", "value_path": "management_summary.risk_level", "highlight": true}
      ]
    },
    "sections": [
      {
        "title": "一、多维绩效看板",
        "blocks": [
          {
            "type": "dashboard",
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
    "station_name": "",
    "station_id": "",
    "organ_name": "",
    "risk_level": "",
    "overall_score": null,
    "major_risk_factors": [],
    "summary_text": ""
  },
  "dashboard_rows": [
    {
      "dimension": "综合风险",
      "score": null,
      "risk_level": "",
      "trend_text": "",
      "core_risk_indicators": []
    }
  ],
  "core_risk_assessment": {
    "summary": "",
    "risk_factors": []
  },
  "behavior_data_analysis": {
    "analysis_items": [
      {
        "dimension": "",
        "top_indicator": "",
        "insight": ""
      }
    ]
  },
  "interventions": {
    "recommendations": [
      {
        "priority": 1,
        "indicator": "",
        "suggestion": ""
      }
    ]
  },
  "appendix": {
    "raw_data": {}
  }
}
```

## 生成规则

- `report_type` 必须为 `station_safety_summary_management`。
- `template_version` 必须为 `20260305`。
- `management_summary.station_name` 使用 `report_source.basic.station_name`。
- `management_summary.station_id` 使用 `report_source.basic.station_id`。
- `management_summary.organ_name` 使用 `report_source.basic.organ_name`。
- `management_summary.risk_level` 使用 `performance_dashboard.summary.overall_level`。
- `management_summary.overall_score` 使用 `performance_dashboard.summary.overall_score`。
- 报告话术按“AI 安全风险分析总结报告回复模版——管理人员”组织：一、多维绩效看板；二、核心风险研判；三、行为与数据关联分析；四、针对性干预建议。
- `dashboard_rows` 对应“一、多维绩效看板”，第一行必须是 `综合风险`，后续为 `交通安全`、`三防安全`、`消防安全`；每行必须包含风险得分、趋势表现和核心风险指标。
- `major_risk_factors`、`dashboard_rows[].core_risk_indicators`、`analysis_items[].top_indicator`、`recommendations[].indicator` 必须逐字来自 `appendix.raw_data.quota_summary[].indicators[].name` 或 `appendix.raw_data.quota_items[].quota_name`。
- `summary_text` 作为多维绩效看板前的管理人员结论句，包含日期、站场、风险等级、综合分和主要风险因素，句式参考“该站场被系统预判为...主要风险因素为...，需引起重视”。
- `core_risk_assessment.summary` 对应“二、核心风险研判”，为单段总结，包含综合风险分、风险等级、排名/对比信息和总体判断。
- `behavior_data_analysis.analysis_items` 对应“三、行为与数据关联分析”，只分析存在核心风险指标的一级指标，按风险得分从高到低使用“风险最高的一级指标是/其次是/最后是”组织。
- `interventions.recommendations` 对应“四、针对性干预建议”，按基础指标风险值或报告来源中的指标顺序使用“风险最高的基础指标是/其次是/再次是/最后是”组织；整改建议优先使用 `appendix.raw_data.suggestions[].suggested_content`，没有建议时，围绕真实指标生成保守的巡检、整改、复核闭环建议。
