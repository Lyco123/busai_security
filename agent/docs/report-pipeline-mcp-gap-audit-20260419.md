# 报告管线 MCP 接入缺口整理

文档基于 [MCP服务设计文档20260417.md](/d:/BUS/agent/docs/MCP服务设计文档20260417.md) 与当前报告管线实现整理，范围仅覆盖现有报告管线：

- 驾驶员报告
- 车辆报告
- 单位报告
- 线路报告
- 事故调查报告

## 建议类 MCP

设计文档中已提供的建议类接口：

- `get_mcp_suggest_absBusSuggestedSub_queryByBusNameAndDate`
- `get_mcp_suggest_absDriverSuggestedSub_queryByDriverNameAndDate`
- `get_mcp_suggest_absRouteSuggestedSub_queryByRouteNameAndDate`
- `get_mcp_suggest_absCompanySuggestedSub_queryByOrganNameAndDate`

当前接入状态：

- 车辆报告：已接入
- 驾驶员报告：已接入
- 线路报告：已接入
- 单位报告：已接入
- 事故调查报告：文档中未发现对应“建议明细” MCP，当前无可接入接口

当前仍未接入的建议部分：

- 事故调查报告对应的建议类 MCP
  说明：在 `MCP服务设计文档20260417.md` 中未检索到事故调查报告专用的建议明细接口

## 趋势类 MCP

设计文档中与现有报告管线直接相关的趋势类接口：

- `get_mcp_base_absCompanyProfileMain/getKeyRisk`
  用途：单位画像关键指标同比/环比/同机构对比
- `get_mcp_base_absCompanyProfileMain/quotaScoreTrend`
  用途：单位画像综合评分趋势

当前接入状态：

- 单位报告 `getKeyRisk`：已接入
- 单位报告 `quotaScoreTrend`：未接入
- 驾驶员报告：文档中未发现对应趋势 MCP
- 车辆报告：文档中未发现对应趋势 MCP
- 线路报告：文档中未发现对应趋势 MCP
- 事故调查报告：文档中未发现对应趋势 MCP

当前仍未接入的趋势部分：

- `get_mcp_base_absCompanyProfileMain/quotaScoreTrend`
  说明：当前单位报告只接入了 `getKeyRisk` 生成维度趋势文案，尚未消费综合评分时间序列趋势

## 备注

- 本次接入已统一放在共享画像适配层与结构化预取入口，避免“预取 report_source”路径绕过补充 MCP。
- 若后续要补 `quotaScoreTrend`，建议仍放在单位共享适配层内统一注入，再由单位报告归一化层决定是否展示为趋势段落或附录时间序列。
