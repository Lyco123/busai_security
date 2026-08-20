# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import timedelta, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from model.vehicle.src.crud import read_raw_db, read_raw_sql
from model.vehicle.src.utils.common import clean_id, read_raw_file, resolve_config_file, smart_date
from model.vehicle.src.utils.logger import logger


BEHAVIOR_MAP_FILE = resolve_config_file("驾驶行为透视表.csv")
WEEKLY_LOOKBACK_DAYS = 6
STATIC_SQL_PATTERN = "ods_jituan_bs_bus*.csv"
BLACK_SPOT_SQL_FILE = "ai_security.ads_event_black_spot.csv"

CAN_REQUIRED_FEATURES = [
    "车辆设备_电池最大电压差",
    "车辆设备_电池电压过低次数",
    "车辆设备_电池电流过高次数",
    "车辆设备_电池最大电流差",
]

VEHICLE_REPAIR_FAULT_FEATURES = [
    "车辆维修_ABS故障(仪表盘)",
    "车辆维修_动力电池故障(电池)",
    "车辆维修_空调工作模式(空调)",
    "车辆维修_单体高低电压差(平台定义域)",
    "车辆维修_左电机故障(电机)",
    "车辆维修_右电机故障(电机)",
    "车辆维修_动力电池故障(整车控制器)",
    "车辆维修_轮胎温度报警(轮胎)",
    "车辆维修_轮胎压力监测(轮胎)",
    "车辆维修_润滑系统故障(润滑系统)",
    "车辆维修_控制器故障代码(打气泵)",
    "车辆维修_控制器故障代码(助力转向泵)",
    "车辆维修_控制器故障代码(DCDC)",
    "车辆维修_绝缘监测故障代码(绝缘监测)",
]

FAULT_TYPE_TO_FEATURE = {
    "ABS故障": "车辆维修_ABS故障(仪表盘)",
    "ABS故障(仪表盘)": "车辆维修_ABS故障(仪表盘)",
    "动力电池故障": "车辆维修_动力电池故障(电池)",
    "动力电池故障(电池)": "车辆维修_动力电池故障(电池)",
    "空调工作模式": "车辆维修_空调工作模式(空调)",
    "空调工作模式(空调)": "车辆维修_空调工作模式(空调)",
    "单体高低电压差": "车辆维修_单体高低电压差(平台定义域)",
    "单体高低电压差(平台定义值)": "车辆维修_单体高低电压差(平台定义域)",
    "单体高低电压差(平台定义域)": "车辆维修_单体高低电压差(平台定义域)",
    "左电机故障": "车辆维修_左电机故障(电机)",
    "左电机故障(电机)": "车辆维修_左电机故障(电机)",
    "右电机故障": "车辆维修_右电机故障(电机)",
    "右电机故障(电机)": "车辆维修_右电机故障(电机)",
    "动力电池故障(整车控制器)": "车辆维修_动力电池故障(整车控制器)",
    "轮胎温度报警": "车辆维修_轮胎温度报警(轮胎)",
    "轮胎温度报警(轮胎)": "车辆维修_轮胎温度报警(轮胎)",
    "轮胎压力监测": "车辆维修_轮胎压力监测(轮胎)",
    "轮胎压力监测(轮胎)": "车辆维修_轮胎压力监测(轮胎)",
    "润滑系统故障": "车辆维修_润滑系统故障(润滑系统)",
    "润滑系统故障(润滑系统)": "车辆维修_润滑系统故障(润滑系统)",
    "控制器故障代码(打气泵)": "车辆维修_控制器故障代码(打气泵)",
    "控制器故障代码(助力转向泵)": "车辆维修_控制器故障代码(助力转向泵)",
    "控制器故障代码(DCDC)": "车辆维修_控制器故障代码(DCDC)",
    "绝缘监测故障代码": "车辆维修_绝缘监测故障代码(绝缘监测)",
    "绝缘监测故障代码(绝缘监测)": "车辆维修_绝缘监测故障代码(绝缘监测)",
}

WEEKLY_PER_KM_EXTRA_COLUMNS = VEHICLE_REPAIR_FAULT_FEATURES + [
    "车辆维修_维修工单数",
]

MANDATORY_ZERO_FEATURES = CAN_REQUIRED_FEATURES + VEHICLE_REPAIR_FAULT_FEATURES + [
    "行驶路况_线路黑点数",
]


def _check_and_log(df: pd.DataFrame | None, table_name: str) -> bool:
    """检查表是否成功读取并输出日志。"""
    if df is None or df.empty:
        logger.warning(f"未读取到 [{table_name}] 数据")
        return False
    logger.info(f"成功读取 [{table_name}]: {len(df)} 行")
    return True


def _load_csv_safe(path: Path) -> pd.DataFrame:
    """按 utf-8-sig 或 gbk 容错读取 CSV。"""
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="gbk", errors="ignore", low_memory=False)


def _pick_first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """按候选顺序返回首个存在的列名。"""
    for column in candidates:
        if column in df.columns:
            return column
    return None


def _filter_date_range(df: pd.DataFrame, date_col: str, start_date: str | None, end_date: str | None) -> pd.DataFrame:
    """按日期列过滤指定时间窗口。"""
    if df is None or df.empty or date_col not in df.columns:
        return df

    result = df.copy()
    result[date_col] = pd.to_datetime(result[date_col], errors="coerce", utc=True).dt.tz_localize(None)
    start_ts = pd.to_datetime(start_date) if start_date else None
    end_ts = pd.to_datetime(end_date) if end_date else None

    if start_ts is not None:
        result = result[result[date_col] >= start_ts]
    if end_ts is not None:
        result = result[result[date_col] <= end_ts]
    return result.copy()


def _get_buffered_start_date(start_date: str | None, lookback_days: int = WEEKLY_LOOKBACK_DAYS) -> str | None:
    """为近 7 天滚动口径向前补足原始读取窗口。"""
    if not start_date:
        return None
    return (pd.to_datetime(start_date) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")


async def _process_can_data(start_date: str | None, end_date: str | None) -> pd.DataFrame:
    """读取 CAN 结果表并生成车辆设备特征。"""
    # CAN 特征优先读取 SQL 导出的明细表，缺失时该类特征会自动跳过。
    _start_date = datetime.strptime(start_date, "%Y-%m-%d")
    _end_date = datetime.strptime(end_date, "%Y-%m-%d")
    start_date_str = _start_date.strftime("%Y%m%d")
    end_date_str = _end_date.strftime("%Y%m%d")

    sqlwhere = f""" ppartition BETWEEN '{start_date_str}' and '{end_date_str}' """
    all_fields = f""" ppartition,obuid,D30,D31,D34,D35"""
    df = await read_raw_db("ai_security.abs_can_stats_result", sqlwhere, all_fields)

    # df = read_raw_file("abs_can_stats_result_*.csv", source="sql")
    if not _check_and_log(df, "CAN压差温差"):
        return pd.DataFrame()

    date_source = "ppartition" if "ppartition" in df.columns else "data_time"
    df["stat_date"] = smart_date(df[date_source])
    df["obuid"] = df["obuid"].apply(clean_id).astype(str)
    df = _filter_date_range(df, "stat_date", start_date, end_date)

    if "D30" in df.columns and "D31" in df.columns:
        df["derived_volt_diff"] = (
            pd.to_numeric(df["D30"], errors="coerce") - pd.to_numeric(df["D31"], errors="coerce")
        ).abs()

    agg_rules = {}
    rename_rules = {}
    if "derived_volt_diff" in df.columns:
        agg_rules["derived_volt_diff"] = "max"
        rename_rules["derived_volt_diff"] = "车辆设备_电池最大电压差"

    if not agg_rules:
        return pd.DataFrame()

    result = df.groupby(["stat_date", "obuid"]).agg(agg_rules).reset_index()
    result = result.rename(columns=rename_rules)

    for column in CAN_REQUIRED_FEATURES:
        if column not in result.columns:
            result[column] = 0.0
    return result[["stat_date", "obuid"] + CAN_REQUIRED_FEATURES]


async def _get_static_features(df_bus_static: pd.DataFrame | None = None) -> pd.DataFrame:
    """读取车辆静态档案并生成静态属性特征。"""
    all_fields = f""" obuid,
        number_plate,
        bus_brand,
        total_weight,
        bus_length,
        battery_capacity,
        bus_age """
    df = df_bus_static if df_bus_static is not None else await read_raw_db("canbus.ods_jituan_bs_bus", None, all_fields)

    # df = df_bus_static if df_bus_static is not None else read_raw_file(STATIC_SQL_PATTERN, source="sql")
    if not _check_and_log(df, "车辆静态档案"):
        return pd.DataFrame()

    df = df.copy()
    df["obuid"] = df["obuid"].apply(clean_id).astype(str)
    df = df.drop_duplicates("obuid", keep="last")

    if "bus_age" not in df.columns:
        logger.warning("静态档案缺少 bus_age 字段，车辆属性_车龄 将输出为空")
        df["bus_age"] = np.nan

    result = pd.DataFrame({"obuid": df["obuid"]})
    result["车辆属性_车辆品牌名称"] = df["bus_brand"].astype(str).str.strip() if "bus_brand" in df.columns else ""#新增
    result["车辆属性_车辆品牌"] = pd.to_numeric(df["bus_brand"], errors="coerce") if "bus_brand" in df.columns else np.nan

    result["车辆属性_车辆自重"] = pd.to_numeric(df["total_weight"], errors="coerce") if "total_weight" in df.columns else np.nan
    result["车辆属性_车长"] = pd.to_numeric(df["bus_length"], errors="coerce") if "bus_length" in df.columns else np.nan
    result["车辆属性_电池容量"] = pd.to_numeric(df["battery_capacity"], errors="coerce") if "battery_capacity" in df.columns else np.nan
    result["车辆属性_车龄"] = pd.to_numeric(df["bus_age"], errors="coerce")
    return result


async def _get_behavior_features(start_date: str | None, end_date: str | None) -> pd.DataFrame:
    """读取驾驶行为汇总表并生成次数类特征。"""
    # 驾驶行为统计直接读取 SQL 导出的宽表结果。
    _start_date = datetime.strptime(start_date, "%Y-%m-%d")
    _end_date = datetime.strptime(end_date, "%Y-%m-%d")
    start_date_str = _start_date.strftime("%Y%m%d")
    end_date_str = _end_date.strftime("%Y%m%d")

    sqlwhere = f""" ppartition BETWEEN '{start_date_str}' and '{end_date_str}' """
    all_fields = f""" ppartition,obuid,COLUMNS('^report_type.*_count$') """
    df = await read_raw_db("ai_security.abs_driver_behavior_sum", sqlwhere, all_fields)

    # df = read_raw_file("abs_driver_behavior_sum_*.csv", source="sql")
    if not _check_and_log(df, "驾驶行为统计表"):
        return pd.DataFrame()

    df["stat_date"] = smart_date(df["ppartition"])
    df["obuid"] = df["obuid"].astype(str).apply(clean_id)
    df = _filter_date_range(df, "stat_date", start_date, end_date)

    map_df = _load_csv_safe(BEHAVIOR_MAP_FILE)
    code_to_name = {}
    if not map_df.empty:
        code_to_name = dict(
            zip(
                map_df["序号"].astype(str).str.replace(r"\.0$", "", regex=True),
                map_df["名称"].astype(str),
            )
        )

    behavior_cols = [column for column in df.columns if column.startswith("report_type") and column.endswith("_count")]
    rename_dict = {}
    agg_rules = {}
    for column in behavior_cols:
        type_code = column.replace("report_type", "").replace("_count", "")
        if type_code not in code_to_name:
            continue
        behavior_name = code_to_name[type_code]
        rename_dict[column] = f"驾驶不良行为_{behavior_name}_次数"
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
        agg_rules[column] = "sum"

    if not agg_rules:
        logger.warning("驾驶行为特征未匹配到有效映射")
        return pd.DataFrame()

    result = df.groupby(["stat_date", "obuid"]).agg(agg_rules).reset_index()
    return result.rename(columns=rename_dict)


async def _get_fault_features(start_date: str | None, end_date: str | None) -> pd.DataFrame:
    """读取故障明细并生成车辆维修故障特征。"""
    # 故障特征改为读取 SQL 导出的故障明细表。
    _start_date = datetime.strptime(start_date, "%Y-%m-%d")
    _end_date = datetime.strptime(end_date, "%Y-%m-%d")
    start_date_str = _start_date.strftime("%Y%m%d")
    end_date_str = _end_date.strftime("%Y%m%d")

    sqlwhere = f""" ppartition BETWEEN '{start_date_str}' and '{end_date_str}' """
    all_fields = f""" ppartition,obuid,fault_type_name """
    df = await read_raw_db("canbus.ads_fault_analysis", sqlwhere, all_fields)

    # df = read_raw_file("ads_fault_analysis_*.csv", source="sql")
    if not _check_and_log(df, "车辆故障数据"):
        return pd.DataFrame()

    df["stat_date"] = smart_date(df["ppartition"])
    df["obuid"] = df["obuid"].apply(clean_id).astype(str)
    df = _filter_date_range(df, "stat_date", start_date, end_date)

    daily_total = df.groupby(["stat_date", "obuid"]).size().reset_index(name="信息_故障当日总次数原始值")
    total_agg = daily_total.rename(columns={"信息_故障当日总次数原始值": "故障_近7天每公里总次数"})
    total_agg["信息_故障当日总次数原始值"] = daily_total["信息_故障当日总次数原始值"].to_numpy()

    if "fault_type_name" in df.columns:
        mapped_df = df[["stat_date", "obuid", "fault_type_name"]].copy()
        mapped_df["fault_type_name"] = mapped_df["fault_type_name"].astype(str).str.strip()
        mapped_df["mapped_fault_feature"] = mapped_df["fault_type_name"].map(FAULT_TYPE_TO_FEATURE)
        mapped_df = mapped_df[mapped_df["mapped_fault_feature"].notna()].copy()

        if not mapped_df.empty:
            mapped_df["fault_count"] = 1
            pivot = (
                mapped_df.pivot_table(
                    index=["stat_date", "obuid"],
                    columns="mapped_fault_feature",
                    values="fault_count",
                    aggfunc="sum",
                    fill_value=0,
                )
                .reset_index()
            )
            pivot.columns = [column if column in ["stat_date", "obuid"] else str(column) for column in pivot.columns]
            total_agg = total_agg.merge(pivot, on=["stat_date", "obuid"], how="left")

    for column in VEHICLE_REPAIR_FAULT_FEATURES:
        if column not in total_agg.columns:
            total_agg[column] = 0.0

    keep_cols = ["stat_date", "obuid", "故障_近7天每公里总次数", "信息_故障当日总次数原始值"] + VEHICLE_REPAIR_FAULT_FEATURES
    return total_agg[keep_cols]


async def _get_aircond_features(start_date: str | None, end_date: str | None) -> pd.DataFrame:
    """读取空调 SQL 聚合结果并生成设备特征。"""
    _start_date = datetime.strptime(start_date, "%Y-%m-%d")
    _end_date = datetime.strptime(end_date, "%Y-%m-%d")
    start_date_str = _start_date.strftime("%Y%m%d")
    end_date_str = _end_date.strftime("%Y%m%d")

    sqlwhere = f""" ppartition BETWEEN '{start_date_str}' and '{end_date_str}' """
    sql = f""" SELECT  ppartition, obuid, SUM(open_time) AS total_open_time, COUNT(*) AS record_count
                FROM canbus.ads_air_conditioner_use where {sqlwhere}
                GROUP BY  ppartition,  obuid"""
    df = await read_raw_sql(sql)

    # df = read_raw_file("*_SELECT_ppartition_obuid_SUM_open_time*.csv", source="sql")
    if not _check_and_log(df, "空调SQL聚合结果"):
        return pd.DataFrame()

    df["stat_date"] = smart_date(df["ppartition"])
    df["obuid"] = df["obuid"].apply(clean_id).astype(str)
    df = _filter_date_range(df, "stat_date", start_date, end_date)

    for column in ["total_open_time", "record_count"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    result = df.rename(
        columns={
            "total_open_time": "车辆设备_空气压缩机开启时长",
            "record_count": "车辆设备_空气压缩机开关次数",
        }
    )
    final_cols = ["stat_date", "obuid", "车辆设备_空气压缩机开启时长", "车辆设备_空气压缩机开关次数"]
    return result[[column for column in final_cols if column in result.columns]]


async def _get_charge_features(start_date: str | None, end_date: str | None) -> pd.DataFrame:
    """读取日充电分析表并生成充电相关特征。"""
    _start_date = datetime.strptime(start_date, "%Y-%m-%d")
    _end_date = datetime.strptime(end_date, "%Y-%m-%d")
    start_date_str = _start_date.strftime('%Y%m%d')
    end_date_str = _end_date.strftime('%Y%m%d')

    sqlwhere = f""" ppartition BETWEEN '{start_date_str}' and '{end_date_str}' """
    all_fields = f"""  ppartition,obuid,day_charge_count,night_charge_count,day_charge_soc,night_charge_soc,
                    use_soc,run_mileage """
    df = await read_raw_db("canbus.ads_day_energy_analysis", sqlwhere, all_fields)

    # df = read_raw_file("ads_day_energy_analysis_*.csv", source="sql")
    if not _check_and_log(df, "充电能耗数据"):
        return pd.DataFrame()

    df["stat_date"] = smart_date(df["ppartition"])
    df["obuid"] = df["obuid"].apply(clean_id).astype(str)
    df = _filter_date_range(df, "stat_date", start_date, end_date)

    for column in ["day_charge_count", "night_charge_count", "day_charge_soc", "night_charge_soc", "use_soc", "run_mileage"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    df["day_total_count"] = df.get("day_charge_count", 0) + df.get("night_charge_count", 0)
    df["total_charge_soc"] = df.get("day_charge_soc", 0) + df.get("night_charge_soc", 0)

    agg = (
        df.groupby(["stat_date", "obuid"])
        .agg(
            {
                "day_total_count": "sum",
                "total_charge_soc": "sum",
                "use_soc": "sum",
                "run_mileage": "sum",
            }
        )
        .reset_index()
    )
    agg["车辆设备_每公里耗电量"] = np.where(agg["run_mileage"] > 0.01, agg["use_soc"] / agg["run_mileage"], 0)
    agg = agg.drop(columns=["use_soc", "run_mileage"])
    return agg.rename(columns={"day_total_count": "车辆设备_日充电次数", "total_charge_soc": "车辆设备_日充电量"})


async def _get_repair_features(start_date: str | None, end_date: str | None, df_bus_static: pd.DataFrame | None = None) -> pd.DataFrame:
    """读取维修记录并通过车牌映射到 obuid。"""
    _start_date = datetime.strptime(start_date, "%Y-%m-%d")
    start_date_str_ym = _start_date.strftime('%Y%m')
    sqlwhere = f""" toYYYYMM(f_indatetime)='{start_date_str_ym}' """
    all_fields=f"""  f_buslisence,f_indatetime """
    df_repair = await read_raw_db("ai_security.ods_jituan_mssql_10_91_172_11_gzbus_repair_v_busteam_project", sqlwhere,all_fields)

    # df_repair = read_raw_file("ods_jituan_mssql_*_repair_*.csv", source="sql")
    # df_static = df_bus_static if df_bus_static is not None else read_raw_file(STATIC_SQL_PATTERN, source="sql")
    df_static = df_bus_static if df_bus_static is not None else await read_raw_db("canbus.ods_jituan_bs_bus")
    if not _check_and_log(df_repair, "车辆维修记录") or not _check_and_log(df_static, "静态档案(维修关联)"):
        return pd.DataFrame()

    df_static = df_static.copy()
    df_static["obuid"] = df_static["obuid"].apply(clean_id).astype(str)
    plate_col = _pick_first_existing_column(df_static, ["number_plate", "plate_no", "license_plate"])
    if plate_col is None:
        logger.warning("静态档案缺少车牌号字段，无法建立维修表车辆映射")
        return pd.DataFrame()

    plate_map = df_static.drop_duplicates(plate_col).set_index(plate_col)["obuid"].to_dict()
    df_repair = df_repair.copy()
    df_repair["obuid"] = df_repair["f_buslisence"].map(plate_map)
    df_repair = df_repair.dropna(subset=["obuid"])
    df_repair["stat_date"] = pd.to_datetime(df_repair["f_indatetime"], errors="coerce").dt.normalize()
    df_repair = _filter_date_range(df_repair, "stat_date", start_date, end_date)

    daily = df_repair.groupby(["stat_date", "obuid"]).size().rename("车辆维修_维修工单数").reset_index()
    if daily.empty:
        return pd.DataFrame()
    return daily


async def _get_trip_context_features(start_date: str | None, end_date: str | None) -> pd.DataFrame:
    """读取线路站点数和转弯点数聚合结果。"""
    _start_date = datetime.strptime(start_date, "%Y-%m-%d")
    _end_date = datetime.strptime(end_date, "%Y-%m-%d")
    start_date_str = _start_date.strftime('%Y%m%d')
    end_date_str = _end_date.strftime('%Y%m%d')

    sqlwhere = f""" ppartition BETWEEN '{start_date_str}' and '{end_date_str}' """
    sql=f"""   SELECT
            drive_date,
            bus_id,
            SUM(turn_count) AS total_turn_count
        FROM (
            SELECT
                toDate(t.ppartition) AS drive_date,
                t.bus_id,
                t.route_id,
                COUNT(b.event_type) AS turn_count
            FROM (select * from canbus.ads_triplog_energy where {sqlwhere}) t
            GLOBAL LEFT JOIN canbus.ads_event_black_spot b
                ON toString(t.route_id) = splitByChar('#', b.route_ids)[1]
               AND b.event_type GLOBAL IN (2, 3)
            GROUP BY
                drive_date,
                bus_id,
                t.route_id
        ) sub
        GROUP BY
            drive_date,
            bus_id;
     
        """
    df_turn = await read_raw_sql(sql)
    # df_turn = read_raw_file("*_SELECT_drive_date_bus_id_sum_turn_count_AS_total_turn*.csv", source="sql")

    sql = f"""
            SELECT
                drive_date,
                bus_id,
                SUM(station_count) AS total_station_count
            FROM (
                SELECT
                    toDate(t.ppartition) AS drive_date,
                    t.bus_id as bus_id,
                    t.route_id as route_id,
                    t.from_station as from_station,
                    t.to_station as to_station,
                    abs(s2.min_sort - s1.min_sort) + 1 AS station_count
                FROM (select * from canbus.ads_triplog_energy where {sqlwhere}) t
                GLOBAL LEFT JOIN (
                    SELECT line_code, motorcade_name, MIN(sort) AS min_sort
                    FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
                    GROUP BY line_code, motorcade_name
                ) s1
                    ON toString(t.route_id) = s1.line_code
                   AND t.from_station = s1.motorcade_name
                GLOBAL LEFT JOIN (
                    SELECT line_code, motorcade_name, MIN(sort) AS min_sort
                    FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
                    GROUP BY line_code, motorcade_name
                ) s2
                    ON toString(t.route_id) = s2.line_code
                   AND t.to_station = s2.motorcade_name
            ) sub
            GROUP BY
                drive_date,
                bus_id;"""

    df_station = await read_raw_sql(sql)
    # df_station = read_raw_file("*_SELECT_drive_date_bus_id_sum_station_count_AS_total_station*.csv", source="sql")

    ok_turn = _check_and_log(df_turn, "线路转弯点聚合表")
    ok_station = _check_and_log(df_station, "线路站点数聚合表")
    if not ok_turn and not ok_station:
        return pd.DataFrame()

    def _normalize_trip_context_df(df: pd.DataFrame, value_col: str, new_value_col: str) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame(columns=["stat_date", "obuid", new_value_col])

        result = df.copy().rename(columns={"drive_date": "stat_date", "bus_id": "obuid", value_col: new_value_col})
        keep_cols = ["stat_date", "obuid", new_value_col]
        result = result[[column for column in keep_cols if column in result.columns]].copy()
        result["stat_date"] = pd.to_datetime(result["stat_date"], errors="coerce").dt.normalize()
        result["obuid"] = result["obuid"].astype(str).apply(clean_id)
        result[new_value_col] = pd.to_numeric(result[new_value_col], errors="coerce").fillna(0)
        result = result[result["stat_date"].notna()]
        result = result[result["obuid"].notna() & (result["obuid"].astype(str).str.strip() != "")]
        result = _filter_date_range(result, "stat_date", start_date, end_date)
        return result.groupby(["stat_date", "obuid"], as_index=False)[new_value_col].sum()

    station_df = _normalize_trip_context_df(df_station, "total_station_count", "车辆运营_线路站点数")
    turn_df = _normalize_trip_context_df(df_turn, "total_turn_count", "车辆运营_线路转弯点数")
    result = pd.merge(station_df, turn_df, on=["stat_date", "obuid"], how="outer")

    if result.empty:
        return pd.DataFrame(columns=["stat_date", "obuid", "车辆运营_线路站点数", "车辆运营_线路转弯点数"])

    for column in ["车辆运营_线路站点数", "车辆运营_线路转弯点数"]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0)
    return result


async def _get_black_spot_features(base_df: pd.DataFrame, start_date: str | None, end_date: str | None) -> pd.DataFrame:
    """按车辆当日行驶线路计算线路黑点数。"""
    _start_date = datetime.strptime(start_date, "%Y-%m-%d")
    start_date_str_ym = _start_date.strftime('%Y%m')
    all_fields = f"""  name,
                route_name,
                route_ids,
                status
                event_type """
    df_black = await read_raw_db("canbus.ads_event_black_spot", None, all_fields)

    # df_black = read_raw_file(BLACK_SPOT_SQL_FILE, source="sql")
    if not _check_and_log(df_black, "线路黑点表"):
        return pd.DataFrame(columns=["stat_date", "obuid", "行驶路况_线路黑点数"])

    route_id_col = _pick_first_existing_column(df_black, ["route_ids", "routeids", "route_id"])
    if route_id_col is None:
        logger.warning("黑点表缺少 route_ids 字段，行驶路况_线路黑点数 将输出为 0")
        return pd.DataFrame(columns=["stat_date", "obuid", "行驶路况_线路黑点数"])

    route_usage = base_df[["stat_date", "obuid", "route_id_str"]].copy()
    route_usage = route_usage.rename(columns={"route_id_str": "route_id"})
    route_usage["stat_date"] = pd.to_datetime(route_usage["stat_date"], errors="coerce").dt.normalize()
    route_usage["obuid"] = route_usage["obuid"].astype(str).apply(clean_id)
    route_usage["route_id"] = route_usage["route_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    route_usage = route_usage[route_usage["stat_date"].notna()]
    route_usage = route_usage[route_usage["route_id"].notna() & (route_usage["route_id"] != "")]
    route_usage = _filter_date_range(route_usage, "stat_date", start_date, end_date)
    route_usage = route_usage.drop_duplicates(["stat_date", "obuid", "route_id"])
    if route_usage.empty:
        return pd.DataFrame(columns=["stat_date", "obuid", "行驶路况_线路黑点数"])

    route_count_df = route_usage.groupby(["stat_date", "obuid"])['route_id'].nunique().reset_index(name="route_count")
    multi_route_vehicle_count = route_count_df.loc[route_count_df["route_count"] > 1, "obuid"].nunique()
    total_vehicle_count = route_count_df["obuid"].nunique()
    logger.info(f"线路黑点数匹配: 多线路车辆 {multi_route_vehicle_count} / 总车辆 {total_vehicle_count}")

    df_black = df_black.copy()
    df_black[route_id_col] = df_black[route_id_col].astype(str).str.strip()
    df_black = df_black[df_black[route_id_col].notna() & (df_black[route_id_col] != "")]
    direction_black_count = df_black.groupby(route_id_col).size().reset_index(name="direction_black_count")
    direction_black_count["route_id"] = direction_black_count[route_id_col].astype(str).str.split("#").str[0].str.strip()
    route_black_count = (
        direction_black_count.groupby("route_id", as_index=False)["direction_black_count"].mean().rename(columns={"direction_black_count": "行驶路况_线路黑点数"})
    )

    route_usage = route_usage.merge(route_black_count, on="route_id", how="left")
    route_usage["行驶路况_线路黑点数"] = pd.to_numeric(route_usage["行驶路况_线路黑点数"], errors="coerce").fillna(0)
    return route_usage.groupby(["stat_date", "obuid"], as_index=False)["行驶路况_线路黑点数"].mean()


def _normalize_behavior_features(df: pd.DataFrame) -> pd.DataFrame:
    """按站点数、转弯点数和里程对驾驶行为做业务归一化。"""
    result = df.copy()
    for column in ["车辆运营_线路转弯点数", "车辆运营_线路站点数", "车辆运营_运营里程"]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")

    safe_mileage = result["车辆运营_运营里程"].replace(0, np.nan) if "车辆运营_运营里程" in result.columns else np.nan
    safe_stations = result["车辆运营_线路站点数"].replace(0, np.nan) if "车辆运营_线路站点数" in result.columns else np.nan
    safe_turns = result["车辆运营_线路转弯点数"].replace(0, np.nan) if "车辆运营_线路转弯点数" in result.columns else np.nan

    turn_behaviors = ["左转弯未刹车", "右转弯未刹车", "不规范转弯"]
    station_behaviors = ["不规范开关门", "不规范出站", "不规范进站"]

    by_station = []
    by_turn = []
    by_mileage = []
    for column in [name for name in result.columns if name.startswith("驾驶不良行为_") and "次数" in name]:
        if any(keyword in column for keyword in turn_behaviors):
            result[column] = (result[column] / safe_turns) * 100
            by_turn.append(column)
        elif any(keyword in column for keyword in station_behaviors):
            result[column] = (result[column] / safe_stations) * 100
            by_station.append(column)
        else:
            result[column] = (result[column] / safe_mileage) * 1000
            by_mileage.append(column)

    logger.info(f"按站点数归一化特征: {', '.join(by_station)}")
    logger.info(f"按转弯点数归一化特征: {', '.join(by_turn)}")
    logger.info(f"按千公里归一化特征: {', '.join(by_mileage[:10])}")
    return result


def _get_weekly_per_km_columns(df: pd.DataFrame) -> list[str]:
    """收集需要按近 7 天每公里折算的次数类特征。"""
    columns = [column for column in df.columns if column.startswith("故障_") and "次数" in column]
    for column in WEEKLY_PER_KM_EXTRA_COLUMNS:
        if column in df.columns and column not in columns:
            columns.append(column)
    return columns


def _apply_weekly_per_km_counts(df: pd.DataFrame) -> pd.DataFrame:
    """把故障和维修次数类特征折算为近 7 天每公里。"""
    result = df.copy()
    required_columns = {"信息_统计日期", "信息_车辆ID", "车辆运营_运营里程"}
    if not required_columns.issubset(result.columns):
        return result

    weekly_columns = _get_weekly_per_km_columns(result)
    if not weekly_columns:
        return result

    if "故障_近7天每公里总次数" in result.columns and "信息_故障当日总次数原始值" not in result.columns:
        result["信息_故障当日总次数原始值"] = pd.to_numeric(result["故障_近7天每公里总次数"], errors="coerce")

    result["信息_统计日期"] = pd.to_datetime(result["信息_统计日期"], errors="coerce")
    result = result.sort_values(["信息_车辆ID", "信息_统计日期"]).copy()
    result[weekly_columns] = result[weekly_columns].apply(pd.to_numeric, errors="coerce").astype(float)
    result["车辆运营_运营里程"] = pd.to_numeric(result["车辆运营_运营里程"], errors="coerce")

    for _, group in result.groupby("信息_车辆ID", sort=False):
        group = group.sort_values("信息_统计日期")
        mileage = group["车辆运营_运营里程"].fillna(0).clip(lower=0)
        weekly_mileage = mileage.rolling(7, min_periods=1).sum()
        weekly_counts = group[weekly_columns].fillna(0).clip(lower=0).rolling(7, min_periods=1).sum()
        normalized = weekly_counts.div(weekly_mileage.replace(0, np.nan), axis=0)
        result.loc[group.index, weekly_columns] = normalized.to_numpy()

    logger.info(f"按近7天每公里折算次数类特征: {', '.join(weekly_columns)}")
    return result


def _ensure_mandatory_feature_columns(df: pd.DataFrame) -> pd.DataFrame:
    """补齐当前业务要求必须保留的占位列。"""
    result = df.copy()
    for column in MANDATORY_ZERO_FEATURES:
        if column not in result.columns:
            result[column] = 0.0
    return result


async def build_feature_frames(start_date: str | None, end_date: str | None, save_path: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """构建 raw_df 和 model_df 两套宽表。"""
    logger.chapter(f"构建特征宽表 | 时间窗口: {start_date} ~ {end_date}")

    source_start_date = _get_buffered_start_date(start_date)
    if source_start_date and start_date and source_start_date != start_date:
        logger.info(f"为计算近7天滚动口径，原始数据读取窗口自动回溯到: {source_start_date} ~ {end_date}")

    sqlwhere = f""" ppartition BETWEEN '{start_date}' and '{end_date}' """
    all_fields = f""" ppartition,organ_id,organ_name,number_plate,obuid,bus_id,route_id,run_mileage,energy,total_second """
    base_df = await read_raw_db("canbus.ads_bus_energy_day_stat", sqlwhere, all_fields)

    # base_df = read_raw_file("ads_bus_energy_day_stat_*.csv", source="sql")
    if base_df is None or base_df.empty:
        raise ValueError("基础能耗数据为空，无法构建宽表")

    base_df["stat_date"] = smart_date(base_df["ppartition"])
    base_df["obuid"] = base_df["obuid"].apply(clean_id).astype(str)
    base_df["route_id_str"] = base_df["route_id"].astype(str).str.replace(r"\.0$", "", regex=True)

    column_mapping = {
        "stat_date": "信息_统计日期",
        "obuid": "信息_车辆ID",
        "bus_id": "信息_车辆自编号ID",
        "number_plate": "信息_车牌号",
        "organ_id": "信息_公司ID",
        "organ_name": "信息_公司名称",
        "route_id_str": "信息_线路ID",
        "run_mileage": "车辆运营_运营里程",
        "energy": "指标_百公里能耗",
        "total_second": "车辆运营_运营时长",
    }
    df_final = base_df[[column for column in column_mapping if column in base_df.columns]].rename(columns=column_mapping)

    for column in ["车辆运营_运营里程", "指标_百公里能耗", "车辆运营_运营时长"]:
        if column in df_final.columns:
            df_final[column] = pd.to_numeric(df_final[column], errors="coerce")
    if "车辆运营_运营时长" in df_final.columns:
        df_final["车辆运营_运营时长"] = df_final["车辆运营_运营时长"] / 3600.0

    original_count = len(df_final)
    df_final["信息_统计日期"] = pd.to_datetime(df_final["信息_统计日期"])
    df_final = _filter_date_range(df_final, "信息_统计日期", source_start_date, end_date)
    logger.info(f"时间筛选({source_start_date or start_date} ~ {end_date}): {original_count} -> {len(df_final)} 行")

    if df_final.empty:
        raise ValueError("筛选后宽表为空，请检查日期范围")

    cleaning_rules = {
        "车辆运营_运营里程": (0, 400.0),
        "指标_百公里能耗": (0, 300.0),
        "车辆运营_运营时长": (0, 24.0),
    }
    for column, (min_value, max_value) in cleaning_rules.items():
        outlier_mask = ((df_final[column] < min_value) | (df_final[column] > max_value)) & df_final[column].notna()
        if outlier_mask.any():
            logger.info(f"发现 [{column}] 极值异常(<{min_value} 或 >{max_value}): {int(outlier_mask.sum())} 条 -> 置为 NaN")
            df_final.loc[outlier_mask, column] = np.nan

    if {"车辆运营_运营里程", "车辆运营_运营时长"}.issubset(df_final.columns):
        hours = df_final["车辆运营_运营时长"]
        df_final["车辆运营_平均速度"] = np.where(hours > 0.01, df_final["车辆运营_运营里程"] / hours, np.nan)
        df_final["行驶路况_拥堵指数"] = np.where(df_final["车辆运营_运营里程"] > 0.01, hours / df_final["车辆运营_运营里程"], np.nan)

    all_fields = f""" obuid,
        number_plate,
        bus_brand,
        total_weight,
        bus_length,
        battery_capacity,
        bus_age """
    df_bus_static = await read_raw_db("canbus.ods_jituan_bs_bus", None, all_fields)

    # df_bus_static = read_raw_file(STATIC_SQL_PATTERN, source="sql")
    extractors = [
        (await _process_can_data(source_start_date, end_date), ["stat_date", "obuid"]),
        (await _get_static_features(df_bus_static), ["obuid"]),
        (await _get_behavior_features(source_start_date, end_date), ["stat_date", "obuid"]),
        (await _get_fault_features(source_start_date, end_date), ["stat_date", "obuid"]),
        (await _get_aircond_features(source_start_date, end_date), ["stat_date", "obuid"]),
        (await _get_charge_features(source_start_date, end_date), ["stat_date", "obuid"]),
        (await _get_repair_features(source_start_date, end_date, df_bus_static), ["stat_date", "obuid"]),
        (await _get_trip_context_features(source_start_date, end_date), ["stat_date", "obuid"]),
        (await _get_black_spot_features(base_df, source_start_date, end_date), ["stat_date", "obuid"]),
    ]

    key_map = {"stat_date": "信息_统计日期", "obuid": "信息_车辆ID"}
    for feature_df, raw_keys in extractors:
        if feature_df is None or feature_df.empty:
            continue

        feature_df = feature_df.rename(columns=key_map)
        merge_keys = [key_map[key] for key in raw_keys if key in key_map]
        for key in merge_keys:
            if key == "信息_统计日期":
                feature_df[key] = pd.to_datetime(feature_df[key])
                df_final[key] = pd.to_datetime(df_final[key])
            else:
                feature_df[key] = feature_df[key].astype(str)
                df_final[key] = df_final[key].astype(str)

        df_final = df_final.merge(feature_df, on=merge_keys, how="left")
        df_final = df_final.loc[:, ~df_final.columns.duplicated()]
        logger.info(f"Merged: {list(feature_df.columns[:2])} ...")

    df_final = _ensure_mandatory_feature_columns(df_final)
    raw_df = _normalize_behavior_features(df_final)
    raw_df = _apply_weekly_per_km_counts(raw_df)
    raw_df = _filter_date_range(raw_df, "信息_统计日期", start_date, end_date)
    model_df = raw_df.copy()

    for prefix in ["故障_", "车辆维修_", "车辆设备_"]:
        fill_columns = [column for column in model_df.columns if column.startswith(prefix)]
        if fill_columns:
            model_df[fill_columns] = model_df[fill_columns].fillna(0)

    for column in ["车辆运营_线路转弯点数", "车辆运营_线路站点数", "行驶路况_线路黑点数"]:
        if column in model_df.columns:
            model_df[column] = model_df[column].fillna(0)

    raw_df["信息_统计日期"] = pd.to_datetime(raw_df["信息_统计日期"]).dt.strftime("%Y-%m-%d")
    model_df["信息_统计日期"] = pd.to_datetime(model_df["信息_统计日期"]).dt.strftime("%Y-%m-%d")

    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        model_df.to_csv(save_path, index=False, encoding="utf-8-sig")
        logger.info(f"特征宽表已保存: {save_path}")

    return raw_df, model_df


async def build_feature_table(start_date: str | None, end_date: str | None, save_path: Path | None = None) -> pd.DataFrame:
    """只返回按训练/评分口径补值后的模型输入宽表。"""
    _, model_df = await build_feature_frames(start_date, end_date, save_path=save_path)
    return model_df