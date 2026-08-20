# -*- coding: utf-8 -*-
"""本地读写工具。

约定：
1. 这里只负责“从哪里读、写到哪里”。
2. 特征、训练、评分、贡献分计算都不放在这里。
3. 后续接数据库时，优先替换本文件中的读写函数或入口里的调用行。
"""
from __future__ import annotations

import json
from glob import glob
from pathlib import Path

import pandas as pd
from clickhouse_driver import client
from xgboost import XGBClassifier

from model.vehicle.src.crud import read_raw_db, save_weights_dict, Vehicle, get_weights
from model.vehicle.src import crud
from model.vehicle.src.config import ALERT_CONFIG, ENERGY_FEATURES, FAULT_FEATURES


# =============================================================================
# 通用小工具
# =============================================================================


def read_csv(path: str | Path) -> pd.DataFrame:
    """读取 CSV；优先 utf-8-sig，失败时兼容 gbk。"""
    try:
        return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="gbk", low_memory=False)


def save_csv(df: pd.DataFrame, path: str | Path) -> None:
    """统一用 utf-8-sig 输出，方便 Excel 直接打开中文。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def require_file(path: str | Path) -> Path:
    """明确要求文件存在，避免路径写错时静默失败。"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"未找到文件: {path}")
    return path


def newest_match(path_pattern: str | Path) -> Path:
    """通配符读取时取最新文件；适合 data/ 下只放最新 raw 宽表的场景。"""
    files = [Path(p) for p in glob(str(path_pattern))]
    files = [p for p in files if p.is_file()]
    if not files:
        raise FileNotFoundError(f"未找到文件: {path_pattern}")
    return max(files, key=lambda p: p.stat().st_mtime)


# =============================================================================
# 1. 读入 raw 宽表
# =============================================================================


async def read_feature_source(raw_path: str | Path) -> pd.DataFrame:
    """读完整 raw 宽表。

    本地版：raw_path 可以是具体 CSV，也可以是通配符。
    数据库对接：优先在 app 入口替换为 read_raw_db；如果想统一封装，也可改这个函数。

    示例：
    # sqlwhere = f"stat_date BETWEEN '{source_start}' AND '{source_end}'"
    # all_fields = "*"
    # raw_df = await read_raw_db("ai_security.tmp_vehicle_profile_feature_source", sqlwhere, all_fields)
    """
    path_text = str(raw_path)
    path = newest_match(path_text) if any(ch in path_text for ch in "*?[") else require_file(raw_path)
    return read_csv(path)

async def read_feature_source_table(table_name:str) -> pd.DataFrame:
    """读完整 raw 宽表。

    本地版：raw_path 可以是具体 CSV，也可以是通配符。
    数据库对接：优先在 app 入口替换为 read_raw_db；如果想统一封装，也可改这个函数。

    示例：
    # sqlwhere = f"stat_date BETWEEN '{source_start}' AND '{source_end}'"
    # all_fields = "*"
    # raw_df = await read_raw_db("ai_security.tmp_vehicle_profile_feature_source", sqlwhere, all_fields)
    """
    sqlwhere = None
    all_fields = "*"
    raw_df = await read_raw_db(table_name, sqlwhere, all_fields)
    return raw_df


# =============================================================================
# 2. 读入 Score 需要的同版本模型产物
# =============================================================================


def weight_suffix(weight_table_path: Path) -> str:
    """从 XGB正式权重表 文件名中提取版本后缀，如 2026-04_2026-04-24。"""
    prefix = "XGB正式权重表_"
    stem = weight_table_path.stem
    if not stem.startswith(prefix):
        raise ValueError(f"权重表文件名必须以 {prefix} 开头: {weight_table_path.name}")
    return stem[len(prefix):]


def read_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_xgb_model(path: str | Path) -> XGBClassifier:
    """读取 XGBoost 原生 json 模型，避免 joblib/sklearn 版本兼容警告。"""
    model = XGBClassifier()
    model.load_model(str(require_file(path)))
    return model


def normalization_stats_dict(stats_df: pd.DataFrame, model_name: str) -> dict:
    """把 normalization_statistics 表转成 normalize_features 需要的字典。"""
    part = stats_df[stats_df["模型名称"].eq(model_name)].copy()
    result = {}

    for _, row in part.iterrows():
        feature = str(row["字段名"])

        # ===== BRAND_PATCH_START: 过滤车辆品牌内部统计，避免进入模型 metadata =====
        if feature.startswith("__brand_"):
            continue
        # ===== BRAND_PATCH_END =====

        result[feature] = {
            "lower": row.get("lower"),
            "upper": row.get("upper"),
            "fill_value": row.get("fill_value", 0),
            "fallback_value": row.get("fallback_value", 0),
        }

    return result

async def load_score_bundle(weight_table_path: str | Path) -> dict[str, object]:
    """按权重表路径读取同版本的模型、metadata 和预处理统计。

    真实 XGB predict_proba 评分不能只读权重表，还必须有同版本模型和预处理统计。
    数据库对接时，如用 get_weights() 读取权重表，也要同步取得同一版本的模型 json、metadata、填充统计和归一化统计。
    """
    weight_table_path = require_file(weight_table_path)
    suffix = weight_suffix(weight_table_path)
    weight_dir = weight_table_path.parent
    batch_dir = weight_dir.parent
    model_dir = batch_dir / "01_models"

    weight_df = read_csv(weight_table_path)
    norm_df = read_csv(require_file(weight_dir / f"normalization_statistics_{suffix}.csv"))

    create_dates = weight_df["创建日期"].dropna().astype(str).drop_duplicates().tolist()
    if len(create_dates) != 1:
        raise ValueError(f"XGB正式权重表创建日期不唯一: {create_dates}")

    energy_metadata = {
        "feature_names": ENERGY_FEATURES,
        "normalization_stats": normalization_stats_dict(norm_df, "车辆能耗模型"),
        "energy_alert_strategy": "DAILY_TOP_PERCENT",
        "energy_alert_top_percent": ALERT_CONFIG["energy_top_percent"],
    }

    fault_metadata = {
        "feature_names": FAULT_FEATURES,
        "normalization_stats": normalization_stats_dict(norm_df, "车辆故障模型"),
        "fault_alert_strategy": "DAILY_TOP_PERCENT",
        "fault_alert_top_percent": ALERT_CONFIG["fault_top_percent"],
    }

    return {
        "weight_batch": batch_dir.name,
        "weight_create_date": create_dates[0],
        "energy_model": load_xgb_model(model_dir / f"能耗XGB模型_{suffix}.json"),
        "fault_model": load_xgb_model(model_dir / f"故障XGB模型_{suffix}.json"),
        "energy_metadata": energy_metadata,
        "fault_metadata": fault_metadata,
        "imputation_statistics": read_csv(require_file(weight_dir / f"imputation_statistics_{suffix}.csv")),
        "normalization_statistics": norm_df,
        "xgb_weight_table": weight_df,
    }


# =============================================================================
# 3. Weight 输出
# =============================================================================


def save_xgb_model(model, path: str | Path) -> None:
    """保存 XGBoost 原生 json 模型。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(path))


async def save_weight_result(result: dict[str, object], paths,start_date,end_date) -> None:
    """保存训练产物。

    数据库对接建议：保留本地文件审计，同时在这里补充 save_weights_dict() 或新权重表写库函数。
    可写库对象通常是 result["xgb_weight_table"]，模型 json/metadata/统计表需保证版本一致。
    """
    month = result["weight_month"]
    date = result["create_date"]
    suffix = f"{month}_{date}"

    save_xgb_model(result["energy_model"], paths.models_dir / f"能耗XGB模型_{suffix}.json")
    save_xgb_model(result["fault_model"], paths.models_dir / f"故障XGB模型_{suffix}.json")

    # (paths.models_dir / f"能耗模型元数据_{suffix}.json").write_text(
    #     json.dumps(result["energy_metadata"], ensure_ascii=False, indent=2), encoding="utf-8"
    # )
    # (paths.models_dir / f"故障模型元数据_{suffix}.json").write_text(
    #     json.dumps(result["fault_metadata"], ensure_ascii=False, indent=2), encoding="utf-8"
    # )

    save_csv(result["xgb_weight_table"], paths.weights_dir / f"XGB正式权重表_{suffix}.csv")
    save_csv(result["imputation_statistics"], paths.weights_dir / f"imputation_statistics_{suffix}.csv")
    save_csv(result["normalization_statistics"], paths.weights_dir / f"normalization_statistics_{suffix}.csv")
    save_csv(result["model_evaluation"], paths.weights_dir / f"模型效果表_{suffix}.csv")


    await save_weights_dict(start_date, end_date, result["xgb_weight_table"].to_dict("records"))

    return result["model_evaluation"].to_dict("records")



# =============================================================================
# 4. Score 输出：01/05 按配置选择正式分或评分卡分
# =============================================================================


def save_01_summary_scores(df: pd.DataFrame, out_dir: Path, score_date: str) -> None:
    """01 评分汇总：默认正式分口径；数据库主表通常优先写这张。"""
    save_csv(df, out_dir / f"01_评分汇总表_{score_date}.csv")


def save_02_original_values(df: pd.DataFrame, out_dir: Path, score_date: str) -> None:
    """02 特征原值：主要用于审计，是否入库可按业务需要决定。"""
    save_csv(df, out_dir / f"02_特征原值表_{score_date}.csv")


def save_03_normalized_values(df: pd.DataFrame, out_dir: Path, score_date: str) -> None:
    """03 归一化值：主要用于模型复核，通常不作为业务主表。"""
    save_csv(df, out_dir / f"03_特征归一化值表_{score_date}.csv")


def save_04_contribution_values(df: pd.DataFrame, out_dir: Path, score_date: str) -> None:
    """04 特征贡献：解释 01 表分值；数据库子表通常优先写这张。"""
    save_csv(df, out_dir / f"04_特征贡献值表_{score_date}.csv")


def save_05_daily_monitor(df: pd.DataFrame, out_dir: Path, score_date: str) -> None:
    """05 每日监控：用于运行检查；是否入库可按监控需求决定。"""
    save_csv(df, out_dir / f"05_每日监控表_{score_date}.csv")


def save_06_unscoreable_vehicles(df: pd.DataFrame, out_dir: Path, score_date: str) -> None:
    """06 无法评分名单：用于排查数据质量；可选写入质量审计表。"""
    save_csv(df, out_dir / f"06_无法评分车辆名单_{score_date}.csv")


def save_07_missing_fill_records(df: pd.DataFrame, out_dir: Path, score_date: str) -> None:
    """07 缺失填充名单：用于复核填充过程；可选写入质量审计表。"""
    save_csv(df, out_dir / f"07_缺失值填充名单_{score_date}.csv")
