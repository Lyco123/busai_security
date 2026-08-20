---
name: generate-unit-report
description: 用于生成单位安全风险分析总结报告（管理人员版），输出严格 JSON，前端按 layout 渲染。
---

# 技能：单位安全风险分析总结报告（管理人员版）

## 使用前提
- 该 skill 只负责在外层已经确定为“单位管理人员版报告生成”后产出最终 JSON。
- 意图识别、查询/报告分流、澄清续跑由外层 router 或 worker 选择层处理，不在本 skill 内再次判断。
- 如果工具结果不能唯一确认目标单位，不要猜测，也不要生成报告。

## 执行目标
- 根据 `organ_name` 查询单位画像数据，输出可直接渲染的结构化 JSON。
- 输出效果必须对齐《单位画像 AI 通用话术（20260409）》中“安全风险分析总结报告话术”的“AI 安全风险分析总结报告回复模版——管理人员”。
- 输出章节、段落顺序、字段组织方式应尽量与已完成的驾驶员/车辆报告管线保持一致，但最终模板参照只能以单位话术文档为准。
- 仅输出 JSON，不输出 Markdown。

## 数据来源约束
1. 优先使用当前轮已经提供的 `report_source`、工具结果或结构化输入生成最终 JSON，不要重复请求同一份数据。
2. 当前单位报告按单位名称查询；如果运行时已经解析出唯一目标，以当前轮提示词和 `report_source` 为准，不得自行改写目标单位。
3. `ppartition` 为可选参数；若提供，必须是 `yyyyMMdd` 格式单日分区；如果当前轮提示词给出固定 `ppartition`，必须按提示词值使用，不得自行改写。
4. 若用户只提供了过泛单位词（如“单位”“公司”“分公司”“集团”）或过短片段，不得模糊猜测到某个单位，必须视为信息不足并等待补充。
5. 若当前轮缺少有效的单位画像数据，且运行时确实提供了数据工具，可再按可用工具约束补查；若补查后仍未命中或 `result/main` 为空，只返回错误 JSON，不得输出报告正文：
```json
{"error":"unit_not_found","message":"未找到该单位画像数据，请确认单位名称后重试"}
```
6. 所有基础指标名称必须逐字来自本次 MCP/工具结果中的可引用子项，优先使用 `quota_summary[].indicators[].name`、`result.quotaScoreSubList[].quotaName`、高风险清单中的同名指标字段或等价明细字段；不得把知识库概括词、管理抓手、维度归纳词或模型自行总结的指标名写入 `management_summary.major_risk_factors`、`dashboard_rows[].core_risk_indicators`、`behavior_data_analysis.analysis_items[].top_indicator`、`behavior_data_analysis.analysis_items[].insight`、`interventions.recommendations[].indicator` 或建议前缀中。若源数据没有该指标名称，最终报告不得出现该名称。

## 模板标注语法（硬约束）
- 数据植入位必须用 `{}`，例如 `{二巴公司}`、`{43}`、`{50/90}`。
- AI 分析发挥必须用 `【】`，不得使用 `[]` 代替。
- 以下字段必须同时满足 `{}` 与 `【】` 标注规则：
  - `layout.summary`
  - `management_summary.summary_text`
  - `core_risk_assessment.summary`
  - `behavior_data_analysis.analysis_items[].insight`
  - `interventions.recommendations[].suggestion`

## 一级指标映射规则（核心）
多维绩效看板固定输出以下 5 行：`综合风险` 必须位于第一行，其余核心维度按 `score` 风险得分从高到低排列，`null` 放最后：
- `综合风险`
- `驾驶员风险`
- `车辆风险`
- `线路风险`
- `站场风险`

取值优先级：
1. 优先读取新结构（若存在）：
   - `performance_dashboard.summary.overall_score` / `performance_dashboard.dimensions.综合风险`
   - `performance_dashboard.dimensions.驾驶员风险`
   - `performance_dashboard.dimensions.车辆风险`
   - `performance_dashboard.dimensions.线路风险`
   - `performance_dashboard.dimensions.站场风险`
2. 若直接结构缺失，则从原始 `quotaScoreSubList` 映射：
   - `综合风险 <- main.score`
   - `驾驶员风险 <- quotaId = 单位画像-驾驶员风险`
   - `车辆风险 <- quotaId = 单位画像-车辆风险`
   - `线路风险 <- quotaId = 单位画像-线路风险`
   - `站场风险 <- quotaId = 单位画像-站场风险`

禁止项：
- 不得把二级指标（事故风险、能耗风险、安全评价、故障风险等）直接作为多维绩效看板一级维度。
- 不得把建议状态计数（待接受、待确认、待优化）当成核心风险指标。
- 不得把 5 行看板写成按分数重排。

## 生成流程（硬约束）
1. 抽取基础信息：
   - 单位名称、单位 ID、风险等级、综合风险分、排名、主要风险因素、统计周期、管理建议状态计数。
2. 生成 `dashboard_rows`：
   - 输出 5 行：`综合风险` + 4 个一级指标。
   - 每项包含：`dimension`、`score`、`trend_text`、`core_risk_indicators`。
   - 行顺序为：`综合风险` 在第一行，后续 `驾驶员风险/车辆风险/线路风险/站场风险` 按 `score` 从高到低排序，`null` 放最后。
   - `core_risk_indicators` 只能填入本次 MCP/工具结果明细中实际存在的基础指标名称。
3. 生成 `core_risk_assessment`：
   - `summary` 对齐话术文档“核心风险研判”的单段总结写法，包含：单位名称、综合风险分、风险状态、排名/相对表现，以及 `【】` 中的 AI 研判。
   - 若源数据提供高风险下级单位/驾驶员/车辆/线路/站场清单，必须承接到对象表结构中。
   - 若源数据暂未提供对象清单，也必须保留对象表对应字段，但 `rows` 为空数组，不得编造。
4. 生成 `behavior_data_analysis.analysis_items`：
   - 默认不重复分析 `综合风险` 行。
   - 重点分析存在核心风险指标的一级指标（驾驶员风险/车辆风险/线路风险/站场风险）。
   - 输出顺序按一级指标风险高低排序；前缀依次为：`风险最高的一级指标是` / `其次是` / `再次是` / `最后是`。
   - 若某一级指标缺少直接报警次数，必须明确写“当前缺少直接报警次数”，不得伪造次数。
5. 生成 `interventions.recommendations`：
   - 按全局高风险基础指标排序输出，不要求与 `analysis_items` 同数量，也不要求一一对应。
   - 最多输出 4 条，最少输出 1 条。
   - `indicator` 必须逐字匹配本次 MCP/工具结果明细中的基础指标名称；不得为了表达管理方向而改写、合并或新增指标名称。
   - 若原始数据已存在干预建议，优先沿用；若缺失，可基于真实指标与维度生成不虚构事实的管理建议。
   - `suggestion` 文本前缀规则：
      - 第1条：`风险最高的基础指标是{...}`
      - 第2条：`其次是{...}`
      - 第3条：`再次是{...}`
      - 第4条：`最后是{...}`
6. 输出 `layout`，前端按 `layout` 渲染。

## 输出结构（必含字段）
```json
{
  "report_type": "unit_safety_summary_management",
  "template_version": "20260409",
  "report_role": "management",
  "layout": {
    "title": "单位安全风险分析总结报告",
    "summary": "",
    "header": {
      "items": [
        {"label": "单位名称", "value_path": "management_summary.organ_name"},
        {"label": "单位ID", "value_path": "management_summary.organ_id"},
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
          {"type": "text", "text_path": "core_risk_assessment.summary"},
          {"type": "text", "text_path": "core_risk_assessment.high_risk_object_summary"},
          {
            "type": "table",
            "columns": [
              {"title": "风险排名", "key": "rank"},
              {"title": "下级单位", "key": "sub_unit"},
              {"title": "驾驶员", "key": "driver"},
              {"title": "车辆", "key": "vehicle"},
              {"title": "线路", "key": "route"},
              {"title": "站场", "key": "station"}
            ],
            "rows_path": "core_risk_assessment.high_risk_objects.rows"
          }
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
    "organ_name": "",
    "organ_id": "",
    "risk_level": "",
    "major_risk_factors": [],
    "suggestion_status": {
      "pending_receive_count": null,
      "pending_confirm_count": null,
      "pending_optimize_count": null
    },
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
    "detail_lines": [],
    "high_risk_object_summary": "",
    "high_risk_objects": {
      "unit_count": null,
      "driver_count": null,
      "vehicle_count": null,
      "route_count": null,
      "station_count": null,
      "rows": []
    }
  },
  "behavior_data_analysis": {"analysis_items": []},
  "interventions": {"recommendations": []},
  "appendix": {"raw_data": {}}
}
```

## 输出前自检
- `dashboard_rows` 固定为 5 行：第一行必须是 `综合风险`，后续四个核心维度按 `score` 风险得分从高到低排列，`null` 放最后。
- `recommendations` 是全局基础指标排序结果，数量为 1-4。
- `core_risk_assessment.high_risk_objects.rows` 只有在源数据存在对象清单时才填充；没有则保留空数组，不得编造。
- `management_summary.major_risk_factors`、`dashboard_rows[].core_risk_indicators`、`analysis_items[].top_indicator`、`recommendations[].indicator` 必须能在本次 `appendix.raw_data` 中回溯到同名字段；发现不存在的指标名时必须移除或替换为真实同名指标，不得改用近义词或上位概念。
- 关键文本字段满足 `{}` + `【】` 标注语法。
- 禁止复用示例数值或编造高风险对象清单。
