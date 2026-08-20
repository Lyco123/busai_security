# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import warnings
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from pandas.errors import PerformanceWarning

from model.vehicle.src.crud import save_scores, get_weights

# from utils.wasm_tool import result

warnings.filterwarnings("ignore", category=PerformanceWarning)

from model.vehicle.src.date_window import get_latest_score_date, get_output_month
from model.vehicle.src.feature_builder import build_feature_frames
from model.vehicle.src.utils.common import BatchPaths, MODELS_ROOT, SQL_DIR, build_batch_paths, find_latest_artifact, normalize_weight_month
from model.vehicle.src.utils.logger import logger


MODEL_FILE_NAME_MAP = {
    "energy": "能耗模型文件",
    "fault": "故障模型文件",
}

METADATA_FILE_NAME_MAP = {
    "energy": "能耗模型元数据",
    "fault": "故障模型元数据",
}

MODEL_NAME_MAP = {
    "energy": "车辆能耗模型",
    "fault": "车辆故障模型",
}

MODEL_ALIAS_MAP = {
    "energy": "能耗风险",
    "fault": "故障风险",
}

# === [修改1] 扩展为 5 张表 ===
SCORE_FILE_NAME_MAP = {
    "original_values": "原值表",
    "normalized_values": "归一化值表",
    "converted_values": "转换值表",
    "individual_scores": "个体分表",
    "risk_scores": "风险分表",
}

WEIGHT_SQL_FILE_NAME = "车辆画像权重SQL读取表.csv"
DEFAULT_TOTAL_SCORE_METHOD = "predict_proba_positive_class_times_100"
SCORE_ONLY_FEATURES = ["车辆属性_车辆品牌"]

@dataclass
class ModelBundle:
    task_name: str
    model_name: str
    model_alias: str
    model: object
    feature_names: list[str]  # 清洗后的模型输入特征名，用于内部取数
    predict_feature_names_raw: list[str]  # booster 中保存的原始特征名，用于 predict
    predict_name_map: dict[str, str]  # 清洗后特征名 -> booster 原始特征名
    score_feature_names: list[str]  # 评分输出特征，含额外解释特征
    full_feature_names: list[str]
    importance_norm: np.ndarray
    importance_softmax: np.ndarray
    feature_categories: dict[str, str]
    zero_rule_groups: set[str]
    total_score_method: str
    # [修改] 读取 SQL 局部权重，用于评分输出按一级、二级、三级回写。
    level_1_weight: float
    level_2_weight_map: dict[str, float]
    level_3_weight_map: dict[str, float]


class ScoreUpdater:
    def __init__(
        self,
        start_date: str,
        end_date: str,
        create_date: str,
        weight_month: str | None = None,
        batch_paths: BatchPaths | None = None,
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.create_date = create_date
        self.weight_month = normalize_weight_month(weight_month, create_date)
        self.create_month = get_output_month(create_date)
        self.batch_paths = batch_paths or build_batch_paths("score", start_date, end_date, create_date)
        self.score_date = ""
        self.df_raw_day = pd.DataFrame()
        self.df_model_day = pd.DataFrame()
        self.model_bundles: list[ModelBundle] = []
        self.weight_sql_df = pd.DataFrame()
        self.weight_start_time: str = ""
        self.brand_fault_share_map: dict[str, float] = {}
        self.brand_energy_share_map: dict[str, float] = {}

    @staticmethod
    def _softmax(values: np.ndarray) -> np.ndarray:
        if values.size == 0:
            return values
        safe_values = np.nan_to_num(values.astype(float), nan=0.0, posinf=0.0, neginf=0.0)
        shifted = safe_values - np.max(safe_values)
        exps = np.exp(shifted)
        denom = np.sum(exps)
        if denom <= 0:
            return np.full(len(values), 1.0 / len(values))
        return exps / denom

    @staticmethod
    def _to_weight_ratio(value: object) -> float:
        numeric = pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0.0).iloc[0]
        return float(numeric) / 100.0

    @staticmethod
    def _canonicalize_feature_name(name: str) -> str:
        text = str(name).strip()
        text = text.replace("开启次数", "开关次数")
        text = text.replace("(平台定义值)", "(平台定义域)")
        text = text.replace("N挡", "N档")
        text = text.replace("（", "(").replace("）", ")")
        return text

    @classmethod
    def _canonicalize_dataframe_columns(cls, df: pd.DataFrame) -> pd.DataFrame:
        """统一宽表列名，便于按清洗后的特征名取数。"""
        result = df.copy()
        result.columns = [cls._canonicalize_feature_name(column).replace(" ", "") for column in result.columns]
        return result
    
    @staticmethod
    def _auto_zero_rule_groups(feature_categories: dict[str, str]) -> set[str]:
        category_map: dict[str, list[str]] = {}
        for feature_name, category in feature_categories.items():
            category_map.setdefault(category, []).append(feature_name)

        zero_rule_groups = set()
        for category, feature_names in category_map.items():
            if category in {"驾驶不良行为", "车辆维修"}:
                zero_rule_groups.add(category)
                continue
            if feature_names and all(("次数" in name) or ("工单数" in name) or ("故障" in name) for name in feature_names):
                zero_rule_groups.add(category)
        return zero_rule_groups

    def _model_patterns(self, task_name: str) -> list[str]:
        return [
            f"{MODEL_FILE_NAME_MAP[task_name]}_{self.weight_month}_*.joblib",
            f"{MODEL_FILE_NAME_MAP[task_name]}_{self.weight_month}.joblib",
        ]

    def _metadata_patterns(self, task_name: str) -> list[str]:
        return [
            f"{METADATA_FILE_NAME_MAP[task_name]}_{self.weight_month}_*.json",
            f"{METADATA_FILE_NAME_MAP[task_name]}_{self.weight_month}.json",
        ]

    def _find_artifact_in_root(self, root_dir: Path, patterns: list[str]) -> Path | None:
        for pattern in patterns:
            path = find_latest_artifact(root_dir, pattern)
            if path is not None:
                return path
        return None

    async def _load_sql_weight_file(self):
        """直接从 SQL 导出权重表读取评分所需权重。"""
        # path = SQL_DIR / WEIGHT_SQL_FILE_NAME
        # if not path.exists():
        #     logger.error(f"未找到权重SQL文件: {path}")
        #     raise FileNotFoundError(f"未找到权重SQL文件: {path}")

        # 从数据库中取权重
        weight_db = await get_weights(self.start_date)
        if not weight_db:
            logger.warning(f"未找到权重文件，跳过该模型。")
            return pd.DataFrame()
        df = pd.DataFrame(weight_db)
        # df = pd.read_csv(path, low_memory=False)
        if df.empty:
            logger.error(f"权重SQL文件为空")
            raise ValueError(f"权重SQL文件为空")

        if "starttime" in df.columns and "start_time" not in df.columns:
            df = df.rename(columns={"starttime": "start_time"})

        required_columns = {
            "parent_name",
            "feature",
            "feature_name",
            "weight_rate1",
            "weight_rate2",
            "weight_rate3",
            "weight",
            "start_time",
        }
        missing_columns = required_columns.difference(df.columns)
        if missing_columns:
            logger.error(f"权重SQL文件缺少字段: {sorted(missing_columns)}")
            raise ValueError(f"权重SQL文件缺少字段: {sorted(missing_columns)}")

        for column in ["weight_rate1", "weight_rate2", "weight_rate3", "weight"]:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
        df["start_time_ts"] = pd.to_datetime(df["start_time"], errors="coerce")
        df = df[df["start_time_ts"].notna()].copy()
        if df.empty:
            logger.error("权重SQL文件的 start_time 全部无法解析")
            raise ValueError("权重SQL文件的 start_time 全部无法解析")

        month_mask = df["start_time_ts"].dt.strftime("%Y-%m") == self.weight_month
        if not month_mask.any():
            logger.error(f"权重SQL文件中不存在 weight_month={self.weight_month} 的记录")
            raise ValueError(f"权重SQL文件中不存在 weight_month={self.weight_month} 的记录")

        df = df[month_mask].copy()
        latest_start_time = df["start_time_ts"].max()
        df = df[df["start_time_ts"] == latest_start_time].copy()
        self.weight_start_time = latest_start_time.strftime("%Y-%m-%d %H:%M:%S")
        self.weight_sql_df = df.reset_index(drop=True)
        logger.info(f"已读取权重SQL，使用 start_time={self.weight_start_time}，共 {len(self.weight_sql_df)} 行")

    @staticmethod
    def _build_feature_categories(feature_names: list[str], group_map: dict[str, list[str]] | None) -> dict[str, str]:
        categories: dict[str, str] = {}
        if isinstance(group_map, dict) and group_map:
            for category, features in group_map.items():
                for feature_name in features:
                    categories[feature_name] = category
        for feature_name in feature_names:
            categories.setdefault(feature_name, feature_name.split("_", 1)[0] if "_" in feature_name else "其他")
        return categories

    @classmethod
    def _build_sql_feature_candidates(cls, row: pd.Series) -> list[str]:
        parent_name = str(row.get("parent_name", "")).strip()
        feature_name = str(row.get("feature_name", "")).strip()
        feature_value = str(row.get("feature", "")).strip()

        raw_feature = feature_value
        for prefix in ["能耗风险_", "故障风险_"]:
            if raw_feature.startswith(prefix):
                raw_feature = raw_feature[len(prefix):]
                break

        display_name = feature_name
        alt_display_name = display_name.replace("开关次数", "开启次数").replace("(平台定义域)", "(平台定义值)").replace("N档", "N挡")

        candidates = {raw_feature}
        if parent_name:
            candidates.add(f"{parent_name}_{display_name}")
            candidates.add(f"{parent_name}_{alt_display_name}")
            if parent_name == "驾驶不良行为":
                candidates.add(f"{parent_name}_{display_name}_次数")
                candidates.add(f"{parent_name}_{alt_display_name}_次数")
            elif parent_name == "车辆维修" and display_name != "维修工单数":
                candidates.add(f"{parent_name}_{display_name}_次数")
                candidates.add(f"{parent_name}_{alt_display_name}_次数")

        expanded = set(candidates)
        for candidate in list(candidates):
            expanded.add(candidate.replace("开关次数", "开启次数"))
            expanded.add(candidate.replace("(平台定义域)", "(平台定义值)"))
            expanded.add(candidate.replace("N档", "N挡"))
        return sorted(expanded)

    def _build_weight_arrays(self, model_alias: str, feature_names: list[str], feature_categories: dict[str, str]):
        model_weight_df = self.weight_sql_df[self.weight_sql_df["feature"].astype(str).str.startswith(f"{model_alias}_")].copy()
        if model_weight_df.empty:
            logger.error(f"权重SQL文件中未找到模型 {model_alias} 的记录")
            raise ValueError(f"权重SQL文件中未找到模型 {model_alias} 的记录")

        provided_sum = float(model_weight_df["weight"].sum())
        if provided_sum <= 0:
            logger.error(f"模型 {model_alias} 的 weight 列无有效值")
            raise ValueError(f"模型 {model_alias} 的 weight 列无有效值")

        if provided_sum > 110:
            logger.warning(f"模型 {model_alias} 的 weight 合计为 {provided_sum:.4f}，疑似非全局权重，改用 weight_rate2 * weight_rate3 / 100 重建全局权重")
            model_weight_df["effective_global_weight"] = model_weight_df["weight_rate2"] * model_weight_df["weight_rate3"] / 100.0
        else:
            model_weight_df["effective_global_weight"] = model_weight_df["weight"]

        row_map: dict[str, pd.Series] = {}
        for _, row in model_weight_df.iterrows():
            for candidate in self._build_sql_feature_candidates(row):
                row_map.setdefault(self._canonicalize_feature_name(candidate), row)

        # MOD 2: Load SQL level-1/2/3 weights for weighted hierarchy output.
        level_1_values = pd.to_numeric(model_weight_df["weight_rate1"], errors="coerce").dropna()
        level_1_weight = self._to_weight_ratio(level_1_values.iloc[0]) if not level_1_values.empty else 0.0
        level_2_weight_map: dict[str, float] = {}
        level_2_source_df = model_weight_df.assign(parent_name=model_weight_df["parent_name"].astype(str).str.strip())
        for parent_name, group_df in level_2_source_df.groupby("parent_name"):
            if parent_name:
                values = pd.to_numeric(group_df["weight_rate2"], errors="coerce").dropna()
                level_2_weight_map[parent_name] = self._to_weight_ratio(values.iloc[0]) if not values.empty else 0.0

        raw_weights = []
        missing_features = []
        level_3_weight_map: dict[str, float] = {}
        for feature_name in feature_names:
            category = feature_categories.get(feature_name, "其他")
            level_2_weight_map.setdefault(category, 0.0)
            row = row_map.get(self._canonicalize_feature_name(feature_name))
            if row is None:
                missing_features.append(feature_name)
                raw_weights.append(0.0)
                level_3_weight_map[feature_name] = 0.0
            else:
                raw_weights.append(float(row.get("effective_global_weight", 0.0)))
                level_3_weight_map[feature_name] = self._to_weight_ratio(row.get("weight_rate3", 0.0))
                if level_2_weight_map.get(category, 0.0) <= 0.0:
                    level_2_weight_map[category] = self._to_weight_ratio(row.get("weight_rate2", 0.0))

        if missing_features:
            logger.warning(f"模型 {model_alias} 有 {len(missing_features)} 个特征未在权重SQL中匹配到，已按 0 处理")

        raw_weights = np.asarray(raw_weights, dtype=float)
        total = float(raw_weights.sum())
        if total <= 0:
            importance_norm = np.full(len(feature_names), 1.0 / len(feature_names))
            importance_softmax = np.full(len(feature_names), 1.0 / len(feature_names))
            logger.warning(f"模型 {model_alias} 的全局权重和为 0，已退化为均匀分配")
        else:
            importance_norm = raw_weights / total
            importance_softmax = self._softmax(raw_weights)

        return importance_norm, importance_softmax, level_1_weight, level_2_weight_map, level_3_weight_map

    def _load_model_bundle(self, task_name: str, model_name: str):
        """加载单个模型所需的模型文件、元数据和 SQL 权重。"""
        model_path = self._find_artifact_in_root(MODELS_ROOT, self._model_patterns(task_name))
        meta_path = self._find_artifact_in_root(MODELS_ROOT, self._metadata_patterns(task_name))

        if model_path is None:
            logger.error(f"未找到模型文件: {MODEL_FILE_NAME_MAP[task_name]}_{self.weight_month}_*.joblib")
            raise FileNotFoundError(f"未找到模型文件: {MODEL_FILE_NAME_MAP[task_name]}_{self.weight_month}_*.joblib")
        if meta_path is None:
            logger.error(f"未找到元数据文件: {METADATA_FILE_NAME_MAP[task_name]}_{self.weight_month}_*.json")
            raise FileNotFoundError(f"未找到元数据文件: {METADATA_FILE_NAME_MAP[task_name]}_{self.weight_month}_*.json")

        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        model = joblib.load(model_path)

        raw_feature_names = getattr(getattr(model, "get_booster", lambda: None)(), "feature_names", None)
        if not raw_feature_names:
            raw_feature_names = metadata.get("feature_names") or []

        if not raw_feature_names:
            logger.warning(f"元数据中无有效特征列表: {meta_path.name}")
            return

        feature_names = [self._canonicalize_feature_name(name).replace(" ", "") for name in raw_feature_names]
        predict_name_map = dict(zip(feature_names, raw_feature_names))

        score_feature_names = list(feature_names)
        for extra_feature in SCORE_ONLY_FEATURES:
            extra_clean = self._canonicalize_feature_name(extra_feature).replace(" ", "")
            if extra_clean not in score_feature_names:
                score_feature_names.append(extra_clean)

        feature_categories = self._build_feature_categories(score_feature_names, metadata.get("group_map"))
 
        importance_norm, importance_softmax, level_1_weight, level_2_weight_map, level_3_weight_map = self._build_weight_arrays(
            MODEL_ALIAS_MAP[task_name],
            score_feature_names,
            feature_categories,
        )
        zero_rule_groups = set(metadata.get("zero_rule_groups") or [])
        if not zero_rule_groups:
            zero_rule_groups = self._auto_zero_rule_groups(feature_categories)

        total_score_method = (
            metadata.get("scoring", {}).get("total_score_method")
            or metadata.get("total_score_method")
            or DEFAULT_TOTAL_SCORE_METHOD
        )

        self.model_bundles.append(
            ModelBundle(
                task_name=task_name,
                model_name=model_name,
                model_alias=MODEL_ALIAS_MAP[task_name],
                model=model,
                feature_names=feature_names,
                predict_feature_names_raw=list(raw_feature_names),
                predict_name_map=predict_name_map,
                score_feature_names=score_feature_names,
                full_feature_names=[f"{model_name}_{feature_name}" for feature_name in score_feature_names],               
                importance_norm=importance_norm,
                importance_softmax=importance_softmax,
                feature_categories=feature_categories,
                zero_rule_groups=zero_rule_groups,
                total_score_method=total_score_method,
                level_1_weight=level_1_weight,
                level_2_weight_map=level_2_weight_map,
                level_3_weight_map=level_3_weight_map,
            )
        )
        logger.info(
            f"已加载 {model_name}: 模型={model_path.name}，元数据={meta_path.name}，特征数={len(feature_names)}，评分输出特征数={len(score_feature_names)}，零值重分配分组={', '.join(sorted(zero_rule_groups)) if zero_rule_groups else '无'}"
        )

    async def load_inputs(self):
        """加载评分所需的模型、元数据、SQL 权重和评分日宽表。"""
        logger.chapter(
            f"评分更新 | 数据窗口: {self.start_date} ~ {self.end_date} | 创建日期: {self.create_date} | 权重月份: {self.weight_month} | 批次: {self.batch_paths.batch_name}"
        )
        await self._load_sql_weight_file()
        self._load_model_bundle("energy", "车辆能耗模型")
        self._load_model_bundle("fault", "车辆故障模型")
        if not self.model_bundles:
            raise ValueError("未加载到任何有效模型和权重，无法评分")

        raw_df, model_df = await build_feature_frames(self.start_date, self.end_date)

        raw_df = self._canonicalize_dataframe_columns(raw_df)
        model_df = self._canonicalize_dataframe_columns(model_df)

        if model_df.empty:
            raise ValueError("评分宽表为空，无法输出评分结果")

        self.score_date = get_latest_score_date(model_df, "信息_统计日期")

        # self._check_month_consistency()

        date_mask = model_df["信息_统计日期"].astype(str) == self.score_date
        self.df_model_day = model_df[date_mask].copy().sort_values(["信息_统计日期", "信息_车辆ID"]).reset_index(drop=True)
        self.df_raw_day = raw_df[raw_df["信息_统计日期"].astype(str) == self.score_date].copy().sort_values(
            ["信息_统计日期", "信息_车辆ID"]
        ).reset_index(drop=True)

        if self.df_model_day.empty:
            raise ValueError(f"日期范围内最新一天 {self.score_date} 没有可评分数据")

        self._build_brand_share_maps()

        logger.info(f"评分使用日期范围内最新一天数据: {self.score_date}，共 {len(self.df_model_day)} 行")

    @staticmethod
    def _normalize_brand_value(series: pd.Series) -> pd.Series:
        return series.fillna("").astype(str).str.strip()


    def _build_brand_share_maps(self):
        brand_series = self._normalize_brand_value(
            self.df_raw_day.get(
                "车辆属性_车辆品牌名称",
                self.df_raw_day.get(
                    "车辆属性_车辆品牌",
                    pd.Series("", index=self.df_raw_day.index),
                ),
            )
        )

        fault_source = pd.to_numeric(
            self.df_raw_day.get(
                "信息_故障当日总次数原始值",
                self.df_raw_day.get(
                    "故障_近7天每公里总次数",
                    pd.Series(0.0, index=self.df_raw_day.index),
                ),
            ),
            errors="coerce",
        ).fillna(0.0)

        fault_mask = fault_source > 0
        if fault_mask.any():
            fault_counts = brand_series[fault_mask].value_counts()
            total_fault = float(fault_counts.sum())
            self.brand_fault_share_map = {
                str(k).strip(): float(v / total_fault)
                for k, v in fault_counts.items()
                if str(k).strip() != ""
            }
        else:
            self.brand_fault_share_map = {}
        self.brand_fault_share_map.setdefault("", 0.0)

        energy_series = pd.to_numeric(
            self.df_raw_day.get(
                "指标_百公里能耗",
                pd.Series(np.nan, index=self.df_raw_day.index),
            ),
            errors="coerce",
        )

        valid_energy = energy_series.dropna()
        if not valid_energy.empty:
            energy_threshold = valid_energy.quantile(0.75)
            high_energy_mask = energy_series >= energy_threshold
            energy_counts = brand_series[high_energy_mask].value_counts()
            total_energy = float(energy_counts.sum())
            self.brand_energy_share_map = (
                {
                    str(k).strip(): float(v / total_energy)
                    for k, v in energy_counts.items()
                    if str(k).strip() != ""
                }
                if total_energy > 0
                else {}
            )
        else:
            self.brand_energy_share_map = {}
        self.brand_energy_share_map.setdefault("", 0.0)
        
    @staticmethod
    def _normalize_feature(
        series: pd.Series,
        method: str = "quantile",
        mapping: dict | None = None,
        zero_is_zero: bool = True,
    ) -> pd.Series:
        """
        统一归一化到 0~1：
        - log_quantile: 先 log1p 再分位数归一化
        - quantile: 直接分位数归一化
        - mapping/share_mapping: 类别映射，mapping 本身应为 0~1
        """
        if method in {"mapping", "share_mapping"}:
            text_series = series.astype(str).fillna("").str.strip()
            out = text_series.map(mapping or {}).fillna(0.0).astype(float).clip(0.0, 1.0)
            return out

        numeric = pd.to_numeric(series, errors="coerce")

        if zero_is_zero:
            active_mask = numeric > 0
        else:
            active_mask = numeric.notna()

        if active_mask.sum() == 0:
            return pd.Series(0.0, index=series.index, dtype=float)

        work = numeric.copy()
        if method == "log_quantile":
            work = np.log1p(work.clip(lower=0))

        ref = work[active_mask]
        q01 = ref.quantile(0.01)
        q99 = ref.quantile(0.99)

        if pd.isna(q01) or pd.isna(q99) or q99 <= q01:
            out = pd.Series(0.0, index=series.index, dtype=float)
            out.loc[active_mask] = 1.0
            if zero_is_zero:
                out.loc[numeric <= 0] = 0.0
            return out

        out = ((work - q01) / (q99 - q01)).clip(0, 1)
        out = out.fillna(0.0)

        if zero_is_zero:
            out.loc[numeric <= 0] = 0.0

        return out

    def _get_normalize_method(self, bundle: ModelBundle, feature_name: str) -> tuple[str, dict | None, str]:
        """
        返回：
        - method: 归一化方法名
        - mapping: 映射字典
        - method_desc: 日志说明
        """
        if feature_name == "车辆属性_车辆品牌":
            if bundle.task_name == "fault":
                return "share_mapping", self.brand_fault_share_map, "share_mapping(故障品牌占比, 0-1)"
            if bundle.task_name == "energy":
                return "share_mapping", self.brand_energy_share_map, "share_mapping(高能耗品牌占比, 0-1)"

        mapping_features = {
            # 后续如有人工类别映射，可在这里补充，数值必须是 0~1
            # "某个类别特征": {"A": 0.2, "B": 0.5, "C": 0.8}
        }

        if feature_name in mapping_features:
            return "mapping", mapping_features[feature_name], "mapping(人工映射, 0-1)"

        log_keywords = ["次数", "时长", "工单数", "故障", "报警", "充电量", "充电次数"]
        if any(keyword in feature_name for keyword in log_keywords):
            return "log_quantile", None, "log_quantile(log1p + 分位数归一化, 0-1)"

        return "quantile", None, "quantile(分位数归一化, 0-1)"
    

    def _predict_total_score(self, bundle: ModelBundle, X_input: pd.DataFrame) -> np.ndarray:
        """基于正类概率生成 0-100 的一级模型总分。"""
        if not hasattr(bundle.model, "predict_proba"):
            raise AttributeError(f"{bundle.model_name} 不支持 predict_proba，无法生成总分")

        prob = np.asarray(bundle.model.predict_proba(X_input), dtype=float)
        if prob.ndim != 2 or prob.shape[1] < 2:
            raise ValueError(f"{bundle.model_name} 的 predict_proba 输出格式异常: {prob.shape}")

        logger.info(f"[{bundle.model_name}] 总分生成方法: predict_proba(prob[:, 1])")
        return np.clip(prob[:, 1], 0.0, 1.0) * 100.0

    
   # === [修改4] 新评分主逻辑：归一化值 -> 转换值/个体分/风险分 ===
    @staticmethod
    def _compute_scaled_feature_scores(
        normalized_matrix: np.ndarray,
        feature_weight_vector: np.ndarray,
        total_score: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        返回：
        - scaling_factors: 缩放因子
        - converted_scores: 转换值 = 归一化值 × 缩放因子
        - individual_scores: 个体分 = 归一化值 × 特征基础权重
        - risk_scores: 风险分 = 个体分 × 缩放因子
        """
        normalized_matrix = np.nan_to_num(
            np.asarray(normalized_matrix, dtype=float),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        feature_weight_vector = np.nan_to_num(
            np.asarray(feature_weight_vector, dtype=float).reshape(1, -1),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        total_score = np.nan_to_num(
            np.asarray(total_score, dtype=float),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )

        individual_scores = normalized_matrix * feature_weight_vector
        individual_sum = individual_scores.sum(axis=1, keepdims=True)

        scaling_factors = np.divide(
            total_score.reshape(-1, 1),
            individual_sum,
            out=np.zeros((len(total_score), 1), dtype=float),
            where=individual_sum > 1e-12,
        )

        converted_scores = normalized_matrix * scaling_factors
        risk_scores = individual_scores * scaling_factors

        return scaling_factors, converted_scores, individual_scores, risk_scores


    def _build_ordered_feature_columns(self):
        level_1 = []
        level_2 = []
        level_3 = []
        for bundle in self.model_bundles:
            if bundle.model_name not in level_1:
                level_1.append(bundle.model_name)
            for feature_name in bundle.score_feature_names:
                level_2_name = f"{bundle.model_name}_{bundle.feature_categories[feature_name]}"
                if level_2_name not in level_2:
                    level_2.append(level_2_name)
            for full_feature_name in bundle.full_feature_names:
                if full_feature_name not in level_3:
                    level_3.append(full_feature_name)
        return level_1, level_2, level_3

    def _get_meta_series(self, column_name: str) -> pd.Series:
        if column_name in self.df_model_day.columns:
            return self.df_model_day[column_name]
        if column_name in self.df_raw_day.columns:
            return self.df_raw_day[column_name]
        return pd.Series(pd.NA, index=self.df_model_day.index)

    # === [修改5] 抽元信息表，简化 build_outputs 表达 ===
    def _build_meta_frame(self) -> pd.DataFrame:
        created_col = "创建日期"
        stat_col = "统计日期"
        plate_col = "车牌号"
        bus_id_col = "车辆自编号ID"
        company_id_col = "公司id"
        company_name_col = "公司名称"
        src_stat_col = "信息_统计日期"
        src_vehicle_col = "信息_车辆ID"
        src_bus_id_col = "信息_车辆自编号ID"
        src_plate_col = "信息_车牌号"
        src_company_id_col = "信息_公司ID"
        src_company_name_col = "信息_公司名称"

        meta = pd.DataFrame(
            {
                stat_col: pd.to_datetime(self.df_model_day[src_stat_col]).dt.strftime("%Y-%m-%d"),
                "obuid": self.df_model_day[src_vehicle_col],
                plate_col: self._get_meta_series(src_plate_col),
                bus_id_col: self._get_meta_series(src_bus_id_col),
                company_id_col: self._get_meta_series(src_company_id_col),
                company_name_col: self._get_meta_series(src_company_name_col),
            }
        )
        meta[created_col] = self.create_date
        return meta

    # === [修改6] 抽单模型输入准备，简化 build_outputs 表达 ===
    def _prepare_model_inputs(
        self,
        bundle: ModelBundle,
    ) -> tuple[pd.DataFrame, list[pd.Series], np.ndarray, np.ndarray, np.ndarray]:
        score_feature_names = bundle.score_feature_names

        X_input = pd.DataFrame(index=self.df_model_day.index)
        raw_series_list: list[pd.Series] = []
        raw_numeric_matrix = []
        normalized_matrix = []
        feature_weight_vector = []

        method_summary: dict[str, dict[str, object]] = {}

        for feature_name in score_feature_names:
            raw_obj_series = self.df_raw_day.get(
                feature_name,
                pd.Series(pd.NA, index=self.df_raw_day.index),
            )
            model_obj_series = self.df_model_day.get(
                feature_name,
                pd.Series(pd.NA, index=self.df_model_day.index),
            )

            if feature_name == "车辆属性_车辆品牌":
                model_series = pd.to_numeric(
                    pd.Series(model_obj_series, index=self.df_model_day.index),
                    errors="coerce",
                ).fillna(0.0)

                raw_display_series = self._normalize_brand_value(
                    self.df_raw_day.get(
                        "车辆属性_车辆品牌名称",
                        pd.Series(raw_obj_series, index=self.df_raw_day.index),
                    )
                )
                model_display_series = self._normalize_brand_value(
                    self.df_model_day.get(
                        "车辆属性_车辆品牌名称",
                        pd.Series(model_obj_series, index=self.df_model_day.index),
                    )
                )
                source_series = raw_display_series if raw_display_series.str.strip().ne("").any() else model_display_series
                raw_numeric = model_series.copy()

            else:
                raw_series = pd.to_numeric(
                    pd.Series(raw_obj_series, index=self.df_raw_day.index),
                    errors="coerce",
                )
                model_series = pd.to_numeric(
                    pd.Series(model_obj_series, index=self.df_model_day.index),
                    errors="coerce",
                ).fillna(0.0)

                source_series = raw_series if raw_series.notna().any() else model_series
                raw_numeric = pd.to_numeric(source_series, errors="coerce")

            method, mapping, method_desc = self._get_normalize_method(bundle, feature_name)

            normalized_series = self._normalize_feature(
                source_series,
                method=method,
                mapping=mapping,
                zero_is_zero=True,
            ).fillna(0.0)

            source_numeric = pd.to_numeric(source_series, errors="coerce")
            method_summary.setdefault(
                method_desc,
                {
                    "feature_count": 0,
                    "empty_count": 0,
                    "all_zero_count": 0,
                },
            )
            method_summary[method_desc]["feature_count"] += 1

            if source_numeric.notna().sum() == 0:
                method_summary[method_desc]["empty_count"] += 1

            if normalized_series.max(skipna=True) == 0:
                method_summary[method_desc]["all_zero_count"] += 1

            category = bundle.feature_categories.get(feature_name, "其他")
            feature_weight = (
                bundle.level_1_weight
                * bundle.level_2_weight_map.get(category, 0.0)
                * bundle.level_3_weight_map.get(feature_name, 0.0)
            )

            # 只有模型真实输入特征才进入 X_input；
            # 额外解释特征，比如车辆品牌，只参与输出解释，不参与 predict。
            if feature_name in bundle.predict_name_map:
                X_input[bundle.predict_name_map[feature_name]] = model_series

            raw_series_list.append(source_series)
            raw_numeric_matrix.append(
                pd.to_numeric(raw_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=float)
            )
            normalized_matrix.append(normalized_series.to_numpy(dtype=float))
            feature_weight_vector.append(feature_weight)

        if bundle.predict_feature_names_raw:
            X_input = X_input.reindex(columns=bundle.predict_feature_names_raw)

        summary_parts = []
        for method_desc, stats in method_summary.items():
            summary_parts.append(
                f"{method_desc}: 特征数={stats['feature_count']}, "
                f"原值全空={stats['empty_count']}, "
                f"归一化全0={stats['all_zero_count']}"
            )

        logger.info(f"[{bundle.model_name}] 归一化方法汇总 -> " + " | ".join(summary_parts))

        return (
            X_input,
            raw_series_list,
            np.column_stack(raw_numeric_matrix) if raw_numeric_matrix else np.empty((len(self.df_model_day), 0)),
            np.column_stack(normalized_matrix) if normalized_matrix else np.empty((len(self.df_model_day), 0)),
            np.asarray(feature_weight_vector, dtype=float),
        )

    def build_outputs(self):
        """构建五张评分结果表。"""
        created_col = "创建日期"
        stat_col = "统计日期"
        total_col = "总分"
        plate_col = "车牌号"
        bus_id_col = "车辆自编号ID"
        company_id_col = "公司id"
        company_name_col = "公司名称"

        meta = self._build_meta_frame()

        # === [修改8] 改为 5 张表 ===
        original_df = meta.copy()
        normalized_df = meta.copy()
        converted_df = meta.copy()
        individual_df = meta.copy()
        risk_df = meta.copy()

        weighted_total_series = np.zeros(len(self.df_model_day), dtype=float)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", PerformanceWarning)
            for bundle in self.model_bundles:
                # X_input, raw_series_list, raw_value_array, normalized_input_array = self._prepare_model_inputs(bundle)
                X_input, raw_series_list, raw_value_array, normalized_input_array, feature_weight_array = self._prepare_model_inputs(bundle)
                if X_input.empty:
                    continue

                total_score = self._predict_total_score(bundle, X_input)
                _, converted_scores, individual_scores, risk_scores = self._compute_scaled_feature_scores(
                    normalized_input_array,
                    feature_weight_array,
                    total_score,
                )


                group_index_map: dict[str, list[int]] = {}
                for idx, feature_name in enumerate(bundle.score_feature_names):
                    group_index_map.setdefault(bundle.feature_categories[feature_name], []).append(idx)

                # 模型级加权总分保留原有口径
                weighted_model_score = total_score * bundle.level_1_weight
                weighted_total_series += weighted_model_score

                # 一级列
                original_df[bundle.model_name] = weighted_model_score
                normalized_df[bundle.model_name] = total_score
                converted_df[bundle.model_name] = total_score
                individual_df[bundle.model_name] = weighted_model_score
                risk_df[bundle.model_name] = weighted_model_score

                # 二级列
                for group_name, indices in group_index_map.items():
                    level_2_name = f"{bundle.model_name}_{group_name}"
                    # original_df[level_2_name] = np.nanmean(raw_value_array[:, indices], axis=1)
                    original_df[level_2_name] = np.nan# 二级原值为空
                    normalized_df[level_2_name] = np.nanmean(normalized_input_array[:, indices], axis=1)
                    converted_df[level_2_name] = np.nanmean(converted_scores[:, indices], axis=1)
                    individual_df[level_2_name] = individual_scores[:, indices].sum(axis=1)
                    risk_df[level_2_name] = risk_scores[:, indices].sum(axis=1)

                # 三级列
                for feature_idx, full_name in enumerate(bundle.full_feature_names):
                    original_df[full_name] = raw_series_list[feature_idx]
                    normalized_df[full_name] = normalized_input_array[:, feature_idx]
                    converted_df[full_name] = converted_scores[:, feature_idx]
                    individual_df[full_name] = individual_scores[:, feature_idx]
                    risk_df[full_name] = risk_scores[:, feature_idx]

        level_1_cols, level_2_cols, level_3_cols = self._build_ordered_feature_columns()
        total_score_series = pd.Series(weighted_total_series, index=self.df_model_day.index)

        for frame in [original_df, normalized_df, converted_df, individual_df, risk_df]:
            frame[total_col] = total_score_series

        ordered_columns = [
            created_col,
            stat_col,
            "obuid",
            bus_id_col,
            plate_col,
            company_id_col,
            company_name_col,
            total_col,
        ] + level_1_cols + level_2_cols + level_3_cols

        for frame in [original_df, normalized_df, converted_df, individual_df, risk_df]:
            for column in ordered_columns:
                if column not in frame.columns:
                    frame[column] = pd.NA

        return (
            original_df[ordered_columns],
            normalized_df[ordered_columns],
            converted_df[ordered_columns],
            individual_df[ordered_columns],
            risk_df[ordered_columns],
        )

    async def save_outputs(self):
        """将五张评分结果表写入当前批次目录，并回写数据库。"""
        original_df, normalized_df, converted_df, individual_df, risk_df = self.build_outputs()
        output_paths = {
            "original_values": self.batch_paths.scores_dir / f"{SCORE_FILE_NAME_MAP['original_values']}_{self.score_date}.csv",
            "normalized_values": self.batch_paths.scores_dir / f"{SCORE_FILE_NAME_MAP['normalized_values']}_{self.score_date}.csv",
            "converted_values": self.batch_paths.scores_dir / f"{SCORE_FILE_NAME_MAP['converted_values']}_{self.score_date}.csv",
            "individual_scores": self.batch_paths.scores_dir / f"{SCORE_FILE_NAME_MAP['individual_scores']}_{self.score_date}.csv",
            "risk_scores": self.batch_paths.scores_dir / f"{SCORE_FILE_NAME_MAP['risk_scores']}_{self.score_date}.csv",
        }
        stale_missing_path = self.batch_paths.scores_dir / f"缺失值检查表_{self.score_date}.csv"
        if stale_missing_path.exists():
            stale_missing_path.unlink()
            logger.info(f"已删除历史遗留文件: {stale_missing_path.name}")

        original_df.to_csv(output_paths["original_values"], index=False, encoding="utf-8-sig")
        normalized_df.to_csv(output_paths["normalized_values"], index=False, encoding="utf-8-sig")
        converted_df.to_csv(output_paths["converted_values"], index=False, encoding="utf-8-sig")
        individual_df.to_csv(output_paths["individual_scores"], index=False, encoding="utf-8-sig")
        risk_df.to_csv(output_paths["risk_scores"], index=False, encoding="utf-8-sig")

        # 数据对接：回写数据库；这里只扩展结果字典内容 
        original_df = original_df.apply(lambda col: pd.to_numeric(col, errors='coerce') if col.dtype == 'float64' else col)
        normalized_df = normalized_df.apply(lambda col: pd.to_numeric(col, errors='coerce') if col.dtype == 'float64' else col)
        converted_df = converted_df.apply(lambda col: pd.to_numeric(col, errors='coerce') if col.dtype == 'float64' else col)
        individual_df = individual_df.apply(lambda col: pd.to_numeric(col, errors='coerce') if col.dtype == 'float64' else col)
        risk_df = risk_df.apply(lambda col: pd.to_numeric(col, errors='coerce') if col.dtype == 'float64' else col)

        result = {}
        result['original_df'] = original_df          # 原值表
        result['normalized_df'] = normalized_df      # 归一化值表（中间层）
        result['converted_df'] = converted_df        # 转换值表
        result['individual_df'] = individual_df      # 个体分表（中间层）
        result['risk_df'] = risk_df                  # 风险分表

        await save_scores(result, self.start_date, self.end_date)

        for path in output_paths.values():
            logger.info(f"评分结果已保存: {path}")

    async def run(self):
        await self.load_inputs()
        await self.save_outputs()
