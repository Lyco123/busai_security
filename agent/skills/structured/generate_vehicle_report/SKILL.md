---
name: generate-vehicle-report
description: 用于生成车辆安全风险分析总结报告（管理人员版），输出严格 JSON，前端按 layout 渲染。
---

# 技能：车辆安全风险分析总结报告（管理人员版）

## 使用前提
- 该 skill 只负责在外层已经确定为“车辆管理人员版报告生成”后产出最终 JSON。
- 意图识别、查询/报告分流、澄清续跑由外层 router 或 worker 选择层处理，不在本 skill 内再次判断。
- 如果工具结果不能唯一确认目标车辆，不要猜测，也不要生成报告。

## 执行目标
- 根据 `numberplate` 查询车辆画像数据，输出可直接渲染的结构化 JSON。
- 输出效果必须对齐《车辆画像 AI 通用话术（20260305）》中“AI 安全风险分析总结报告回复模版——管理人员”。
- 输出体验、章节结构、字段组织方式与驾驶员报告 skill 保持一致。
- 仅输出 JSON，不输出 Markdown。

## 数据来源约束
1. 优先使用当前轮已经提供的 `report_source`、工具结果或结构化输入生成最终 JSON，不要重复请求同一份数据。
2. 当前车辆报告只支持按车牌号查询，不接受车辆自编号、profile `identifier` 或 profile `id` 作为报告主查询键。
3. `ppartition` 为可选参数；未提供时默认查询最新画像日期。若提供，必须是 `yyyyMMdd` 格式单日分区；如果当前轮提示词给出固定 `ppartition`，必须按提示词值使用，不得自行改写。
4. 若用户只提供了过短片段（如单个字母、单个汉字、1-3 位数字），不得模糊猜测到某台车，必须视为信息不足并等待补充。
5. 若当前轮缺少可用的车辆画像数据，且运行时确实提供了数据工具，可再按可用工具约束补查；若最终仍未命中或 `result/main` 为空，只返回错误 JSON，不得输出报告正文：
```json
{"error":"vehicle_not_found","message":"未找到该车辆画像数据，请确认车牌号后重试"}
```
6. 所有基础指标名称必须逐字来自本次 MCP/工具结果中的可引用子项，优先使用 `quota_summary[].indicators[].name`、`result.quotaScoreSubList[].quotaName` 或等价明细字段；不得把知识库概括词、管理抓手、维度归纳词或模型自行总结的指标名写入 `major_risk_factors`、`dashboard_rows[].core_risk_indicators`、`behavior_data_analysis.analysis_items[].top_indicator`、`behavior_data_analysis.analysis_items[].insight`、`interventions.recommendations[].indicator` 或建议前缀中。若源数据没有该指标名称，最终报告不得出现该名称。

## 模板标注语法（硬约束）
- 数据植入位必须用 `{}`，例如 `{粤A12345}`、`{43}`、`{50/90}`。
- AI 分析发挥必须用 `【】`，不得使用 `[]` 代替。
- 以下字段必须同时满足 `{}` 与 `【】` 标注规则：
  - `layout.summary`
  - `management_summary.summary_text`
  - `core_risk_assessment.summary`
  - `behavior_data_analysis.analysis_items[].insight`
  - `interventions.recommendations[].suggestion`
- `core_risk_assessment.detail_lines` 是兼容字段，可保留为空数组；不要再把它作为必写正文段落。

## 一级指标映射规则（核心）
目标一级指标固定为以下三项，最终输出中只能出现这三项名称：
- `综合风险`
- `故障风险`
- `能耗风险`

取值优先级：
1. 优先读取新结构（若存在）：
   - `performance_dashboard.dimensions.综合风险`
   - `performance_dashboard.dimensions.故障风险`
   - `performance_dashboard.dimensions.能耗风险`
2. 若新结构缺失，则从车辆通用结构映射：
   - `综合风险 <- performance_dashboard.summary.overall_score / risk_profile.overall`
   - `故障风险 <- risk_profile.mechanical / health_status.overall_score / health_status.overall`
   - `能耗风险 <- risk_profile.operation / energy_profile.overall / operation_profile.overall`
3. 若某维度缺少直接明细指标，可从以下位置提取基础风险因子：
   - `high_risk_indicators.indicators`
   - `alerts`
   - `maintenance.open_items`
   - `violations`
   - `appendix.raw_data.alerts_counts`

禁止项：
- 不得把 `机械风险/运营风险/运行风险/车辆健康/综合安全` 直接作为 `dashboard_rows.dimension` 输出。
- 不得把告警列表、保养列表、建议列表直接当作一级维度名称。
- 不得把 `故障告警/维修待办/保养项` 归到 `能耗风险`。
- 不得把 `?`、`??`、`未知`、`待评估` 之类占位词直接输出为风险状态；若原始等级无效，必须结合综合分映射为稳定标签。

## 生成流程（硬约束）
1. 抽取基础信息：
   - 车牌号、自编号、车型、所属车队、风险等级、风险分、排名、主要风险因素、统计周期。
2. 生成 `management_summary` 与 `layout.summary`：
   - 首句严格对齐参考话术：`{日期区间}车辆{车牌}(自编号{自编号})被系统预判为{风险等级}，主要风险因素为{...}，需引起重视。`
   - `layout.summary` 与 `management_summary.summary_text` 语义保持一致。
   - 优先输出可读日期区间；如果只能拿到单日，则输出可读日期。
3. 生成 `dashboard_rows`：
   - 仅输出三个一级指标：`综合风险`、`故障风险`、`能耗风险`。
   - 每项包含：`dimension`、`score`、`trend_text`、`core_risk_indicators`。
   - 行顺序为：`综合风险` 在第一行，后续 `故障风险/能耗风险` 按 `score` 从高到低排序，`null` 放最后。
   - 不要按分数重排整张看板。
   - `综合风险` 的 `core_risk_indicators` 可列 2-4 个综合性主风险因子；`故障风险/能耗风险` 应尽量保留该维度在多维看板中实际出现的全部核心基础指标，不要擅自压缩成 1-2 个。
   - `core_risk_indicators` 只能填入本次 MCP/工具结果明细中实际存在的基础指标名称。
4. 生成 `core_risk_assessment`：
   - 该章节只输出一个总结段 `summary`，不要再展开 3 条编号明细。
   - `summary` 必须对齐参考话术，包含：车辆标识、综合风险分、风险状态、排名/相对表现；AI 判断写入 `【】`。
   - `detail_lines` 保留为空数组即可，不要强行补写。
5. 生成 `behavior_data_analysis.analysis_items`：
   - 该章节分析“多维绩效看板”中真正需要解释的一级指标。
   - 如果某一级指标没有核心风险，则不要为了凑数硬写。
   - 默认不要分析 `综合风险`，避免把总分维度与分项维度重复叙述。
   - 优先分析 `故障风险`、`能耗风险` 中存在核心风险指标的维度。
   - 每条包含：`rank_label`、`dimension`、`top_indicator`、`alert_count`、`insight`；如某维度在多维看板中列了多个核心指标，`insight` 必须把这些指标全部展开说明。
   - `insight` 参考话术风格：
     - 第一条前缀：`风险最高的一级指标是{...}`
     - 第二条前缀：`其次是{...}`
     - 第三条前缀：`再次是{...}`
   - 只有当源数据中存在可核验次数时，才能写成 `{某指标N次}`；若缺少直接次数，必须明确说明“当前缺少直接报警指标/次数”，不得伪造数字。
   - `综合风险` 不属于行为与数据关联分析要展开的一级指标，默认不要分析；重点展开 `故障风险`、`能耗风险` 在多维看板中出现的全部指标及其源数据。
6. 生成 `interventions.recommendations`：
   - 该章节不是按一级维度一一对应生成，而是按全局基础指标风险值排序输出建议。
   - 指标排名依据系统“风险追踪列表”或等价原始来源中的基础指标风险值分数。
   - 最多输出 4 条，最少输出 1 条。
   - `priority` 必须是 `1..N`。
   - `indicator` 必须是该条建议针对的基础指标名。
   - `indicator` 必须逐字匹配本次 MCP/工具结果明细中的基础指标名称；不得为了表达管理方向而改写、合并或新增指标名称。
   - `suggestion` 文本前缀规则：
     - 第1条：`风险最高的基础指标是{...}`
     - 第2条：`其次是{...}`
     - 第3条：`再次是{...}`
     - 第4条：`最后是{...}`
   - 若原始数据存在对应建议，优先沿用；若缺失，可基于维度给出不虚构事实的管理动作建议。
7. 输出 `layout`，前端按 `layout` 渲染。

## 输出结构（必含字段）
```json
{
  "report_type": "vehicle_safety_summary_management",
  "template_version": "20260305",
  "report_role": "management",
  "layout": {
    "title": "车辆安全风险分析总结报告",
    "summary": "",
    "header": {
      "items": [
        {"label": "车牌号", "value_path": "management_summary.plate_number"},
        {"label": "自编号", "value_path": "management_summary.vehicle_id"},
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
    "plate_number": "",
    "vehicle_id": "",
    "vehicle_model": "",
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
- `trend_text` 统一格式：`同比X，环比Y，同单位比Z，同线路比W`。
- 无法从数据直接映射的值使用 `null` 或 `"—"`，禁止输出“暂无/待补充/建议事项/未知”。
- 若某维度缺少直接明细指标，允许输出维度级管理抓手，但必须显式说明“当前缺少直接报警指标/次数”，不得伪造具体告警数据。
- `major_risk_factors` 必须来自真实数据中的告警、待维修项、高风险指标或违章行为，不得凭空编造。
- `major_risk_factors`、`dashboard_rows[].core_risk_indicators`、`analysis_items[].top_indicator`、`recommendations[].indicator` 必须能在本次附录原始数据中回溯到同名字段；无法回溯同名字段时删除该指标，不得改用近义词或上位概念。
- 附录仅放本次查询用到的原始数据，不输出无关内容。

## 输出前自检（必须全部满足）
- `dashboard_rows` 仅含三个一级指标：第一行必须是 `综合风险`，后续 `故障风险/能耗风险` 按 `score` 风险得分从高到低排列，`null` 放最后。
- `layout.summary` 与 `management_summary.summary_text` 对齐参考模板首句，包含日期、车牌、自编号、风险等级、主要风险因素。
- `core_risk_assessment.summary` 为单段总结，不再强制要求编号明细。
- `core_risk_assessment.detail_lines` 允许为空数组。
- `analysis_items` 仅分析有核心风险的一级指标，默认不重复分析 `综合风险`。
- `recommendations` 是全局基础指标排序结果，不要求与 `analysis_items` 同数量，也不要求一一对应。
- 所有输出的基础指标名称均能在 `appendix.raw_data` 中找到同名来源；发现不存在的指标名时必须移除或替换为真实同名指标。
- `recommendations[0].suggestion` 包含 `风险最高的基础指标是`。
- 当存在第2/3/4条建议时，前缀分别为 `其次是`、`再次是`、`最后是`。
- 关键文本字段满足 `{}` + `【】` 标注语法。

## 禁止事项
- 禁止未查询数据直接生成报告。
- 禁止仅输出旧模板字段代替主结构（如仅输出 `risk_profile/maintenance/alerts`）。
- 禁止把 `机械风险/运营风险/运行风险/车辆健康` 作为一级维度直接输出。
- 禁止把 `综合风险` 当作与分项风险并列展开重复分析。
- 禁止复用固定示例数值（如 43、23、20、50/90、86次）作为本次真实结论。
- 禁止虚构政策依据、维修结论、告警次数、排名数据。
- 若源数据只有旧结构，也必须生成上述统一 JSON；允许通过映射补齐，不得退回旧平铺结构。
## 路由边界
- 本 skill 只能在路由层已经明确确认为“正式车辆报告请求”之后执行。
- 如果目标车辆存在歧义、冲突，或者无法唯一确认，不得生成报告。
- 如果用户最新意图是“不要正式报告”“只要口头汇报”“只看要点”“先查信息”“先看情况”等查询式表达，不得生成报告正文。
- 如果当前轮只提供了部分 JSON 片段或部分键值槽位，不得猜测缺失目标，应等待剩余必需字段补齐。
- 多轮对话中必须始终服从用户最新明确指定的目标车辆和最新明确指定的输出格式。
