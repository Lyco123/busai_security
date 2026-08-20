# MCP `aisecurity` 工具 description 剩余问题 review

**审查对象**：`agent/docs/MCP服务设计文档20260601.md`。

**范围说明**：本稿按 20260517 版本的组织方式，围绕具体 MCP tool 记录 20260517 第一版 review 后仍未收敛、且会影响工具选择、参数填写或字段解释的 description / schema 口径问题。接口列表与正文顺序、samples 顺序对齐问题已直接回写源文件，不再列入本 review。

**临时补丁提示**：`score` / `originalValue` 语义说明用于当前 MCP 字段命名和 description 未修正前的兼容口径；上游 MCP schema/description 明确区分源指标分与最终风险分后，应删除对应二次包装补丁和 prompt guardrail。

---

## 全局文案基线（跨多个工具）

| 对象 | 建议替换文案 | 备注 |
|---|---|---|
| `X-Transparent-Para` | **透传扩展参数（可选；通常由客户端或网关注入）** | 多处仍写「透明参数，用于传递额外的参数」，单位事故统计接口中甚至仍为 `none`。 |
| `pageNo` | **页码，默认 1** 或 **页码；客户端须传** | 必选状态必须和默认值口径二选一，不要同时写「必选=是」和「默认1」。 |
| `pageSize` | **每页条数，默认 20** 或 **每页条数；客户端须传** | 统一「每页条数」，避免「每页数量」等弱描述。 |
| `ppartition` | **日期，格式为 yyyyMMdd，例如 20251231；不传时查询该对象最近一个有画像数据的日期。** | 仅适用于 GET 画像类接口；若某接口使用固定日期、昨天或统计窗口，应在对应工具单独说明。 |
| 列表类工具空 Body | **Body 为空时按当前用户可见范围查询，具体范围以接口权限为准。** | 不要写成「查询所有车辆/所有驾驶员/所有站场」，避免模型扩展成全局事实。 |
| 数量/名单类问法 | **涉及数量、名单、ID、所属单位等结构化业务数据时，必须来自接口真实返回字段或基于完整分页结果计算；未调用成功、返回为空或字段为空时，不得给出具体数值、姓名、ID 或单位。** | 这是跨列表类与画像类工具的 grounding 基线，避免模型把样例值、历史结果或语言补全当真实业务数据。 |
| 画像指标分数 | **画像指标中 `score` 是上游源指标分/计算中间值，不是最终分数；`originalValue` 才是最终风险分/最终风险贡献，数值越高表示风险越高、越突出，不是安全分。** | 适用于驾驶员、车辆、单位、线路、站场、事故画像指标树。建议明细类 `score` 无 `originalValue` 时，仍按风险建议分/优先级分解释。 |
| `organId` | **机构 ID** 或 **单位 ID** | 若字段语义为 ID，不要写「机构编号」等近义弱口径。 |
| `driverName` | **驾驶员姓名** | 个别统计接口仍写「驾驶员名称」，建议统一。 |
| `routeName` | **线路名称** 或按所在对象写明 **所属线路名称** | 仍有说明为 `none` 的位置。 |

---

## 输出 alias / fieldSemantics 建议清单（按 MCP tool）

**建议实现方式**：不要改动现有字段名以免影响客户端兼容；在 MCP 输出中新增 `fieldAliases` 和 `fieldSemantics`（或等价结构）说明旧字段的机器可读语义。若服务端更倾向平铺字段，也可以按下表 alias 名新增同值字段。所有风险分、风险值、风险贡献字段默认按「数值越高，风险越高」解释，除非字段语义明确写成完成率、合格率、下降率等非风险指标。

**备注**：本节 alias 是给 MCP 服务端输出结构的兼容性增强建议，不要求删除或重命名现有字段；涉及 `score` / `originalValue` 的 alias 用于修正当前命名误导，后续若服务端字段名和 schema 已改为明确语义，可同步移除客户端侧临时补丁和 prompt guardrail。

| MCP tool | 建议新增 alias / fieldSemantics |
|---|---|
| `get_mcp_base_absBusProfileMain_queryByNumberplate` | `result.main.score -> overall_risk_score`；`result.quotaScoreSubList[].score -> source_metric_score`；`result.quotaScoreSubList[].originalValue -> final_risk_score` / `final_risk_contribution`；`result.quotaScoreSubList[].weightRate -> metric_weight_rate`；`result.quotaScoreSubList[].riskData -> raw_business_value`；`pendingReceiveCount -> pending_accept_suggestion_count`；`pendingConfirmCount -> pending_intervention_count`；`pendingOptimizeCount -> pending_optimization_count`。 |
| `get_mcp_base_absCompanyProfileMain_queryCompanyProfile` | 同画像指标结构：`result.main.score -> overall_risk_score`；`quotaScoreSubList[].score -> source_metric_score`；`quotaScoreSubList[].originalValue -> final_risk_score` / `final_risk_contribution`；`weightRate -> metric_weight_rate`；`riskData -> raw_business_value`；三类 `pending*Count` 同上。 |
| `get_mcp_base_absDriverProfileMain_queryDriverProfile` | 同画像指标结构：`result.main.score -> overall_risk_score`；`quotaScoreSubList[].score -> source_metric_score`；`quotaScoreSubList[].originalValue -> final_risk_score` / `final_risk_contribution`；`weightRate -> metric_weight_rate`；`riskData -> raw_business_value`；三类 `pending*Count` 同上。 |
| `get_mcp_base_absRouteProfileMain_queryRouteProfile` | 同画像指标结构：`result.main.score -> overall_risk_score`；`quotaScoreSubList[].score -> source_metric_score`；`quotaScoreSubList[].originalValue -> final_risk_score` / `final_risk_contribution`；`weightRate -> metric_weight_rate`；`riskData -> raw_business_value`；`routeId -> route_id`；`routeName -> route_name`；三类 `pending*Count` 同上。 |
| `post_mcp_base_odsJituanBsBus_list` | `records[].busName` / `numberPlate -> vehicle_plate_no`（按实际字段二选一标注）；`records[].busId -> vehicle_id`；`records[].organName -> owning_org_name`；`records[].routeName -> bound_route_name`；分页包装字段如存在需补 `total -> total_record_count`、`records -> current_page_records`，避免把当前页条数当总数。 |
| `post_mcp_ods_odsJituanBsBusPark_list`（样例 6/26 重复） | `records[].busParkName` / `parkName -> bus_park_name`；`records[].busStationName -> related_bus_station_name`；`records[].organName -> owning_org_name`；如返回服务车辆数、使用单位数等数量字段，补 `service_vehicle_count`、`using_org_count`；分页包装字段同列表类统一为 `total_record_count` / `current_page_records`。 |
| `post_mcp_ods_odsJituanBsBusStation_list` | `records[].busStationId -> bus_station_id`；`records[].busStationName -> bus_station_name`；`records[].organName -> owning_org_name`；`records[].manageOrgName -> managing_org_name`；`stationType -> station_type_code`；`stationProperties -> station_property_code`；如有字典文本，补 `stationType_dictText -> station_type_text`、`stationProperties_dictText -> station_property_text`；分页包装字段补 `total_record_count` / `current_page_records`。 |
| `post_mcp_ods_odsJituanBsEmployee_list` | `records[].employeeName` / `driverName -> driver_name`；`employeeId -> driver_id`；`employeeCode -> driver_code`；`organName -> owning_org_name`；`routeName -> bound_route_name`；分页包装字段补 `total_record_count` / `current_page_records`。 |
| `post_mcp_ods_odsJituanBsRoute_list` | `records[].routeId -> route_id`；`routeName -> route_name`；`organName -> owning_org_name`；`busCount -> registered_vehicle_count_on_route`；`driverCount -> registered_driver_count_on_route`；分页包装字段补 `total_record_count` / `current_page_records`。 |
| `get_mcp_base_adsAccidentProfileMain_queryAccidentProfile` | 同画像指标结构：`result.main.score -> overall_accident_risk_score`；`quotaScoreSubList[].score -> source_metric_score`；`quotaScoreSubList[].originalValue -> final_risk_score` / `final_risk_contribution`；`weightRate -> metric_weight_rate`；`riskData -> raw_business_value`；三类 `pending*Count` 同上。 |
| `get_mcp_suggest_absBusSuggestedSub_queryByBusNameAndDate` | `score -> source_metric_score`；`originalValue -> final_risk_score` / `final_risk_contribution`；`weightRate -> metric_weight_rate`；`riskData -> raw_business_value`；`suggestedContent -> management_suggestion`；`acceptStatu -> accept_status_code`；`acceptStatu_dictText -> accept_status_text`；`disposeStatu -> dispose_status_code`；`disposeStatu_dictText -> dispose_status_text`；`optimizeStatus -> optimize_status_code`；`optimizeStatus_dictText -> optimize_status_text`；`optimizeScoreBefore -> risk_score_before_optimization`；`optimizeScore -> risk_score_after_optimization`。 |
| `get_mcp_suggest_absDriverSuggestedSub_queryByDriverNameAndDate` | 同建议明细结构：`score -> source_metric_score`；`originalValue -> final_risk_score` / `final_risk_contribution`；`riskData -> raw_business_value`；`suggestedContent -> management_suggestion`；三类状态字段 alias 同上；另补 `driverName -> driver_name`、`driverId -> driver_id`。 |
| `get_mcp_suggest_absRouteSuggestedSub_queryByRouteNameAndDate` | 同建议明细结构：`score -> source_metric_score`；`originalValue -> final_risk_score` / `final_risk_contribution`；`riskData -> raw_business_value`；`suggestedContent -> management_suggestion`；三类状态字段 alias 同上；另补 `routeName -> route_name`、`routeId -> route_id`。 |
| `get_mcp_suggest_absCompanySuggestedSub_queryByOrganNameAndDate` | 同建议明细结构：`score -> source_metric_score`；`originalValue -> final_risk_score` / `final_risk_contribution`；`riskData -> raw_business_value`；`suggestedContent -> management_suggestion`；三类状态字段 alias 同上；另补 `organName -> organization_name`、`organId -> organization_id`。 |
| `get_mcp_blackspot_adsEventBlackSpot_queryConfirmedBlackSpots` | `blackType -> blackspot_type_code`；`blackType_dictText -> blackspot_type_text`；`eventType -> event_type_code`；`eventLevel -> event_level_code`；`eventLevel_dictText -> event_level_text`；`eventCount -> blackspot_event_count`；`clusterSize -> clustered_event_count`；`startDate -> warning_start_date`；`endDate -> warning_end_date`；`longitude -> longitude_wgs84_or_gcj02`（坐标系需明确）；`latitude -> latitude_wgs84_or_gcj02`；`routeIds -> related_route_ids`。 |
| `get_mcp_base_absCompanyProfileMain_quotaScoreTrend` | `result[].quotaScores[].ppartition -> trend_period_label`；`quotaScores[].score -> trend_source_metric_score`；`quotaScores[].originalValue -> trend_final_risk_score` / `trend_final_risk_contribution`；如果 `quotaId` 为「总分」，需补 `quotaId/score/originalValue` 的语义为 `overall_risk_score_trend`。 |
| `get_mcp_base_absCompanyProfileMain_getKeyRisk` | `currentRiskValue -> current_raw_risk_value`；`convertedScore -> current_converted_risk_score`；`previousPeriodRiskValue -> mom_risk_value_change_rate_percent`，明确不是上期风险值；`previousPeriodScore -> previous_period_converted_risk_score`；`lastYearSameDateRiskValue -> yoy_risk_value_change_rate_percent`；`lastYearSameDateScore -> last_year_same_date_converted_risk_score`；`organAvgRiskValue -> organ_average_risk_value_change_rate_percent`；`organAvgScore -> organ_average_converted_risk_score`；`routeAvgRiskValue -> route_average_risk_value_change_rate_percent`；`routeAvgScore -> route_average_converted_risk_score`；现有 `previousPeriodRiskValue0` / `lastYearSameDateRiskValue0` / `organAvgRiskValue0` / `routeAvgRiskValue0` 如保留，分别 alias 为对应基准期/均值的 `*_raw_risk_value`，并建议后续改掉 `0` 后缀。 |
| `get_mcp_base_absDriverProfileMain_driverRiskScore` | 同 `DriverRiskScoreItemVO` 对比结构：`currentRiskValue -> current_raw_risk_value`；`convertedScore -> current_converted_risk_score`；`previousPeriodRiskValue -> mom_risk_value_change_rate_percent`，明确不是上月分数/上期风险值；`previousPeriodScore -> previous_period_converted_risk_score`；`lastYearSameDateRiskValue -> yoy_risk_value_change_rate_percent`；`lastYearSameDateScore -> last_year_same_date_converted_risk_score`；`organAvgRiskValue -> organ_average_risk_value_change_rate_percent`；`organAvgScore -> organ_average_converted_risk_score`；`routeAvgRiskValue -> route_average_risk_value_change_rate_percent`；`routeAvgScore -> route_average_converted_risk_score`。 |
| `get_mcp_base_absDriverProfileMain_getQuotaScoreTop` | `result[].quotaScores[].ppartition -> trend_period_label`；`quotaScores[].score -> trend_source_metric_score`；`quotaScores[].originalValue -> trend_final_risk_score` / `trend_final_risk_contribution`；`quotaId -> metric_id`；`quotaName -> metric_name`；说明 Top 结果按高风险指标/重点指标返回，不能把 `score` 当最终风险分。 |
| `get_mcp_base_absDriverProfileMain_quotaScoreTrend` | `result[].quotaScores[].ppartition -> trend_period_label`；`quotaScores[].score -> trend_source_metric_score`；`quotaScores[].originalValue -> trend_final_risk_score` / `trend_final_risk_contribution`；若 `quotaId` / `quotaName` 为「总分」，补 `overall_risk_score_trend` 语义；所有趋势风险分均为数值越高风险越高。 |
| `get_mcp_ods_odsJituanBsEmployee_getOrganAccident` | `accidentCount -> organization_accident_count`；`accidentDescList -> accident_description_page_items`；`ppartitionStart -> statistics_start_date`；`ppartitionEnd -> statistics_end_date`；`organName -> organization_name`；需说明 `accidentDescList` 受分页影响，不能用其长度代替事故总数。 |
| `get_mcp_ods_odsJituanBsEmployee_getDriverCheckCount` / `get_mcp_ods_odsJituanBsEmployee_getDriderCheckCount` | `allCount -> planned_pre_trip_check_count`；`actualCount -> actual_pre_trip_check_count`；`qualifiedCount -> qualified_pre_trip_check_count`；`unqualifiedCount -> unqualified_pre_trip_check_count`；`completePer -> pre_trip_check_completion_rate_percent`；`unqualifiedPer -> pre_trip_check_unqualified_rate_percent`；`ppartition -> statistics_date`。 |
| `get_mcp_ods_odsJituanBsEmployee_getBehaviorStat` | `employeeName -> driver_name`；`employeeId -> driver_id`；`eventType -> behavior_type_code`；`eventName -> behavior_type_name`；`eventNum -> behavior_event_count`；`ranking -> behavior_count_rank`，必须补排名范围；`ppartitionStart -> statistics_start_date`；`ppartitionEnd -> statistics_end_date`。 |
| `get_mcp_ods_odsJituanBsEmployee_getAccidentList` | `accidentDate -> accident_time`；`accidentPlace -> accident_location`；`accidentDesc -> accident_description`；`lineName -> route_name`；`busLicenseNum -> vehicle_plate_no`；`busCode -> vehicle_self_no`；`driverName -> driver_name`；`accidentLiability -> liability_code`，建议新增 `accidentLiability_dictText -> liability_text`；`opinionStatus -> handling_opinion_status_code`，建议新增字典文本 alias；`isBlackspot -> is_blackspot_related`。 |
| `get_mcp_base_absCompanyProfileMain_getOrganAccidentCount` | `accidentCount -> organization_accident_count_in_window`；`trafficCount -> organization_traffic_violation_count_in_window`；需要在 `fieldSemantics` 标出统计窗口由 `day` 和 `ppartition` 决定，`ppartition` 为空时的默认结束日也要写清。 |
| `get_mcp_ods_odsJituanBsEmployee_getDriverAccidentCount` | `accidentCount -> driver_accident_count_in_window`；`trafficCount -> driver_traffic_violation_count_in_window`；`workTime -> driver_work_hours_in_window`；`workDay -> driver_work_days_in_window`；`workTimeOver -> driver_overtime_hours_in_window`；`behaviorCounts[].eventType -> behavior_type_name`；`behaviorCounts[].eventCount -> behavior_event_count_in_behavior_window`；需要说明 `day` 作用于事故/违章窗口，`behaviorDay` 作用于行为统计窗口。 |
| `get_mcp_base_absBusStationProfileMain_queryBusStationProfile` | 同画像指标结构：`result.main.score -> overall_risk_score`；`quotaScoreSubList[].score -> source_metric_score`；`quotaScoreSubList[].originalValue -> final_risk_score` / `final_risk_contribution`；`weightRate -> metric_weight_rate`；`riskData -> raw_business_value`；`busStationName -> bus_station_name`；`manageOrgName -> managing_org_name`；三类 `pending*Count` 同上。 |
| `get_mcp_suggest_absBusStationSuggestedSub_queryByBusStationNameAndDate` | 同建议明细结构：`score -> source_metric_score`；`originalValue -> final_risk_score` / `final_risk_contribution`；`riskData -> raw_business_value`；`suggestedContent -> management_suggestion`；三类状态字段 alias 同上；另补 `busStationName -> bus_station_name`、`busStationId -> bus_station_id`。 |
| `get_mcp_base_absBusProfileMain_getAccidentBusInfo` | `speed -> accident_moment_speed`；`acceleration -> accident_moment_acceleration`；`brakePedal -> accident_moment_brake_pedal_percent`；`acceleratorPedal -> accident_moment_accelerator_pedal_percent`；`gear -> accident_moment_gear`；`gearAfter -> post_accident_gear`；`blackSpotCount -> related_blackspot_count`；`fault -> vehicle_fault_info`；`maintainType -> maintenance_type`；`maintainTime -> maintenance_time`；`accidentDate -> accident_time`。 |

---

## XXXX 替换质量复核

**结论**：`MCP服务设计文档20260601.md` 中已经没有字面 `XXXX` 残留，但并不是所有占位都被高质量替换。部分默认值、省略行为和分页口径仍存在冲突、模糊或待确认文案。

| 对象/位置 | 当前替换结果 | 问题 | 建议 |
|---|---|---|---|
| 风险追踪类 `pageNo` / `pageSize` | 参数表写 `必选=是`，说明又写「页码，默认1」「每页条数，默认20」。 | required 与 default 口径冲突。 | 若服务端可默认，改为 `必选=否`；若客户端必须传，删除默认值说明。 |
| 风险追踪类 `ppartition` | 工具级写「不传时查询该对象最近一个有数的日期」，参数表只写日期格式。 | 工具级和参数级不一致，参数表缺少省略行为。 | 参数表同步写「不传时查询该对象最近一个有数的日期」。 |
| GET 画像类 `ppartition` | 有的写「不传时查询有数据日期」，有的写「当前有数日期」，有的只写格式。 | 同类接口省略行为不统一。 | 统一为「不传时查询该对象最近一个有画像数据的日期」；若某接口不同，单独说明。 |
| 驾驶员趋势 `dateType` | 已填 `1` 近7天、`2` 近30天、`3` 近1年，默认近7天。 | 这一项基本可用。 | 保留；建议补充取值类型是字符串还是数字。 |
| 单位趋势 `dateType` | 已填 `2` 近5期、`3` 近一年，默认近5期。 | 这一项基本可用，但与驾驶员趋势枚举不同。 | 保留；明确这是单位趋势接口专属枚举，不要复用到驾驶员趋势。 |
| 驾驶员指标对比 `parentId` | 已填「不传时默认查询总览」并给指标例子。 | 基本可用，但「父指标id」大小写和字段名说明不规范。 | 改为「父指标 ID；不传时默认查询总览」。 |
| 驾驶员指标趋势 `quotaId` | 已填「不传时默认查询总览」并给指标例子。 | 基本可用，但仍写「指标id」。 | 改为「指标 ID；不传时默认查询总览」。 |
| 单位指标对比父指标参数 | 工具级写「父指标」，但参数表未清晰出现 `parentId` 或等价字段。 | 原 `XXXX` 可能被省略掉了，而不是被确认成真实参数。 | 明确实际参数名、是否可省略、默认查询范围。 |
| 列表类空 Body | 多处填成「默认查询所有车辆/站场/线路/驾驶员」。 | 未确认权限范围，容易诱导模型输出全局结论。 | 改为「按当前用户可见范围查询，具体范围以接口权限为准」。 |
| 站场/线路 POST 分页 | 仍有「页码」「每页页数量」「每页数量，默认10条数据」。 | 默认值和术语未统一，仍有笔误。 | 统一为「页码，默认1」「每页条数，默认10」或按真实行为写「客户端须传」。 |
| 不良行为统计 `day` | 已填默认30。 | 只填了天数，没填窗口方向。 | 写清以 `ppartition` 为结束日向前回溯，还是从 `ppartition` 起向后统计。 |
| 不良行为统计 `ranking` | schema 仍写「需确认排名范围」。 | 说明还未完成。 | 确认排名范围是所属线路、所属单位还是全部可见驾驶员。 |
| 单位事故统计 `day` / `ppartition` | 已填默认30天、以 `ppartition` 为结束日向前回溯；`ppartition` 不传查昨天。 | 这两项基本可用。 | 保留；建议确认「昨天」按服务端时区还是业务日期。 |
| 单位事故统计分页 | 工具级仍写「分页口径需确认」，参数表写作用于 `accidentDescList、事故明细查询`。 | 一边说不返回结构化事故明细，一边写事故明细查询，口径冲突。 | 改为「分页作用于 `accidentDescList` 事故描述摘要列表」或「分页参数不生效，保留兼容」。 |
| 驾驶员事故工时统计 `day` / `behaviorDay` | 已填 `day` 默认365、`behaviorDay` 默认30。 | 基本可用，但未说明两个窗口分别作用于事故还是行为统计结果的边界。 | 补充 `day` 用于事故统计窗口，`behaviorDay` 用于行为统计窗口。 |

**验收标准**：占位符替换不能只做到“没有 `XXXX`”，还需要同时满足三点：参数必填性与默认值不冲突、省略行为能指导模型是否可不传、统计/分页口径不会让模型把当前页或样例值当作全量事实。

---

## 1. `get_mcp_suggest_absCompanySuggestedSub_queryByOrganNameAndDate`

**用途**：单位风险追踪/管理建议明细查询。

### 工具级 `description`

**当前问题**：当前 description 主要表达为“单位风险追踪明细”，虽然返回 `acceptStatu`、`disposeStatu`、`optimizeStatus`、`suggestedContent` 等字段，但没有明确写入“管理效果、管理闭环、干预执行、处置状态、待接收/待确认/待优化”等用户高频问法。用户问「三分公司的管理效果如何」时，模型容易绕过本工具，只查单位画像。

**替换文案**：

> 按单位名称和日期分页查询单位风险追踪/管理建议明细。`organName` 必填，含义与单位画像中的单位名称一致；`ppartition` 可选，不传时查询该机构最近一个有数的日期。该接口用于回答单位管理效果、管理闭环、干预执行、处置状态、风险是否已处理、待接收建议、待确认处理、待优化风险等问题；返回建议内容、风险指标、风险等级、建议日期、接受状态、处置状态、优化状态、处置时间、优化时间等字段。用户询问“管理效果/闭环/处置/干预/待确认/待优化/待接收”时，应优先使用本接口；如需同时解释风险来源，可再联合单位画像接口。

### 参数级 `description`

| 字段 | 当前问题 | 建议 |
|---|---|---|
| `pageNo` / `pageSize` | 风险追踪类接口仍有「必选=是」但说明为「默认1 / 默认20」的组合。 | 若服务端可默认，改为 `必选=否`，说明写「页码，默认1」「每页条数，默认20」；若客户端必须传，删除默认值说明。 |
| `ppartition` | 省略行为应与工具级说明一致。 | **日期，格式为 yyyyMMdd，例如 20251231；不传时查询该机构最近一个有数的日期。** |

### 字段级 `description`

| 字段 | 建议 description |
|---|---|
| `suggestedContent` | 管理建议/干预建议内容。 |
| `acceptStatu` | 建议接受状态编码；优先使用 `acceptStatu_dictText` 面向用户解释。 |
| `acceptStatu_dictText` | 建议接受状态文本，例如未接受、已接受、拒绝等，具体取值以接口返回为准。 |
| `disposeStatu` | 处置状态编码；优先使用 `disposeStatu_dictText` 面向用户解释。 |
| `disposeStatu_dictText` | 处置状态文本，用于判断建议是否已处置、待处置或处置中，具体取值以接口返回为准。 |
| `optimizeStatus` | 优化状态；用于判断已处置风险是否仍待优化。 |
| `score` / `riskScore` | 建议明细风险分/风险优先级分，数值越高表示风险越高、越需要关注，不是安全分。 |
| `optimizeScore` | 优化后风险分或优化评价分，具体口径以接口返回为准。 |
| `disposeTime` | 处置时间。 |
| `optimizeTime` | 优化时间。 |

### 验收用例

| 用户问题 | 期望 | 不应出现 |
|---|---|---|
| 三分公司的管理效果如何？ | 优先调用本工具；可联合单位画像。 | 仅调用单位画像后输出完整管理效果结论。 |
| 三分公司有哪些待确认处理？ | 调用本工具，关注接受/处置状态。 | 用画像指标风险分替代待确认明细。 |
| 三分公司的风险有没有处理完？ | 调用本工具，关注接受/处置/优化状态。 | 仅用综合评分或排名判断已处理。 |

---

## 2. `get_mcp_base_absCompanyProfileMain_queryCompanyProfile`

**用途**：单位画像明细查询。

### 工具级 `description`

**当前问题**：当前 description 写明返回待接受、待确认、待优化建议统计数和指标分数列表，容易让模型误判为单查画像接口即可回答“管理效果”，忽略明细级处置状态和闭环进度。

**建议补充边界文案**：

> 本接口主要用于查询单位画像、综合风险分、评价类型、排名、风险构成、指标分数列表和建议状态数量概览。若用户询问单位“管理效果、管理闭环、干预执行、处置状态、风险是否已处理、待接收/待确认/待优化建议明细”，不得仅凭本接口下结论，应优先或联合查询 `get_mcp_suggest_absCompanySuggestedSub_queryByOrganNameAndDate` 获取明细级处置状态和闭环进度。

### 参数级 `description`

| 字段 | 当前问题 | 建议 |
|---|---|---|
| `ppartition` | GET 画像类接口省略行为表述不一致。 | **日期，格式为 yyyyMMdd，例如 20251231；不传时查询该单位最近一个有画像数据的日期。** |

### 字段级 `description`

| 字段 | 当前问题 | 建议 |
|---|---|---|
| `pendingReceiveCount` | 容易被误解为完整管理效果明细。 | **待接受建议数（未接受）；仅为数量概览，管理效果明细需查询单位风险追踪明细接口。** |
| `pendingConfirmCount` | 容易被误解为完整处理状态。 | **待干预建议数（已接受待处理）；仅为数量概览，明细处置状态需查询单位风险追踪明细接口。** |
| `pendingOptimizeCount` | 容易被误解为完整优化明细。 | **待优化建议数（已处理待优化）；仅为数量概览，明细优化状态需查询单位风险追踪明细接口。** |
| `score` / `originalValue` / 指标分数字段 | 容易把上游 `score` 误当最终分数。 | **画像指标中 `score` 是源指标分/计算中间值，不是最终分数；`originalValue` 是最终风险分/最终风险贡献，数值越高表示风险越高、越突出。** |

### 验收用例

| 用户问题 | 期望 | 不应出现 |
|---|---|---|
| 三分公司的风险在哪里？ | 可调用本工具，围绕风险构成回答。 | 强制只讲建议闭环。 |
| 三分公司的管理效果如何？ | 本工具可作为风险背景，但必须联合风险追踪明细。 | 将风险画像结论冒充管理效果结论。 |

---

## 3. `get_mcp_base_absCompanyProfileMain_quotaScoreTrend`

**用途**：单位画像综合评级评分趋势。

### 工具级 `description`

**当前问题**：单位画像综合评级评分趋势返回模型仍使用 `DriverQuotaScoreTrendVO` 命名，但 description 缺少说明，模型可能把单位指标结果误解释为驾驶员指标结果。

**建议补充**：

> 返回模型名沿用 `Driver*` 历史命名；当前接口实际对象为单位画像指标结果。
> 趋势中的 `score` / `quotaScore` 为趋势源指标分；若同时返回 `originalValue` 或最终风险值，应优先用后者解释最终风险贡献。所有风险分数均按数值越高风险越高解释。

---

## 4. `get_mcp_base_absCompanyProfileMain_getKeyRisk`

**用途**：单位画像指标对比。

### 工具级 `description`

**当前问题**：单位画像指标对比返回模型仍使用 `DriverRiskScoreItemVO` 命名，但 description 缺少说明。

**建议补充**：

> 返回模型名沿用 `Driver*` 历史命名；当前接口实际对象为单位画像指标对比结果。
> 对比结果中的 `score` / `riskScore` 为源指标分；若同时返回 `originalValue`，`originalValue` 才是最终风险分/最终风险贡献。所有风险分数均按数值越高风险越高解释。

### 参数级 `description`

| 字段 | 当前问题 | 建议 |
|---|---|---|
| 父指标参数 | 文档标题写“父指标”，但参数名和省略行为仍需确认。 | 明确实际参数名是 `parentId` 还是 `quotaId`；若可省略，写清不传时查询的指标范围。 |

---

## 5. `post_mcp_ods_odsJituanBsRoute_list`

**用途**：线路明细列表查询。

### 工具级 `description`

**当前问题**：列表类工具仍可能出现“Body 为空时查询所有”口径。

**建议补充**：

> Body 为空时按当前用户可见范围查询，具体范围以接口权限为准；不要在面向用户回答中扩展为全局全部线路。

**当前问题**：该工具返回 `busCount`、`driverCount`，但 description 没有明确“线路车辆数/驾驶员数”这类高频数量问法应优先使用本工具字段，模型可能转去查驾驶员列表，或在未调用工具时补全数量和名单。

**建议补充**：

> 当用户询问“XX线路有多少驾驶员/驾驶员数量/多少台车/车辆数量”时，应优先按 `routeName`、`routeCode` 或 `routeId` 查询本接口，并使用返回记录中的 `driverCount`、`busCount` 回答。若同一名称命中多条线路，应分别列出每条线路的 `routeName`、`routeId`、所属单位/车队及对应数量；不要擅自合并，除非用户明确要求合计。若 `driverCount` 或 `busCount` 为空，不得编造数量，应说明线路台账未返回该字段，并按 `routeId` 补查驾驶员或车辆明细列表后再统计。

### 字段级 `description`

| 字段 | 当前问题 | 建议 |
|---|---|---|
| `driverCount` | 仅写“驾驶员数”，没有说明这是线路驾驶员数量查询的首选字段。 | **驾驶员数；用于回答该线路登记/台账中的驾驶员数量。为空时不能视为 0，需补查驾驶员明细或说明未返回。** |
| `busCount` | 仅写“车辆数”，没有说明这是线路车辆数量查询的首选字段。 | **车辆数；用于回答该线路登记/台账中的车辆数量。为空时不能视为 0，需补查车辆明细或说明未返回。** |

---

## 6. `post_mcp_base_odsJituanBsBus_list`

**用途**：车辆明细列表查询。

### 工具级 `description`

**当前问题**：仍有「Body 为空时默认查询所有车辆」之类表述。

**建议补充**：

> Body 为空时按当前用户可见范围查询，具体范围以接口权限为准；不要在面向用户回答中扩展为全局全部车辆。

**当前问题**：车辆列表可按线路、机构、车牌等字段查询，但 description 没有明确它在“线路车辆名单/车辆数”场景中是线路台账 `busCount` 为空时的补查工具；模型可能直接用单页 `records.length` 当总数。

**建议补充**：

> 本接口可用于按 `routeId`、`routeName`、`organId`、`numberPlate` 等条件查询车辆明细。用户询问“某线路有哪些车辆/车辆名单/车辆数量”时，优先使用线路明细接口的 `busCount`；若 `busCount` 为空或需要车辆名单，再用线路接口返回的 `routeId` 查询本接口。统计数量时必须使用分页总数或完整分页结果，不能把当前页 `records.length`、`pageSize=1` 的返回条数当作总车辆数。

---

## 7. `post_mcp_ods_odsJituanBsBusPark_list`

**用途**：车辆站场/车场明细列表查询。

### 工具级 `description`

**当前问题**：仍有「Body 为空时默认查询所有站场/车场」之类表述。

**建议补充**：

> Body 为空时按当前用户可见范围查询，具体范围以接口权限为准；不要在面向用户回答中扩展为全局全部站场或车场。

**当前问题**：站场/车场工具返回可能包含服务车辆数、使用单位等数量/归属字段，但 description 没有限定“数量字段为空或未返回时不得补全”。

**建议补充**：

> 当用户询问站场/车场服务车辆数、归属单位、使用单位或站场清单时，只能基于本接口真实返回字段回答。若数量字段为空或未返回，应说明接口未提供该数量，不得用样例值、估计值或当前页条数补齐。

---

## 8. `post_mcp_ods_odsJituanBsBusStation_list`

**用途**：站场明细列表查询。

### 工具级 `description`

**当前问题**：列表空条件查询范围容易被模型理解为全局事实。

**建议补充**：

> Body 为空时按当前用户可见范围查询，具体范围以接口权限为准；不要在面向用户回答中扩展为全局全部站场。

**当前问题**：站点/站场列表属于明细查询，若用户问“有多少个站点/站场”或“名单”，模型可能把分页当前页数量当总量。

**建议补充**：

> 用户询问站点/站场数量或名单时，必须使用接口返回的分页总数字段或完整分页结果；不能把当前页 `records.length` 当作总数。未取得完整结果时，应说明仅返回当前页或当前可见范围内的结果。

---

## 9. `post_mcp_ods_odsJituanBsEmployee_list`

**用途**：驾驶员明细列表查询。

### 工具级 `description`

**当前问题**：仍有「Body 为空时默认查询所有驾驶员」之类表述。

**建议补充**：

> Body 为空时按当前用户可见范围查询，具体范围以接口权限为准；不要在面向用户回答中扩展为全局全部驾驶员。

**当前问题**：该工具常被用于线路驾驶员补查，但 description 没有明确分页统计规则，容易出现 `pageSize=1` 只返回 1 条却回答“共 1 名驾驶员”的错误。

**建议补充**：

> 本接口可用于按 `routeId`、`organId`、`employeeName`、`status` 等条件查询驾驶员明细。用户询问“某线路有哪些驾驶员/驾驶员名单/驾驶员数量”时，优先使用线路明细接口的 `driverCount`；若 `driverCount` 为空或用户需要名单，再用线路接口返回的 `routeId` 查询本接口。统计驾驶员数量时必须使用分页总数字段或完整分页结果；如果只请求了 `pageSize=1` 或只拿到第一页，只能说明“当前页返回 1 条”，不得据此判断总人数为 1。未取得真实返回时，不得生成驾驶员姓名、数量、线路 ID 或所属单位。

### 字段级 `description`

| 字段 | 当前问题 | 建议 |
|---|---|---|
| `driverName` / `employeeName` | 个别位置仍写「驾驶员名称」。 | 统一为 **驾驶员姓名**。 |
| `organId` | 有的地方写「机构编号」。 | 若字段语义为 ID，统一为 **机构 ID** 或 **单位 ID**。 |

---

## 10. `get_mcp_ods_odsJituanBsEmployee_getBehaviorStat`

**用途**：驾驶员不良行为统计。

### 工具级 `description`

**当前问题**：`day` 只写统计窗口天数，仍未说明窗口方向；`ranking` 的排名范围也仍待确认。

**建议补充**：

> `day` 与 `ppartition` 共同决定统计起止日期；需明确是以 `ppartition` 为结束日向前回溯，还是从 `ppartition` 起向后统计。`ranking` 为排名；需明确排名范围是所属线路、所属单位还是全部可见驾驶员。

### 字段级 `description`

| 字段 | 当前问题 | 建议 |
|---|---|---|
| `driverName` | 个别统计接口仍写「驾驶员名称」。 | **驾驶员姓名**。 |
| `ranking` | 排名范围不明确。 | **排名；需明确排名范围是所属线路、所属单位还是全部可见驾驶员。** |

---

## 11. `get_mcp_ods_odsJituanBsEmployee_getDriverCheckCount`

**用途**：线路岗前检查统计。

### 工具级 `description`

**当前问题**：正文路径已写为 `getDriverCheckCount`，但 description 中仍保留「接口路径如保留 getDriderCheckCount，需注明这是历史路径拼写」的待办式表述。

**建议处理**：

| 实际路径 | 建议处理 |
|---|---|
| 已改为 `getDriverCheckCount` | 删除 `getDriderCheckCount` 说明。 |
| 线上仍是 `getDriderCheckCount` | 路径和工具名保持历史拼写，并明确「业务含义为 Driver/岗前检查统计」。 |

---

## 12. `get_mcp_ods_odsJituanBsEmployee_getOrganAccident`

**用途**：单位事故统计。

### 工具级 `description`

**当前问题**：`pageNo` / `pageSize` 写成作用于 `accidentDescList、事故明细查询`，但工具级说明又说「不返回结构化事故明细」。

**建议二选一**：

| 实际行为 | 建议写法 |
|---|---|
| 分页作用于事故描述摘要 | **分页参数作用于 `accidentDescList` 事故描述摘要列表。** |
| 分页参数不生效 | **当前接口分页参数不生效，保留为兼容参数。** |

### 参数级 `description`

| 字段 | 当前问题 | 建议 |
|---|---|---|
| `X-Transparent-Para` | 仍为 `none` 或旧文案。 | **透传扩展参数（可选；通常由客户端或网关注入）**。 |
| `day` | 统计窗口方向不明确。 | **统计窗口天数；需明确是以 `ppartition` 为结束日向前回溯，还是从 `ppartition` 起向后统计。** |

---

## 13. GET 画像类接口公共收口

**涉及工具**：

- `get_mcp_base_absDriverProfileMain_queryDriverProfile`
- `get_mcp_base_absBusProfileMain_queryByNumberplate`
- `get_mcp_base_absRouteProfileMain_queryRouteProfile`
- `get_mcp_base_absBusStationProfileMain_queryBusStationProfile`
- `get_mcp_base_absCompanyProfileMain_queryCompanyProfile`
- `get_mcp_base_adsAccidentProfileMain_queryAccidentProfile`

### 参数级 `description`

**当前问题**：同类画像接口中有的写「不传时默认当前有数日期」，有的只写日期格式，有的写「有数据日期的画像数据」。

**建议统一模板**：

> 日期，格式为 yyyyMMdd，例如 20251231；不传时查询该对象最近一个有画像数据的日期。

如某接口使用固定日期或昨天，则单独说明，不要混用「当前有数日期」「有数据日期」等近义表述。

### 字段级 `description`

**建议统一模板**：

> 画像指标树中 `score` 是上游源指标分/计算中间值，不是最终分数；`originalValue` 是最终风险分/最终风险贡献，应优先用于报告指标分数和贡献解释。所有风险分数字段均按数值越高风险越高解释，不是安全分。

> `originalValue` 如未明确标注为次数/条数/起数，不得仅凭字段名推断为行为次数；画像指标中应按最终风险分/最终风险贡献解释。

---

## 14. 其他弱描述或笔误收口

| 涉及位置 | 当前问题 | 建议 |
|---|---|---|
| 多个 schema 的 `routeName` | 仍有说明为 `none` 的位置。 | 改为「线路名称」或按所在对象写明「所属线路名称」。 |
| 多个 schema 的 `direction` | 描述末尾残留 `s`。 | 删除尾部多余字符。 |
| 多个 schema 的 `pageSize` | 部分位置仍写「每页数量」。 | 统一为「每页条数」。 |
| 多个 schema 的 `organId` | 有的地方写「机构编号」。 | 若字段语义为 ID，统一为「机构 ID」或「单位 ID」。 |

---

## 建议收口顺序

1. 补强 `get_mcp_suggest_absCompanySuggestedSub_queryByOrganNameAndDate` 与 `get_mcp_base_absCompanyProfileMain_queryCompanyProfile` 的单位管理效果边界，避免风险画像冒充管理效果。
2. 统一 `X-Transparent-Para`、`pageNo`、`pageSize`、`ppartition` 这些高频公共参数。
3. 收口列表类工具的「查询所有」为「当前用户可见范围」。
4. 给单位趋势/对比接口复用 `Driver*` 模型名加解释。
5. 补齐统计类窗口、排名和分页对象。
6. 清理 schema 弱描述、`none` 和明显笔误。
