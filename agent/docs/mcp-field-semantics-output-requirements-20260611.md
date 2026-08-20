# MCP fieldSemantics 输出要求

## 目的

当前 MCP tool 的返回 JSON 中缺少字段级语义说明，模型只能根据字段名猜测业务含义。由于部分字段名存在明显误导，例如 `score`、`originalValue`、`previousPeriodRiskValue`，模型容易把风险原始分误当最终风险分，或把环比增长率误当上期风险值。

本改造要求 MCP 服务端在工具返回内容中增加 `fieldSemantics`，直接说明字段真实业务含义、计量口径和禁止误读项。

覆盖范围：按 `MCP服务设计文档20260610.md` 的接口列表全量整理，包含交信投当前交付给我方的 32 个 MCP 接口。

## 输出位置

`fieldSemantics` 应放在 MCP 返回 JSON 的顶层，和 `success`、`message`、`code`、`result` 同级。

推荐结构：

```json
{
  "success": true,
  "message": "",
  "code": 200,
  "result": [],
  "fieldSemantics": {
    "score": "对应指标风险原始分，不是最终风险分。",
    "originalValue": "由 `score` 按 `weightRate` 权重换算得到的最终风险分/最终风险贡献，数值越高风险越高。"
  },
  "timestamp": 1780000000000,
  "path": "/driver/profile",
  "pathArgs": {}
}
```

如果同一字段在不同嵌套位置含义不同，使用路径写法：

```json
{
  "fieldSemantics": {
    "result.main.score": "画像综合风险分。",
    "result.quotaScoreSubList[].score": "对应指标风险原始分，不是最终风险分。",
    "result.quotaScoreSubList[].originalValue": "由 `score` 按 `weightRate` 权重换算得到的最终风险分/最终风险贡献，数值越高风险越高。"
  }
}
```

## 通用规则

- 不删除、不重命名现有字段，避免影响已有客户端。
- 当前阶段只要求 `fieldSemantics`，不要求新增字段别名。
- 语义说明使用中文自然语言，不使用英文别名。
- 所有风险分、风险值、风险贡献字段默认按“数值越高，风险越高”解释，除非字段语义明确写成完成率、合格率、下降率等非风险指标。
- `score` / `originalValue` 的说明用于修正当前字段命名误导；后续若服务端字段名和 schema 已改为明确语义，可同步移除客户端侧临时补丁和 prompt guardrail。

## 逐工具 fieldSemantics 清单

| MCP tool | 建议新增 / 覆盖的 fieldSemantics |
|---|---|
| `get_mcp_base_absBusProfileMain_queryByNumberplate` | `result.main.score`：车辆画像综合风险分；`quotaScoreSubList[].score`：对应指标风险原始分，不是最终风险分；`quotaScoreSubList[].originalValue`：由 `score` 按 `weightRate` 权重换算得到的最终风险分/最终风险贡献，数值越高风险越高；风险等级：4级危险型为 65-100 分，3级关注型为 55-64 分，2级观察型为 45-54 分，1级安全型为 0-44 分；`busName` / `numberPlate`：车辆牌照或车辆名称，需按实际返回字段说明；`busId`：车辆 ID；`weightRate`：指标权重；`riskData`：原始业务值或原始业务描述；三类 `pending*Count`：建议状态数量概览，不是建议内容明细。 |
| `get_mcp_base_absBusProfileMain_busRiskScore` | `currentRiskValue`：当前原始风险值；`convertedScore`：当前换算后风险分；`previousPeriodRiskValue`：环比风险值增长率，不是上期风险值；`previousPeriodScore`：上期换算后风险分；`lastYearSameDateRiskValue`：同比风险值增长率，不是去年同期风险值；`lastYearSameDateScore`：去年同期换算后风险分；`organAvgRiskValue` / `routeAvgRiskValue`：相对同机构/同线路均值的变化率；`organAvgScore` / `routeAvgScore`：同机构/同线路换算后均值。 |
| `get_mcp_base_absCompanyProfileMain_queryCompanyProfile` | `result.main.score`：单位画像综合风险分；`quotaScoreSubList[].score`：对应指标风险原始分，不是最终风险分；`originalValue`：由 `score` 按 `weightRate` 权重换算得到的最终风险分/最终风险贡献，数值越高风险越高；风险等级：4级危险型为 65-100 分，3级关注型为 55-64 分，2级观察型为 45-54 分，1级安全型为 0-44 分；`organName`：单位名称；`organId`：单位 ID；`weightRate`：指标权重；`riskData`：原始业务值；三类 `pending*Count`：建议状态数量概览，不是建议内容明细。 |
| `get_mcp_base_absDriverProfileMain_queryDriverProfile` | `result.main.score`：驾驶员画像综合风险分；`quotaScoreSubList[].score`：对应指标风险原始分，不是最终风险分；`originalValue`：由 `score` 按 `weightRate` 权重换算得到的最终风险分/最终风险贡献，数值越高风险越高；风险等级：4级危险型为 65-100 分，3级关注型为 55-64 分，2级观察型为 45-54 分，1级安全型为 0-44 分；`employeeName` / `driverName`：驾驶员姓名；`employeeId`：驾驶员 ID；`employeeCode`：驾驶员工号；`weightRate`：指标权重；`riskData`：原始业务值；三类 `pending*Count`：建议状态数量概览，不是建议内容明细。 |
| `get_mcp_base_absRouteProfileMain_queryRouteProfile` | `result.main.score`：线路画像综合风险分；`quotaScoreSubList[].score`：对应指标风险原始分，不是最终风险分；`originalValue`：由 `score` 按 `weightRate` 权重换算得到的最终风险分/最终风险贡献，数值越高风险越高；风险等级：4级危险型为 65-100 分，3级关注型为 55-64 分，2级观察型为 45-54 分，1级安全型为 0-44 分；`routeId`：线路 ID；`routeName`：线路名称；三类 `pending*Count`：建议状态数量概览，不是建议内容明细。 |
| `get_mcp_base_absRouteProfileMain_routeRiskScore` | `currentRiskValue`：当前原始风险值；`convertedScore`：当前换算后风险分；`previousPeriodRiskValue`：环比风险值增长率，不是上期风险值；`previousPeriodScore`：上期换算后风险分；`lastYearSameDateRiskValue`：同比风险值增长率，不是去年同期风险值；`lastYearSameDateScore`：去年同期换算后风险分；`organAvgRiskValue` / `routeAvgRiskValue`：相对同机构/同线路均值的变化率；`organAvgScore` / `routeAvgScore`：同机构/同线路换算后均值。 |
| `post_mcp_base_odsJituanBsBus_list` | `busName` / `numberPlate`：车辆牌照或车辆名称，需按实际返回字段说明；`busId`：车辆 ID；`organName`：所属单位；`routeName`：所属线路；分页包装字段需说明 `total` 是总记录数、`records` 是当前页记录，不能把当前页条数当总数。 |
| `post_mcp_ods_odsJituanBsBusPark_list` | `busParkName` / `parkName`：车场名称；`busStationName`：关联站场名称；`organName`：所属单位；服务车辆数、使用单位数等数量字段如存在，需说明是接口返回数量；分页包装字段需说明总数和当前页记录的区别。 |
| `post_mcp_ods_odsJituanBsBusStation_list` | `busStationId`：站场 ID；`busStationName`：站场名称；`organName`：所属单位；`manageOrgName`：管理单位；`stationType`、`stationProperties`：站场类型/属性编码；如有 `_dictText` 字段，说明其为对应编码的中文文本。 |
| `post_mcp_ods_odsJituanBsEmployee_list` | `employeeName` / `driverName`：驾驶员姓名；`employeeId`：驾驶员 ID；`employeeCode`：驾驶员工号；`organName`：所属单位；`routeName`：所属线路；分页包装字段需说明总数和当前页记录的区别。 |
| `post_mcp_ods_odsJituanBsRoute_list` | `routeId`：线路 ID；`routeName`：线路名称；`organName`：所属单位；`busCount`：该线路登记车辆数；`driverCount`：该线路登记驾驶员数；分页包装字段需说明总数和当前页记录的区别。 |
| `get_mcp_base_adsAccidentProfileMain_queryAccidentProfile` | `result.main.score`：事故画像综合风险分；`quotaScoreSubList[].score`：对应指标风险原始分，不是最终风险分；`originalValue`：由 `score` 按 `weightRate` 权重换算得到的最终风险分/最终风险贡献，数值越高风险越高；风险等级：4级危险型为 65-100 分，3级关注型为 55-64 分，2级观察型为 45-54 分，1级安全型为 0-44 分；`organName`：单位名称；`organId`：单位 ID；`weightRate`：指标权重；`riskData`：原始业务值；三类 `pending*Count`：建议状态数量概览，不是建议内容明细。 |
| `get_mcp_suggest_absBusSuggestedSub_queryByBusNameAndDate` | `score`：建议关联指标风险原始分，不是最终风险分；`originalValue`：由 `score` 按 `weightRate` 权重换算得到的最终风险分/最终风险贡献，数值越高风险越高；`weightRate`：指标权重；`riskData`：原始业务值；`suggestedContent`：管理/干预建议内容；三类状态字段语义同建议明细结构；`acceptStatu`、`disposeStatu`、`optimizeStatus`：状态编码，优先使用对应 `_dictText` 面向用户解释；`optimizeScoreBefore` / `optimizeScore`：优化前后风险分；`busName` / `numberPlate`：车辆牌照或车辆名称，需按实际返回字段说明；`busId`：车辆 ID。 |
| `get_mcp_suggest_absDriverSuggestedSub_queryByDriverNameAndDate` | `score`：对应指标风险原始分，不是最终风险分；`originalValue`：由 `score` 按 `weightRate` 权重换算得到的最终风险分/最终风险贡献，数值越高风险越高；`riskData`：原始业务值；`suggestedContent`：管理/干预建议内容；三类状态字段语义同建议明细结构；`acceptStatu`、`disposeStatu`、`optimizeStatus`：状态编码，优先使用对应 `_dictText` 面向用户解释；`optimizeScoreBefore` / `optimizeScore`：优化前后风险分；`employeeName` / `driverName`：驾驶员姓名；`employeeId` / `driverId`：驾驶员 ID；`employeeCode`：驾驶员工号。 |
| `get_mcp_suggest_absRouteSuggestedSub_queryByRouteNameAndDate` | `score`：对应指标风险原始分，不是最终风险分；`originalValue`：由 `score` 按 `weightRate` 权重换算得到的最终风险分/最终风险贡献，数值越高风险越高；`riskData`：原始业务值；`suggestedContent`：管理/干预建议内容；三类状态字段语义同建议明细结构；`acceptStatu`、`disposeStatu`、`optimizeStatus`：状态编码，优先使用对应 `_dictText` 面向用户解释；`optimizeScoreBefore` / `optimizeScore`：优化前后风险分；`routeName`：线路名称；`routeId`：线路 ID。 |
| `get_mcp_suggest_absCompanySuggestedSub_queryByOrganNameAndDate` | `score`：对应指标风险原始分，不是最终风险分；`originalValue`：由 `score` 按 `weightRate` 权重换算得到的最终风险分/最终风险贡献，数值越高风险越高；`riskData`：原始业务值；`suggestedContent`：管理/干预建议内容；三类状态字段语义同建议明细结构；`acceptStatu`、`disposeStatu`、`optimizeStatus`：状态编码，优先使用对应 `_dictText` 面向用户解释；`optimizeScoreBefore` / `optimizeScore`：优化前后风险分；`organName`：单位名称；`organId`：单位 ID。 |
| `get_mcp_blackspot_adsEventBlackSpot_queryConfirmedBlackSpots` | `blackType`：黑点类型编码；`blackType_dictText`：黑点类型中文文本；`eventType`：事件类型编码；`eventLevel`：事件等级编码；`eventLevel_dictText`：事件等级中文文本；`eventCount`：黑点事件次数；`clusterSize`：聚类事件数量；`startDate` / `endDate`：告警开始/结束日期；`longitude` / `latitude`：经纬度，需明确坐标系；`routeIds`：关联线路 ID 列表；`routeName`：关联线路名称列表。 |
| `get_mcp_base_absCompanyProfileMain_quotaScoreTrend` | `quotaScores[].ppartition`：趋势周期标签；`quotaScores[].score`：趋势中的指标风险原始分，不是最终风险分；`quotaScores[].originalValue`：趋势中由 `score` 按 `weightRate` 权重换算得到的最终风险分/最终风险贡献，数值越高风险越高；`quotaId`：指标 ID；`quotaName`：指标名称；当 `quotaId` / `quotaName` 为「总分」时，该组数据表示综合风险分趋势；`organName`：单位名称；`organId`：单位 ID。 |
| `get_mcp_base_absCompanyProfileMain_getKeyRisk` | `currentRiskValue`：当前原始风险值；`convertedScore`：当前换算后风险分；`previousPeriodRiskValue`：环比风险值增长率，不是上期换算后风险分/原始风险值；`previousPeriodScore`：上期换算后风险分；`lastYearSameDateRiskValue`：同比风险值增长率，不是去年同期换算后风险分/原始风险值；`lastYearSameDateScore`：去年同期换算后风险分；`organAvgRiskValue` / `routeAvgRiskValue`：相对同机构/同线路原始风险值均值的变化率；`organAvgScore` / `routeAvgScore`：同机构/同线路换算后风险分的均值；`xxxRiskValue0` 如保留，需说明是对应基准期/均值的原始风险值，并建议后续去掉 `0` 后缀；`organName`：单位名称；`organId`：单位 ID。 |
| `get_mcp_base_absDriverProfileMain_driverRiskScore` | `currentRiskValue`：当前原始风险值；`convertedScore`：当前换算后风险分；`previousPeriodRiskValue`：环比风险值增长率，不是上月换算后风险分/上期原始风险值；`previousPeriodScore`：上期换算后风险分；`lastYearSameDateRiskValue`：同比风险值增长率，不是去年同期换算后风险分/原始风险值；`lastYearSameDateScore`：去年同期换算后风险分；`organAvgRiskValue` / `routeAvgRiskValue`：相对同机构/同线路原始风险值均值的变化率；`organAvgScore` / `routeAvgScore`：同机构/同线路换算后风险分的均值；`employeeName` / `driverName`：驾驶员姓名；`employeeId`：驾驶员 ID；`employeeCode`：驾驶员工号。 |
| `get_mcp_base_absDriverProfileMain_getQuotaScoreTop` | `quotaScores[].ppartition`：趋势周期标签；`quotaScores[].score`：对应指标风险原始分，不是最终风险分；`quotaScores[].originalValue`：由 `score` 按 `weightRate` 权重换算得到的最终风险分/最终风险贡献，数值越高风险越高；`quotaId`：指标 ID；`quotaName`：指标名称；Top 结果按 `originalValue` 表示高风险/重点指标，不得把 `score` 当最终风险分；`employeeName` / `driverName`：驾驶员姓名；`employeeId`：驾驶员 ID；`employeeCode`：驾驶员工号。 |
| `get_mcp_base_absDriverProfileMain_quotaScoreTrend` | `quotaScores[].ppartition`：趋势周期标签；`quotaScores[].score`：趋势中的指标风险原始分，不是最终风险分；`quotaScores[].originalValue`：趋势中由 `score` 按 `weightRate` 权重换算得到的最终风险分/最终风险贡献，数值越高风险越高；`quotaId`：指标 ID；`quotaName`：指标名称；当 `quotaId` / `quotaName` 为「总分」时，该组数据表示综合风险分趋势；`employeeName` / `driverName`：驾驶员姓名；`employeeId`：驾驶员 ID；`employeeCode`：驾驶员工号。 |
| `get_mcp_ods_odsJituanBsEmployee_getOrganAccident` | `accidentCount`：单位事故总数；`accidentDescList`：当前页事故描述摘要列表，受分页影响，不能用其长度代替事故总数；`ppartitionStart` / `ppartitionEnd`：统计开始/结束日期；`organName`：单位名称；`organId`：单位 ID。 |
| `get_mcp_ods_odsJituanBsEmployee_getDriverCheckCount` / `get_mcp_ods_odsJituanBsEmployee_getDriderCheckCount` | `allCount`：应完成岗前检查次数；`actualCount`：实际完成岗前检查次数；`qualifiedCount`：合格次数；`unqualifiedCount`：不合格次数；`completePer`：完成率百分比；`unqualifiedPer`：不合格率百分比；`ppartition`：统计日期；`employeeName` / `driverName`：驾驶员姓名；`employeeId`：驾驶员 ID；`employeeCode`：驾驶员工号；`organName`：所属单位；`routeName`：所属线路。 |
| `get_mcp_ods_odsJituanBsEmployee_getBehaviorStat` | `employeeName` / `driverName`：驾驶员姓名；`employeeId`：驾驶员 ID；`employeeCode`：驾驶员工号；`organName`：所属单位；`routeName`：所属线路；`eventType`：行为类型编码；`eventName`：行为类型名称；`eventNum`：行为发生次数；`ranking`：行为次数排名，必须说明排名范围；`ppartitionStart` / `ppartitionEnd`：统计开始/结束日期。 |
| `get_mcp_ods_odsJituanBsEmployee_getAccidentList` | `accidentDate`：事故时间；`accidentPlace`：事故地点；`accidentDesc`：事故描述；`lineName`：线路名称；`busLicenseNum`：车牌号；`busCode`：车辆自编号；`employeeName` / `driverName`：驾驶员姓名；`employeeId`：驾驶员 ID；`employeeCode`：驾驶员工号；`accidentLiability`：责任编码，建议补对应字典文本；`opinionStatus`：处理意见状态编码，建议补对应字典文本；`isBlackspot`：是否关联黑点。 |
| `get_mcp_base_absCompanyProfileMain_getOrganAccidentCount` | `organName`：单位名称；`organId`：单位 ID；`accidentCount`：统计窗口内单位事故数；`trafficCount`：统计窗口内单位交通违法/违章数；需说明统计窗口由 `day` 和 `ppartition` 共同决定，且 `ppartition` 为空时的默认结束日期必须写清。 |
| `get_mcp_ods_odsJituanBsEmployee_getDriverAccidentCount` | `employeeName` / `driverName`：驾驶员姓名；`employeeId`：驾驶员 ID；`employeeCode`：驾驶员工号；`organName`：所属单位；`routeName`：所属线路；`accidentCount`：驾驶员事故统计窗口内事故数；`trafficCount`：驾驶员事故统计窗口内交通违法/违章数；`workTime`：统计窗口内工时；`workDay`：统计窗口内工作天数；`workTimeOver`：统计窗口内超时工时；`behaviorCounts[].eventType`：行为类型名称；`behaviorCounts[].eventCount`：行为统计窗口内行为次数；需说明 `day` 作用于事故/违章窗口，`behaviorDay` 作用于行为统计窗口。 |
| `get_mcp_base_absBusStationProfileMain_queryBusStationProfile` | `result.main.score`：站场画像综合风险分；`quotaScoreSubList[].score`：对应指标风险原始分，不是最终风险分；`originalValue`：由 `score` 按 `weightRate` 权重换算得到的最终风险分/最终风险贡献，数值越高风险越高；风险等级：4级危险型为 65-100 分，3级关注型为 55-64 分，2级观察型为 45-54 分，1级安全型为 0-44 分；`weightRate`：指标权重；`riskData`：原始业务值；`busStationName`：站场名称；`busStationId`：站场 ID；`manageOrgName`：管理单位；三类 `pending*Count`：建议状态数量概览，不是建议内容明细。 |
| `get_mcp_base_absBusStationProfileMain_stationRiskScore` | `currentRiskValue`：当前原始风险值；`convertedScore`：当前换算后风险分；`previousPeriodRiskValue`：环比风险值增长率，不是上期风险值；`previousPeriodScore`：上期换算后风险分；`lastYearSameDateRiskValue`：同比风险值增长率，不是去年同期风险值；`lastYearSameDateScore`：去年同期换算后风险分；`organAvgRiskValue` / `routeAvgRiskValue`：相对同机构/同线路均值的变化率；`organAvgScore` / `routeAvgScore`：同机构/同线路换算后均值。 |
| `get_mcp_suggest_absBusStationSuggestedSub_queryByBusStationNameAndDate` | `score`：对应指标风险原始分，不是最终风险分；`originalValue`：由 `score` 按 `weightRate` 权重换算得到的最终风险分/最终风险贡献，数值越高风险越高；`riskData`：原始业务值；`suggestedContent`：管理/干预建议内容；三类状态字段语义同建议明细结构；`acceptStatu`、`disposeStatu`、`optimizeStatus`：状态编码，优先使用对应 `_dictText` 面向用户解释；`optimizeScoreBefore` / `optimizeScore`：优化前后风险分；`busStationName`：站场名称；`busStationId`：站场 ID。 |
| `get_mcp_base_absBusProfileMain_getAccidentBusInfo` | `speed`：事故时刻车速；`acceleration`：事故时刻加速度；`brakePedal`：事故时刻制动踏板开度/比例；`acceleratorPedal`：事故时刻加速踏板开度/比例；`gear`：事故时刻挡位；`gearAfter`：事故后挡位；`blackSpotCount`：关联黑点数量；`fault`：车辆故障信息；`maintainType`：维修类型；`maintainTime`：维修时间；`accidentDate`：事故时间；`busName` / `numberPlate`：车辆牌照或车辆名称，需按实际返回字段说明；`busId`：车辆 ID。 |

