# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import OrderedDict

# 只保留会影响模型结果的配置；路径和文件输出放在 app_*.py / data_io.py。

# Score 对外输出口径：formal=正式分，scorecard=评分卡分；默认正式分。
SCORE_OUTPUT_MODE = "formal"

# 正式预警策略：能耗每日 Top30%，故障每日 Top5%，边界统一映射到 65 分。
BUSINESS_SCORE_THRESHOLD = 65.0
ALERT_CONFIG = {
    "energy_top_percent": 0.30,
    "fault_top_percent": 0.15,
    "business_score_threshold": BUSINESS_SCORE_THRESHOLD,
}

# 标签规则：能耗使用 D-30 同线路 LOO + D0 同车型 LOO；故障使用未来 7 天。
LABEL_CONFIG = {
    "energy_target_col": "Target_高能耗",
    "fault_target_col": "Target_未来7天以内故障",
    "energy_route_lookback_days": 30,
    "energy_route_ratio": 1.05,
    "energy_type_ratio": 1.10,
    "energy_loo_min_other_n": 2,
    "energy_high_risk_threshold": BUSINESS_SCORE_THRESHOLD,
    "fault_future_days": 7,
    "fault_source_candidates": [
        "信息_故障当日总次数原始值",
        "故障_当日总次数",
        "信息_当日故障次数",
    ],
}

# 原始数据读取窗口和故障 rolling 窗口。
WINDOW_CONFIG = {
    "source_lookback_days": 30,
    "energy_route_lookback_days": 30,
    "fault_rolling_days": 30,
    "fault_shift_days": 1,
}

# 数据质量：硬性异常会影响能耗可评分资格。
DATA_QUALITY_CONFIG = {
    "ENERGY_PER_100KM_MIN": 0,
    "ENERGY_PER_100KM_MAX": 1000,
    "RUN_MILEAGE_MIN": 0,
    "RUN_MILEAGE_MAX": 400,
    "RUN_HOURS_MIN": 0,
    "RUN_HOURS_MAX": 24,
}

OUTLIER_RULES = {
    "信息_车辆百公里能耗": (0, 1000.0),
    "指标_百公里能耗": (0, 500.0),
    "车辆运营_运营里程": (0, 400.0),
    "车辆运营_运营时长": (0, 24.0),
}

# 训练与评分参数。
XGB_WEIGHT_CAP_N = 40
NORMALIZE_LOWER_Q = 0.01
NORMALIZE_UPPER_Q = 0.99
NORMALIZE_FALLBACK_VALUE = 0
LEVEL_1_WEIGHT_MAP = {"车辆能耗模型": 0.6, "车辆故障模型": 0.4}

# =============================================================================
# 特征清单与字段规格
# =============================================================================

ENERGY_FEATURES = [
    "车辆属性_车龄",
    "车辆属性_车长",
    "车辆属性_车辆品牌",
    "车辆属性_车辆自重",
    "车辆运营_运营时长",
    "车辆运营_平均速度",
    "车辆运营_拥堵指数",
    "行驶路况_线路黑点密度",
    "行驶路况_线路客流量密度",
    "行驶路况_线路站点密度",
    "行驶路况_转弯密度",
    "车辆设备_空调开启时长占比",
    "车辆设备_百公里空气压缩机开启时长",
    "车辆设备_百公里空气压缩机开关次数",
    "车辆设备_百公里充电次数",
    "车辆设备_百公里充电SOC",
    "驾驶不良行为_急加减速类_千公里次数",
    "驾驶不良行为_超速类_千公里次数",
    "驾驶不良行为_滑行类_千公里次数",
    "驾驶不良行为_坡道路况不规范类_千公里次数",
    "驾驶不良行为_设备使用违规类_千公里次数",
    "驾驶不良行为_起步路口进站类_千公里次数",
    "驾驶不良行为_站点作业类_百站违规率",
    "驾驶不良行为_转弯作业类_百转弯点违规率",
    "驾驶不良行为_档位手刹类_公里次数",
    "驾驶不良行为_违规类型数",
]

FAULT_FEATURES = [
    "车辆属性_车龄",
    "车辆属性_车长",
    "车辆属性_车辆品牌",
    "车辆属性_车辆自重",
    "车辆运营_近30日运营里程累计",
    "车辆运营_近30日运营时长累计",
    "车辆运营_近30日平均速度",
    "车辆运营_近30日拥堵指数",
    "行驶路况_近30日线路黑点密度",
    "行驶路况_近30日线路客流量密度",
    "行驶路况_近30日线路站点密度",
    "行驶路况_近30日转弯密度",
    "车辆设备_近30日空调开启时长占比",
    "车辆设备_近30日百公里空气压缩机开启时长",
    "车辆设备_近30日百公里空气压缩机开关次数",
    "车辆设备_近30日百公里充电次数",
    "车辆设备_近30日百公里充电SOC",
    "车辆设备_近30日电池最大电压差均值",
    "车辆设备_近30日电池最大电压均值",
    "车辆设备_近30日电池最高温度均值",
    "车辆设备_近30日电池最高温度最大值",
    "车辆设备_近30日电池最大电流差均值",
    "车辆设备_近30日电池最高电流均值",
    "车辆维修_近30日动力电池相关故障次数",
    "车辆维修_近30日维修故障类型数",
    "车辆维修_近30日维修故障总次数",
    "车辆维修_近30日三电系统故障次数",
    "车辆维修_近30日轮胎相关故障次数",
    "车辆维修_近30日控制器相关故障次数",
    "车辆维修_近30日高危故障次数",
]

MODEL_FEATURE_ALLOWLIST_BY_TASK = {
    "energy": ENERGY_FEATURES,
    "fault": FAULT_FEATURES,
}

MODEL_FEATURE_ALLOWLIST = list(OrderedDict.fromkeys(ENERGY_FEATURES + FAULT_FEATURES))

QUALITY_FIELDS = [
    "是否可训练",
    "是否可评分",
    "不可训练原因",
    "不可评分原因",
    "异常字段列表",
]

# 这些字段缺失时按 0 处理，代表“当天没有该事件/记录”。
# 该清单同时服务 features.py 和 preprocessing.py，因此保留在 config.py。
EVENT_ZERO_FEATURES = ['驾驶不良行为_起步急加速_次数', '驾驶不良行为_急加速_次数', '驾驶不良行为_急减速_次数', '驾驶不良行为_急刹车_次数', '驾驶不良行为_急停_次数', '驾驶不良行为_斑马线超速_次数', '驾驶不良行为_区间超速_次数', '驾驶不良行为_全局超速_次数', '驾驶不良行为_空档滑行_次数', '驾驶不良行为_熄火滑行_次数', '驾驶不良行为_平路不规范行为_次数', '驾驶不良行为_上坡不规范行为_次数', '驾驶不良行为_下坡不规范行为_次数', '驾驶不良行为_违规使用空调_次数', '驾驶不良行为_违规使用总电_次数', '驾驶不良行为_车辆起步不关门_次数', '驾驶不良行为_路口大油门_次数', '驾驶不良行为_进站违规制动_次数', '驾驶不良行为_不规范进站_次数', '驾驶不良行为_不规范出站_次数', '驾驶不良行为_安全启动_次数', '驾驶不良行为_左转弯未刹车_次数', '驾驶不良行为_不规范转弯_次数', '驾驶不良行为_右转弯未刹车_次数', '驾驶不良行为_违规使用手刹_次数', '驾驶不良行为_停站N档违规_次数', '驾驶不良行为_违规使用N档_次数', '驾驶不良行为_停车不挂N档_次数', '车辆维修_ABS故障(仪表盘)', '车辆维修_动力电池故障(电池)', '车辆维修_空调工作模式(空调)', '车辆维修_单体高低电压差(平台定义域)', '车辆维修_左电机故障(电机)', '车辆维修_右电机故障(电机)', '车辆维修_动力电池故障(整车控制器)', '车辆维修_轮胎温度报警(轮胎)', '车辆维修_轮胎压力监测(轮胎)', '车辆维修_润滑系统故障(润滑系统)', '车辆维修_控制器故障代码(打气泵)', '车辆维修_控制器故障代码(助力转向泵)', '车辆维修_控制器故障代码(DCDC)', '车辆维修_绝缘监测故障代码(绝缘监测)', '驾驶不良行为_急加减速类_千公里次数', '驾驶不良行为_超速类_千公里次数', '驾驶不良行为_滑行类_千公里次数', '驾驶不良行为_坡道路况不规范类_千公里次数', '驾驶不良行为_设备使用违规类_千公里次数', '驾驶不良行为_起步路口进站类_千公里次数', '驾驶不良行为_站点作业类_百站违规率', '驾驶不良行为_转弯作业类_百转弯点违规率', '驾驶不良行为_档位手刹类_公里次数', '驾驶不良行为_违规类型数', '驾驶不良行为_近30日急加减速类_千公里次数', '驾驶不良行为_近30日超速类_千公里次数', '驾驶不良行为_近30日滑行类_千公里次数', '驾驶不良行为_近30日坡道路况不规范类_千公里次数', '驾驶不良行为_近30日设备使用违规类_千公里次数', '驾驶不良行为_近30日起步路口进站类_千公里次数', '驾驶不良行为_近30日站点作业类_百站违规率', '驾驶不良行为_近30日转弯作业类_百转弯点违规率', '驾驶不良行为_近30日档位手刹类_公里次数', '驾驶不良行为_近30日违规类型数', '车辆维修_近30日动力电池相关故障次数', '车辆维修_近30日维修故障类型数', '车辆维修_近30日维修故障总次数', '车辆维修_近30日三电系统故障次数', '车辆维修_近30日轮胎相关故障次数', '车辆维修_近30日控制器相关故障次数', '车辆维修_近30日高危故障次数', '车辆维修_维修工单数', '车辆设备_日充电次数', '车辆设备_日充电SOC', '车辆设备_百公里充电次数', '车辆设备_百公里充电SOC', '车辆设备_近30日百公里充电次数', '车辆设备_近30日百公里充电SOC', '故障_当日总次数', '信息_故障当日总次数原始值', 'report_type1_count', 'report_type2_count', 'report_type3_count', 'report_type4_count', 'report_type5_count', 'report_type6_count', 'report_type7_count', 'report_type8_count', 'report_type9_count', 'report_type10_count', 'report_type11_count', 'report_type12_count', 'report_type13_count', 'report_type14_count', 'report_type15_count', 'report_type16_count', 'report_type17_count', 'report_type18_count', 'report_type19_count', 'report_type20_count', 'report_type21_count', 'report_type22_count', 'report_type23_count', 'report_type24_count', 'report_type25_count', 'report_type26_count', 'report_type27_count', 'report_type28_count', 'fault_abs_dashboard_count', 'fault_power_battery_count', 'fault_aircond_mode_count', 'fault_cell_voltage_diff_count', 'fault_left_motor_count', 'fault_right_motor_count', 'fault_battery_vcu_count', 'fault_tire_temp_count', 'fault_tire_pressure_count', 'fault_lubrication_count', 'fault_controller_air_pump_count', 'fault_controller_steering_pump_count', 'fault_controller_dcdc_count', 'fault_insulation_count', 'fault_total_count', 'fault_total_count_raw', 'repair_order_count', 'day_charge_count', 'night_charge_count']

IMPUTATION_MIN_GROUP_COUNT = 10
IMPUTATION_GROUPS_BY_TASK = {
    "energy": [
        ["信息_线路ID", "车辆属性_车辆类型"],
        ["信息_route_id", "车辆属性_车辆类型"],
        ["车辆属性_车辆类型"],
        ["信息_线路ID"],
        ["信息_route_id"],
    ],
    "fault": [
        ["车辆属性_车辆类型"],
        ["车辆属性_车辆品牌"],
        ["信息_公司ID"],
        ["信息_organ_id"],
    ],
    "default": [
        ["车辆属性_车辆类型"],
        ["信息_organ_id"],
    ],
}
