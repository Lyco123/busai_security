---
name: generate-driver-report
description: 用于生成驾驶员安全风险分析总结报告（管理人员版），输出严格 JSON，前端按 layout 渲染。
---

## 使用前提
- 该 skill 只负责在外层已经确定为“驾驶员管理人员版报告生成”后产出最终 JSON。
- 意图识别、查询/报告分流、澄清续跑由外层 router 或 worker 选择层处理，不在本 skill 内再次判断。
- 如果工具结果不能唯一确认目标驾驶员，不要猜测，也不要生成报告。
# 技能：驾驶员安全风险分析总结报告（管理人员版）

## 执行目标
- 根据 `driver_name` 查询驾驶员数据，输出可直接渲染的结构化 JSON。
- 输出效果必须对齐《驾驶员画像 AI 通用话术（20260305）》中的“管理人员版”模板。
- 仅输出 JSON，不输出 Markdown。

## 数据来源约束
1. 优先使用当前轮已经提供的 `report_source`、工具结果或结构化输入生成最终 JSON，不要重复请求同一份数据。
2. 当前驾驶员报告优先按驾驶员姓名查询；如果运行时已经解析出工号或唯一目标，以当前轮提示词和 `report_source` 为准，不得自行改写目标驾驶员。
3. `ppartition` 为可选参数；未提供时默认查询最新画像日期。若提供，必须是 `yyyyMMdd` 格式单日分区；如果当前轮提示词给出固定 `ppartition`，必须按提示词值使用，不得自行改写。
4. 若用户只提供了过短片段（如单个字母、单个汉字、1-3 位数字），不得模糊猜测到某位驾驶员，必须视为信息不足并等待补充。
5. 若当前轮缺少有效的驾驶员画像数据，且运行时确实提供了数据工具，可再按可用工具约束补查；若补查后仍未命中或 `result/main` 为空，只返回错误 JSON，不得输出报告正文：
```json
{"error":"driver_not_found","message":"未找到该驾驶员，请确认姓名或工号后重试"}
```
6. 所有基础指标名称必须逐字来自本次 MCP/工具结果中的可引用子项，优先使用 `quota_summary[].indicators[].name`、`result.quotaScoreSubList[].quotaName`、高风险清单中的同名指标字段或等价明细字段；不得把知识库概括词、管理抓手、维度归纳词或模型自行总结的指标名写入 `management_summary.major_risk_factors`、`dashboard_rows[].core_risk_indicators`、`behavior_data_analysis.analysis_items[].top_indicator`、`behavior_data_analysis.analysis_items[].insight`、`interventions.recommendations[].indicator` 或建议前缀中。若源数据没有该指标名称，最终报告不得出现该名称。

## 模板标注语法（硬约束）
- 数据植入位必须用 `{}`，例如 `{张三}`、`{43}`、`{50/90}`。
- AI分析发挥必须用 `【】`，不得使用 `[]` 代替。
- 以下字段必须同时满足 `{}` 与 `【】` 标注规则：
  - `layout.summary`
  - `management_summary.summary_text`
  - `core_risk_assessment.summary`
  - `behavior_data_analysis.analysis_items[].insight`
  - `interventions.recommendations[].suggestion`

## 一级指标映射规则（核心）
多维绩效看板固定输出以下 5 行：`综合风险` 必须位于第一行，其余核心维度按 `score` 风险得分从高到低排列，`null` 放最后：
- `综合风险`
- `事故风险`
- `能耗风险`
- `服务态度`
- `安全评价`

取值优先级：
1. 优先读取新结构（若存在）：
   - `performance_dashboard.summary.overall_score` / `performance_dashboard.dimensions.综合风险`
   - `performance_dashboard.dimensions.事故风险`
   - `performance_dashboard.dimensions.能耗风险`
   - `performance_dashboard.dimensions.服务态度`
   - `performance_dashboard.dimensions.安全评价`
2. 若新结构缺失，则从旧结构映射：
   - `综合风险 <- performance_dashboard.summary.overall_score`
   - `事故风险 <- performance_dashboard.dimensions.综合安全`
   - `能耗风险 <- performance_dashboard.dimensions.行车技能`
   - `服务态度 <- performance_dashboard.dimensions.驾驶态度`
   - `安全评价 <- performance_dashboard.dimensions.行为习惯`

禁止项：
- 不得把 `综合安全/行车技能/驾驶态度/行为习惯` 直接作为 `dashboard_rows.dimension` 输出。
- 不得把 `综合风险` 与四个一级指标混写成整体按分数重排；`综合风险` 必须始终在第一行，后续四个一级指标再按风险得分降序排列。

## 生成流程（硬约束）
1. 抽取基础信息：
   - 姓名、工号、风险等级、综合风险分、排名、主要风险因素。
2. 生成 `dashboard_rows`：
   - 输出 5 行：`综合风险` + 4 个一级指标。
   - 每项包含：`dimension`、`score`、`trend_text`、`core_risk_indicators`。
   - 行顺序为：`综合风险` 在第一行，后续 `事故风险/能耗风险/服务态度/安全评价` 按 `score` 从高到低排序，`null` 放最后。
   - `core_risk_indicators` 只能填入本次 MCP/工具结果明细中实际存在的基础指标名称。
3. 生成 `core_risk_assessment`：
   - `summary` 对齐话术文档“核心风险研判”的单段总结写法，包含：综合风险分、风险状态、排名/相对表现，以及 `【】` 中的 AI 研判。
   - `detail_lines` 为兼容字段，可输出空数组，不要求展开 4 条细项。
4. 生成 `behavior_data_analysis.analysis_items`：
   - 默认不重复分析 `综合风险` 行。
   - 重点分析存在核心风险指标的一级指标（事故风险/能耗风险/服务态度/安全评价）。
   - 每条包含：`rank_label`、`dimension`、`top_indicator`、`alert_count`、`insight`。
   - 输出顺序按一级指标风险高低排序；前缀依次为：`风险最高的一级指标是` / `其次是` / `再次是` / `最后是`。
   - 若某一级指标缺少直接报警次数，必须明确写“当前缺少直接报警次数”，不得伪造次数。
5. 生成 `interventions.recommendations`：
   - 该章节按全局高风险基础指标排序输出，不要求与 `analysis_items` 同数量，也不要求一一对应。
   - 最多输出 4 条，最少输出 1 条。
   - `priority` 必须是 `1..N`。
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
  "report_type": "driver_safety_summary_management",
  "template_version": "20260305",
  "report_role": "management",
  "layout": {
    "title": "驾驶员安全风险分析总结报告",
    "summary": "",
    "header": {
      "items": [
        {"label": "驾驶员", "value_path": "management_summary.driver_name"},
        {"label": "工号", "value_path": "management_summary.driver_id"},
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
          {"type": "list", "items_path": "core_risk_assessment.detail_lines", "ordered": true}
        ]
      },
      {
        "title": "三、行为与数据关联分析",
        "blocks": [
          {"type": "list", "items_path": "behavior_data_analysis.analysis_items", "ordered": true}
        ]
      },
      {
        "title": "四、针对性干预建议",
        "blocks": [
          {"type": "list", "items_path": "interventions.recommendations", "ordered": true}
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
    "driver_name": "",
    "driver_id": "",
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
- `trend_text` 统一格式：`同比X，环比Y，同单位比Z，同线路比W`。
- 无法从数据直接映射的值使用 `null` 或 `"—"`，禁止输出“暂无/待补充/建议事项/未知”。
- 若某维度缺少直接明细指标，允许输出维度级管理抓手，但必须显式说明“当前缺少直接报警指标/次数”，不得伪造具体告警数据。
- 附录仅放本次查询用到的原始数据，不输出无关内容。

## 输出前自检（必须全部满足）
- `dashboard_rows` 固定为 5 行：第一行必须是 `综合风险`，后续四个核心维度按 `score` 风险得分从高到低排列，`null` 放最后。
- `core_risk_assessment.summary` 对齐话术文档中的单段“核心风险研判”写法。
- `analysis_items` 默认不展开 `综合风险`，且只分析真正存在核心风险的一级指标。
- `recommendations` 是全局基础指标排序结果，不要求与 `analysis_items` 同数量，也不要求一一对应。
- `management_summary.major_risk_factors`、`dashboard_rows[].core_risk_indicators`、`analysis_items[].top_indicator`、`recommendations[].indicator` 必须能在本次 `appendix.raw_data` 中回溯到同名字段；发现不存在的指标名时必须移除或替换为真实同名指标，不得改用近义词或上位概念。
- `recommendations[0].suggestion` 包含 `风险最高的基础指标是`；
  若存在第 2 条建议，则包含 `其次是`。
- 关键文本字段满足 `{}` + `【】` 标注语法。

## 禁止事项
- 禁止未查询数据直接生成报告。
- 禁止输出旧模板字段代替主结构（如仅输出 `performance_dashboard`）。
- 禁止在最终正文里输出 `综合安全/行车技能/驾驶态度/行为习惯` 作为四个一级维度。
- 禁止把 5 行看板写成按分数重排；看板顺序必须固定，但分析和建议可以按风险高低排序。
- 禁止复用固定示例数值（如 91.74、200 次、50/90）作为本次真实结论。
