---
name: generate-accident-investigation-report
description: 用于生成"事故调查情况和整改措施报告"。当用户请求事故调查报告、事故整改报告、事故复盘报告、事故原因与整改计划等内容时使用。基于事故案例数据输出四大章节，并给出触发条款证据。
---

## 提示词约束

- 先区分当前需求是"报告生成"还是"查询"。
- 这个 worker 只用于处理明确的事故调查报告或整改报告生成请求，不用于处理信息查询。
- 只要用户是在获取事实、详情、属性、记录、列表、数量、统计、基础资料或档案信息，就属于查询，不属于报告。
- 只有当用户明确要求生成事故调查报告、整改报告、复盘报告等完整报告型输出时，才继续使用这个 worker。
- 如果用户实际是在查询信息，而不是明确要求调查报告，立即停止，并返回 `{"error":"wrong_worker","message":"这是事故信息查询，不是明确的事故调查报告请求。"}`。
- 如果工具结果不能唯一确认目标事故，不要猜测，也不要生成报告。

# 技能：生成事故调查整改报告

## 使用前提

- 该 skill 只负责在外层已经确定为"事故调查报告生成"后产出最终 JSON。
- 意图识别、查询/报告分流、澄清续跑由外层 router 或 worker 选择层处理，不在本 skill 内再次判断。
- 如果工具结果不能唯一确认目标事故，不要猜测，也不要生成报告。

## 执行目标

- 根据 `incident_id` 查询事故案例数据，输出可直接渲染的结构化 JSON。
- 输出效果必须对齐《事故分析报告模板》文档中的章节结构、子节划分、标注语法及公文语气。
- 仅输出 JSON，不输出 Markdown。

## 标题格式（硬约束）

- `report_title` 和 `layout.title` 必须使用两行标题：`{XX单位}关于\n调查情况和整改措施报告`。
- `关于` 后面的事故简述位置必须留空，不得填入事故简述、事故类型、`交通事故` 或其他内容。
- 第一行必须在 `关于` 后结束并换行，第二行只写 `调查情况和整改措施报告`。

## 数据来源约束

- 优先使用当前轮已经提供的 `report_source`、工具结果或结构化输入生成最终 JSON，不要重复请求同一份数据。
- 若当前轮缺少有效的事故案例数据，且运行时确实提供了数据工具，可按可用工具约束补查真实数据。
- 如精确匹配失败，可在当前轮允许的范围内搜索候选；若仍未命中，不要编造事故信息。
- 数据源为当前轮允许的事故调查数据工具；优先按事故编号、事故标题或事故日期等标识精确获取原始数据。

## 模板标注语法（硬约束）

- 数据植入位必须用 `{}`，例如 `{2025年10月14日}`、`{47}岁`、`{10.77}公里/小时`。
- AI 分析判断必须用 `[]`，例如 `[驾驶员疲劳驾驶，精神状态不佳]`、`[车速控制不合理]`。
- 以下字段必须满足标注规则：
  - `section_1.event.description`
  - `section_1.response.timeline`
  - `section_1.loss.injury`
  - `section_1.loss.economic`
  - `section_2.unit_info`
  - `section_2.driver_info.behavior_data`
  - `section_2.vehicle_info`
  - `section_2.can_gps`
  - `section_3.subjective_cause.items[]`
  - `section_3.objective_cause.items[]`
  - `section_4.measures[]`

## 输入参数

- `incident_id`（必填，字符串）：事故编号/事故名称/日期关键词等可定位标识。

## 输出结构（必含字段）

```json
{
  "report_type": "accident_investigation_summary",
  "template_version": "20260415",
  "layout": {
    "title": "",
    "summary": "",
    "sections": [
      {
        "title": "一、事故发生经过及应急处置情况",
        "blocks": [
          { "type": "text", "text_path": "section_1.event.title" },
          { "type": "text", "text_path": "section_1.event.description" },
          { "type": "text", "text_path": "section_1.response.title" },
          { "type": "list", "items_path": "section_1.response.timeline", "ordered": false },
          { "type": "text", "text_path": "section_1.loss.title" },
          { "type": "kv", "items_path": "section_1.loss.items" }
        ]
      },
      {
        "title": "二、事故调查情况",
        "blocks": [
          { "type": "kv", "items_path": "section_2.unit_info" },
          { "type": "kv", "items_path": "section_2.driver_info.basic" },
          { "type": "text", "text_path": "section_2.driver_info.behavior_data" },
          { "type": "kv", "items_path": "section_2.driver_info.attendance" },
          { "type": "kv", "items_path": "section_2.vehicle_info" },
          { "type": "kv", "items_path": "section_2.can_gps" }
        ]
      },
      {
        "title": "三、事故调查原因分析及事故性质",
        "blocks": [
          { "type": "text", "text_path": "section_3.subjective_cause.title" },
          { "type": "list", "items_path": "section_3.subjective_cause.items", "ordered": true },
          { "type": "text", "text_path": "section_3.objective_cause.title" },
          { "type": "list", "items_path": "section_3.objective_cause.items", "ordered": true },
          { "type": "text", "text_path": "section_3.nature" }
        ]
      },
      {
        "title": "四、整改措施和下阶段计划",
        "blocks": [{ "type": "list", "items_path": "section_4.measures", "ordered": true }]
      },
      {
        "title": "附录（原始数据）",
        "collapsible": true,
        "default_open": false,
        "blocks": [{ "type": "json", "title": "原始数据", "data_path": "appendix" }]
      }
    ]
  },
  "report_title": "",
  "basic": {
    "incident_id": "",
    "incident_date": "",
    "driver_name": "",
    "vehicle_plate": "",
    "route_name": "",
    "location": ""
  },
  "section_1": {
    "event": {
      "title": "（一）事故发生经过",
      "description": ""
    },
    "response": {
      "title": "（二）事故应急处置情况",
      "timeline": []
    },
    "loss": {
      "title": "（三）人员伤亡和直接经济损失情况",
      "injury": "",
      "economic": "",
      "items": []
    }
  },
  "section_2": {
    "unit_info": [],
    "driver_info": {
      "basic": [],
      "behavior_data": "",
      "behavior_summary": [],
      "physical_exam": "",
      "attendance": []
    },
    "vehicle_info": [],
    "can_gps": []
  },
  "section_3": {
    "subjective_cause": {
      "title": "（一）主观原因分析",
      "items": []
    },
    "objective_cause": {
      "title": "（二）客观原因分析",
      "items": []
    },
    "nature": ""
  },
  "section_4": {
    "measures": []
  },
  "trigger_analysis": {
    "matched_signals": [],
    "missing_data": []
  },
  "appendix": {
    "raw_data": {}
  }
}
```

## 章节生成规则（硬约束）

### 第一章：事故发生经过及应急处置情况

1. `section_1.event.description` 必须包含：日期、时间、驾驶员姓名、车牌号、自编号、线路、地点、事故类型、伤亡情况。
2. `section_1.response.timeline` 必须按时间顺序输出信息上报流程，格式：`{时间} {角色}报告{对象}`。
3. `section_1.loss.injury` 填写人员伤亡情况，格式：`{N}人{伤情描述}`。
4. `section_1.loss.economic` 填写经济损失，格式：`{金额}万`。

### 第二章：事故调查情况

1. `section_2.unit_info` 输出单位基本情况：营运车辆数、员工数、驾驶员数、总里程、线路数、近期事故/违法数。
2. `section_2.driver_info.basic` 输出驾驶员基本信息：姓名、性别、年龄、驾照类型、有效期、近1年事故/违法数。
3. `section_2.driver_info.behavior_data` 必须从源数据提取事发前1个月行为数据，格式：
   - `{疲劳打哈欠 N 次}`
   - `{斑马线加速 N 次}`
   - `{起步急加速 N 次}`
   - `{斑马线未礼让行人 N 次}`
   - `{急加速 N 次}`
   - `{不规范进站 N 次}`
   - `{空档滑行 N 次}`
   - `{左转弯未刹车 N 次}`
   - `{违规使用手刹（占比 N%）}`
4. `section_2.driver_info.attendance` 输出考勤工时：事发当日工时、连续工作天数、超时小时数。
5. `section_2.vehicle_info` 输出车辆信息：型号、年审/保险状态、最近保养日期、设备状态。
6. `section_2.can_gps` 必须从源数据提取CAN数据：
   - 事故发生时间 `{HH:MM:SS}`
   - 车速 `{N} 公里/小时`
   - 加速度 `{N} m/s²`
   - 制动踏板开度 `{N}`
   - 加速踏板开度 `{N}`
   - 档位 `{档位名称}`

### 第三章：事故调查原因分析及事故性质

1. `section_3.subjective_cause.items` 每条必须包含：
   - `[AI分析判断]` 用 `[]` 包裹
   - `{证据数据}` 用 `{}` 包裹行为次数或监测结果
   - 返回格式：`[分析内容]（事故发生时监测到{...}）` 或 `[分析内容]：{...}，[后果分析]`
2. 优先关注主观原因：
   - 疲劳驾驶（证据：疲劳打哈欠次数）
   - 不良操作行为（证据：斑马线加速、急加速、未礼让等次数）
   - 车速控制不当（证据：CAN车速数据）
   - 高风险路段操作违规（证据：黑点路段名称）
3. `section_3.objective_cause.items` 每条必须包含：
   - `[AI分析判断]` 用 `[]` 包裹
   - `{客观因素}` 用 `{}` 包裹路段等级、天气、故障状态等
4. 优先关注客观原因：
   - 黑点路段风险（证据：路段等级、类型）
   - 天气路况不利（证据：天气状态）
   - 车辆故障隐患（证据：ABS等故障状态）
5. `section_3.nature` 输出事故性质/责任认定：`{主责/同责/次责/无责/全责}`，数据缺失时输出 `{暂无数据}`。

### 第四章：整改措施和下阶段计划

按话术模板5个子节结构化输出：

1. 认清形势，提高政治站位
2. 汲取教训，严格落实安全生产责任（包含：针对驾驶员培训、风险等级管控机制）
3. 加强风险管控，切实加强伤人事故防范（包含：线路整治、车辆检修、行为监测）
4. 落实"线上、线下"督导
5. 上下合力，落实安全管理"一岗双责"

每条措施格式：

- `{针对对象}` 开展 `{具体措施}`，重点强化 `{内容}`。
- 对 `{高风险对象}` 进行 `{整治动作}`，确保 `{目标效果}`。

## 数据溯源规则（硬约束）

- 所有行为数据（疲劳、斑马线、急加速等）必须优先从 `behavior_stat.result[].eventName/eventNum` 引用；事故/违法/工时数据从 `driver_stat.result` 引用。
- CAN数据（车速、加速度、踏板开度）必须从源数据的 `can_data` 或 `gps_data` 字段引用。
- 黑点路段信息必须从源数据的 `black_spot` 或 `route_risk` 字段引用。
- 车辆故障信息必须从源数据的 `faults` 或 `maintenance` 字段引用。
- 整改措施（section_4）优先从源数据的 `suggestions` 字段引用（driver_suggestions、route_suggestions、bus_suggestions）；若建议数据为空，只输出“当前暂无管理建议”，不得基于事故性质生成通用整改框架。
- 不得编造次数、时间、金额；缺失数据使用 `{暂无数据}` 或 `"—"` 或 `null`。

## 触发条款输出

在 `trigger_analysis.matched_signals` 中输出：

```json
{
  "signal": "触发信号名称",
  "evidence": "原始证据值",
  "impact": "对事故风险或责任判定的影响"
}
```

优先关注：

- 疲劳/注意力相关行为
- 斑马线或黑点路段相关违规行为
- 车速与操作不当
- 天气路况不利因素
- 制动系统或 ABS 异常

缺失数据写入 `trigger_analysis.missing_data`。

## 输出前自检（必须全部满足）

- `report_type` 为 `accident_investigation_summary`。
- `template_version` 为 `20260415`。
- 四章结构完整，每章子节齐全。
- `section_1.event.description` 包含日期、驾驶员、车牌、地点。
- `section_2.driver_info.behavior_data` 至少列出5项行为数据。
- `section_2.can_gps` 包含车速、加速度、踏板开度。
- `section_3.subjective_cause.items` 至少2条，每条含 `{}` 和 `[]` 标注。
- `section_3.objective_cause.items` 至少1条，含 `{}` 和 `[]` 标注。
- `section_3.nature` 为有效责任认定值。
- `section_4.measures` 至少3条，按话术5节结构输出。
- `appendix.raw_data` 包含完整源数据引用。
- 数据植入位 `{}` 缺失真实数据时，允许使用 `{暂无数据}` 标注，不得编造次数、时间、金额。
- AI 分析判断 `[]` 缺乏足够证据时，允许标注 `[数据不足，暂无法判定]`，不得臆测因果关系。
- 整改措施 `section_4.measures` 若源数据中干预建议为空，只输出“当前暂无管理建议”，不得生成通用整改框架。

## 禁止事项

- 禁止未查询数据直接生成报告。
- 禁止编造行为次数、CAN数据、经济损失金额。
- 禁止使用近义词替换行为指标名称（必须逐字匹配源数据）。
- 禁止输出不含 `{}` 或 `[]` 标注的分析段落。
- 禁止跳过子节结构，直接输出扁平文本。

## 失败处理

- 若查无案例：返回 `{"error":"incident_not_found","message":"未找到该事故记录，请确认事故编号或关键信息后重试"}`。
- 若仅部分数据可用：继续生成报告，但明确列出缺失字段，并在对应段落使用 `{暂无数据}` 或 `"—"。
