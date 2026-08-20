INSERT OR REPLACE INTO agent_profiles (id, kind, name, identifier, data, updated_at)
VALUES
  (
    'driver-001',
    'driver',
    '张三',
    'D-001',
    '{"basic":{"driver_name":"张三","driver_id":"driver-001","fleet_name":"一车队","hire_date":"2019-04-12","experience_years":6},"performance_dashboard":{"summary":{"overall_score":91.74,"overall_level":"危险型","overall_trend_delta":-0.24},"dimensions":{"综合排行":{"rank_position":18,"rank_total":90,"percentile":20.0,"display":"Top 20.0% (排名 18/90)","biz_note":"绩效总览"},"综合安全":{"score":91.74,"trend_delta":-0.24,"biz_note":"核心考核指标"},"行车技能":{"score":94.7,"trend_delta":-2.69,"biz_note":"操控平稳性"},"驾驶态度":{"score":88.4,"trend_delta":-2.07,"biz_note":"合规意识（抽烟/接打/遮挡）"},"行为习惯":{"score":91.13,"trend_delta":-1.81,"biz_note":"长期防御性习惯"}},"system_risk":{"level":"危险型","tags":["生理失控(36次)","注意力涣散(262次)","评分下滑"],"notes":"45-100 分为危险/关注/观察指标"}},"core_risk_assessment":{"summary":"综合安全评分 91.74（危险型）且持续下滑，行车技能/驾驶态度/行为习惯同步下降，呈系统性恶化特征。","key_findings":["综合安全处于高位且有下降趋势","行车技能下降幅度最大（-2.69）","分神与疲劳告警频发，风险集中化"],"evidence":[{"indicator":"综合安全","score":91.74,"trend_delta":-0.24,"note":"连续下滑"},{"indicator":"行车技能","score":94.7,"trend_delta":-2.69,"note":"下降明显"},{"indicator":"驾驶态度","score":88.4,"trend_delta":-2.07,"note":"同步走低"}],"attention_flags":["评分下滑","注意力涣散"]},"behavior_data_analysis":{"correlation_points":[{"signal":"分神行为高发","evidence":"262次分神告警","impact":"行为习惯分持续下滑"},{"signal":"疲劳与生理失控关联","evidence":"36次生理失控","impact":"综合安全评分下行"}],"supporting_stats":[{"name":"分神告警","value":"262次","trend_delta":0.12},{"name":"疲劳告警","value":"33次","trend_delta":0.08}],"conclusion":"风险行为与评分下滑高度相关，需要立即干预。"},"interventions":{"recommendations":[{"title":"排班与休息干预","priority":"高","action":"高峰期减少连续驾驶，增加中途休息","rationale":"疲劳与生理失控高度相关","expected_effect":"降低分神/疲劳告警"},{"title":"专项复训","priority":"中","action":"制动平稳性与防御性驾驶训练","rationale":"行车技能下降幅度较大","expected_effect":"提升行车技能评分"}],"follow_up":{"monitor_window_days":30,"recheck_items":["分神告警","疲劳告警","行车技能评分"]}},"appendix":{"raw_data":{"score_history":[{"date":"2025-01-01","overall_score":92.1},{"date":"2025-02-01","overall_score":91.74}],"alerts_counts":{"distraction":262,"fatigue":33,"physiological_loss":36},"ranking_snapshot":{"rank_position":18,"rank_total":90,"percentile":20.0},"source_window":{"window_days":90,"as_of":"2025-02-01"}}}}',
    '2025-01-20T08:00:00Z'
  ),
  (
    'driver-002',
    'driver',
    '李四',
    'D-002',
    '{"basic":{"driver_name":"李四","driver_id":"driver-002","fleet_name":"二车队","hire_date":"2016-09-01","experience_years":9},"performance_dashboard":{"summary":{"overall_score":58.4,"overall_level":"关注型","overall_trend_delta":-0.12},"dimensions":{"综合排行":{"rank_position":45,"rank_total":90,"percentile":50.0,"display":"Top 50.0% (排名 45/90)","biz_note":"绩效总览"},"综合安全":{"score":58.4,"trend_delta":-0.12,"biz_note":"核心考核指标"},"行车技能":{"score":62.1,"trend_delta":-0.8,"biz_note":"操控平稳性"},"驾驶态度":{"score":56.7,"trend_delta":-0.4,"biz_note":"合规意识"},"行为习惯":{"score":55.2,"trend_delta":-0.3,"biz_note":"防御性习惯"}},"system_risk":{"level":"关注型","tags":["超速(4次)","疲劳告警(1次)"],"notes":"45-100 分为危险/关注/观察指标"}},"core_risk_assessment":{"summary":"综合安全 58.4（关注型），近期略有下滑，超速与疲劳事件仍需关注。","key_findings":["超速次数偏高，影响综合安全评分","疲劳告警存在，需加强管理","整体风险可控但趋势向下"],"evidence":[{"indicator":"综合安全","score":58.4,"trend_delta":-0.12,"note":"轻微下滑"},{"indicator":"行车技能","score":62.1,"trend_delta":-0.8,"note":"下降明显"},{"indicator":"超速次数","score":4,"trend_delta":0.0,"note":"仍偏高"}],"attention_flags":["轻度下滑","超速偏高"]},"behavior_data_analysis":{"correlation_points":[{"signal":"超速行为持续","evidence":"4次超速","impact":"综合安全评分下降"},{"signal":"疲劳告警","evidence":"1次疲劳驾驶","impact":"驾驶态度评分偏低"}],"supporting_stats":[{"name":"超速次数","value":"4次","trend_delta":0.0},{"name":"疲劳告警","value":"1次","trend_delta":0.0}],"conclusion":"需要加强超速与疲劳管理以稳定评分。"},"interventions":{"recommendations":[{"title":"超速管控提醒","priority":"中","action":"重点路段设置超速提醒与复训","rationale":"超速次数偏高","expected_effect":"降低超速次数"},{"title":"疲劳管理提示","priority":"中","action":"夜班前加强休息检查与提醒","rationale":"存在疲劳告警","expected_effect":"降低疲劳告警"}],"follow_up":{"monitor_window_days":30,"recheck_items":["超速次数","疲劳告警","综合安全评分"]}},"appendix":{"raw_data":{"score_history":[{"date":"2025-01-01","overall_score":58.8},{"date":"2025-02-01","overall_score":58.4}],"alerts_counts":{"speeding":4,"fatigue":1},"ranking_snapshot":{"rank_position":45,"rank_total":90,"percentile":50.0},"source_window":{"window_days":90,"as_of":"2025-02-01"}}}}',
    '2025-01-20T08:00:00Z'
  ),
  (
    'vehicle-001',
    'vehicle',
    '车辆 A12345',
    'A12345',
    '{"basic":{"vehicle_id":"BUS-102","plate_number":"A12345","type":"新能源","fleet_name":"一车队","purchase_date":"2020-07-01","mileage_km":182000},"risk_profile":{"overall":61.8,"level":"??","mechanical":58.2,"operation":64.1},"maintenance":{"last_service":"2024-12-20","next_service":"2025-03-20","open_items":["制动片检查","电池健康复查"]},"alerts":[{"type":"制动温度","severity":"medium","last_seen":"2025-01-14T09:15:00Z"}],"violations":{"speeding":1,"lane_departure":0},"suggestions":[{"title":"7 天内完成制动片检查","priority":"?"}]}',
    '2025-01-20T08:00:00Z'
  ),
  (
    'vehicle-002',
    'vehicle',
    '车辆 B67890',
    'B67890',
    '{"basic":{"vehicle_id":"BUS-207","plate_number":"B67890","type":"柴油","fleet_name":"二车队","purchase_date":"2018-03-15","mileage_km":245000},"risk_profile":{"overall":55.2,"level":"??","mechanical":52.4,"operation":57.9},"maintenance":{"last_service":"2024-11-05","next_service":"2025-02-05","open_items":["机油分析","冷却系统检查"]},"alerts":[{"type":"发动机振动","severity":"low","last_seen":"2025-01-11T16:40:00Z"}],"violations":{"speeding":0,"lane_departure":1},"suggestions":[{"title":"下次保养前安排冷却系统检查","priority":"?"}]}',
    '2025-01-20T08:00:00Z'
  ),
  (
    'route-01',
    'route',
    '1路',
    'R-01',
    '{"basic":{"route_name":"1路","route_id":"R-01","fleet_name":"一车队","length_km":28.5,"trips_per_day":120},"risk_profile":{"overall":63.7,"level":"??","traffic":66.5,"infrastructure":58.4},"high_risk_segments":[{"segment":"站点4至站点7","issue":"急刹频次偏高","score":71.2}],"incidents":{"total":3,"latest":{"date":"2025-01-05","type":"险情", "location":"路口12"}},"suggestions":[{"title":"调整站点5附近高峰发车间隔","priority":"?"}]}',
    '2025-01-20T08:00:00Z'
  ),
  (
    'route-02',
    'route',
    '12路',
    'R-12',
    '{"basic":{"route_name":"12路","route_id":"R-12","fleet_name":"二车队","length_km":35.2,"trips_per_day":96},"risk_profile":{"overall":57.9,"level":"??","traffic":59.1,"infrastructure":55.8},"high_risk_segments":[{"segment":"场站至站点3","issue":"速度波动偏大","score":64.0}],"incidents":{"total":1,"latest":{"date":"2024-12-22","type":"轻微延误","location":"2号桥"}},"suggestions":[{"title":"关注清晨班次速度波动","priority":"?"}]}',
    '2025-01-20T08:00:00Z'
  ),
  (
    'incident-2025-10-14-gz-01',
    'incident_case',
    '2025-10-14 环市西路段刮碰事故',
    'INC-20251014-01',
    '{"report_title":"XX单位关于XX交通事故调查情况和整改措施报告","basic":{"incident_id":"INC-20251014-01","organization":"广州巴士集团二分公司二车队","accident_date":"2025-10-14","accident_time":"13:16:01","location":"环市西路段斑马线处","route_name":"363路","driver_name":"龚永添","vehicle_id":"粤A05764D/236622"},"section_1_event_and_response":{"accident_process":{"description":"车辆左后侧与小型车辆右前侧发生刮碰，事故未造成人员受伤。","weather":"雨天湿滑路面"},"emergency_response":{"reporting_flow":[{"time":"18:32","step":"驾驶员报告车队"},{"time":"18:37","step":"车队上报安全部门及片区责任人"},{"time":"18:45","step":"片区向集团安全部报告"},{"time":"19:38","step":"报属地交管部门"}]},"casualty_and_loss":{"injury":"1人头部受伤、肺部出血","direct_loss_amount":105.35,"currency":"万元"}},"section_2_investigation":{"unit_and_route_overview":{"operating_vehicles":4,"employees":224,"drivers":56,"year_total_mileage_wan_km":731.97,"cumulative_safe_mileage_wan_km":12265,"operating_routes":35,"accidents_last_half_month":6,"violations_last_half_month":0,"incident_route":"363路","incident_route_km":23,"route_allocation_vehicles":29},"driver_profile":{"name":"龚永添","gender":"男","age":47,"license":"A1A2E","recent_accidents":0,"recent_violations":0,"behavior_counts":{"fatigue_yawn":4,"zebra_crossing_acceleration":10,"start_sudden_acceleration":4,"zebra_crossing_no_yield":10,"sudden_acceleration":24,"irregular_stop_entry":20,"neutral_coasting":18,"left_turn_no_brake":17,"improper_handbrake_ratio":0.2},"medical_exam_2024":"心理测评一级","work_hours":{"daily_hours":6.35,"consecutive_work_days":3,"overtime":false}},"vehicle_profile":{"model":"纯电动客车","annual_inspection_valid":true,"insurance_valid":true,"last_maintenance":"2025-01-14","equipment_status":"正常"},"replay_and_can":{"speed_kmh":10.77,"acceleration_mps2":1.0,"brake_pedal_opening":0,"throttle_opening":0.3,"gear":"前进挡"}},"section_3_cause_and_nature":{"subjective_causes":["驾驶员疲劳驾驶，注意力集中程度下降（监测到4次疲劳打哈欠行为）。","驾驶员存在斑马线加速、起步急加速、未礼让行人等不良操作行为。","车速控制不合理，在高风险路段未严格遵守限速及安全操作规范。"],"objective_causes":["事发路段为一级斑马线黑点路段，通行环境复杂、车流密集。","雨天湿滑路面导致通行安全性下降。","车辆ABS故障状态异常，存在制动相关硬件故障隐患。"],"accident_nature":"主责"},"section_4_rectification_plan":{"awareness_and_responsibility":["认清形势，提高政治站位，严防死守安全生产工作。","汲取教训，严格落实安全生产责任。"],"targeted_training_and_controls":["针对高风险驾驶员（龚永添）开展专项安全培训及警示教育。","建立驾驶员风险等级动态管控机制，对1级风险驾驶员采取轮岗调整、暂停营运培训等措施。"],"risk_control_and_prevention":["对高风险线路及一级事故黑点路段开展专项整治，增设警示标识并强化巡逻管控。","加强车辆日常检修维护，重点排查制动系统（如ABS）关键部件。","强化驾驶员行为监测，对斑马线加速、未礼让行人等行为加大处罚力度。"],"online_offline_supervision":["线上依托监控系统实时监测并触发预警整改。","线下提升高风险线路和黑点路段督导频次，严查违规操作。"],"accountability_and_culture":["明确各级管理人员安全管理职责并纳入绩效考核。","强化员工安全意识教育，营造人人讲安全氛围。"]},"trigger_analysis":{"matched_signals":[{"signal":"疲劳驾驶触发","evidence":"fatigue_yawn=4","impact":"提示注意力下降，作为主观原因证据。"},{"signal":"斑马线高风险行为触发","evidence":"zebra_crossing_acceleration=10, zebra_crossing_no_yield=10","impact":"直接提升斑马线场景事故风险。"},{"signal":"黑点路段触发","evidence":"route_risk_level=一级斑马线黑点路段","impact":"作为客观高风险环境证据。"},{"signal":"制动系统隐患触发","evidence":"abs_status=异常","impact":"支撑车辆硬件风险判断。"}],"missing_data":[]},"appendix":{"raw_data":{"source":"XX单位.md","ingested_at":"2026-02-25","notes":"用于事故调查整改报告生成示例"}}}',
    '2025-02-25T11:00:00Z'
  );

INSERT OR REPLACE INTO agent_sessions (id, title, preview, created_at, updated_at)
VALUES (
  'session-demo',
  '示例会话',
  '欢迎使用 BUS 智能助手，请描述你的需求。',
  '2025-01-20T08:30:00Z',
  '2025-01-20T08:32:00Z'
);

INSERT OR REPLACE INTO agent_messages (id, session_id, role, content, created_at, status)
VALUES
  (
    'msg-demo-1',
    'session-demo',
    'system',
    '欢迎使用 BUS 智能助手，请描述你的需求。',
    '2025-01-20T08:30:00Z',
    'complete'
  ),
  (
    'msg-demo-2',
    'session-demo',
    'user',
    '生成张三的驾驶员报告。',
    '2025-01-20T08:31:00Z',
    'complete'
  ),
  (
    'msg-demo-3',
    'session-demo',
    'assistant',
    '{"note":"这是种子数据示例。"}',
    '2025-01-20T08:32:00Z',
    'complete'
  );
