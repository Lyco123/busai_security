# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

import numpy as np
import pandas as pd

from model.vehicle.src.config import (
    DATA_QUALITY_CONFIG,
    EVENT_ZERO_FEATURES,
    IMPUTATION_GROUPS_BY_TASK,
    IMPUTATION_MIN_GROUP_COUNT,
    NORMALIZE_FALLBACK_VALUE,
    NORMALIZE_LOWER_Q,
    NORMALIZE_UPPER_Q,
    QUALITY_FIELDS,
)


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce")
    return pd.Series(np.nan, index=df.index, dtype=float)


def _text(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    for col in candidates:
        if col in df.columns:
            return df[col].astype("string").fillna("").str.strip()
    return pd.Series("", index=df.index, dtype="string")


def _has_value(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    return _text(df, candidates).ne("")


def _append_reason(reason_map: list[list[str]], mask: pd.Series, reason: str, abnormal_col: str | None = None, abnormal_map: list[list[str]] | None = None) -> None:
    idx = np.flatnonzero(mask.fillna(False).to_numpy())
    for i in idx:
        reason_map[i].append(reason)
        if abnormal_col and abnormal_map is not None:
            abnormal_map[i].append(abnormal_col)


def _join(values: list[list[str]]) -> list[str]:
    return [";".join(dict.fromkeys(items)) for items in values]


def fill_event_missing_zero(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in EVENT_ZERO_FEATURES:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
    return out


def build_quality_flags(df: pd.DataFrame, task_name: str, mode: str = "score") -> pd.DataFrame:
    if task_name not in {"energy", "fault"}:
        raise ValueError(f"unsupported task_name: {task_name}")
    if mode not in {"train", "score"}:
        raise ValueError(f"unsupported mode: {mode}")

    out = fill_event_missing_zero(df)
    train_reasons: list[list[str]] = [[] for _ in range(len(out))]
    score_reasons: list[list[str]] = [[] for _ in range(len(out))]
    abnormal: list[list[str]] = [[] for _ in range(len(out))]

    if task_name == "energy":
        energy = _num(out, "信息_车辆百公里能耗")
        mileage = _num(out, "车辆运营_运营里程")
        hours = _num(out, "车辆运营_运营时长")
        bus_type = _text(out, ["车辆属性_车辆类型", "static_bus_type"])
        route_ok = _has_value(out, ["信息_route_id", "route_id", "信息_线路ID"])
        target = _num(out, "Target_高能耗")
        confidence = _text(out, ["能耗标签置信等级"])

        checks = [
            (energy.isna(), "百公里能耗缺失", "信息_车辆百公里能耗"),
            (energy <= DATA_QUALITY_CONFIG["ENERGY_PER_100KM_MIN"], "百公里能耗<=0", "信息_车辆百公里能耗"),
            (energy > DATA_QUALITY_CONFIG["ENERGY_PER_100KM_MAX"], "百公里能耗>1000", "信息_车辆百公里能耗"),
            (mileage.isna(), "运营里程缺失", "车辆运营_运营里程"),
            (mileage <= DATA_QUALITY_CONFIG["RUN_MILEAGE_MIN"], "运营里程<=0", "车辆运营_运营里程"),
            (hours.isna(), "运营时长缺失", "车辆运营_运营时长"),
            (hours <= DATA_QUALITY_CONFIG["RUN_HOURS_MIN"], "运营时长<=0", "车辆运营_运营时长"),
            (~route_ok, "route_id为空", "信息_route_id"),
            (bus_type.eq(""), "车辆属性_车辆类型缺失", "车辆属性_车辆类型"),
            (confidence.str.lower().eq("low"), "能耗标签低置信", "能耗标签置信等级"),
        ]
        for mask, reason, col in checks:
            _append_reason(train_reasons, mask, reason, col, abnormal)
            _append_reason(score_reasons, mask, reason, col, abnormal)
        _append_reason(train_reasons, target.isna(), "Target_高能耗缺失", "Target_高能耗", abnormal)

    else:
        bus_ok = _has_value(out, ["信息_bus_id", "信息_车辆ID", "bus_id"])
        date_ok = pd.to_datetime(_text(out, ["信息_ppartition", "信息_统计日期", "stat_date"]), errors="coerce").notna()
        target = _num(out, "Target_未来7天以内故障")
        mileage30 = _num(out, "车辆运营_近30日运营里程累计")
        hours30 = _num(out, "车辆运营_近30日运营时长累计")

        checks = [
            (~bus_ok, "bus_id为空", "信息_bus_id"),
            (~date_ok, "统计日期为空", "信息_ppartition"),
            (mileage30.isna(), "近30日运营里程缺失", "车辆运营_近30日运营里程累计"),
            (mileage30 <= 0, "近30日运营里程<=0", "车辆运营_近30日运营里程累计"),
            (hours30.isna(), "近30日运营时长缺失", "车辆运营_近30日运营时长累计"),
            (hours30 <= 0, "近30日运营时长<=0", "车辆运营_近30日运营时长累计"),
        ]
        for mask, reason, col in checks:
            _append_reason(train_reasons, mask, reason, col, abnormal)
            _append_reason(score_reasons, mask, reason, col, abnormal)

        _append_reason(train_reasons, target.isna(), "Target_未来7天以内故障缺失", "Target_未来7天以内故障", abnormal)

    out["不可训练原因"] = _join(train_reasons)
    out["不可评分原因"] = _join(score_reasons)
    out["异常字段列表"] = _join(abnormal)
    out["是否可训练"] = out["不可训练原因"].eq("")
    out["是否可评分"] = out["不可评分原因"].eq("")

    for col in QUALITY_FIELDS:
        if col not in out.columns:
            out[col] = "" if "原因" in col or col == "异常字段列表" else False
    return out


# =============================================================================
# 缺失填充 fit/apply
# =============================================================================


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _key_frame(df: pd.DataFrame, fields: list[str]) -> pd.Series:
    if not fields:
        return pd.Series("", index=df.index, dtype="string")
    parts: list[pd.Series] = []
    for field in fields:
        if field in df.columns:
            parts.append(df[field].astype("string").fillna("__MISSING__").str.strip())
        else:
            parts.append(pd.Series("__MISSING__", index=df.index, dtype="string"))
    key = parts[0]
    for part in parts[1:]:
        key = key.str.cat(part, sep="|")
    return key


def _feature_type(feature: str) -> str:
    if feature in EVENT_ZERO_FEATURES or "次数" in feature or "故障" in feature or "工单" in feature:
        return "event_count"
    return "continuous"


def _groups_for_task(task_name: str) -> list[list[str]]:
    return IMPUTATION_GROUPS_BY_TASK.get(task_name, IMPUTATION_GROUPS_BY_TASK["default"])


def fit_imputation_statistics(
    df: pd.DataFrame,
    feature_names: Iterable[str],
    task_name: str,
    model_name: str,
    create_date: str,
    train_start: str,
    train_end: str,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    groups = _groups_for_task(task_name)
    group_keys: list[tuple[int, list[str], pd.Series]] = []
    for level, fields in enumerate(groups, start=1):
        valid_fields = [field for field in fields if field in df.columns]
        if valid_fields:
            group_keys.append((level, valid_fields, _key_frame(df, valid_fields)))
    for feature in feature_names:
        values = _to_numeric(df[feature]) if feature in df.columns else pd.Series(np.nan, index=df.index)
        feature_type = _feature_type(feature)
        global_median = 0.0 if feature_type == "event_count" else values.median()
        if pd.isna(global_median):
            global_median = 0.0
        frames.append(pd.DataFrame([
            {
                "模型名称": model_name,
                "task_name": task_name,
                "字段名": feature,
                "字段类型": feature_type,
                "填充策略": "event_fill_zero" if feature_type == "event_count" else "group_median",
                "group_level": "global",
                "分组字段": "",
                "分组值": "",
                "分组样本数": int(values.notna().sum()),
                "分组中位数": float(global_median),
                "一级分组字段": "",
                "一级分组值": "",
                "一级分组样本数": np.nan,
                "一级分组中位数": np.nan,
                "二级分组字段": "",
                "二级分组值": "",
                "二级分组样本数": np.nan,
                "二级分组中位数": np.nan,
                "全局中位数": float(global_median),
                "最终fallback策略": "global_median" if feature_type != "event_count" else "fill_zero",
                "create_date": create_date,
                "train_start": train_start,
                "train_end": train_end,
            }
        ]))
        if feature_type == "event_count":
            continue
        for level, valid_fields, key in group_keys:
            stat = pd.DataFrame({"_key": key, "_value": values}).dropna(subset=["_value"])
            if stat.empty:
                continue
            grouped = stat.groupby("_key")["_value"].agg(["count", "median"]).reset_index()
            grouped = grouped[grouped["count"] >= IMPUTATION_MIN_GROUP_COUNT]
            if grouped.empty:
                continue
            frame = pd.DataFrame({
                "模型名称": model_name,
                "task_name": task_name,
                "字段名": feature,
                "字段类型": feature_type,
                "填充策略": "group_median",
                "group_level": f"group_{level}",
                "分组字段": "+".join(valid_fields),
                "分组值": grouped["_key"].astype(str),
                "分组样本数": grouped["count"].astype(int),
                "分组中位数": grouped["median"].astype(float),
                "一级分组字段": "+".join(valid_fields) if level == 1 else "",
                "一级分组值": grouped["_key"].astype(str) if level == 1 else "",
                "一级分组样本数": grouped["count"].astype(int) if level == 1 else np.nan,
                "一级分组中位数": grouped["median"].astype(float) if level == 1 else np.nan,
                "二级分组字段": "+".join(valid_fields) if level == 2 else "",
                "二级分组值": grouped["_key"].astype(str) if level == 2 else "",
                "二级分组样本数": grouped["count"].astype(int) if level == 2 else np.nan,
                "二级分组中位数": grouped["median"].astype(float) if level == 2 else np.nan,
                "全局中位数": float(global_median),
                "最终fallback策略": f"group_{level}",
                "create_date": create_date,
                "train_start": train_start,
                "train_end": train_end,
            })
            frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def apply_imputation_statistics(
    df: pd.DataFrame,
    feature_names: Iterable[str],
    stats_df: pd.DataFrame,
    task_name: str,
    model_name: str,
) -> tuple[pd.DataFrame, dict[str, object], pd.DataFrame]:
    out = df.copy()
    detail_rows: list[dict[str, object]] = []
    total_missing = 0
    fill_counts = defaultdict(int)
    missing_by_field: dict[str, int] = {}
    task_stats = stats_df[stats_df["task_name"].astype(str).eq(task_name)].copy() if "task_name" in stats_df.columns else stats_df.copy()
    groups = _groups_for_task(task_name)
    group_specs = [
        (level, [field for field in fields if field in out.columns])
        for level, fields in enumerate(groups, start=1)
    ]
    group_specs = [(level, fields) for level, fields in group_specs if fields]
    group_key_cache: dict[int, pd.Series] = {}

    for feature in feature_names:
        if feature not in out.columns:
            out[feature] = np.nan
        out[feature] = _to_numeric(out[feature])
        missing = out[feature].isna()
        out[f"{feature}_was_missing"] = missing.astype(int)
        missing_count = int(missing.sum())
        missing_by_field[feature] = missing_count
        total_missing += missing_count
        if missing_count == 0:
            continue

        feature_stats = task_stats[task_stats["字段名"].astype(str).eq(feature)].copy()
        feature_type = feature_stats["字段类型"].dropna().iloc[0] if not feature_stats.empty and feature_stats["字段类型"].notna().any() else _feature_type(feature)
        filled_event = filled_group = filled_global = filled_zero = 0
        if feature_type == "event_count":
            out.loc[missing, feature] = 0.0
            filled_event = missing_count
            fill_counts["event_fill_zero"] += missing_count
        else:
            remaining = missing.copy()
            for level, valid_fields in group_specs:
                level_stats = feature_stats[feature_stats["group_level"].astype(str).eq(f"group_{level}")]
                if level_stats.empty:
                    continue
                mapping = dict(zip(level_stats["分组值"].astype(str), pd.to_numeric(level_stats["分组中位数"], errors="coerce")))
                key = group_key_cache.get(level)
                if key is None:
                    key = _key_frame(out, valid_fields)
                    group_key_cache[level] = key
                values = key.map(mapping)
                can_fill = remaining & values.notna()
                if can_fill.any():
                    out.loc[can_fill, feature] = values.loc[can_fill].astype(float)
                    n = int(can_fill.sum())
                    filled_group += n
                    fill_counts["group_median"] += n
                    remaining = out[feature].isna()
            if remaining.any():
                global_rows = feature_stats[feature_stats["group_level"].astype(str).eq("global")]
                global_value = pd.to_numeric(global_rows["全局中位数"], errors="coerce").dropna().iloc[0] if not global_rows.empty and pd.to_numeric(global_rows["全局中位数"], errors="coerce").notna().any() else np.nan
                if pd.notna(global_value):
                    out.loc[remaining, feature] = float(global_value)
                    n = int(remaining.sum())
                    filled_global += n
                    fill_counts["global_median"] += n
                remaining = out[feature].isna()
            if remaining.any():
                out.loc[remaining, feature] = 0.0
                n = int(remaining.sum())
                filled_zero += n
                fill_counts["final_fill_zero"] += n
        for level, fields in group_specs:
            if feature in fields and missing_count:
                group_key_cache.pop(level, None)
        non_null_rate = float(out[feature].notna().mean()) if len(out) else 0.0
        detail_rows.append(
            {
                "模型名称": model_name,
                "字段名": feature,
                "缺失数": missing_count,
                "缺失率": missing_count / len(out) if len(out) else 0.0,
                "事件类填0数": filled_event,
                "分组中位数填充数": filled_group,
                "全局中位数填充数": filled_global,
                "最终填0数": filled_zero,
                "填充后非空率": non_null_rate,
                "填充策略": "event_fill_zero" if feature_type == "event_count" else "group_median",
                "fallback次数": filled_global + filled_zero,
                "fallback比例": (filled_global + filled_zero) / missing_count if missing_count else 0.0,
            }
        )

    top10 = ";".join(f"{field}:{count}" for field, count in sorted(missing_by_field.items(), key=lambda item: item[1], reverse=True)[:10] if count > 0)
    total_fill = int(sum(fill_counts.values()))
    summary = {
        "模型名称": model_name,
        "总缺失字段数": int(sum(1 for count in missing_by_field.values() if count > 0)),
        "总缺失值数": int(total_missing),
        "总填充数": total_fill,
        "分组中位数填充比例": fill_counts["group_median"] / total_fill if total_fill else 0.0,
        "全局中位数填充比例": fill_counts["global_median"] / total_fill if total_fill else 0.0,
        "最终填0比例": fill_counts["final_fill_zero"] / total_fill if total_fill else 0.0,
        "缺失率最高字段Top10": top10,
    }
    return out, summary, pd.DataFrame(detail_rows)


def normalize_features(
    df: pd.DataFrame,
    feature_names: Iterable[str],
    train_stats: dict[str, dict[str, float | str]] | None = None,
) -> tuple[pd.DataFrame, dict[str, dict[str, float | str]]]:
    out = pd.DataFrame(index=df.index)
    stats: dict[str, dict[str, float | str]] = {}
    for feature in feature_names:
        values = pd.to_numeric(df[feature], errors="coerce") if feature in df.columns else pd.Series(np.nan, index=df.index)
        if feature in EVENT_ZERO_FEATURES:
            values = values.fillna(0.0).clip(lower=0)
        method = "log_quantile" if any(key in feature for key in ["次数", "工单数", "故障", "违规率"]) else "quantile"
        if train_stats and feature in train_stats:
            item = train_stats[feature]
            q01 = float(item.get("q01", NORMALIZE_FALLBACK_VALUE))
            q99 = float(item.get("q99", 1.0))
            method = str(item.get("method", method))
        else:
            work_for_stats = values.copy()
            if method == "log_quantile":
                work_for_stats = np.log1p(work_for_stats.clip(lower=0))
            ref = work_for_stats.dropna()
            q01 = float(ref.quantile(NORMALIZE_LOWER_Q)) if not ref.empty else float(NORMALIZE_FALLBACK_VALUE)
            q99 = float(ref.quantile(NORMALIZE_UPPER_Q)) if not ref.empty else 1.0

        work = values.copy()
        if method == "log_quantile":
            work = np.log1p(work.clip(lower=0))
        if not np.isfinite(q01) or not np.isfinite(q99) or q99 <= q01:
            norm = pd.Series(np.where(values.notna() & (values > 0), 1.0, NORMALIZE_FALLBACK_VALUE), index=df.index, dtype=float)
            norm[values.isna() & (feature not in EVENT_ZERO_FEATURES)] = np.nan
        else:
            norm = ((work - q01) / (q99 - q01)).clip(0, 1)
        if feature in EVENT_ZERO_FEATURES:
            norm = norm.fillna(float(NORMALIZE_FALLBACK_VALUE))
        out[feature] = norm
        stats[feature] = {"q01": q01, "q99": q99, "method": method}
    return out, stats


def fit_normalization_statistics(
    df: pd.DataFrame,
    feature_names: Iterable[str],
) -> dict[str, dict[str, float | str]]:
    _, stats = normalize_features(df, feature_names)
    return stats


def apply_normalization_statistics(
    df: pd.DataFrame,
    feature_names: Iterable[str],
    stats: dict[str, dict[str, float | str]],
) -> pd.DataFrame:
    normalized, _ = normalize_features(df, feature_names, stats)
    return normalized


