# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import timedelta
from typing import Any
import warnings

import numpy as np
import pandas as pd
from pandas.errors import PerformanceWarning

from model.vehicle.src.utils import logger, clean_id
from model.vehicle.src.preprocessing import fill_event_missing_zero, build_quality_flags


warnings.filterwarnings("ignore", category=PerformanceWarning)

from model.vehicle.src.config import (
    LABEL_CONFIG,
    OUTLIER_RULES,
    WINDOW_CONFIG,
)
from model.vehicle.src.config import (
    ENERGY_FEATURES,
    EVENT_ZERO_FEATURES,
    FAULT_FEATURES,
    MODEL_FEATURE_ALLOWLIST,
    MODEL_FEATURE_ALLOWLIST_BY_TASK,
    QUALITY_FIELDS,
)


KEYS = {
    "date": "信息_ppartition",
    "bus": "信息_bus_id",
    "route": "信息_route_id",
}
SOURCE_COLUMNS = {
    "mileage": "src_run_mileage",
    "energy_per_100km": "src_mileage_energy",
    "total_energy": "src_energy",
    "total_second": "src_total_second",
}

INFO_COLUMNS = [
    "信息_ppartition_raw",
    "信息_obuid",
    "信息_bus_code",
    "信息_number_plate",
    "信息_organ_id",
    "信息_organ_name",
    "信息_route_name",
    "信息_vehicle_type",
    "信息_bus_type",
    "信息_fuel_type",
]

CAN_SOURCE_MAP = {
    "车辆设备_电池最大电压": ["can_D30_max", "D30_max", "maxD30"],
    "车辆设备_电池最低电压": ["can_D31_min", "D31_min", "minD31"],
    "车辆设备_电池最高电流": ["can_D29_max", "D29_max", "maxD29"],
    "车辆设备_电池最小电流": ["can_D29_min", "D29_min", "minD29"],
    "车辆设备_电池最高温度": ["can_D34_max", "D34_max", "maxD34"],
    "车辆设备_电池最低温度": ["can_D35_min", "D35_min", "minD35"],
    "车辆设备_标准电压": ["can_standard_voltage"],
    "车辆设备_标准电流": ["can_standard_current"],
}

LEGACY_OUTPUT_ALIAS_MAP = {
    "信息_ppartition": "信息_统计日期",
    "信息_bus_id": "信息_车辆ID",
    "信息_number_plate": "信息_车牌号",
    "信息_organ_id": "信息_公司ID",
    "信息_organ_name": "信息_公司名称",
    "信息_route_id": "信息_线路ID",
    "信息_route_name": "信息_线路名称",
}



# raw 事件字段与聚合字段规格。顺序来自正式 EVENT_ZERO_FEATURES，后续如改字段清单需同步检查切片位置。
DETAIL_BEHAVIOR_FEATURES = EVENT_ZERO_FEATURES[:28]
DETAIL_REPAIR_FEATURES = EVENT_ZERO_FEATURES[28:42]
BEHAVIOR_AGG_OUTPUTS = EVENT_ZERO_FEATURES[42:52]
BEHAVIOR_AGG_WINDOW_OUTPUTS = EVENT_ZERO_FEATURES[52:62]
REPAIR_AGG_OUTPUTS = EVENT_ZERO_FEATURES[62:69]
REPORT_TYPE_TO_DETAIL = [(f"report_type{i}_count", detail) for i, detail in enumerate(DETAIL_BEHAVIOR_FEATURES, start=1)]
RAW_BEHAVIOR_TO_DETAIL = []

BEHAVIOR_AGG_SPECS = {
    "behavior_cat_1": {"details": DETAIL_BEHAVIOR_FEATURES[0:5], "output": BEHAVIOR_AGG_OUTPUTS[0], "window_output": BEHAVIOR_AGG_WINDOW_OUTPUTS[0], "denominator": "mileage", "scale": 1000.0},
    "behavior_cat_2": {"details": DETAIL_BEHAVIOR_FEATURES[5:8], "output": BEHAVIOR_AGG_OUTPUTS[1], "window_output": BEHAVIOR_AGG_WINDOW_OUTPUTS[1], "denominator": "mileage", "scale": 1000.0},
    "behavior_cat_3": {"details": DETAIL_BEHAVIOR_FEATURES[8:10], "output": BEHAVIOR_AGG_OUTPUTS[2], "window_output": BEHAVIOR_AGG_WINDOW_OUTPUTS[2], "denominator": "mileage", "scale": 1000.0},
    "behavior_cat_4": {"details": DETAIL_BEHAVIOR_FEATURES[10:13], "output": BEHAVIOR_AGG_OUTPUTS[3], "window_output": BEHAVIOR_AGG_WINDOW_OUTPUTS[3], "denominator": "mileage", "scale": 1000.0},
    "behavior_cat_5": {"details": DETAIL_BEHAVIOR_FEATURES[13:15], "output": BEHAVIOR_AGG_OUTPUTS[4], "window_output": BEHAVIOR_AGG_WINDOW_OUTPUTS[4], "denominator": "mileage", "scale": 1000.0},
    "behavior_cat_6": {"details": DETAIL_BEHAVIOR_FEATURES[15:18], "output": BEHAVIOR_AGG_OUTPUTS[5], "window_output": BEHAVIOR_AGG_WINDOW_OUTPUTS[5], "denominator": "mileage", "scale": 1000.0},
    "behavior_cat_7": {"details": DETAIL_BEHAVIOR_FEATURES[18:21], "output": BEHAVIOR_AGG_OUTPUTS[6], "window_output": BEHAVIOR_AGG_WINDOW_OUTPUTS[6], "denominator": "station", "scale": 100.0},
    "behavior_cat_8": {"details": DETAIL_BEHAVIOR_FEATURES[21:24], "output": BEHAVIOR_AGG_OUTPUTS[7], "window_output": BEHAVIOR_AGG_WINDOW_OUTPUTS[7], "denominator": "turn", "scale": 100.0},
    "behavior_cat_9": {"details": DETAIL_BEHAVIOR_FEATURES[24:28], "output": BEHAVIOR_AGG_OUTPUTS[8], "window_output": BEHAVIOR_AGG_WINDOW_OUTPUTS[8], "denominator": "mileage", "scale": 1.0},
}

_RAW_REPAIR_FIELDS = EVENT_ZERO_FEATURES[106:120]
RAW_REPAIR_TO_DETAIL = list(zip(_RAW_REPAIR_FIELDS, DETAIL_REPAIR_FEATURES))
RAW_EVENT_COUNT_FIELDS = EVENT_ZERO_FEATURES[78:]
_REPAIR_AGG_NAMES = [col.split("_", 1)[1][4:] for col in REPAIR_AGG_OUTPUTS]
REPAIR_AGG_SPECS = {
    _REPAIR_AGG_NAMES[0]: [DETAIL_REPAIR_FEATURES[i] for i in [1, 6, 3, 13]],
    _REPAIR_AGG_NAMES[3]: [DETAIL_REPAIR_FEATURES[i] for i in [1, 6, 3, 13, 4, 5, 12]],
    _REPAIR_AGG_NAMES[4]: [DETAIL_REPAIR_FEATURES[i] for i in [7, 8]],
    _REPAIR_AGG_NAMES[5]: [DETAIL_REPAIR_FEATURES[i] for i in [10, 11, 12]],
    _REPAIR_AGG_NAMES[6]: [DETAIL_REPAIR_FEATURES[i] for i in [1, 6, 3, 13, 4, 5, 12]],
}

ENERGY_DIAGNOSIS_FIELDS = [
    "信息_车辆百公里能耗",
    "车辆运营_运营里程",
    "车辆运营_运营时长",
    "信息_同线路其他车辆数",
    "信息_同线路LOO百公里能耗均值",
    "信息_同线路百公里能耗偏离倍数",
    "type_other_n",
    "type_other_mean",
    "type_other_deviation_rate",
    "type_confidence_level",
    "type_low_confidence_reason",
    LABEL_CONFIG["energy_target_col"],
    "energy_diagnosis_score",
]
FAULT_LABEL_FIELDS = [
    "故障_当日总次数",
    "信息_故障当日总次数原始值",
    LABEL_CONFIG["fault_target_col"],
]

def _num(df: pd.DataFrame, col: str, default: float | None = None) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce")
    return pd.Series(default, index=df.index, dtype=float)


def _clean_key(s: pd.Series) -> pd.Series:
    return s.apply(clean_id).astype(str).replace({"nan": np.nan, "None": np.nan, "unknown": np.nan, "": np.nan})


def _safe_divide(numerator: pd.Series, denominator: pd.Series, scale: float = 1.0) -> pd.Series:
    num = pd.to_numeric(numerator, errors="coerce")
    den = pd.to_numeric(denominator, errors="coerce")
    return pd.Series(np.where(den > 0, num / den * scale, np.nan), index=numerator.index)


def _first_existing(df: pd.DataFrame, candidates: list[str]) -> str | None:
    return next((col for col in candidates if col in df.columns), None)


def _filter_dates(df: pd.DataFrame, date_col: str, start_date: str | None, end_date: str | None) -> pd.DataFrame:
    if df.empty or date_col not in df.columns:
        return df
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce").dt.normalize()
    mask = out[date_col].notna()
    if start_date:
        mask &= out[date_col] >= pd.to_datetime(start_date)
    if end_date:
        mask &= out[date_col] <= pd.to_datetime(end_date)
    return out.loc[mask].copy()


def _buffer_date(date_str: str | None, days: int, sign: int) -> str | None:
    if not date_str:
        return None
    return (pd.to_datetime(date_str) + timedelta(days=sign * days)).strftime("%Y-%m-%d")


def _normalize_source_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    rename = {
        "信息_统计日期": KEYS["date"],
        "统计日期": KEYS["date"],
        "ppartition": KEYS["date"],
        "raw_ppartition": "信息_ppartition_raw",
        "stat_date": KEYS["date"],
        "信息_车辆ID": KEYS["bus"],
        "车辆ID": KEYS["bus"],
        "bus_id": KEYS["bus"],
        "信息_线路ID": KEYS["route"],
        "route_id": KEYS["route"],
        "obuid": "信息_obuid",
        "bus_code": "信息_bus_code",
        "number_plate": "信息_number_plate",
        "organ_id": "信息_organ_id",
        "organ_name": "信息_organ_name",
        "route_name": "信息_route_name",
    }
    out = out.rename(columns={k: v for k, v in rename.items() if k in out.columns})
    out = out.loc[:, ~out.columns.duplicated()].copy()
    if KEYS["date"] not in out.columns or KEYS["bus"] not in out.columns:
        raise ValueError("源表缺少主键字段: 需要 信息_ppartition/信息_bus_id 或兼容别名")
    out[KEYS["date"]] = pd.to_datetime(out[KEYS["date"]], errors="coerce").dt.normalize()
    out[KEYS["bus"]] = _clean_key(out[KEYS["bus"]])
    if KEYS["route"] in out.columns:
        out[KEYS["route"]] = out[KEYS["route"]].astype("string").fillna("").str.strip()
    return out


def _apply_outliers(df: pd.DataFrame, rules: dict[str, tuple[float, float]]) -> pd.DataFrame:
    out = df.copy()
    for col, (lo, hi) in rules.items():
        if col not in out.columns:
            continue
        values = pd.to_numeric(out[col], errors="coerce")
        mask = values.notna() & ((values <= lo) | (values > hi))
        if mask.any():
            values.loc[mask] = np.nan
        out[col] = values
    return out

def _history_sum_before_date(
    frame: pd.DataFrame,
    group_cols: list[str],
    date_col: str,
    value_cols: list[str],
    window_days: int,
) -> pd.DataFrame:
    return (
        frame.sort_values([*group_cols, date_col])
        .set_index(date_col)
        .groupby(group_cols, sort=False)[value_cols]
        .rolling(f"{window_days}D", closed="left", min_periods=1)
        .sum()
        .reset_index()
    )


def _route_source_to_car_day(
    source: pd.DataFrame,
    outlier_rules: dict[str, tuple[float, float]],
    route_lookback_days: int,
) -> pd.DataFrame:
    df = _normalize_source_columns(source)
    date_col, bus_col, route_col = KEYS["date"], KEYS["bus"], KEYS["route"]
    for required in [route_col, SOURCE_COLUMNS["mileage"], SOURCE_COLUMNS["energy_per_100km"], SOURCE_COLUMNS["total_second"], SOURCE_COLUMNS["total_energy"]]:
        if required not in df.columns:
            logger.warning(f"tmp_vrp_00 缺少字段: {required}，后续按缺失处理")
            df[required] = np.nan
    if route_col not in df.columns:
        df[route_col] = ""

    df["车辆运营_运营里程"] = _num(df, SOURCE_COLUMNS["mileage"])
    df["信息_车辆百公里能耗"] = _num(df, SOURCE_COLUMNS["energy_per_100km"])
    df["指标_百公里能耗"] = df["信息_车辆百公里能耗"]
    df["车辆运营_运营时长"] = _num(df, SOURCE_COLUMNS["total_second"]) / 3600.0
    df["信息_当日总能耗"] = _num(df, SOURCE_COLUMNS["total_energy"])
    missing_energy = df["信息_车辆百公里能耗"].isna() & df["信息_当日总能耗"].notna() & (df["车辆运营_运营里程"] > 0)
    df.loc[missing_energy, "信息_车辆百公里能耗"] = (
        df.loc[missing_energy, "信息_当日总能耗"] / df.loc[missing_energy, "车辆运营_运营里程"] * 100.0
    )
    df["指标_百公里能耗"] = df["信息_车辆百公里能耗"]
    df = _apply_outliers(df, outlier_rules)

    valid = df.loc[
        (df["信息_车辆百公里能耗"] > 0) & df[route_col].ne(""),
        [date_col, bus_col, route_col, "信息_车辆百公里能耗"],
    ].copy()
    valid["_energy_sum"] = valid["信息_车辆百公里能耗"]
    valid["_sample_n"] = 1.0
    route_day = valid.groupby([route_col, date_col], as_index=False)[["_energy_sum", "_sample_n"]].sum()
    bus_route_day = valid.groupby([route_col, bus_col, date_col], as_index=False)[["_energy_sum", "_sample_n"]].sum()
    route_history = _history_sum_before_date(route_day, [route_col], date_col, ["_energy_sum", "_sample_n"], route_lookback_days).rename(
        columns={"_energy_sum": "_route_hist_sum", "_sample_n": "_route_hist_n"}
    )
    self_history = _history_sum_before_date(bus_route_day, [route_col, bus_col], date_col, ["_energy_sum", "_sample_n"], route_lookback_days).rename(
        columns={"_energy_sum": "_self_hist_sum", "_sample_n": "_self_hist_n"}
    )
    df = df.merge(route_history, on=[route_col, date_col], how="left")
    df = df.merge(self_history, on=[route_col, bus_col, date_col], how="left")
    # 线路基准仅使用过去30日，并剔除目标车辆历史观测，避免当天信息和本车惯性泄漏到标签。
    df["信息_同线路其他车辆数"] = df["_route_hist_n"].fillna(0) - df["_self_hist_n"].fillna(0)
    route_other_sum = df["_route_hist_sum"].fillna(0) - df["_self_hist_sum"].fillna(0)
    df["信息_同线路LOO百公里能耗均值"] = np.where(
        df["信息_同线路其他车辆数"] > 0,
        route_other_sum / df["信息_同线路其他车辆数"],
        np.nan,
    )

    df["_估算能耗"] = df["信息_车辆百公里能耗"] * df["车辆运营_运营里程"] / 100.0
    df["_route_loo_weighted"] = df["信息_同线路LOO百公里能耗均值"] * df["车辆运营_运营里程"]

    info_cols = [c for c in INFO_COLUMNS if c in df.columns]
    protected = {
        date_col,
        bus_col,
        route_col,
        SOURCE_COLUMNS["mileage"],
        SOURCE_COLUMNS["energy_per_100km"],
        SOURCE_COLUMNS["total_energy"],
        SOURCE_COLUMNS["total_second"],
        "_route_hist_sum",
        "_route_hist_n",
        "_self_hist_sum",
        "_self_hist_n",
        "_估算能耗",
        "_route_loo_weighted",
    }
    generated = {
        "车辆运营_运营里程",
        "信息_车辆百公里能耗",
        "指标_百公里能耗",
        "车辆运营_运营时长",
        "信息_当日总能耗",
        "信息_同线路其他车辆数",
        "信息_同线路LOO百公里能耗均值",
    }
    aux_cols = [c for c in df.columns if c not in protected | generated | set(info_cols)]
    max_aux_cols = [c for c in aux_cols if c in RAW_EVENT_COUNT_FIELDS or c.startswith("report_type")]
    first_aux_cols = [c for c in aux_cols if c not in set(max_aux_cols)]
    for col in max_aux_cols:
        df[col] = _num(df, col, 0).fillna(0)

    agg = {
        "信息_route_id": (route_col, lambda x: "、".join(sorted(set(x.dropna().astype(str))))),
        "信息_线路ID": (route_col, lambda x: "、".join(sorted(set(x.dropna().astype(str))))),
        "信息_同线路其他车辆数": ("信息_同线路其他车辆数", "min"),
        "车辆运营_运营里程": ("车辆运营_运营里程", "sum"),
        "车辆运营_运营时长": ("车辆运营_运营时长", "sum"),
        "信息_当日总能耗": ("信息_当日总能耗", "sum"),
        "_估算能耗": ("_估算能耗", "sum"),
        "_route_loo_weighted": ("_route_loo_weighted", "sum"),
    }
    base = df.groupby([date_col, bus_col], as_index=False).agg(**agg)
    if info_cols:
        base = base.merge(df.groupby([date_col, bus_col], as_index=False)[info_cols].first(), on=[date_col, bus_col], how="left")
    if first_aux_cols:
        base = base.merge(df.groupby([date_col, bus_col], as_index=False)[first_aux_cols].first(), on=[date_col, bus_col], how="left")
    if max_aux_cols:
        base = base.merge(df.groupby([date_col, bus_col], as_index=False)[max_aux_cols].max(), on=[date_col, bus_col], how="left")
    profile = {
        "tmp_vrp_00原始行数": int(len(source)),
        "energy_route_day_frame行数": int(len(df.drop_duplicates([date_col, bus_col, route_col]))),
        "fault_bus_day_frame去重前行数": int(len(df)),
        "fault_bus_day_frame去重后行数": int(len(base)),
        "stat_date_bus_id重复行数": int(max(len(df) - len(base), 0)),
    }

    base["信息_车辆百公里能耗"] = np.where(
        base["车辆运营_运营里程"] > 0,
        base["_估算能耗"] / base["车辆运营_运营里程"] * 100.0,
        np.nan,
    )
    base["指标_百公里能耗"] = base["信息_车辆百公里能耗"]
    base["信息_同线路LOO百公里能耗均值"] = np.where(
        base["车辆运营_运营里程"] > 0,
        base["_route_loo_weighted"] / base["车辆运营_运营里程"],
        np.nan,
    )
    base = base.drop(columns=["_估算能耗", "_route_loo_weighted"])
    base.attrs["source_profile"] = profile
    return _derive_base_features(base)


def _derive_base_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    mileage = _num(out, "车辆运营_运营里程")
    hours = _num(out, "车辆运营_运营时长")
    out["车辆运营_平均速度"] = _safe_divide(mileage, hours)
    out["车辆运营_拥堵指数"] = _safe_divide(hours, mileage)
    out["行驶路况_拥堵指数"] = out["车辆运营_拥堵指数"]

    simple_map = {
        "static_total_weight": "车辆属性_车辆自重",
        "static_bus_length": "车辆属性_车长",
        "static_bus_brand": "车辆属性_车辆品牌",
        "static_bus_type": "车辆属性_车辆类型",
        "static_bus_age": "车辆属性_车龄",
        "static_battery_capacity": "车辆属性_电池容量",
        "total_open_time": "车辆设备_空气压缩机开启时长",
        "aircond_open_time_minutes": "车辆设备_空气压缩机开启时长",
        "record_count": "车辆设备_空气压缩机开关次数",
        "aircond_record_count": "车辆设备_空气压缩机开关次数",
        "route_passenger_flow": "行驶路况_线路客流量",
        "line_passenger_flow": "行驶路况_线路客流量",
        "passenger_flow": "行驶路况_线路客流量",
        "passenger_count": "行驶路况_线路客流量",
        "passenger_total": "行驶路况_线路客流量",
        "route_black_count": "行驶路况_线路黑点数",
        "route_trip_count": "行驶路况_线路班次数",
        "route_cnt": "行驶路况_线路数",
        "station_missing_route_cnt": "行驶路况_站点缺失线路数",
        "black_missing_route_cnt": "行驶路况_黑点缺失线路数",
        "denom_station_count": "行驶路况_站点数",
        "denom_turn_count": "行驶路况_转弯数",
        "线路客流量": "行驶路况_线路客流量",
        "线路客流": "行驶路况_线路客流量",
        "行驶路况_线路黑点数": "行驶路况_线路黑点数",
        "fault_total_count": "故障_当日总次数",
        "fault_total_count_raw": "信息_故障当日总次数原始值",
        "repair_order_count": "车辆维修_当日维修工单数",
    }
    for src, dst in simple_map.items():
        if src in out.columns and dst not in out.columns:
            out[dst] = out[src]
    if "车辆维修_当日维修工单数" in out.columns:
        out["车辆维修_维修工单数"] = _num(out, "车辆维修_当日维修工单数", 0).fillna(0).clip(lower=0)

    # if "static_bus_brand_name" in out.columns:
    #     out["车辆属性_车辆品牌名称"] = out["static_bus_brand_name"].astype("string").fillna("").str.strip()
    # else:
    #     out["车辆属性_车辆品牌名称"] = out.get("车辆属性_车辆品牌", pd.Series("", index=out.index)).astype("string").fillna("").str.strip()
# ===== BRAND_NAME_FIX_START: 业务版车辆品牌名称稳健兜底 =====
    # static_bus_brand_name 可能存在但为空；此时继续回退到 static_bus_brand / 车辆属性_车辆品牌
    brand_name = pd.Series("", index=out.index, dtype="string")

    for col in ["static_bus_brand_name", "static_bus_brand", "车辆属性_车辆品牌"]:
        if col in out.columns:
            candidate = out[col].astype("string").fillna("").str.strip()
            brand_name = brand_name.mask(brand_name.eq(""), candidate)

    out["车辆属性_车辆品牌名称"] = brand_name

    # 确保后续 modeling.py 可以找到 BRAND_FEATURE，再用品牌名称重新覆盖为普通编号
    if "车辆属性_车辆品牌" not in out.columns:
        out["车辆属性_车辆品牌"] = out["车辆属性_车辆品牌名称"]
# ===== BRAND_NAME_FIX_END =====

    if "车辆属性_车辆类型" in out.columns:
        out["车辆属性_车辆类型"] = out["车辆属性_车辆类型"].astype("string").fillna("").str.strip()

    for col in ["车辆属性_车辆自重", "车辆属性_车长", "车辆属性_车辆品牌", "车辆属性_车龄", "车辆属性_电池容量"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    for dst, candidates in CAN_SOURCE_MAP.items():
        source = _first_existing(out, candidates)
        if source is not None:
            out[dst] = _num(out, source)
    out["车辆设备_电池最大电压差"] = (_num(out, "车辆设备_电池最大电压") - _num(out, "车辆设备_电池最低电压")).abs()
    out["车辆设备_电池最大电流差"] = (_num(out, "车辆设备_电池最高电流") - _num(out, "车辆设备_电池最小电流")).abs()

    station_col = _first_existing(out, ["denom_station_count", "车辆运营_线路站点数", "线路站点数"])
    turn_col = _first_existing(out, ["denom_turn_count", "车辆运营_线路转弯点数", "线路转弯点数"])
    if station_col:
        out["行驶路况_线路站点密度"] = _safe_divide(_num(out, station_col), mileage)
    if turn_col:
        out["行驶路况_转弯密度"] = _safe_divide(_num(out, turn_col), mileage)
    if "行驶路况_线路黑点数" in out.columns:
        out["行驶路况_线路黑点密度"] = _safe_divide(_num(out, "行驶路况_线路黑点数"), mileage)
    if "行驶路况_线路客流量" in out.columns:
        out["行驶路况_线路客流量密度"] = _safe_divide(_num(out, "行驶路况_线路客流量"), mileage)

    day_charge_count = _num(out, "day_charge_count", 0).fillna(0) + _num(out, "night_charge_count", 0).fillna(0)
    day_charge_soc = _num(out, "day_charge_soc", 0).fillna(0) + _num(out, "night_charge_soc", 0).fillna(0)
    out["车辆设备_日充电次数"] = day_charge_count
    out["车辆设备_日充电SOC"] = day_charge_soc
    out["车辆设备_百公里充电次数"] = _safe_divide(day_charge_count, mileage, 100.0)
    out["车辆设备_百公里充电SOC"] = _safe_divide(day_charge_soc, mileage, 100.0)
    out["车辆设备_百公里空气压缩机开启时长"] = _safe_divide(_num(out, "车辆设备_空气压缩机开启时长"), mileage, 100.0)
    out["车辆设备_百公里空气压缩机开关次数"] = _safe_divide(_num(out, "车辆设备_空气压缩机开关次数"), mileage, 100.0)
    out["车辆设备_空调开启时长占比"] = _safe_divide(_num(out, "车辆设备_空气压缩机开启时长"), hours)
    return out

def _merge_behavior(df: pd.DataFrame, start_date: str | None, end_date: str | None) -> pd.DataFrame:
    out = df.copy()
    # 驾驶行为直接来自完整 raw 宽表的 report_type*_count 字段，正式流程不再读取侧表。

    for raw, detail in RAW_BEHAVIOR_TO_DETAIL:
        out[detail] = _num(out, raw, 0).fillna(0).clip(lower=0)
    for raw, detail in REPORT_TYPE_TO_DETAIL:
        if raw in out.columns:
            out[detail] = _num(out, raw, 0).fillna(0).clip(lower=0)
    mileage = _num(out, "车辆运营_运营里程")
    station = _num(out, "denom_station_count")
    turn = _num(out, "denom_turn_count")
    positive_type_flags = []
    for _, spec in BEHAVIOR_AGG_SPECS.items():
        raw_count = sum((_num(out, col, 0).fillna(0).clip(lower=0) for col in spec["details"]), start=pd.Series(0.0, index=out.index))
        out[f"_行为聚合次数_{spec['output']}"] = raw_count
        denom = mileage if spec["denominator"] == "mileage" else (station if spec["denominator"] == "station" else turn)
        out[spec["output"]] = _safe_divide(raw_count, denom, spec["scale"])
        positive_type_flags.append(raw_count > 0)
    out["驾驶不良行为_违规类型数"] = pd.concat(positive_type_flags, axis=1).sum(axis=1) if positive_type_flags else 0
    return out


def _add_energy_label(df: pd.DataFrame, label_cfg: dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    date_col = KEYS["date"]
    energy = _num(out, "信息_车辆百公里能耗")
    bus_type = out.get("车辆属性_车辆类型", pd.Series("", index=out.index)).astype("string").fillna("").str.strip()
    out["车辆属性_车辆类型"] = bus_type
    valid_type = out[energy.notna() & (energy > 0) & bus_type.ne("")].copy()
    type_stats = valid_type.groupby([date_col, "车辆属性_车辆类型"])["信息_车辆百公里能耗"].agg(["sum", "count"]).rename(columns={"sum": "_type_sum", "count": "_type_n"})
    out = out.merge(type_stats, on=[date_col, "车辆属性_车辆类型"], how="left")
    out["信息_同车型其他车辆数"] = pd.to_numeric(out["_type_n"], errors="coerce") - 1
    out["信息_同车型LOO百公里能耗均值"] = np.where(
        out["信息_同车型其他车辆数"] > 0,
        (out["_type_sum"] - out["信息_车辆百公里能耗"]) / out["信息_同车型其他车辆数"],
        np.nan,
    )
    out = out.drop(columns=[c for c in ["_type_sum", "_type_n"] if c in out.columns])
    for deprecated_col in [
        "信息_同车长其他车辆数",
        "信息_同车长LOO百公里能耗均值",
        "信息_同车长百公里能耗偏离倍数",
        "标签_是否大于同车长阈值",
    ]:
        if deprecated_col not in out.columns:
            out[deprecated_col] = np.nan

    route_ratio = float(label_cfg["energy_route_ratio"])
    type_ratio = float(label_cfg["energy_type_ratio"])
    min_other = int(label_cfg["energy_loo_min_other_n"])
    threshold = float(label_cfg["energy_high_risk_threshold"])
    route_base = _num(out, "信息_同线路LOO百公里能耗均值")
    type_base = _num(out, "信息_同车型LOO百公里能耗均值")
    route_n = _num(out, "信息_同线路其他车辆数").fillna(0)
    type_n = _num(out, "信息_同车型其他车辆数").fillna(0)

    out["信息_同线路百公里能耗偏离倍数"] = np.where(route_base > 0, energy / route_base, np.nan)
    out["信息_同车型百公里能耗偏离倍数"] = np.where(type_base > 0, energy / type_base, np.nan)
    out["type_other_n"] = type_n
    out["type_other_mean"] = out["信息_同车型LOO百公里能耗均值"]
    out["type_other_deviation_rate"] = out["信息_同车型百公里能耗偏离倍数"]
    low_route = route_n < min_other
    low_type = type_n < min_other
    out["能耗标签置信等级"] = np.where(low_route | low_type, "low", "high")
    out["type_confidence_level"] = np.where(low_type, "low", "high")
    out["type_low_confidence_reason"] = np.where(low_type, "同车型其他车辆数不足", "")
    out["低置信原因"] = np.select(
        [low_route & low_type, low_route, low_type],
        ["过去30日同线路其他样本和当天同车型其他车辆数不足", "过去30日同线路其他样本数不足", "当天同车型其他车辆数不足"],
        default="",
    )
    out["标签_是否大于同线路阈值"] = (energy > route_base * route_ratio) & (route_base > 0)
    out["标签_是否大于同车型阈值"] = (energy > type_base * type_ratio) & (type_base > 0)
    high_conf = out["能耗标签置信等级"].eq("high")
    out[label_cfg["energy_target_col"]] = (high_conf & out["标签_是否大于同线路阈值"] & out["标签_是否大于同车型阈值"]).astype(int)

    # route_dev = out["信息_同线路百公里能耗偏离倍数"] - 1.0
    # type_dev = out["信息_同车型百公里能耗偏离倍数"] - 1.0
    # route_excess = (route_dev - (route_ratio - 1.0)).clip(lower=0)
    # type_excess = (type_dev - (type_ratio - 1.0)).clip(lower=0)
    # combined_excess = pd.concat([route_excess, type_excess], axis=1).max(axis=1)
    # base_dev = pd.concat([route_dev.clip(lower=0), type_dev.clip(lower=0)], axis=1).max(axis=1).fillna(0)
    # score = np.where(
    #     out[label_cfg["energy_target_col"]].eq(1),
    #     np.clip(65.0 + combined_excess.fillna(0) * 200.0, 65.0, 100.0),
    #     np.clip(base_dev * 65.0, 0.0, 64.0),
    # )
    # out["energy_diagnosis_score"] = pd.Series(score, index=out.index).where(high_conf, np.nan)
    # ===== ENERGY_SCORE_PATCH_START: 基于高能耗标准线的正负偏离程度计算能耗诊断分 =====
    # 以“高能耗标准线”为基准计算偏离程度：
    # route_margin > 0 表示超过 同线路LOO均值 × route_ratio
    # type_margin  > 0 表示超过 同车型LOO均值 × type_ratio
    route_margin = out["信息_同线路百公里能耗偏离倍数"] / route_ratio - 1.0
    type_margin = out["信息_同车型百公里能耗偏离倍数"] / type_ratio - 1.0

    # 高能耗要求两个标准都超过，因此综合偏离取较弱项
    combined_margin = pd.concat([route_margin, type_margin], axis=1).min(axis=1)

    # ===== BUSINESS_SCORE_PATCH_START: 允许能耗低风险车辆最低得0分 =====
    low_score_min = 0.0
    low_score_max = 64.0
    # ===== BUSINESS_SCORE_PATCH_END =====

    # 低分段采用稳健分位数锚点，避免单个极端低能耗车辆影响整体分布
    # 含义：负向偏离最低的约5%车辆接近 0 分，接近高能耗标准线的车辆接近 64 分
    low_anchor_quantile = 0.05

    negative_margin = combined_margin.where(high_conf & combined_margin.lt(0)).dropna()

    if len(negative_margin) > 0:
        low_anchor = float(negative_margin.quantile(low_anchor_quantile))

        # 极端情况下，如果5%分位数无效或太接近0，则退回最小负向偏离
        if not np.isfinite(low_anchor) or low_anchor >= -1e-12:
            low_anchor = float(negative_margin.min())
    else:
        low_anchor = np.nan

    if pd.notna(low_anchor) and low_anchor < 0:
        # progress 越接近 1，说明越接近高能耗标准线，风险分越高
        progress = ((combined_margin - low_anchor) / (0.0 - low_anchor)).clip(0.0, 1.0)

        # ===== BUSINESS_SCORE_PATCH_START: 平滑65分以下分布，减少50~64分集中 =====
        # gamma > 1：让低风险车辆分数更保守，只有接近标准线时才明显升高
        low_score_gamma = 1.8
        low_score = low_score_min + (progress ** low_score_gamma) * (low_score_max - low_score_min)
        # ===== BUSINESS_SCORE_PATCH_END =====
    else:
        low_score = pd.Series(low_score_max, index=out.index)
    # 超过标准线后，从 65 分开始，根据超过程度继续加分
    high_score = 65.0 + combined_margin.clip(lower=0).fillna(0) * 200.0

    score = np.where(
        out[label_cfg["energy_target_col"]].eq(1),
        np.clip(high_score, 65.0, 100.0),
        np.clip(low_score, low_score_min, 64.0),
    )

    out["energy_diagnosis_score"] = pd.Series(score, index=out.index).where(high_conf, np.nan)
    # ===== ENERGY_SCORE_PATCH_END =====    
    
    
    out["是否能耗高风险"] = (out["energy_diagnosis_score"] >= threshold).fillna(False).astype(int)
    return out


def _add_future_fault_label(df: pd.DataFrame, label_cfg: dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    target = str(label_cfg["fault_target_col"])
    source_col = next((col for col in label_cfg.get("fault_source_candidates", []) if col in out.columns), None)
    if source_col is None:
        out[target] = np.nan
        logger.warning("宽表缺少当日故障次数字段，故障标签置为NaN")
        return out
    n_days = int(label_cfg.get("fault_future_days", 7))
    out[KEYS["date"]] = pd.to_datetime(out[KEYS["date"]], errors="coerce").dt.normalize()
    out[KEYS["bus"]] = _clean_key(out[KEYS["bus"]])
    out = out.sort_values([KEYS["bus"], KEYS["date"]]).copy()
    max_available_date = out[KEYS["date"]].max()
    fault_day = out[[KEYS["bus"], KEYS["date"]]].copy()
    fault_day["_fault"] = pd.to_numeric(out[source_col], errors="coerce").fillna(0)
    fault_dates = fault_day.loc[fault_day["_fault"] > 0, [KEYS["bus"], KEYS["date"]]].drop_duplicates()
    if fault_dates.empty:
        out[target] = 0.0
    else:
        hit_days = pd.concat(
            [
                fault_dates.assign(**{KEYS["date"]: fault_dates[KEYS["date"]] - pd.Timedelta(days=step)})
                for step in range(1, n_days + 1)
            ],
            ignore_index=True,
        ).drop_duplicates()
        hit_index = pd.MultiIndex.from_frame(hit_days[[KEYS["bus"], KEYS["date"]]])
        out[target] = pd.MultiIndex.from_frame(out[[KEYS["bus"], KEYS["date"]]]).isin(hit_index).astype(float)
    immature = out[KEYS["date"]].notna() & (out[KEYS["date"]] + pd.Timedelta(days=n_days) > max_available_date)
    if immature.any():
        out.loc[immature, target] = np.nan
        logger.warning(
            f"[未来故障标签] 源数据最大日期={max_available_date.date()}，"
            f"{int(immature.sum())} 条样本未来{n_days}天标签未成熟，置为NaN并由训练质量过滤"
        )
    out["信息_未来故障观察窗口"] = f"未来第1天至第{n_days}天以内"
    out["信息_未来窗口是否故障"] = out[target]
    out["信息_未来故障标签列"] = target
    return out


def _rolling_excluding_today(df: pd.DataFrame, columns: list[str], window: int, agg: str) -> pd.DataFrame:
    requested = list(dict.fromkeys(columns))
    present = [col for col in requested if col in df.columns]
    result = pd.DataFrame(np.nan, index=df.index, columns=requested)
    if not present:
        return result
    values = df[present].apply(pd.to_numeric, errors="coerce")
    shifted = values.groupby(df[KEYS["bus"]], sort=False).shift(1)
    grouped = shifted.groupby(df[KEYS["bus"]], sort=False).rolling(window, min_periods=1)
    rolled = getattr(grouped, agg)().reset_index(level=0, drop=True).reindex(df.index)
    result[present] = rolled[present]
    return result


def _add_fault_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values([KEYS["bus"], KEYS["date"]]).copy()
    window = int(WINDOW_CONFIG.get("fault_rolling_days", 30))
    for col in EVENT_ZERO_FEATURES:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    repair_sources = DETAIL_REPAIR_FEATURES + ["车辆维修_维修工单数"]
    sum_sources = [
        "车辆运营_运营里程",
        "车辆运营_运营时长",
        "车辆设备_空气压缩机开启时长",
        "车辆设备_空气压缩机开关次数",
        "车辆设备_日充电次数",
        "车辆设备_日充电SOC",
        *repair_sources,
    ]
    mean_map = {
        "行驶路况_线路黑点密度": "行驶路况_近30日线路黑点密度",
        "行驶路况_线路客流量密度": "行驶路况_近30日线路客流量密度",
        "行驶路况_线路站点密度": "行驶路况_近30日线路站点密度",
        "行驶路况_转弯密度": "行驶路况_近30日转弯密度",
        "车辆设备_电池最大电压差": "车辆设备_近30日电池最大电压差均值",
        "车辆设备_电池最大电压": "车辆设备_近30日电池最大电压均值",
        "车辆设备_电池最高温度": "车辆设备_近30日电池最高温度均值",
        "车辆设备_电池最大电流差": "车辆设备_近30日电池最大电流差均值",
        "车辆设备_电池最高电流": "车辆设备_近30日电池最高电流均值",
    }
    sum30 = _rolling_excluding_today(out, sum_sources, window, "sum")
    mean30 = _rolling_excluding_today(out, list(mean_map), window, "mean")
    max30 = _rolling_excluding_today(out, ["车辆设备_电池最高温度"], window, "max")

    out["车辆运营_近30日运营里程累计"] = sum30["车辆运营_运营里程"]
    out["车辆运营_近30日运营时长累计"] = sum30["车辆运营_运营时长"]
    out["车辆运营_近30日平均速度"] = _safe_divide(out["车辆运营_近30日运营里程累计"], out["车辆运营_近30日运营时长累计"])
    out["车辆运营_近30日拥堵指数"] = _safe_divide(out["车辆运营_近30日运营时长累计"], out["车辆运营_近30日运营里程累计"])
    out[list(mean_map.values())] = mean30[list(mean_map)].to_numpy()
    out["车辆设备_近30日电池最高温度最大值"] = max30["车辆设备_电池最高温度"]

    ac_duration30 = sum30["车辆设备_空气压缩机开启时长"]
    out["车辆设备_近30日空调开启时长占比"] = _safe_divide(ac_duration30, out["车辆运营_近30日运营时长累计"])
    out["车辆设备_近30日百公里空气压缩机开启时长"] = _safe_divide(ac_duration30, out["车辆运营_近30日运营里程累计"], 100.0)
    out["车辆设备_近30日百公里空气压缩机开关次数"] = _safe_divide(sum30["车辆设备_空气压缩机开关次数"], out["车辆运营_近30日运营里程累计"], 100.0)
    out["车辆设备_近30日百公里充电次数"] = _safe_divide(sum30["车辆设备_日充电次数"], out["车辆运营_近30日运营里程累计"], 100.0)
    out["车辆设备_近30日百公里充电SOC"] = _safe_divide(sum30["车辆设备_日充电SOC"], out["车辆运营_近30日运营里程累计"], 100.0)

    repair30 = sum30[repair_sources].fillna(0)
    for name, details in REPAIR_AGG_SPECS.items():
        out[f"车辆维修_近30日{name}"] = repair30[details].sum(axis=1)
    detail_type_count = (repair30[DETAIL_REPAIR_FEATURES] > 0).sum(axis=1)
    order_count = repair30["车辆维修_维修工单数"]
    out["车辆维修_近30日维修故障类型数"] = (order_count > 0).astype(int) + detail_type_count
    out["车辆维修_近30日维修故障总次数"] = order_count + repair30[DETAIL_REPAIR_FEATURES].sum(axis=1)
    return out


def _drop_non_model_source_columns(df: pd.DataFrame) -> pd.DataFrame:
    keep = set(MODEL_FEATURE_ALLOWLIST + ENERGY_DIAGNOSIS_FIELDS + FAULT_LABEL_FIELDS + QUALITY_FIELDS)
    keep.update([KEYS["date"], KEYS["bus"], KEYS["route"], "信息_统计日期", "信息_车辆ID", "信息_车牌号", "信息_公司ID", "信息_公司名称", "信息_线路ID", "信息_route_id", "信息_vehicle_type", "信息_bus_type", "信息_fuel_type", "车辆属性_车辆品牌名称", "车辆属性_车辆类型"])
    cols = [c for c in df.columns if c in keep]
    return df[cols].copy()


def _apply_legacy_output_aliases(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for src, dst in LEGACY_OUTPUT_ALIAS_MAP.items():
        if src in out.columns and dst not in out.columns:
            out[dst] = out[src]
    if "信息_车辆ID" in out.columns:
        out["信息_车辆ID"] = _clean_key(out["信息_车辆ID"])
    if "信息_统计日期" in out.columns:
        out["信息_统计日期"] = pd.to_datetime(out["信息_统计日期"], errors="coerce").dt.strftime("%Y-%m-%d")
    return out


def _ensure_model_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for feature in MODEL_FEATURE_ALLOWLIST:
        if feature not in out.columns:
            out[feature] = 0.0 if feature in EVENT_ZERO_FEATURES else np.nan
        out[feature] = pd.to_numeric(out[feature], errors="coerce")
        if feature in EVENT_ZERO_FEATURES:
            out[feature] = out[feature].fillna(0.0)
    return out


async def required_source_window(
    start_date: str,
    end_date: str,
    *,
    for_training: bool,
) -> tuple[str, str]:
    """返回构建特征所需的原始数据窗口。"""
    if not start_date or not end_date:
        raise ValueError("必须提供 start_date 和 end_date")
    energy_route_lookback = int(LABEL_CONFIG.get("energy_route_lookback_days", WINDOW_CONFIG.get("energy_route_lookback_days", 30)))
    lookback = max(int(WINDOW_CONFIG.get("source_lookback_days", 30)), energy_route_lookback)
    future_days = int(LABEL_CONFIG.get("fault_future_days", 7)) if for_training else 0
    source_start = _buffer_date(start_date, lookback, -1)
    source_end = _buffer_date(end_date, future_days, 1) if for_training else end_date
    return str(source_start), str(source_end)


async def build_feature_frames(
    source_df: pd.DataFrame,
    start_date: str,
    end_date: str,
    *,
    for_training: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """根据完整 raw 宽表构建正式特征；本函数不负责文件或数据库读取。"""
    source_start, source_end = await required_source_window(start_date, end_date, for_training=for_training)
    energy_route_lookback = int(LABEL_CONFIG.get("energy_route_lookback_days", WINDOW_CONFIG.get("energy_route_lookback_days", 30)))
    include_future_fault = bool(for_training)
    src = source_df.copy()
    if src.empty:
        raise ValueError("原始 raw 宽表为空")
    src = _filter_dates(_normalize_source_columns(src), KEYS["date"], source_start, source_end)
    raw_df = _route_source_to_car_day(src, OUTLIER_RULES, energy_route_lookback)
    source_profile = dict(raw_df.attrs.get("source_profile", {}))
    raw_df = _merge_behavior(raw_df, source_start, source_end)

    for col in DETAIL_REPAIR_FEATURES + ["车辆维修_维修工单数", "故障_当日总次数", "信息_故障当日总次数原始值"]:
        if col in raw_df.columns:
            raw_df[col] = pd.to_numeric(raw_df[col], errors="coerce").fillna(0).clip(lower=0)
        else:
            raw_df[col] = 0.0
    if "故障_当日总次数" not in raw_df.columns or raw_df["故障_当日总次数"].sum() == 0:
        raw_df["故障_当日总次数"] = _num(raw_df, "信息_故障当日总次数原始值", 0).fillna(0).clip(lower=0)

    raw_df = _add_energy_label(raw_df, LABEL_CONFIG)
    if include_future_fault:
        raw_df = _add_future_fault_label(raw_df, LABEL_CONFIG)
    for raw_col, detail_col in RAW_REPAIR_TO_DETAIL:
        if raw_col in raw_df.columns:
            raw_df[detail_col] = _num(raw_df, raw_col, 0).fillna(0).clip(lower=0)
    raw_df = _add_fault_rolling_features(raw_df)
    raw_df = _filter_dates(raw_df, KEYS["date"], start_date, end_date)
    raw_df.attrs["source_profile"] = source_profile
    raw_df = _ensure_model_features(raw_df)
    raw_df = fill_event_missing_zero(raw_df)
    if for_training:
        return raw_df, pd.DataFrame(index=raw_df.index)

    energy_quality = build_quality_flags(raw_df, "energy", mode="score")
    fault_quality = build_quality_flags(raw_df, "fault", mode="score")
    raw_df["是否可训练"] = energy_quality["是否可训练"] & fault_quality["是否可训练"]
    raw_df["是否可评分"] = energy_quality["是否可评分"] | fault_quality["是否可评分"]
    raw_df["不可训练原因"] = (energy_quality["不可训练原因"].fillna("").astype(str) + ";" + fault_quality["不可训练原因"].fillna("").astype(str)).str.strip(";")
    raw_df["不可评分原因"] = (energy_quality["不可评分原因"].fillna("").astype(str) + ";" + fault_quality["不可评分原因"].fillna("").astype(str)).str.strip(";")
    raw_df["异常字段列表"] = (energy_quality["异常字段列表"].fillna("").astype(str) + ";" + fault_quality["异常字段列表"].fillna("").astype(str)).str.strip(";")

    raw_df[KEYS["date"]] = pd.to_datetime(raw_df[KEYS["date"]], errors="coerce").dt.strftime("%Y-%m-%d")
    raw_df = _apply_legacy_output_aliases(raw_df)
    model_df = _drop_non_model_source_columns(raw_df)
    model_df = _apply_legacy_output_aliases(model_df)
    return raw_df, model_df




