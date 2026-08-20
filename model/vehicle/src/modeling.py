# -*- coding: utf-8 -*-
from __future__ import annotations

import time

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from model.vehicle.src.config import (
    ALERT_CONFIG,
    BUSINESS_SCORE_THRESHOLD,
    DATA_QUALITY_CONFIG,
    ENERGY_FEATURES,
    FAULT_FEATURES,
    LABEL_CONFIG,
    LEVEL_1_WEIGHT_MAP,
    MODEL_FEATURE_ALLOWLIST_BY_TASK,
    OUTLIER_RULES,
    SCORE_OUTPUT_MODE,
    XGB_WEIGHT_CAP_N,
)
from model.vehicle.src.preprocessing import normalize_features

MODEL_NAME_MAP = {
    "energy": "车辆能耗模型",
    "fault": "车辆故障模型",
}

SCORE_SCALE_METHOD = "daily_boundary_piecewise_linear_to_65"
SCORE_SCALE_VERSION = "daily_boundary_to_65_v1"

# ===== BRAND_PATCH_START: 车辆品牌普通编号入模与解释统计常量 =====
BRAND_FEATURE = "车辆属性_车辆品牌"
BRAND_NAME_FEATURE = "车辆属性_车辆品牌名称"
BRAND_LABEL_FIELD = "__brand_label_encoding__"
BRAND_RISK_FIELD = "__brand_risk_rate__"
BRAND_RISK_ALPHA = 100.0
# ===== BRAND_PATCH_END =====


# ===== BRAND_PATCH_START: 车辆品牌普通编号入模与风险率解释函数 =====
def _brand_name(df: pd.DataFrame) -> pd.Series:
    """解释用品牌名称：优先使用品牌名称字段，兜底使用品牌字段。"""
    if BRAND_NAME_FEATURE in df.columns:
        return df[BRAND_NAME_FEATURE].astype("string").fillna("").str.strip()
    if BRAND_FEATURE in df.columns:
        return df[BRAND_FEATURE].astype("string").fillna("").str.strip()
    return pd.Series("", index=df.index, dtype="string")


def _brand_label_name(df: pd.DataFrame) -> pd.Series:
    """普通编号只允许使用品牌名称字段，避免用已编码的品牌字段反推。"""
    if BRAND_NAME_FEATURE in df.columns:
        return df[BRAND_NAME_FEATURE].astype("string").fillna("").str.strip()
    return pd.Series("", index=df.index, dtype="string")


def _brand_label_encoding_rows(
        df: pd.DataFrame,
        create_date: str,
        train_start: str,
        train_end: str,
) -> list[dict[str, object]]:
    """训练期生成车辆品牌普通编号映射；不读取标签，不计算风险率。"""
    brand = _brand_label_name(df)
    brands = sorted(
        b for b in brand.dropna().astype(str).str.strip().unique().tolist()
        if b and b != "__OTHER__"
    )

    rows = [{
        "模型名称": "车辆品牌编号映射",
        "task_name": "brand_label_encoding",
        "字段名": BRAND_LABEL_FIELD,
        "品牌名称": "__OTHER__",
        "编号值": 0.0,
        "create_date": create_date,
        "train_start": train_start,
        "train_end": train_end,
    }]

    for i, brand_name in enumerate(brands, start=1):
        rows.append({
            "模型名称": "车辆品牌编号映射",
            "task_name": "brand_label_encoding",
            "字段名": BRAND_LABEL_FIELD,
            "品牌名称": brand_name,
            "编号值": float(i),
            "create_date": create_date,
            "train_start": train_start,
            "train_end": train_end,
        })

    return rows


def _brand_label_mapping(stats_df: pd.DataFrame) -> tuple[dict[str, float], float]:
    if stats_df.empty:
        return {}, 0.0

    required = {"字段名", "品牌名称", "编号值"}
    if not required.issubset(stats_df.columns):
        return {}, 0.0

    part = stats_df[stats_df["字段名"].astype(str).eq(BRAND_LABEL_FIELD)].copy()
    if part.empty:
        return {}, 0.0

    mapping = dict(zip(
        part["品牌名称"].astype(str),
        pd.to_numeric(part["编号值"], errors="coerce"),
    ))

    other_value = float(mapping.get("__OTHER__", 0.0))
    return mapping, other_value


def _apply_brand_label_encoding(df: pd.DataFrame, stats_df: pd.DataFrame) -> pd.DataFrame:
    """按训练期普通编号映射替换车辆品牌；评分期新品牌映射为 __OTHER__。"""
    out = df.copy()

    if BRAND_FEATURE not in out.columns:
        return out

    if BRAND_NAME_FEATURE not in out.columns:
        out[BRAND_NAME_FEATURE] = _brand_name(out)

    mapping, other_value = _brand_label_mapping(stats_df)
    brand = _brand_label_name(out)

    out[BRAND_FEATURE] = brand.map(mapping).fillna(other_value).astype(float)
    return out


def _brand_risk_rows(
        df: pd.DataFrame,
        task_name: str,
        target_col: str,
        create_date: str,
        train_start: str,
        train_end: str,
) -> list[dict[str, object]]:
    """训练期品牌风险率；只用于 03/04 解释统计，不参与 XGB 训练、评分和权重计算。"""
    brand = _brand_name(df)
    y = pd.to_numeric(df[target_col], errors="coerce") if target_col in df.columns else pd.Series(
        np.nan,
        index=df.index,
        dtype=float,
    )
    global_rate = float(y.mean()) if y.notna().any() else 0.0

    stat = (
        pd.DataFrame({"品牌名称": brand, "y": y})
        .dropna(subset=["y"])
        .groupby("品牌名称")["y"]
        .agg(["sum", "count"])
        .reset_index()
    )

    stat["风险率"] = (
        (stat["sum"] + BRAND_RISK_ALPHA * global_rate)
        / (stat["count"] + BRAND_RISK_ALPHA)
    )

    rows = [{
        "模型名称": MODEL_NAME_MAP[task_name],
        "task_name": task_name,
        "字段名": BRAND_RISK_FIELD,
        "品牌名称": "__GLOBAL__",
        "样本数": int(y.notna().sum()),
        "正样本数": int(y.fillna(0).sum()),
        "归一化值": global_rate,
        "create_date": create_date,
        "train_start": train_start,
        "train_end": train_end,
    }]

    for _, r in stat.iterrows():
        rows.append({
            "模型名称": MODEL_NAME_MAP[task_name],
            "task_name": task_name,
            "字段名": BRAND_RISK_FIELD,
            "品牌名称": str(r["品牌名称"]),
            "样本数": int(r["count"]),
            "正样本数": int(r["sum"]),
            "归一化值": float(r["风险率"]),
            "create_date": create_date,
            "train_start": train_start,
            "train_end": train_end,
        })

    return rows


def _brand_risk_norm_series(df: pd.DataFrame, task_name: str, stats_df: pd.DataFrame) -> pd.Series:
    """评分期按训练期品牌风险率生成解释用归一化值。"""
    if stats_df.empty:
        return pd.Series(0.0, index=df.index, dtype=float)

    if "字段名" not in stats_df.columns or "task_name" not in stats_df.columns:
        return pd.Series(0.0, index=df.index, dtype=float)

    part = stats_df[
        stats_df["字段名"].astype(str).eq(BRAND_RISK_FIELD)
        & stats_df["task_name"].astype(str).eq(task_name)
    ].copy()

    if part.empty:
        return pd.Series(0.0, index=df.index, dtype=float)

    global_part = part.loc[
        part["品牌名称"].astype(str).eq("__GLOBAL__"),
        "归一化值",
    ]
    clean_global = pd.to_numeric(global_part, errors="coerce").dropna()
    global_value = float(clean_global.iloc[0]) if len(clean_global) else 0.0

    mapping = dict(zip(
        part["品牌名称"].astype(str),
        pd.to_numeric(part["归一化值"], errors="coerce"),
    ))

    brand = _brand_name(df)
    return brand.map(mapping).fillna(global_value).astype(float).clip(0, 1)
# ===== BRAND_PATCH_END =====


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce")
    return pd.Series(np.nan, index=df.index, dtype=float)


def _safe_metric(func, y_true, y_pred_or_score, default: float = 0.0) -> float:
    try:
        if len(np.unique(y_true)) < 2 and func in {roc_auc_score, average_precision_score}:
            return default
        return float(func(y_true, y_pred_or_score))
    except Exception:
        return default


def scale_score_to_business_threshold(
        raw_score: pd.Series | np.ndarray,
        raw_threshold: float,
        business_threshold: float = BUSINESS_SCORE_THRESHOLD,
) -> pd.Series | np.ndarray:
    if not 0.0 < float(raw_threshold) < 100.0:
        raise ValueError(f"raw_threshold 必须位于 (0, 100)，当前值={raw_threshold}")
    if not 0.0 < float(business_threshold) < 100.0:
        raise ValueError(f"business_threshold 必须位于 (0, 100)，当前值={business_threshold}")
    is_series = isinstance(raw_score, pd.Series)
    values = pd.to_numeric(raw_score, errors="coerce").to_numpy(dtype=float) if is_series else np.asarray(raw_score,
                                                                                                          dtype=float)
    values = np.clip(values, 0.0, 100.0)
    # 按每日业务预警容量确定评分卡边界，并映射到固定业务分 65；正式预警名单以确定性排名为准，避免边界同分导致数量失控
    scaled = np.where(
        values <= raw_threshold,
        business_threshold * values / raw_threshold,
        business_threshold + (100.0 - business_threshold) * (values - raw_threshold) / (100.0 - raw_threshold),
    )
    return pd.Series(scaled, index=raw_score.index, name=raw_score.name) if is_series else scaled


def apply_daily_alert_strategy(
        raw_score: pd.Series,
        dates: pd.Series,
        vehicle_ids: pd.Series,
        strategy: str,
        strategy_param: float | int,
) -> pd.DataFrame:
    """按日容量形成预警名单及评分卡边界，返回排名、边界和放缩分。"""
    result = pd.DataFrame(index=raw_score.index)
    for col in ["scorecard_rank", "daily_raw_boundary", "scorecard_scaled", "daily_scoreable_count", "daily_alert_n",
                "boundary_tie_count"]:
        result[col] = np.nan
    result["is_alert"] = 0
    result["capacity_shortfall"] = 0
    work = pd.DataFrame(
        {
            "date": pd.to_datetime(dates, errors="coerce"),
            "raw": pd.to_numeric(raw_score, errors="coerce").clip(0.0, 100.0),
            "vehicle_id": vehicle_ids.astype("string").fillna(""),
            "_row_order": np.arange(len(raw_score)),
        },
        index=raw_score.index,
    ).dropna(subset=["date", "raw"])
    if work.empty:
        return result
    work = work.sort_values(["date", "raw", "vehicle_id", "_row_order"], ascending=[True, False, True, True],
                            kind="mergesort")
    work["scorecard_rank"] = work.groupby("date", sort=False).cumcount() + 1
    work["daily_scoreable_count"] = work.groupby("date", sort=False)["raw"].transform("size")
    strategy = str(strategy).lower()
    if strategy != "daily_top_percent":
        raise ValueError(f"不支持的正式预警策略: {strategy}")
    param = float(strategy_param)
    if not 0.0 < param <= 1.0:
        raise ValueError(f"每日预警比例必须位于 (0, 1]，当前值={param}")
    work["daily_alert_n"] = np.ceil(work["daily_scoreable_count"] * param).astype(int)
    work["is_alert"] = (work["scorecard_rank"] <= work["daily_alert_n"]).astype(int)
    boundaries = work.loc[work["scorecard_rank"].eq(work["daily_alert_n"]), ["date", "raw"]].set_index("date")["raw"]
    work["daily_raw_boundary"] = work["date"].map(boundaries)
    work["_is_boundary_tie"] = work["raw"].eq(work["daily_raw_boundary"])
    work["boundary_tie_count"] = work.groupby("date", sort=False)["_is_boundary_tie"].transform("sum")
    work["scorecard_scaled"] = np.nan
    for date_value, day_idx in work.groupby("date", sort=False).groups.items():
        boundary = float(boundaries.loc[date_value])
        work.loc[day_idx, "scorecard_scaled"] = scale_score_to_business_threshold(work.loc[day_idx, "raw"],
                                                                                  boundary).to_numpy()
    result.loc[work.index, work.columns.intersection(result.columns)] = work[work.columns.intersection(result.columns)]
    result["is_alert"] = result["is_alert"].fillna(0).astype(int)
    result["capacity_shortfall"] = result["capacity_shortfall"].fillna(0).astype(int)
    return result


# ===== BUSINESS_SCORE_PATCH_START: 兜底车辆复用正常车辆形成的同日评分边界 =====
def _scale_with_policy_boundary(
        raw_score: pd.Series,
        dates: pd.Series,
        policy: pd.DataFrame,
) -> pd.Series:
    """按正常可评分车辆的同日边界放缩全量XGB分；无边界时保留原始分。"""
    raw = pd.to_numeric(raw_score, errors="coerce").clip(0.0, 100.0)
    date_values = pd.to_datetime(dates, errors="coerce").dt.normalize()
    policy_boundary = pd.to_numeric(policy["daily_raw_boundary"], errors="coerce")
    scaled = raw.copy()

    for date_value in date_values.dropna().unique():
        day_mask = date_values.eq(date_value)
        boundaries = policy_boundary.loc[day_mask].dropna()
        if boundaries.empty:
            continue
        boundary = float(boundaries.iloc[0])
        if 0.0 < boundary < 100.0:
            scaled.loc[day_mask] = scale_score_to_business_threshold(
                raw.loc[day_mask], boundary
            ).to_numpy()

    return scaled.clip(lower=0.0, upper=100.0)
# ===== BUSINESS_SCORE_PATCH_END =====


def compute_formal_scores(
        df: pd.DataFrame,
        energy_model,
        energy_features: list[str],
        energy_train_stats: dict[str, dict[str, float | str]],
        fault_model,
        fault_features: list[str],
        fault_train_stats: dict[str, dict[str, float | str]],
        scoreable_energy: pd.Series,
        scoreable_fault: pd.Series,
) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["energy_diagnosis_score"] = _num(df, "energy_diagnosis_score").where(scoreable_energy)
    out["能耗正式分"] = out["energy_diagnosis_score"]
    out["是否能耗规则真实高风险"] = (
            out["energy_diagnosis_score"] >= BUSINESS_SCORE_THRESHOLD
    ).fillna(False).astype(int)
    out["energy_xgb_raw_probability"] = np.nan
    out["energy_scorecard_raw"] = np.nan
    # ===== BUSINESS_SCORE_PATCH_START: 对全部车辆预测，供不可评分车辆兜底 =====
    if len(df) > 0 and energy_model is not None:
        norm_energy, _ = normalize_features(df, energy_features, energy_train_stats)
        X_energy = norm_energy.reindex(columns=energy_features).fillna(0.0)
        prob = np.clip(np.asarray(energy_model.predict_proba(X_energy)[:, 1], dtype=np.float64), 0.0, 1.0)
        out["energy_xgb_raw_probability"] = prob
        out["energy_scorecard_raw"] = prob * 100.0
    out["fault_xgb_raw_probability"] = np.nan
    out["fault_scorecard_raw"] = np.nan
    if len(df) > 0 and fault_model is not None:
        norm_fault, _ = normalize_features(df, fault_features, fault_train_stats)
        X_fault = norm_fault.reindex(columns=fault_features).fillna(0.0)
        prob = np.clip(np.asarray(fault_model.predict_proba(X_fault)[:, 1], dtype=np.float64), 0.0, 1.0)
        out["fault_xgb_raw_probability"] = prob
        out["fault_scorecard_raw"] = prob * 100.0
    # ===== BUSINESS_SCORE_PATCH_END =====
    out["能耗原始评分卡分"] = out["energy_scorecard_raw"]
    out["故障原始评分卡分"] = out["fault_scorecard_raw"]
    return out


def compute_contribution(
        normalized_df: pd.DataFrame,
        weight_df: pd.DataFrame,
        raw_model_score: pd.Series,
        formal_score: pd.Series,
        meta_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    features = list(weight_df["三级指标"])
    weight_pct = pd.to_numeric(weight_df["三级全局权重_cap后"], errors="coerce").fillna(0.0)
    weight_ratio = weight_pct / 100.0 if float(weight_pct.sum()) > 1.5 else weight_pct
    work = normalized_df.reindex(columns=features)
    raw = work.mul((weight_ratio * 100.0).to_numpy(dtype=float), axis=1)
    raw_sum = raw.sum(axis=1, min_count=1)
    formal = pd.to_numeric(formal_score, errors="coerce")
    no_formal = formal.isna()
    can_align = formal.notna() & raw_sum.notna() & (raw_sum > 1e-12)
    factor = pd.Series(np.nan, index=raw_sum.index, dtype=float)
    factor.loc[can_align] = formal.loc[can_align] / raw_sum.loc[can_align]
    final = raw.mul(factor, axis=0)
    zero_sum = formal.notna() & ~can_align
    if zero_sum.any() and len(features):
        distribution = (weight_ratio / weight_ratio.sum()).to_numpy(dtype=float)
        final.loc[zero_sum, features] = formal.loc[zero_sum].to_numpy()[:, None] * distribution
    final.loc[no_formal, :] = np.nan
    # 模型总分由 XGB 预测结果产生；解释权重仅用于将正式总分拆解为各特征贡献，不能替代模型预测总分
    scorecard_score = final.sum(axis=1, min_count=1)
    if len(features):
        correction = formal - scorecard_score
        correction_mask = formal.notna() & correction.notna()
        final.loc[correction_mask, features[0]] = final.loc[correction_mask, features[0]] + correction.loc[
            correction_mask]
        scorecard_score = final.sum(axis=1, min_count=1)
    result = pd.DataFrame(index=normalized_df.index)
    result["贡献分合计"] = scorecard_score
    for feature in features:
        result[feature] = final[feature]
    return result


def fbeta_score_value(precision: float, recall: float, beta: float = 2.0) -> float:
    denom = beta * beta * precision + recall
    return (1 + beta * beta) * precision * recall / denom if denom > 0 else 0.0


def build_strategy_evaluation_row(
        model_name: str,
        scoring_object: str,
        evaluation_scope: str,
        dates: pd.Series,
        vehicle_ids: pd.Series,
        y_true: pd.Series,
        raw_score: pd.Series,
        strategy: str,
        strategy_param: float | int,
        scoring_type: str = "formal_model_performance",
) -> dict[str, object]:
    values = pd.DataFrame(
        {
            "date": pd.to_datetime(dates, errors="coerce"),
            "vehicle_id": vehicle_ids,
            "y": pd.to_numeric(y_true, errors="coerce"),
            "raw": pd.to_numeric(raw_score, errors="coerce"),
        }
    ).dropna(subset=["y", "raw"])
    policy = apply_daily_alert_strategy(values["raw"], values["date"], values["vehicle_id"], strategy, strategy_param)
    y = values["y"].astype(int)
    pred = policy["is_alert"].astype(int)
    precision = _safe_metric(lambda a, b: precision_score(a, b, zero_division=0), y, pred)
    recall = _safe_metric(lambda a, b: recall_score(a, b, zero_division=0), y, pred)
    daily_alerts = pred.groupby(values["date"]).sum()
    boundaries = \
    pd.DataFrame({"date": values["date"], "boundary": policy["daily_raw_boundary"]}).dropna().drop_duplicates("date")[
        "boundary"]
    return {
        "模型名称": model_name,
        "评分对象": scoring_object,
        "评分类型": scoring_type,
        "evaluation_scope": evaluation_scope,
        "train_start": "",
        "train_end": "",
        "eval_start": values["date"].min().strftime("%Y-%m-%d") if len(values) else "",
        "eval_end": values["date"].max().strftime("%Y-%m-%d") if len(values) else "",
        "样本数": int(len(values)),
        "正样本数": int(y.sum()),
        "预测高风险数": int(pred.sum()),
        "命中数": int(((pred == 1) & (y == 1)).sum()),
        "预警策略": strategy.upper(),
        "策略参数": strategy_param,
        "每日平均预警车辆数": float(daily_alerts.mean()) if len(daily_alerts) else 0.0,
        "每日最小预警车辆数": int(daily_alerts.min()) if len(daily_alerts) else 0,
        "每日最大预警车辆数": int(daily_alerts.max()) if len(daily_alerts) else 0,
        "日预警标准差": float(daily_alerts.std(ddof=0)) if len(daily_alerts) else 0.0,
        "平均原始边界分": float(boundaries.mean()) if len(boundaries) else np.nan,
        "最小原始边界分": float(boundaries.min()) if len(boundaries) else np.nan,
        "最大原始边界分": float(boundaries.max()) if len(boundaries) else np.nan,
        "业务分阈值": BUSINESS_SCORE_THRESHOLD,
        "放缩方法": SCORE_SCALE_METHOD,
        "Precision": precision,
        "Recall": recall,
        "F1": _safe_metric(lambda a, b: f1_score(a, b, zero_division=0), y, pred),
        "F2": fbeta_score_value(precision, recall),
        "Accuracy": _safe_metric(accuracy_score, y, pred),
        "PR_AUC": _safe_metric(average_precision_score, y, values["raw"]),
        "ROC_AUC": _safe_metric(roc_auc_score, y, values["raw"]),
    }


def _as_series(values, feature_names: list[str]) -> pd.Series:
    return pd.Series(np.asarray(values, dtype=float), index=feature_names).replace([np.inf, -np.inf], np.nan).fillna(
        0.0).clip(lower=0)


def normalize_weight_pct(raw_weights: pd.Series) -> pd.Series:
    weights = pd.to_numeric(raw_weights, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(lower=0)
    total = float(weights.sum())
    if total <= 1e-12:
        if len(weights) == 0:
            return weights
        return pd.Series(100.0 / len(weights), index=weights.index)
    out = weights / total * 100.0
    if len(out):
        out.iloc[-1] += 100.0 - float(out.sum())
    return out


def extract_xgb_weight(model, feature_names: list[str]) -> pd.Series:
    raw = pd.Series(0.0, index=feature_names, dtype=float)
    try:
        booster = model.get_booster()
        score = booster.get_score(importance_type="weight")
        for feature in feature_names:
            raw.loc[feature] = float(score.get(feature, 0.0))
        if raw.sum() > 0:
            return raw
        booster_names = getattr(booster, "feature_names", None) or []
        for idx, feature in enumerate(feature_names):
            raw.loc[feature] = float(
                score.get(f"f{idx}", score.get(booster_names[idx], 0.0) if idx < len(booster_names) else 0.0))
        if raw.sum() > 0:
            return raw
    except Exception as exc:  # pragma: no cover - fallback path
        logger.warning(f"XGB booster.get_score(weight)失败，退化到 feature_importances_: {exc}")

    values = getattr(model, "feature_importances_", np.zeros(len(feature_names)))
    return _as_series(values, feature_names)


def apply_weight_cap(raw_weights: pd.Series, cap_n: float = 40.0) -> pd.DataFrame:
    before = normalize_weight_pct(raw_weights)
    remaining = before.copy()
    capped = pd.Series(False, index=before.index)
    after = pd.Series(0.0, index=before.index, dtype=float)
    cap_value = float(cap_n)

    while len(remaining) > 0:
        over = remaining > cap_value
        if not over.any():
            rest_total = float(remaining.sum())
            budget = 100.0 - float(after.sum())
            if rest_total > 1e-12:
                after.loc[remaining.index] = remaining / rest_total * budget
            break
        capped_idx = remaining[over].index
        after.loc[capped_idx] = cap_value
        capped.loc[capped_idx] = True
        budget = 100.0 - float(after.sum())
        remaining = remaining.loc[~over]
        if budget <= 1e-12:
            after.loc[remaining.index] = 0.0
            break
        rest_total = float(remaining.sum())
        if rest_total <= 1e-12:
            if len(remaining) > 0:
                after.loc[remaining.index] = budget / len(remaining)
            break
        remaining = remaining / rest_total * budget

    after = after.clip(lower=0)
    total = float(after.sum())
    if total <= 1e-12 and len(after):
        after[:] = 100.0 / len(after)
    elif len(after):
        after *= 100.0 / float(after.sum())
        after.iloc[-1] += 100.0 - float(after.sum())

    return pd.DataFrame(
        {
            "feature_name": before.index,
            "cap_before_weight": before.values,
            "cap_after_weight": after.values,
            "is_capped": capped.values,
            "cap_n": cap_value,
        }
    )


def weight_entropy(weight_pct: pd.Series) -> float:
    p = pd.to_numeric(weight_pct, errors="coerce").fillna(0.0).clip(lower=0) / 100.0
    p = p[p > 0]
    if p.empty:
        return 0.0
    return float(-(p * np.log(p)).sum())


def build_weight_report(
        model_name: str,
        weight_source: str,
        y: pd.Series,
        cap_df: pd.DataFrame,
        train_start: str,
        train_end: str,
        create_date: str,
) -> dict[str, object]:
    weight = pd.to_numeric(cap_df["cap_after_weight"], errors="coerce").fillna(0.0).sort_values(ascending=False)
    y_num = pd.to_numeric(y, errors="coerce").fillna(0).astype(int)
    sample_count = int(len(y_num))
    pos_count = int(y_num.sum())
    return {
        "模型名称": model_name,
        "权重来源": weight_source,
        "训练窗口_start": train_start,
        "训练窗口_end": train_end,
        "训练样本数": sample_count,
        "正样本数": pos_count,
        "正样本率": pos_count / sample_count if sample_count else 0.0,
        "入模特征数": int(len(cap_df)),
        "有效权重特征数": int((pd.to_numeric(cap_df["cap_after_weight"], errors="coerce").fillna(0) > 0).sum()),
        "零权重特征数": int((pd.to_numeric(cap_df["cap_after_weight"], errors="coerce").fillna(0) <= 0).sum()),
        "WEIGHT_CAP_N": float(cap_df["cap_n"].iloc[0]) if not cap_df.empty else 0.0,
        "触发cap特征数": int(cap_df["is_capped"].sum()) if "is_capped" in cap_df.columns else 0,
        "Top1权重占比": float(weight.iloc[:1].sum()) if len(weight) else 0.0,
        "Top3权重占比": float(weight.iloc[:3].sum()) if len(weight) else 0.0,
        "Top5权重占比": float(weight.iloc[:5].sum()) if len(weight) else 0.0,
        "权重熵": weight_entropy(cap_df.set_index("feature_name")["cap_after_weight"]) if not cap_df.empty else 0.0,
        "创建日期": create_date,
    }


# =============================================================================
# 权重训练入口类
# =============================================================================

try:
    from xgboost import XGBClassifier
except ImportError:  # pragma: no cover
    XGBClassifier = None

from .features import build_feature_frames
from .preprocessing import apply_imputation_statistics, build_quality_flags, fit_imputation_statistics

from .utils import get_latest_score_date, get_month, logger


def _feature_category(feature_name: str) -> str:
    return feature_name.split("_", 1)[0] if "_" in feature_name else "其他"


def build_weight_table(
        model_name: str,
        weight_source: str,
        cap_df: pd.DataFrame,
        train_start: str,
        train_end: str,
        weight_month: str,
        create_date: str,
) -> pd.DataFrame:
    if cap_df.empty:
        return pd.DataFrame()
    df = cap_df.copy()
    df["二级指标"] = df["feature_name"].map(lambda x: _feature_category(str(x)))
    category_weight = df.groupby("二级指标")["cap_after_weight"].sum().to_dict()
    level1_weight = float(LEVEL_1_WEIGHT_MAP.get(model_name, 0.0) * 100.0)
    rows = []
    for _, row in df.iterrows():
        category = str(row["二级指标"])
        c_weight = float(category_weight.get(category, 0.0))
        f_weight = float(row["cap_after_weight"])
        rows.append({
            "模型名称": model_name,
            "权重来源": weight_source,
            "一级指标": model_name,
            "一级权重": level1_weight,
            "二级指标": category,
            "二级局部权重": c_weight,
            "三级指标": row["feature_name"],
            "三级局部权重": f_weight / c_weight * 100.0 if c_weight > 1e-12 else 0.0,
            "三级全局权重_cap前": float(row["cap_before_weight"]),
            "三级全局权重_cap后": f_weight,
            "是否触发cap": bool(row["is_capped"]),
            "WEIGHT_CAP_N": float(row["cap_n"]),
            "训练窗口_start": train_start,
            "训练窗口_end": train_end,
            "权重月份": weight_month,
            "创建日期": create_date,
        })
    return pd.DataFrame(rows)


class WeightUpdater:
    """权重训练计算流程；外部读写由 data_io 负责。"""

    def __init__(
            self,
            start_date: str,
            end_date: str,
            create_date: str,
            energy_alert_top_percent: float | None = None,
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.create_date = create_date
        if not self.start_date or not self.end_date or not self.create_date:
            raise ValueError("必须提供 start_date/end_date/create_date")
        self.weight_month = get_month(self.create_date)
        self.energy_alert_top_percent = float(
            ALERT_CONFIG["energy_top_percent"] if energy_alert_top_percent is None else energy_alert_top_percent
        )
        if not 0.0 < self.energy_alert_top_percent <= 1.0:
            raise ValueError(f"energy_top_percent 必须位于 (0, 1]，当前值={self.energy_alert_top_percent}")
        self.raw_df = pd.DataFrame()
        self.metadata: dict[str, dict[str, object]] = {}
        self.imputation_stats = pd.DataFrame()
        self.normalization_stats_rows: list[dict[str, object]] = []
        self.training_evaluation_rows: list[dict[str, object]] = []
        # BRAND_PATCH: 保存训练期车辆品牌普通编号映射，便于调试和输出到 normalization_statistics
        self.brand_label_encoding_stats = pd.DataFrame()

    @staticmethod
    def _target_col(task_name: str) -> str:
        return LABEL_CONFIG["energy_target_col"] if task_name == "energy" else LABEL_CONFIG["fault_target_col"]

    @staticmethod
    def _build_xgb(task_name: str, y: pd.Series):
        if XGBClassifier is None:
            raise ImportError("未安装 xgboost，无法训练和保存 XGB json 模型")
        pos = max(float(y.sum()), 1.0)
        neg = max(float(len(y) - y.sum()), 1.0)
        params = {
            "n_estimators": 260 if task_name == "fault" else 180,
            "max_depth": 5 if task_name == "fault" else 4,
            "learning_rate": 0.035,
            "subsample": 0.85,
            "colsample_bytree": 0.85,
            "min_child_weight": 3,
            "reg_alpha": 0.05,
            "reg_lambda": 1.0,
            "scale_pos_weight": min(neg / pos, 20.0),
            "random_state": 42,
            "n_jobs": -1,
            "eval_metric": "logloss",
            "importance_type": "weight",
        }
        return XGBClassifier(**params)

    async def load_training_data(self, source_df: pd.DataFrame):
        self.raw_df, _ = await build_feature_frames(source_df, self.start_date, self.end_date, for_training=True)
        if self.raw_df.empty:
            raise ValueError("评分宽表为空")

        # ===== BRAND_PATCH_START: 训练阶段先生成并应用车辆品牌普通编号 =====
        self.brand_label_encoding_stats = pd.DataFrame(
            _brand_label_encoding_rows(
                self.raw_df,
                self.create_date,
                self.start_date,
                self.end_date,
            )
        )
        self.normalization_stats_rows.extend(
            self.brand_label_encoding_stats.to_dict("records")
        )
        self.raw_df = _apply_brand_label_encoding(
            self.raw_df,
            self.brand_label_encoding_stats,
        )

        stats_frames = []
        for task_name, features in MODEL_FEATURE_ALLOWLIST_BY_TASK.items():
            # ===== BRAND_PATCH_START: 品牌风险率只作为 03/04 解释统计，不参与模型训练 =====
            target_col = self._target_col(task_name)
            self.normalization_stats_rows.extend(
                _brand_risk_rows(
                    self.raw_df,
                    task_name,
                    target_col,
                    self.create_date,
                    self.start_date,
                    self.end_date,
                )
            )
            # ===== BRAND_PATCH_END =====

            stats_frames.append(
                fit_imputation_statistics(
                    self.raw_df, features, task_name, MODEL_NAME_MAP[task_name], self.create_date, self.start_date,
                    self.end_date
                )
            )
        self.imputation_stats = pd.concat(stats_frames, ignore_index=True)

    def _prepare_task_data(self, task_name: str) -> tuple[
        pd.DataFrame, pd.DataFrame, pd.Series, list[str], dict[str, dict[str, float | str]]]:
        features = MODEL_FEATURE_ALLOWLIST_BY_TASK[task_name]
        target_col = self._target_col(task_name)
        task_df, _, _ = apply_imputation_statistics(
            self.raw_df,
            features,
            self.imputation_stats,
            task_name,
            MODEL_NAME_MAP[task_name],
        )
        flagged = build_quality_flags(task_df, task_name, mode="train")
        trainable = flagged[flagged["是否可训练"]].copy()
        if target_col not in trainable.columns:
            raise ValueError(f"{MODEL_NAME_MAP[task_name]} 缺少标签列: {target_col}")
        y = pd.to_numeric(trainable[target_col], errors="coerce").fillna(0).astype(int)
        if y.nunique() < 2:
            raise ValueError(f"{MODEL_NAME_MAP[task_name]} 标签只有单一类别，无法训练")
        X_raw = trainable.reindex(columns=features)
        X_norm, stats = normalize_features(X_raw, features)
        for feature, item in stats.items():
            self.normalization_stats_rows.append(
                {
                    "模型名称": MODEL_NAME_MAP[task_name],
                    "task_name": task_name,
                    "字段名": feature,
                    **item,
                    "create_date": self.create_date,
                    "train_start": self.start_date,
                    "train_end": self.end_date,
                }
            )
        X_model = X_norm.reindex(columns=features).fillna(0.0)
        return trainable, X_model, y, features, stats

    @staticmethod
    def _time_ordered_split(dates: pd.Series) -> tuple[pd.Series, pd.Series]:
        parsed = pd.to_datetime(dates, errors="coerce")
        unique_dates = sorted(parsed.dropna().unique())
        if len(unique_dates) < 2:
            raise ValueError("训练期日期不足，无法按时间划分内部验证集")
        valid_days = max(1, int(np.ceil(len(unique_dates) * 0.2)))
        valid_start = unique_dates[-valid_days]
        return parsed < valid_start, parsed >= valid_start

    def _fit_xgb_and_metrics(
            self,
            task_name: str,
            X: pd.DataFrame,
            y: pd.Series,
            dates: pd.Series,
            vehicle_ids: pd.Series,
            features: list[str],
    ):
        train_mask, valid_mask = self._time_ordered_split(dates)
        X_train, X_valid = X.loc[train_mask], X.loc[valid_mask]
        y_train, y_valid = y.loc[train_mask], y.loc[valid_mask]
        if y_train.nunique() < 2 or y_valid.nunique() < 2:
            raise ValueError(f"{MODEL_NAME_MAP[task_name]} 时间验证集缺少双类别样本，无法评价正式预警策略")
        validation_model = self._build_xgb(task_name, y_train)
        validation_model.fit(X_train, y_train)
        train_raw = pd.Series(validation_model.predict_proba(X_train)[:, 1] * 100.0, index=X_train.index)
        valid_raw = pd.Series(validation_model.predict_proba(X_valid)[:, 1] * 100.0, index=X_valid.index)
        if task_name == "energy":
            model_label = "能耗放缩评分卡"
            score_object = "energy_scorecard_scaled"
            strategy = "daily_top_percent"
            strategy_param = self.energy_alert_top_percent
        else:
            model_label = "故障放缩评分卡"
            score_object = "fault_scorecard_scaled"
            strategy = "daily_top_percent"
            strategy_param = ALERT_CONFIG["fault_top_percent"]
        train_dates = pd.to_datetime(dates.loc[train_mask], errors="coerce")
        validation_row: dict[str, object] | None = None
        for scope, scope_dates, scope_ids, scope_y, scope_raw in [
            ("train", train_dates, vehicle_ids.loc[train_mask], y_train, train_raw),
            ("validation", dates.loc[valid_mask], vehicle_ids.loc[valid_mask], y_valid, valid_raw),
        ]:
            row = build_strategy_evaluation_row(
                model_label, score_object, scope, scope_dates, scope_ids, scope_y, scope_raw, strategy, strategy_param
            )
            row["总分来源"] = "xgb_predict_proba_x_100"
            row["train_start"] = train_dates.min().strftime("%Y-%m-%d")
            row["train_end"] = train_dates.max().strftime("%Y-%m-%d")
            self.training_evaluation_rows.append(row)
            if scope == "validation":
                validation_row = row
        if validation_row is None:
            raise ValueError(f"{MODEL_NAME_MAP[task_name]} 未生成验证评估结果")
        method = "daily_operational_capacity_boundary"
        selection_scope = "evaluation_scope_daily_ranking"
        common_scale_config = {
            "energy_alert_strategy": "DAILY_TOP_PERCENT",
            "energy_alert_top_percent": self.energy_alert_top_percent,
            "fault_alert_strategy": "DAILY_TOP_PERCENT",
            "fault_alert_top_percent": ALERT_CONFIG["fault_top_percent"],
            "business_score_threshold": BUSINESS_SCORE_THRESHOLD,
            "scale_method": SCORE_SCALE_METHOD,
            "scale_version": SCORE_SCALE_VERSION,
            "daily_boundary_method": method,
            "model_total_score_source": "xgb_predict_proba_x_100",
            "energy_rule_version": "energy_route_D30_LOO_type_D0_LOO",
            "fault_rule_version": "fault_future_D7",
        }
        if task_name == "energy":
            scale_config = {
                "raw_score_source": "energy_xgb_raw_probability_x_100",
                **common_scale_config,
            }
        else:
            scale_config = {
                "raw_score_source": "fault_xgb_raw_probability_x_100",
                **common_scale_config,
            }
        final_model = self._build_xgb(task_name, y)
        final_model.fit(X, y)
        metrics = {"ROC_AUC": validation_row["ROC_AUC"], "PR_AUC": validation_row["PR_AUC"]}
        return final_model, metrics, scale_config

    def _build_metadata(
            self,
            task_name: str,
            features: list[str],
            train_stats: dict[str, dict[str, float | str]],
            xgb_report: dict[str, object],
            xgb_metrics: dict[str, float],
            scale_config: dict[str, object],
    ) -> dict[str, object]:
        return {
            "task_name": task_name,
            "model_name": MODEL_NAME_MAP[task_name],
            "start_date": self.start_date,
            "end_date": self.end_date,
            "create_date": self.create_date,
            "weight_month": self.weight_month,
            "label_config": dict(LABEL_CONFIG),
            "feature_names": features,
            "normalization_stats": train_stats,
            "formal_score": "energy_scorecard_scaled" if task_name == "energy" else "fault_scorecard_scaled",
            "explain_methods": {"xgb": "xgboost_importance_weight_with_cap"},
            "weight_cap": {"xgb": XGB_WEIGHT_CAP_N},
            "formal_feature_count": len(features),
            "training_reports": {"xgb": xgb_report, "xgb_validation_metrics": xgb_metrics},
            "model_total_score_source": "xgb_predict_proba_x_100",
            "energy_rule_version": "energy_route_D30_LOO_type_D0_LOO",
            "fault_rule_version": "fault_future_D7",
            **scale_config,
        }

    def _run_task(self, task_name: str) -> tuple[pd.DataFrame, dict[str, object], object, dict[str, object]]:
        trainable, X, y, features, stats = self._prepare_task_data(task_name)
        date_col = next((col for col in ["信息_统计日期", "信息_ppartition", "stat_date"] if col in trainable.columns),
                        None)
        if date_col is None:
            raise ValueError(f"{MODEL_NAME_MAP[task_name]} missing validation date column")
        id_col = next((col for col in ["信息_车辆ID", "信息_bus_id", "bus_id"] if col in trainable.columns), None)
        if id_col is None:
            raise ValueError(f"{MODEL_NAME_MAP[task_name]} missing vehicle id column")
        model, xgb_metrics, scale_config = self._fit_xgb_and_metrics(task_name, X, y, trainable[date_col],
                                                                     trainable[id_col], features)
        xgb_raw = extract_xgb_weight(model, features)
        xgb_cap = apply_weight_cap(xgb_raw, XGB_WEIGHT_CAP_N)
        model_name = MODEL_NAME_MAP[task_name]
        xgb_table = build_weight_table(model_name, "XGB_SPLIT_WEIGHT", xgb_cap, self.start_date, self.end_date,
                                       self.weight_month, self.create_date)
        xgb_report = build_weight_report(model_name, "XGB_SPLIT_WEIGHT", y, xgb_cap, self.start_date, self.end_date,
                                         self.create_date)
        metadata = self._build_metadata(task_name, features, stats, xgb_report, xgb_metrics, scale_config)
        return xgb_table, xgb_report, model, metadata

    async def run(self, source_df: pd.DataFrame) -> dict[str, object]:
        run_started = time.perf_counter()
        await self.load_training_data(source_df)
        xgb_tables = []
        models: dict[str, object] = {}
        metadatas: dict[str, dict[str, object]] = {}
        for task_name in ["energy", "fault"]:
            xgb_table, _, model, metadata = self._run_task(task_name)
            xgb_tables.append(xgb_table)
            models[task_name] = model
            metadatas[task_name] = metadata

        xgb_weight_table = pd.concat(xgb_tables, ignore_index=True)
        normalization_statistics = pd.DataFrame(self.normalization_stats_rows)
        training_eval = pd.DataFrame(self.training_evaluation_rows)
        logger.info(f"[运行] 训练窗口={self.start_date}~{self.end_date} | 权重表创建日期={self.create_date}")
        logger.info(f"[特征] 能耗={len(ENERGY_FEATURES)} | 故障={len(FAULT_FEATURES)}")
        # BUSINESS_SCORE_PATCH: 日志显示真实配置比例，避免硬编码与实际参数不一致。
        logger.info(
            f"[策略] 能耗Top{self.energy_alert_top_percent * 100:.0f}% | "
            f"故障Top{float(ALERT_CONFIG['fault_top_percent']) * 100:.0f}% | "
            f"业务阈值={BUSINESS_SCORE_THRESHOLD:.0f}"
        )
        for model_name in ["能耗放缩评分卡", "故障放缩评分卡"]:
            train_row = training_eval[
                training_eval["模型名称"].eq(model_name) & training_eval["evaluation_scope"].eq("train")].iloc[0]
            valid_row = training_eval[
                training_eval["模型名称"].eq(model_name) & training_eval["evaluation_scope"].eq("validation")].iloc[0]
            short_name = "能耗" if model_name.startswith("能耗") else "故障"
            logger.info(
                f"[样本] {short_name} train={int(train_row['样本数'])}/{int(train_row['正样本数'])} | "
                f"validation={int(valid_row['样本数'])}/{int(valid_row['正样本数'])}"
            )
            logger.info(
                f"[效果] {short_name} validation Precision={valid_row['Precision']:.4f} Recall={valid_row['Recall']:.4f} "
                f"F1={valid_row['F1']:.4f} F2={valid_row['F2']:.4f} ROC_AUC={valid_row['ROC_AUC']:.4f}"
            )
        logger.info(f"[计算] Weight 计算完成 | 总耗时={time.perf_counter() - run_started:.2f}s")
        return {
            "energy_model": models["energy"],
            "fault_model": models["fault"],
            "energy_metadata": metadatas["energy"],
            "fault_metadata": metadatas["fault"],
            "xgb_weight_table": xgb_weight_table,
            "model_evaluation": training_eval,
            "imputation_statistics": self.imputation_stats,
            "normalization_statistics": normalization_statistics,
            "train_start": self.start_date,
            "train_end": self.end_date,
            "create_date": self.create_date,
            "weight_month": self.weight_month,
        }


class ScoreUpdater:
    """评分计算流程；外部读写由 data_io 负责。"""

    def __init__(self, start_date: str, end_date: str, create_date: str):
        self.start_date = start_date
        self.end_date = end_date
        self.create_date = create_date
        if not self.start_date or not self.end_date or not self.create_date:
            raise ValueError("必须提供 start_date/end_date/create_date")
        self.weight_batch = ""
        self.raw_df = pd.DataFrame()
        self.pre_impute_df = pd.DataFrame()
        self.scored_df = pd.DataFrame()
        self.score_date = ""
        self.weight_create_date = ""
        self.energy_model = None
        self.fault_model = None
        self.metadata: dict[str, dict] = {}
        self.xgb_weight_table = pd.DataFrame()
        self.imputation_stats = pd.DataFrame()
        # BRAND_PATCH: 保存训练期 normalization_statistics，供评分期品牌普通编号和解释风险率复用
        self.normalization_statistics = pd.DataFrame()
        self.imputation_summaries: dict[str, dict[str, object]] = {}
        self.imputation_details = pd.DataFrame()
        self.source_profile: dict[str, object] = {}

    async def _load_inputs(self, source_df: pd.DataFrame, bundle: dict[str, object]):
        self.weight_batch = str(bundle.get("weight_batch", ""))
        self.weight_create_date = str(bundle["weight_create_date"])
        self.metadata["energy"] = dict(bundle["energy_metadata"])
        self.metadata["fault"] = dict(bundle["fault_metadata"])
        self.energy_model = bundle["energy_model"]
        self.fault_model = bundle["fault_model"]
        self.xgb_weight_table = bundle["xgb_weight_table"].copy()
        self.imputation_stats = bundle["imputation_statistics"].copy()
        # BRAND_PATCH: 评分阶段必须使用训练期 normalization_statistics 中的车辆品牌映射
        self.normalization_statistics = bundle["normalization_statistics"].copy()

        self.raw_df, _ = await build_feature_frames(source_df, self.start_date, self.end_date, for_training=False)
        if self.raw_df.empty:
            raise ValueError("评分宽表为空")
        self.source_profile = dict(self.raw_df.attrs.get("source_profile", {}))

        # ===== BRAND_PATCH_START: 评分阶段复用训练期车辆品牌普通编号映射 =====
        self.raw_df = _apply_brand_label_encoding(
            self.raw_df,
            self.normalization_statistics,
        )
        # ===== BRAND_PATCH_END =====

        # 评分阶段使用训练批次的填充统计，不能重新拟合。
        self.pre_impute_df = self.raw_df.copy()
        for task_name in ["energy", "fault"]:
            features = self.metadata[task_name].get("feature_names",
                                                    ENERGY_FEATURES if task_name == "energy" else FAULT_FEATURES)
            self.raw_df, summary, _ = apply_imputation_statistics(
                self.raw_df, features, self.imputation_stats, task_name, MODEL_NAME_MAP[task_name]
            )
            self.imputation_summaries[MODEL_NAME_MAP[task_name]] = summary
        self.score_date = get_latest_score_date(self.raw_df, "信息_统计日期")

    @staticmethod
    def _first_existing(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
        for col in candidates:
            if col in df.columns:
                return df[col]
        return pd.Series(pd.NA, index=df.index)

    def _display_base(self, df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "评分创建日期": self.create_date,
                "权重表创建日期": self.weight_create_date,
                "统计日期": self._first_existing(df, ["信息_统计日期", "统计日期"]),
                "车辆ID": self._first_existing(df, ["信息_车辆ID", "车辆ID", "信息_bus_id"]),
                "车牌号": self._first_existing(df, ["信息_车牌号", "车牌号"]),
                "公司ID": self._first_existing(df, ["信息_公司ID", "公司ID"]),
                "公司名称": self._first_existing(df, ["信息_公司名称", "公司名称"]),
                "线路ID": self._first_existing(df, ["信息_线路ID", "线路ID", "信息_route_id"]),
                "车辆类型": self._first_existing(df, ["车辆属性_车辆类型", "车辆类型", "信息_vehicle_type"]),
            },
            index=df.index,
        )

    def _apply_quality(self) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
        df = self.raw_df.copy()
        energy_q = build_quality_flags(df, "energy", mode="score")
        fault_q = build_quality_flags(df, "fault", mode="score")
        energy_scoreable = energy_q["是否可评分"].astype(bool)
        fault_scoreable = fault_q["是否可评分"].astype(bool)
        df["是否可评分_能耗"] = energy_scoreable
        df["是否可评分_故障"] = fault_scoreable
        df["不可评分原因_能耗"] = energy_q["不可评分原因"].fillna("")
        df["不可评分原因_故障"] = fault_q["不可评分原因"].fillna("")
        df["异常字段列表_能耗"] = energy_q["异常字段列表"].fillna("")
        df["异常字段列表_故障"] = fault_q["异常字段列表"].fillna("")
        df["是否可训练"] = energy_q["是否可训练"].astype(bool) | fault_q["是否可训练"].astype(bool)
        df["是否可评分"] = energy_scoreable | fault_scoreable
        df["不可训练原因"] = (energy_q["不可训练原因"].fillna("").astype(str) + ";" + fault_q["不可训练原因"].fillna("").astype(str)).str.strip(
            ";")
        df["不可评分原因"] = (energy_q["不可评分原因"].fillna("").astype(str) + ";" + fault_q["不可评分原因"].fillna("").astype(str)).str.strip(
            ";")
        df["异常字段列表"] = (energy_q["异常字段列表"].fillna("").astype(str) + ";" + fault_q["异常字段列表"].fillna("").astype(str)).str.strip(
            ";")
        return df, energy_scoreable, fault_scoreable

    def _compute_scores_and_contributions(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        df, energy_scoreable, fault_scoreable = self._apply_quality()
        formal = compute_formal_scores(
            df,
            self.energy_model,
            self.metadata["energy"].get("feature_names", ENERGY_FEATURES),
            self.metadata["energy"].get("normalization_stats", {}),
            self.fault_model,
            self.metadata["fault"].get("feature_names", FAULT_FEATURES),
            self.metadata["fault"].get("normalization_stats", {}),
            energy_scoreable,
            fault_scoreable,
        )
        self.scored_df = df.reset_index(drop=True).copy()
        formal = formal.reset_index(drop=True)
        for col in formal.columns:
            self.scored_df[col] = formal[col].values
        energy_features = self.metadata["energy"].get("feature_names", ENERGY_FEATURES)
        fault_features = self.metadata["fault"].get("feature_names", FAULT_FEATURES)
        energy_norm, _ = normalize_features(self.scored_df, energy_features,
                                            self.metadata["energy"].get("normalization_stats", {}))
        fault_norm, _ = normalize_features(self.scored_df, fault_features,
                                           self.metadata["fault"].get("normalization_stats", {}))
        # ===== BRAND_PATCH_START: 03/04 解释阶段使用品牌风险率覆盖品牌归一化值 =====
        if BRAND_FEATURE in energy_features:
            energy_norm[BRAND_FEATURE] = _brand_risk_norm_series(
                self.scored_df,
                "energy",
                self.normalization_statistics,
            )

        if BRAND_FEATURE in fault_features:
            fault_norm[BRAND_FEATURE] = _brand_risk_norm_series(
                self.scored_df,
                "fault",
                self.normalization_statistics,
            )
        # ===== BRAND_PATCH_END =====

        energy_raw = pd.to_numeric(self.scored_df["energy_scorecard_raw"], errors="coerce")
        fault_raw = pd.to_numeric(self.scored_df["fault_scorecard_raw"], errors="coerce")
        ids = self.scored_df["信息_车辆ID"] if "信息_车辆ID" in self.scored_df else self.scored_df["信息_bus_id"]

        # ===== BUSINESS_SCORE_PATCH_START: 兜底车辆不参与原Top比例边界、排名和预警名额 =====
        energy_scoreable_mask = pd.Series(np.asarray(energy_scoreable, dtype=bool), index=self.scored_df.index)
        fault_scoreable_mask = pd.Series(np.asarray(fault_scoreable, dtype=bool), index=self.scored_df.index)
        energy_policy = apply_daily_alert_strategy(
            energy_raw.where(energy_scoreable_mask),
            self.scored_df["信息_统计日期"],
            ids,
            str(self.metadata["energy"]["energy_alert_strategy"]).lower(),
            float(self.metadata["energy"]["energy_alert_top_percent"]),
        )
        fault_policy = apply_daily_alert_strategy(
            fault_raw.where(fault_scoreable_mask),
            self.scored_df["信息_统计日期"],
            ids,
            str(self.metadata["fault"]["fault_alert_strategy"]).lower(),
            float(self.metadata["fault"]["fault_alert_top_percent"]),
        )
        energy_xgb_scaled = _scale_with_policy_boundary(
            energy_raw, self.scored_df["信息_统计日期"], energy_policy
        )
        fault_xgb_scaled = _scale_with_policy_boundary(
            fault_raw, self.scored_df["信息_统计日期"], fault_policy
        )
        # ===== BUSINESS_SCORE_PATCH_END =====

        self.scored_df["energy_scorecard_raw"] = energy_raw
        self.scored_df["energy_daily_raw_boundary"] = energy_policy["daily_raw_boundary"]
        self.scored_df["energy_scorecard_scaled"] = energy_policy["scorecard_scaled"]
        self.scored_df["energy_scorecard_rank"] = energy_policy["scorecard_rank"]

        # ===== BUSINESS_SCORE_PATCH_START: 规则分优先，缺失时使用同日边界XGB分兜底 =====
        rule_energy_score = pd.to_numeric(self.scored_df["energy_diagnosis_score"], errors="coerce")
        energy_fallback = ((~energy_scoreable_mask) | rule_energy_score.isna()) & energy_xgb_scaled.notna()
        self.scored_df.loc[energy_fallback, "energy_diagnosis_score"] = energy_xgb_scaled.loc[energy_fallback]
        self.scored_df.loc[energy_fallback, "energy_scorecard_scaled"] = energy_xgb_scaled.loc[energy_fallback]
        self.scored_df["能耗正式分"] = self.scored_df["energy_diagnosis_score"]
        # 合法的规则0分保留，不触发XGB兜底。
        # ===== BUSINESS_SCORE_PATCH_END =====

        self.scored_df["是否能耗评分卡高风险"] = energy_policy["is_alert"]
        self.scored_df["能耗边界同分数量"] = energy_policy["boundary_tie_count"]
        self.scored_df["能耗当日预警车辆数"] = energy_policy["daily_alert_n"]
        self.scored_df["能耗预警策略"] = str(self.metadata["energy"]["energy_alert_strategy"]).upper()
        self.scored_df["能耗策略参数"] = float(self.metadata["energy"]["energy_alert_top_percent"])
        self.scored_df["能耗总分来源"] = "rule_or_xgb_fallback"
        self.scored_df["fault_daily_raw_boundary"] = fault_policy["daily_raw_boundary"]
        self.scored_df["fault_scorecard_scaled"] = fault_policy["scorecard_scaled"]
        self.scored_df["fault_scorecard_rank"] = fault_policy["scorecard_rank"]

        # ===== BUSINESS_SCORE_PATCH_START: 故障分缺失时使用同日边界XGB分兜底 =====
        fault_fallback = ((~fault_scoreable_mask) | self.scored_df["fault_scorecard_scaled"].isna()) & fault_xgb_scaled.notna()
        self.scored_df.loc[fault_fallback, "fault_scorecard_scaled"] = fault_xgb_scaled.loc[fault_fallback]
        # ===== BUSINESS_SCORE_PATCH_END =====

        self.scored_df["是否故障评分卡高风险"] = fault_policy["is_alert"]
        self.scored_df["故障边界同分数量"] = fault_policy["boundary_tie_count"]
        self.scored_df["故障当日预警车辆数"] = fault_policy["daily_alert_n"]
        self.scored_df["故障容量不足"] = fault_policy["capacity_shortfall"]
        self.scored_df["故障预警策略"] = str(self.metadata["fault"]["fault_alert_strategy"]).upper()
        self.scored_df["故障策略参数"] = float(self.metadata["fault"]["fault_alert_top_percent"])
        self.scored_df["故障总分来源"] = "daily_scaled_or_xgb_fallback"
        self.scored_df["能耗原始评分卡分"] = self.scored_df["energy_scorecard_raw"]
        self.scored_df["能耗每日原始边界分"] = self.scored_df["energy_daily_raw_boundary"]
        self.scored_df["能耗放缩评分卡分"] = self.scored_df["energy_scorecard_scaled"]
        self.scored_df["能耗评分卡排名"] = self.scored_df["energy_scorecard_rank"]
        self.scored_df["故障原始评分卡分"] = self.scored_df["fault_scorecard_raw"]
        self.scored_df["故障每日原始边界分"] = self.scored_df["fault_daily_raw_boundary"]
        self.scored_df["故障放缩评分卡分"] = self.scored_df["fault_scorecard_scaled"]
        self.scored_df["故障评分卡排名"] = self.scored_df["fault_scorecard_rank"]
        self.scored_df["车辆能耗模型"] = self.scored_df["energy_scorecard_scaled"]
        self.scored_df["车辆故障模型"] = self.scored_df["fault_scorecard_scaled"]
        self.scored_df["综合画像分"] = (
                LEVEL_1_WEIGHT_MAP["车辆能耗模型"] * self.scored_df["energy_scorecard_scaled"].fillna(0)
                + LEVEL_1_WEIGHT_MAP["车辆故障模型"] * self.scored_df["fault_scorecard_scaled"].fillna(0)
        )
        empty_both = self.scored_df["energy_scorecard_scaled"].isna() & self.scored_df["fault_scorecard_scaled"].isna()
        self.scored_df.loc[empty_both, "综合画像分"] = np.nan
        self.scored_df["正式综合画像分"] = (
                LEVEL_1_WEIGHT_MAP["车辆能耗模型"] * self.scored_df["energy_diagnosis_score"].fillna(0)
                + LEVEL_1_WEIGHT_MAP["车辆故障模型"] * self.scored_df["fault_scorecard_scaled"].fillna(0)
        )
        formal_empty = self.scored_df["energy_diagnosis_score"].isna() & self.scored_df["fault_scorecard_scaled"].isna()
        self.scored_df.loc[formal_empty, "正式综合画像分"] = np.nan
        normalized = self._display_base(self.scored_df)
        for feature in energy_features:
            normalized[f"能耗模型_{feature}"] = energy_norm[feature].to_numpy()
        for feature in fault_features:
            normalized[f"故障模型_{feature}"] = fault_norm[feature].to_numpy()

        contribution_tables: list[pd.DataFrame] = []
        for task_name, features, raw_score_col, score_col in [
            ("energy", energy_features, "energy_scorecard_raw", "车辆能耗模型"),
            ("fault", fault_features, "fault_scorecard_raw", "车辆故障模型"),
        ]:
            model_name = MODEL_NAME_MAP[task_name]
            norm = energy_norm if task_name == "energy" else fault_norm
            weights = self.xgb_weight_table[self.xgb_weight_table["模型名称"].eq(model_name)].copy()
            contrib = compute_contribution(
                norm,
                weights,
                self.scored_df[raw_score_col],
                self.scored_df[score_col],
            )
            contrib["task_name"] = task_name
            contrib["_score_date"] = self.scored_df["信息_统计日期"].astype(str).values
            contribution_tables.append(contrib)

        return (
            normalized,
            pd.concat(contribution_tables, ignore_index=True),
        )

    def _latest(self, df: pd.DataFrame) -> pd.DataFrame:
        date_col = "信息_统计日期" if "信息_统计日期" in df.columns else "统计日期" if "统计日期" in df.columns else None
        if date_col is None:
            return df
        return df[df[date_col].astype(str).eq(self.score_date)].copy()

    def _summary_table(self, score_mode: str = "scorecard") -> pd.DataFrame:
        latest = self._latest(self.scored_df)
        base = self._display_base(latest)
        if score_mode == "formal":
            base["能耗分"] = latest["energy_diagnosis_score"].values if "energy_diagnosis_score" in latest else pd.NA
            base["能耗排名"] = np.nan
            base["综合画像分"] = latest["正式综合画像分"].values if "正式综合画像分" in latest else pd.NA
        else:
            base["能耗分"] = latest["energy_scorecard_scaled"].values if "energy_scorecard_scaled" in latest else pd.NA
            base["能耗排名"] = latest["energy_scorecard_rank"].values if "energy_scorecard_rank" in latest else pd.NA
            base["综合画像分"] = latest["综合画像分"].values if "综合画像分" in latest else pd.NA
        base["故障分"] = latest["fault_scorecard_scaled"].values if "fault_scorecard_scaled" in latest else pd.NA
        base["故障排名"] = latest["fault_scorecard_rank"].values if "fault_scorecard_rank" in latest else pd.NA
        columns = [
            "评分创建日期", "权重表创建日期", "统计日期", "车辆ID", "车牌号", "公司ID", "公司名称", "线路ID",
            "车辆类型",
            "能耗分", "能耗排名", "故障分", "故障排名", "综合画像分",
        ]
        return base.reindex(columns=columns)

    def _task_features(self, task_name: str) -> list[str]:
        """读取当前模型实际使用的特征名。"""
        default = ENERGY_FEATURES if task_name == "energy" else FAULT_FEATURES
        return list(self.metadata[task_name].get("feature_names", default))

    def _prefixed_feature_table(self, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """把能耗/故障两套特征横向展开为一车一行，列名前加风险类型。"""
        latest = self._latest(self.scored_df).reset_index(drop=True)
        base = self._display_base(latest).reset_index(drop=True)

        for task_name, prefix in [("energy", "能耗风险"), ("fault", "故障风险")]:
            frame = frames.get(task_name, pd.DataFrame()).reset_index(drop=True)
            features = self._task_features(task_name)

            for feature in features:
                out_col = f"{prefix}_{feature}"
                if not frame.empty and feature in frame.columns:
                    base[out_col] = frame[feature].reindex(base.index).values
                else:
                    base[out_col] = pd.NA

        return base

    # def _original_values_table(self) -> pd.DataFrame:
    #     latest = self._latest(self.scored_df)
    #     base = self._display_base(latest)
    #     features = list(dict.fromkeys(
    #         list(self.metadata["energy"].get("feature_names", ENERGY_FEATURES))
    #         + list(self.metadata["fault"].get("feature_names", FAULT_FEATURES))
    #     ))
    #     for feature in features:
    #         base[feature] = latest[feature].values if feature in latest.columns else pd.NA
    #     return base

    # ===== BRAND_PATCH_START: 02 原值表展示车辆品牌文本而非普通编号 =====
    def _original_values_table(self) -> pd.DataFrame:
        """02_特征原值表：能耗/故障特征分开列名，一车一行。

        车辆品牌模型内部使用普通编号；
        但 02 原值表面向业务审计，展示品牌文本名称。
        """
        latest = self._latest(self.scored_df).copy()

        display = latest.copy()
        if BRAND_FEATURE in display.columns and BRAND_NAME_FEATURE in display.columns:
            display[BRAND_FEATURE] = display[BRAND_NAME_FEATURE]

        return self._prefixed_feature_table({
            "energy": display,
            "fault": display,
        })
    # ===== BRAND_PATCH_END =====

    def _normalized_values_table(self, normalized: pd.DataFrame) -> pd.DataFrame:
        """03_特征归一化值表：格式与 02 保持一致，一车一行。"""
        latest = self._latest(normalized).drop(columns=["weight_batch"], errors="ignore")

        frames: dict[str, pd.DataFrame] = {}

        for task_name, old_prefix in [
            ("energy", "能耗模型"),
            ("fault", "故障模型"),
        ]:
            features = self._task_features(task_name)
            part = pd.DataFrame(index=latest.index)

            for feature in features:
                # 兼容当前 normalized 中的旧列名：能耗模型_xxx / 故障模型_xxx
                old_col = f"{old_prefix}_{feature}"

                if old_col in latest.columns:
                    part[feature] = latest[old_col]
                elif feature in latest.columns:
                    part[feature] = latest[feature]
                else:
                    part[feature] = pd.NA

            frames[task_name] = part

        return self._prefixed_feature_table(frames)

    def _contribution_values_table(
            self,
            contribution_wide: pd.DataFrame,
            score_mode: str = "scorecard",
    ) -> pd.DataFrame:
        """04_特征贡献值表：格式与 02/03 保持一致，一车一行。"""
        if contribution_wide.empty:
            return pd.DataFrame()

        latest = self._latest(self.scored_df).reset_index(drop=True)
        frames: dict[str, pd.DataFrame] = {}

        for task_name in ["energy", "fault"]:
            features = self._task_features(task_name)

            part = contribution_wide[
                contribution_wide["task_name"].eq(task_name)
                & contribution_wide["_score_date"].astype(str).eq(self.score_date)
                ].reset_index(drop=True)

            if part.empty:
                frames[task_name] = pd.DataFrame(index=latest.index)
                continue

            part = part.iloc[: len(latest)].copy()
            part = part.reindex(columns=features)

            # formal 模式下，能耗对外使用 energy_diagnosis_score，
            # 因此需要把能耗评分卡贡献按 总正式分 / 总评分卡分 等比例缩放。
            if score_mode == "formal" and task_name == "energy":
                scaled = pd.to_numeric(latest["energy_scorecard_scaled"], errors="coerce")
                formal = pd.to_numeric(latest["energy_diagnosis_score"], errors="coerce")

                factor = pd.Series(np.nan, index=latest.index, dtype=float)
                nonzero = scaled.abs() > 1e-12
                factor.loc[nonzero] = formal.loc[nonzero] / scaled.loc[nonzero]
                factor.loc[~nonzero & formal.fillna(0).eq(0)] = 0.0

                anomaly = (~nonzero) & formal.fillna(0).ne(0)
                if anomaly.any():
                    logger.warning(
                        f"能耗正式贡献分发现 {int(anomaly.sum())} 条评分卡分为0但正式分非0，贡献值置空待核查"
                    )

                part = part.mul(factor, axis=0)
                part.loc[anomaly, features] = np.nan

            frames[task_name] = part

        return self._prefixed_feature_table(frames)

    # def _contribution_values_table(self, contribution_wide: pd.DataFrame, score_mode: str = "scorecard") -> pd.DataFrame:
    #     if contribution_wide.empty:
    #         return pd.DataFrame()
    #     latest = self._latest(self.scored_df).reset_index(drop=True)
    #     base = self._display_base(latest)
    #     rows: list[pd.DataFrame] = []
    #     for task_name, model_name, score_col, features in [
    #         ("energy", "能耗放缩评分卡", "energy_scorecard_scaled", self.metadata["energy"].get("feature_names", ENERGY_FEATURES)),
    #         ("fault", "故障放缩评分卡", "fault_scorecard_scaled", self.metadata["fault"].get("feature_names", FAULT_FEATURES)),
    #     ]:
    #         part = contribution_wide[
    #             contribution_wide["task_name"].eq(task_name)
    #             & contribution_wide["_score_date"].astype(str).eq(self.score_date)
    #         ].reset_index(drop=True)
    #         if part.empty:
    #             continue
    #         part = part.iloc[: len(base)].copy()
    #         out = base.copy()
    #         if score_mode == "formal" and task_name == "energy":
    #             scaled = pd.to_numeric(latest["energy_scorecard_scaled"], errors="coerce")
    #             formal_score = pd.to_numeric(latest["energy_diagnosis_score"], errors="coerce")
    #             factor = pd.Series(np.nan, index=latest.index, dtype=float)
    #             nonzero = scaled.abs() > 1e-12
    #             factor.loc[nonzero] = formal_score.loc[nonzero] / scaled.loc[nonzero]
    #             factor.loc[~nonzero & formal_score.fillna(0).eq(0)] = 0.0
    #             anomaly = (~nonzero) & formal_score.fillna(0).ne(0)
    #             if anomaly.any():
    #                 logger.warning(f"能耗正式贡献分发现 {int(anomaly.sum())} 条放缩评分卡分为0但正式分非0的记录，贡献值置空待核查")
    #             out["模型名称"] = "能耗正式评分"
    #             out["模型分"] = formal_score.values
    #             for feature in features:
    #                 values = pd.to_numeric(part[feature], errors="coerce") * factor
    #                 values.loc[anomaly] = np.nan
    #                 out[feature] = values.values
    #         else:
    #             out["模型名称"] = ("故障正式评分" if score_mode == "formal" and task_name == "fault" else model_name)
    #             out["模型分"] = latest[score_col].values if score_col in latest else pd.NA
    #             for feature in features:
    #                 out[feature] = part[feature].values if feature in part.columns else pd.NA
    #         feature_cols = [feature for feature in features if feature in out.columns]
    #         out["贡献分合计"] = out[feature_cols].sum(axis=1, min_count=1)
    #         rows.append(out)
    #     if not rows:
    #         return pd.DataFrame()
    #     result = pd.concat(rows, ignore_index=True)
    #     base_cols = ["评分创建日期", "权重表创建日期", "统计日期", "车辆ID", "车牌号", "公司名称", "车辆类型", "模型名称", "模型分"]
    #     feature_cols = [col for col in result.columns if col not in set(base_cols + ["公司ID", "线路ID", "贡献分合计"])]
    #     return result.reindex(columns=base_cols + feature_cols + ["贡献分合计"])

    @staticmethod
    def _split_items(value) -> list[str]:
        if pd.isna(value):
            return []
        return [item for item in str(value).split(";") if item]

    @staticmethod
    def _quality_rule_info(field: str, reason: str) -> tuple[str, object, object]:
        if field == "信息_车辆百公里能耗":
            return "非空且 >0 且 <=1000；特征构建阶段同规则异常值转NaN", DATA_QUALITY_CONFIG["ENERGY_PER_100KM_MIN"], \
            DATA_QUALITY_CONFIG["ENERGY_PER_100KM_MAX"]
        if field == "指标_百公里能耗":
            lo, hi = OUTLIER_RULES.get("指标_百公里能耗", (0, 500.0))
            return "特征构建阶段 <=0 或 >500 转NaN", lo, hi
        if field == "车辆运营_运营里程":
            lo, hi = OUTLIER_RULES.get("车辆运营_运营里程",
                                       (DATA_QUALITY_CONFIG["RUN_MILEAGE_MIN"], DATA_QUALITY_CONFIG["RUN_MILEAGE_MAX"]))
            return "非空且 >0；特征构建阶段 >400 转NaN", lo, hi
        if field == "车辆运营_运营时长":
            lo, hi = OUTLIER_RULES.get("车辆运营_运营时长",
                                       (DATA_QUALITY_CONFIG["RUN_HOURS_MIN"], DATA_QUALITY_CONFIG["RUN_HOURS_MAX"]))
            return "非空且 >0；特征构建阶段 >24 转NaN", lo, hi
        if field in {"车辆运营_近30日运营里程累计", "车辆运营_近30日运营时长累计"}:
            return "非空且 >0", 0, ""
        if field in {"信息_route_id", "信息_线路ID", "route_id", "车辆属性_车辆类型", "信息_bus_id", "信息_车辆ID",
                     "信息_ppartition", "信息_统计日期"}:
            return "非空", "", ""
        if field == "能耗标签置信等级":
            return "不允许 low", "", ""
        if "缺失" in reason or "为空" in reason:
            return "非空", "", ""
        return "", "", ""

    def _quality_original_value(self, idx, field: str):
        if field and not self.pre_impute_df.empty:
            pre = self.pre_impute_df.reset_index(drop=True)
            if idx in pre.index and field in pre.columns:
                return pre.at[idx, field]
        latest = self._latest(self.scored_df)
        if field and idx in latest.index and field in latest.columns:
            return latest.at[idx, field]
        return pd.NA

    def _unscoreable_vehicle_table(self) -> pd.DataFrame:
        columns = [
            "评分创建日期", "权重表创建日期", "统计日期", "车辆ID", "车牌号", "公司名称", "线路ID", "车辆类型",
            "模型名称", "不可评分原因", "异常字段", "异常前原始值", "生效质量规则",
        ]
        latest = self._latest(self.scored_df)
        if latest.empty:
            return pd.DataFrame(columns=columns)
        rows: list[dict[str, object]] = []
        for display_name, scoreable_col, reason_col, abnormal_col in [
            ("能耗放缩评分卡", "是否可评分_能耗", "不可评分原因_能耗", "异常字段列表_能耗"),
            ("故障放缩评分卡", "是否可评分_故障", "不可评分原因_故障", "异常字段列表_故障"),
        ]:
            if scoreable_col not in latest.columns:
                continue
            bad = ~latest[scoreable_col].astype(bool)
            for idx, row in latest[bad].iterrows():
                reasons = self._split_items(row.get(reason_col, ""))
                fields = self._split_items(row.get(abnormal_col, ""))
                if not reasons:
                    reasons = ["其他"]
                base = self._display_base(latest.loc[[idx]]).iloc[0].to_dict()
                for pos, reason in enumerate(reasons):
                    field = fields[pos] if pos < len(fields) else (fields[0] if len(fields) == 1 else "")
                    rule, lower, upper = self._quality_rule_info(field, reason)
                    rows.append({
                        **{col: base.get(col, pd.NA) for col in columns[:8]},
                        "模型名称": display_name,
                        "不可评分原因": reason,
                        "异常字段": field,
                        "异常前原始值": self._quality_original_value(idx, field),
                        "生效质量规则": rule,
                    })
        return pd.DataFrame(rows, columns=columns)

    @staticmethod
    def _group_key(df: pd.DataFrame, fields: list[str]) -> pd.Series:
        parts = [
            df[field].astype("string").fillna("__MISSING__").str.strip()
            if field in df.columns else pd.Series("__MISSING__", index=df.index, dtype="string")
            for field in fields
        ]
        if not parts:
            return pd.Series("", index=df.index, dtype="string")
        key = parts[0]
        for part in parts[1:]:
            key = key.str.cat(part, sep="|")
        return key

    def _fill_audit_for_missing(self, task_name: str, feature: str, latest: pd.DataFrame,
                                filled: pd.Series) -> pd.DataFrame:
        feature_stats = self.imputation_stats[
            self.imputation_stats["task_name"].astype(str).eq(task_name)
            & self.imputation_stats["字段名"].astype(str).eq(feature)
            ].copy()
        feature_type = feature_stats["字段类型"].dropna().iloc[0] if not feature_stats.empty and feature_stats[
            "字段类型"].notna().any() else ""
        audit = pd.DataFrame(index=filled.index)
        audit["字段类型"] = "事件计数类特征" if feature_type == "event_count" else "连续型特征"
        audit["填充策略"] = np.where(filled.notna(), "零值兜底填充", "未成功填充")
        audit["填充分组字段"] = ""
        audit["填充分组值"] = ""
        assigned = pd.Series(False, index=filled.index)
        if feature_type == "event_count":
            audit.loc[filled.notna(), "填充策略"] = "事件计数类缺失填0"
            return audit
        for level in sorted(
                feature_stats["group_level"].dropna().astype(str).loc[
                    feature_stats["group_level"].astype(str).str.startswith("group_")].unique(),
                key=lambda value: int(value.split("_")[-1]) if value.split("_")[-1].isdigit() else 99,
        ):
            level_stats = feature_stats[feature_stats["group_level"].astype(str).eq(level)]
            if level_stats.empty:
                continue
            fields_text = str(level_stats["分组字段"].dropna().iloc[0]) if level_stats["分组字段"].notna().any() else ""
            fields = [item for item in fields_text.split("+") if item]
            key = self._group_key(latest, fields)
            mapping = dict(
                zip(level_stats["分组值"].astype(str), pd.to_numeric(level_stats["分组中位数"], errors="coerce")))
            values = key.map(mapping)
            match = filled.notna() & values.notna() & np.isclose(filled.astype(float), values.astype(float), rtol=0,
                                                                 atol=1e-12) & ~assigned
            if match.any():
                audit.loc[match, "填充策略"] = "分组中位数填充"
                audit.loc[match, "填充分组字段"] = fields_text
                audit.loc[match, "填充分组值"] = key.loc[match].astype(str)
                assigned |= match
        global_rows = feature_stats[feature_stats["group_level"].astype(str).eq("global")]
        global_value = pd.to_numeric(global_rows["全局中位数"], errors="coerce").dropna().iloc[
            0] if not global_rows.empty and pd.to_numeric(global_rows["全局中位数"],
                                                          errors="coerce").notna().any() else np.nan
        global_match = filled.notna() & ~assigned
        if pd.notna(global_value):
            global_match &= np.isclose(filled.astype(float), float(global_value), rtol=0, atol=1e-12)
            audit.loc[global_match, "填充策略"] = "全局中位数回退填充"
            assigned |= global_match
        audit.loc[filled.isna(), "填充策略"] = "未成功填充"
        return audit

    def _missing_fill_table(self) -> pd.DataFrame:
        columns = [
            "评分创建日期", "权重表创建日期", "统计日期", "车辆ID", "车牌号", "公司名称", "线路ID", "车辆类型",
            "模型名称", "缺失特征", "缺失前原始值", "填充策略", "填充值", "填充后值", "是否填充成功",
        ]
        if self.pre_impute_df.empty or self.scored_df.empty:
            return pd.DataFrame(columns=columns)
        pre = self.pre_impute_df.reset_index(drop=True)
        latest = self._latest(self.scored_df)
        pre_latest = pre.loc[latest.index].copy()
        rows: list[pd.DataFrame] = []
        for task_name, display_name, features in [
            ("energy", "能耗放缩评分卡", self.metadata["energy"].get("feature_names", ENERGY_FEATURES)),
            ("fault", "故障放缩评分卡", self.metadata["fault"].get("feature_names", FAULT_FEATURES)),
        ]:
            for feature in features:
                raw = pd.to_numeric(pre_latest[feature],
                                    errors="coerce") if feature in pre_latest.columns else pd.Series(np.nan,
                                                                                                     index=pre_latest.index)
                missing = raw.isna()
                if not missing.any():
                    continue
                idx = raw[missing].index
                part = self._display_base(latest.loc[idx]).reindex(
                    columns=["评分创建日期", "权重表创建日期", "统计日期", "车辆ID", "车牌号", "公司名称", "线路ID",
                             "车辆类型"])
                filled = pd.to_numeric(latest.loc[idx, feature],
                                       errors="coerce") if feature in latest.columns else pd.Series(np.nan, index=idx)
                audit = self._fill_audit_for_missing(task_name, feature, latest.loc[idx], filled)
                part["模型名称"] = display_name
                part["缺失特征"] = feature
                part["缺失前原始值"] = raw.loc[idx].values
                part["填充策略"] = audit["填充策略"].values
                part["填充值"] = filled.values
                part["填充后值"] = filled.values
                part["是否填充成功"] = filled.notna().astype(int).values
                rows.append(part)
        return pd.concat(rows, ignore_index=True).reindex(columns=columns) if rows else pd.DataFrame(columns=columns)

    def _monitor_table(
            self,
            unscoreable_table: pd.DataFrame,
            missing_fill_table: pd.DataFrame,
            score_formula_error: float,
            contribution_error: float,
            score_mode: str,
    ) -> pd.DataFrame:
        latest = self._latest(self.scored_df)
        total = int(len(latest))
        unscoreable_vehicle_count = int(
            unscoreable_table[["统计日期", "车辆ID"]].drop_duplicates().shape[0]) if not unscoreable_table.empty else 0
        unscoreable_record_count = int(len(unscoreable_table))
        missing_vehicle_count = int(missing_fill_table[["统计日期", "车辆ID"]].drop_duplicates().shape[
                                        0]) if not missing_fill_table.empty else 0
        missing_record_count = int(len(missing_fill_table))
        fill_success = int(
            pd.to_numeric(missing_fill_table.get("是否填充成功", pd.Series(dtype=float)), errors="coerce").fillna(
                0).sum()) if missing_record_count else 0
        row = {
            "评分创建日期": self.create_date,
            "权重表创建日期": self.weight_create_date,
            "统计日期": self.score_date,
            "输出分值口径": "正式分" if score_mode == "formal" else "评分卡分",
            "评分车辆数": total,
            "能耗可评分车辆数": int(latest["是否可评分_能耗"].sum()) if len(latest) else 0,
            "故障可评分车辆数": int(latest["是否可评分_故障"].sum()) if len(latest) else 0,
            "任一模型不可评分车辆数": unscoreable_vehicle_count,
            "能耗高风险车辆数": int(latest["是否能耗评分卡高风险"].sum()) if len(latest) else 0,
            "故障高风险车辆数": int(latest["是否故障评分卡高风险"].sum()) if len(latest) else 0,
            "无法评分原因记录数": unscoreable_record_count,
            "缺失填充车辆数": missing_vehicle_count,
            "缺失填充记录数": missing_record_count,
            "填充失败记录数": missing_record_count - fill_success,
            "综合分公式最大误差": score_formula_error,
            "贡献值最大误差": contribution_error,
        }
        return pd.DataFrame([row])

    @staticmethod
    def _max_abs_diff(left: pd.Series, right: pd.Series) -> float:
        diff = (pd.to_numeric(left, errors="coerce") - pd.to_numeric(right, errors="coerce")).abs().dropna()
        return float(diff.max()) if len(diff) else 0.0

    def _score_formula_error(self, score_mode: str = "scorecard") -> float:
        latest = self._latest(self.scored_df)
        if score_mode == "formal":
            expected = (
                    LEVEL_1_WEIGHT_MAP["车辆能耗模型"] * pd.to_numeric(latest["energy_diagnosis_score"],
                                                                       errors="coerce").fillna(0)
                    + LEVEL_1_WEIGHT_MAP["车辆故障模型"] * pd.to_numeric(latest["fault_scorecard_scaled"],
                                                                         errors="coerce").fillna(0)
            )
            return self._max_abs_diff(latest["正式综合画像分"], expected)
        expected = (
                LEVEL_1_WEIGHT_MAP["车辆能耗模型"] * pd.to_numeric(latest["energy_scorecard_scaled"],
                                                                   errors="coerce").fillna(0)
                + LEVEL_1_WEIGHT_MAP["车辆故障模型"] * pd.to_numeric(latest["fault_scorecard_scaled"],
                                                                     errors="coerce").fillna(0)
        )
        return self._max_abs_diff(latest["综合画像分"], expected)

    # @staticmethod
    # def _contribution_error(table: pd.DataFrame) -> float:
    #     if table.empty or not {"模型分", "贡献分合计"}.issubset(table.columns):
    #         return 0.0
    #     return ScoreUpdater._max_abs_diff(table["模型分"], table["贡献分合计"])

    def _contribution_error(self, table: pd.DataFrame, score_mode: str = "scorecard") -> float:
        """校验 04 表中能耗/故障贡献列加总是否等于对应模型分。"""
        if table.empty:
            return 0.0

        latest = self._latest(self.scored_df).reset_index(drop=True)

        energy_cols = [f"能耗风险_{f}" for f in self._task_features("energy") if f"能耗风险_{f}" in table.columns]
        fault_cols = [f"故障风险_{f}" for f in self._task_features("fault") if f"故障风险_{f}" in table.columns]

        errors = []

        if energy_cols:
            energy_sum = table[energy_cols].sum(axis=1, min_count=1)
            energy_target_col = "energy_diagnosis_score" if score_mode == "formal" else "energy_scorecard_scaled"
            errors.append(self._max_abs_diff(energy_sum, latest[energy_target_col]))

        if fault_cols:
            fault_sum = table[fault_cols].sum(axis=1, min_count=1)
            errors.append(self._max_abs_diff(fault_sum, latest["fault_scorecard_scaled"]))

        return max(errors) if errors else 0.0

    async def run(self, source_df: pd.DataFrame, bundle: dict[str, object]) -> dict[str, pd.DataFrame]:
        run_started = time.perf_counter()
        output_mode = str(SCORE_OUTPUT_MODE).lower()
        if output_mode not in {"formal", "scorecard"}:
            raise ValueError(f"SCORE_OUTPUT_MODE 只能是 formal 或 scorecard，当前值={SCORE_OUTPUT_MODE}")

        await self._load_inputs(source_df, bundle)
        normalized, contribution_wide = self._compute_scores_and_contributions()
        unscoreable_vehicles = self._unscoreable_vehicle_table()
        missing_fill_records = self._missing_fill_table()
        summary = self._summary_table(score_mode=output_mode)
        contribution_values = self._contribution_values_table(contribution_wide, score_mode=output_mode)
        score_formula_error = self._score_formula_error(score_mode=output_mode)
        # contribution_error = self._contribution_error(contribution_values)
        contribution_error = self._contribution_error(contribution_values, score_mode=output_mode)
        tables = {
            "summary_scores": summary,

            # "original_values": self._original_values_table(),
            # "normalized_values": self._latest(normalized).drop(columns=["weight_batch"], errors="ignore"),
            # "contribution_values": contribution_values,
            "original_values": self._original_values_table(),
            "normalized_values": self._normalized_values_table(normalized),
            "contribution_values": contribution_values,

            "daily_monitor": self._monitor_table(
                unscoreable_vehicles,
                missing_fill_records,
                score_formula_error,
                contribution_error,
                output_mode,
            ),
            "unscoreable_vehicles": unscoreable_vehicles,
            "missing_fill_records": missing_fill_records,
        }
        latest = self._latest(self.scored_df)
        mode_text = "正式分" if output_mode == "formal" else "评分卡分"
        logger.info(f"[运行] 评分日期={self.score_date} | 评分创建日期={self.create_date} | 输出口径={mode_text}")
        logger.info(f"[模型] 权重批次={self.weight_batch} | 权重表创建日期={self.weight_create_date}")
        logger.info(
            f"[样本] 总车辆={len(latest)} | 能耗可评分={int(latest['是否可评分_能耗'].sum())} | "
            f"故障可评分={int(latest['是否可评分_故障'].sum())} | 任一不可评分={int(tables['daily_monitor']['任一模型不可评分车辆数'].iloc[0])}"
        )
        # BUSINESS_SCORE_PATCH: 日志显示真实配置比例，评分逻辑不变。
        logger.info(
            f"[预警] 能耗Top{float(self.metadata['energy']['energy_alert_top_percent']) * 100:.0f}%="
            f"{int(latest['是否能耗评分卡高风险'].sum())} | "
            f"故障Top{float(self.metadata['fault']['fault_alert_top_percent']) * 100:.0f}%="
            f"{int(latest['是否故障评分卡高风险'].sum())}"
        )
        logger.info(
            f"[质量] 无法评分记录={len(unscoreable_vehicles)} | 缺失填充记录={len(missing_fill_records)} | "
            f"填充失败={int(tables['daily_monitor']['填充失败记录数'].iloc[0])}"
        )
        logger.info(f"[校验] 综合分={score_formula_error:.3e} | 贡献={contribution_error:.3e}")
        logger.info(f"[计算] Score 计算完成 | 总耗时={time.perf_counter() - run_started:.2f}s")
        return tables
