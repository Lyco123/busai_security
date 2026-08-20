# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import f1_score, precision_recall_curve, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

from model.vehicle.src.crud import save_weights_dict

try:
    from xgboost import XGBClassifier
except ImportError:  # pragma: no cover
    XGBClassifier = None

from model.vehicle.src.date_window import get_output_month
from model.vehicle.src.feature_builder import build_feature_table
from model.vehicle.src.utils.common import BatchPaths, build_batch_paths, normalize_weight_month
from model.vehicle.src.utils.logger import logger


MODEL_NAME_MAP = {
    "energy": "车辆能耗模型",
    "fault": "车辆故障模型",
}

MODEL_ALIAS_MAP = {
    "energy": "能耗风险",
    "fault": "故障风险",
}

MODEL_FILE_NAME_MAP = {
    "energy": "能耗模型文件",
    "fault": "故障模型文件",
}

METADATA_FILE_NAME_MAP = {
    "energy": "能耗模型元数据",
    "fault": "故障模型元数据",
}

WEIGHT_EXPORT_FILE_NAME = "车辆画像权重SQL读取表"
LEVEL_1_WEIGHT_MAP = {
    "车辆能耗模型": 0.6,
    "车辆故障模型": 0.4,
}

DISPLAY_NAME_MAP = {
    "空气压缩机开启次数": "空气压缩机开关次数",
    "单体高低电压差(平台定义值)": "单体高低电压差(平台定义域)",
    "停车不挂N挡": "停车不挂N档",
}


class WeightUpdater:
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
        self.batch_paths = batch_paths or build_batch_paths("weight", start_date, end_date, create_date)
        self.df_wide = pd.DataFrame()

    async def load_training_data(self):
        """读取训练窗口内全部数据并构建训练宽表。"""
        logger.chapter(
            f"权重更新 | 数据窗口: {self.start_date} ~ {self.end_date} | 创建日期: {self.create_date} | 输出月份: {self.weight_month} | 批次: {self.batch_paths.batch_name}"
        )
        if self.weight_month != self.create_month:
            logger.warning(f"weight_month={self.weight_month} 与 create_date 所在月份 {self.create_month} 不一致")

        self.df_wide = await build_feature_table(self.start_date, self.end_date)
        if self.df_wide.empty:
            raise ValueError("训练宽表为空，无法更新权重")
        self.df_wide = self._calculate_labels(self.df_wide)

    def _calculate_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """基于当前宽表生成高能耗和未来 1 天故障标签。"""
        logger.info("开始构建训练标签")
        result = df.copy()
        result["信息_统计日期"] = pd.to_datetime(result["信息_统计日期"])

        if {"指标_百公里能耗", "信息_线路ID"}.issubset(result.columns):
            mean_energy = result.groupby(["信息_统计日期", "信息_线路ID"])["指标_百公里能耗"].transform("mean")
            result["Target_高能耗"] = ((result["指标_百公里能耗"] > mean_energy * 1.15) & (mean_energy > 0)).astype(int)
            pos_count = int(result["Target_高能耗"].sum())
            logger.info(f"[高能耗] 正样本数: {pos_count} ({pos_count / len(result):.2%})")

        fault_source_col = "信息_故障当日总次数原始值" if "信息_故障当日总次数原始值" in result.columns else "故障_近7天每公里总次数"
        if fault_source_col in result.columns:
            result = result.sort_values(["信息_车辆ID", "信息_统计日期"]).copy()
            future_faults = result.groupby("信息_车辆ID")[fault_source_col].shift(-1)
            result["Target_未来1天故障"] = (future_faults.fillna(0) > 0).astype(int)
            pos_count = int(result["Target_未来1天故障"].sum())
            logger.info(f"[未来1天故障] 正样本数: {pos_count} ({pos_count / len(result):.2%})")

        result["信息_统计日期"] = result["信息_统计日期"].dt.strftime("%Y-%m-%d")
        return result

    @staticmethod
    def _prepare_features(df: pd.DataFrame, exclude_cols: list[str] | None = None):
        """筛出可训练的数值特征并按训练口径补值。"""
        exclude_cols = exclude_cols or []
        base_prefixes = ["信息_", "Target_", "指标_", "Unnamed"]



        # candidates = [column for column in df.columns if np.issubdtype(df[column].dtype, np.number)]
        # 修改后：使用 select_dtypes 获取数值列名
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        candidates = [col for col in df.columns if col in numeric_cols]
        candidates = [column for column in candidates if not any(str(column).startswith(prefix) for prefix in base_prefixes)]
        candidates = [column for column in candidates if column not in exclude_cols]

        result = df.copy()
        for column in candidates:
            result[column] = pd.to_numeric(result[column], errors="coerce")
            result[column] = result[column].fillna(0)
        return result, candidates

    @staticmethod
    def _find_best_threshold(y_true, y_prob, task_name: str) -> float:
        precisions, recalls, thresholds = precision_recall_curve(y_true, y_prob)
        thresholds = np.append(thresholds, 1)

        if task_name == "fault":
            beta = 1.25
            f_beta = ((1 + beta**2) * precisions * recalls) / ((beta**2 * precisions) + recalls + 1e-8)
            valid_mask = thresholds >= 0.35
            if np.sum(valid_mask) > 0:
                masked = f_beta.copy()
                masked[~valid_mask] = -1
                return float(thresholds[np.argmax(masked)])
            return 0.45

        f1_5 = (3.25 * precisions * recalls) / (2.25 * precisions + recalls + 1e-8)
        return float(max(thresholds[np.argmax(f1_5)], 0.35))

    def _build_model(self, task_name: str, pos_ratio: float):
        use_xgboost = XGBClassifier is not None
        if task_name == "fault":
            params = {
                "n_estimators": 250,
                "max_depth": 6,
                "learning_rate": 0.02,
                "scale_pos_weight": 5.0,
                "min_child_weight": 4,
                "gamma": 0.1,
                "reg_alpha": 0.1,
                "subsample": 0.85,
                "colsample_bytree": 0.75,
                "random_state": 42,
                "n_jobs": -1,
                "eval_metric": "logloss",
                "importance_type": "weight",
            }
        else:
            params = {
                "n_estimators": 200,
                "max_depth": 5,
                "learning_rate": 0.035,
                "scale_pos_weight": min(pos_ratio * 1.2, 5),
                "min_child_weight": 5,
                "reg_alpha": 1.0,
                "gamma": 0.1,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "random_state": 42,
                "n_jobs": -1,
                "importance_type": "weight",
            }

        if use_xgboost:
            return XGBClassifier(**params)

        logger.warning("xgboost 未安装，回退到 GradientBoostingClassifier")
        return GradientBoostingClassifier(
            n_estimators=min(params["n_estimators"], 200),
            learning_rate=params["learning_rate"],
            max_depth=params["max_depth"],
            random_state=params["random_state"],
        )

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

    def _extract_importance_views(self, model, features: list[str]):
        if not features:
            return np.array([]), np.array([]), np.array([])

        raw_importance = np.asarray(getattr(model, "feature_importances_", np.zeros(len(features))), dtype=float)
        raw_importance = np.nan_to_num(raw_importance, nan=0.0, posinf=0.0, neginf=0.0)
        raw_importance = np.clip(raw_importance, a_min=0.0, a_max=None)

        total = float(raw_importance.sum())
        if total <= 0:
            importance_norm = np.full(len(features), 1.0 / len(features))
            importance_softmax = np.full(len(features), 1.0 / len(features))
        else:
            importance_norm = raw_importance / total
            importance_softmax = self._softmax(raw_importance)
        return raw_importance, importance_norm, importance_softmax

    @staticmethod
    def _group_feature_map(features: list[str]) -> dict[str, list[str]]:
        group_map: dict[str, list[str]] = {}
        for feature in features:
            category = feature.split("_", 1)[0] if "_" in feature else "其他"
            group_map.setdefault(category, []).append(feature)
        return group_map

    @staticmethod
    def _select_zero_rule_groups(group_map: dict[str, list[str]]) -> list[str]:
        zero_rule_groups = []
        for group_name, group_features in group_map.items():
            if group_name in {"驾驶不良行为", "车辆维修"}:
                zero_rule_groups.append(group_name)
                continue
            if group_features and all(("次数" in feature) or ("工单数" in feature) or ("故障" in feature) for feature in group_features):
                zero_rule_groups.append(group_name)
        return sorted(set(zero_rule_groups))

    def _weight_export_file_path(self) -> Path:
        return self.batch_paths.weights_dir / f"{WEIGHT_EXPORT_FILE_NAME}_{self.weight_month}_{self.create_date}.csv"

    def _model_file_path(self, task_name: str) -> Path:
        return self.batch_paths.models_dir / f"{MODEL_FILE_NAME_MAP[task_name]}_{self.weight_month}_{self.create_date}.joblib"

    def _metadata_file_path(self, task_name: str) -> Path:
        return self.batch_paths.models_dir / f"{METADATA_FILE_NAME_MAP[task_name]}_{self.weight_month}_{self.create_date}.json"

    def _clear_task_artifacts(self, task_name: str):
        for path in [self._model_file_path(task_name), self._metadata_file_path(task_name)]:
            if path.exists():
                path.unlink()

    @staticmethod
    def _feature_display_name(raw_feature_name: str) -> str:
        feature_leaf = raw_feature_name.split("_", 1)[1] if "_" in raw_feature_name else raw_feature_name
        if feature_leaf.endswith("_次数"):
            feature_leaf = feature_leaf[:-3]
        return DISPLAY_NAME_MAP.get(feature_leaf, feature_leaf)

    @staticmethod
    def _feature_sql_name(category: str, display_name: str) -> str:
        if category == "驾驶不良行为":
            return f"{category}_{display_name}_次数"
        return f"{category}_{display_name}"

    def _write_model_and_metadata(
        self,
        task_name: str,
        model,
        features: list[str],
        threshold: float,
        metrics: dict[str, float],
        group_map: dict[str, list[str]],
        zero_rule_groups: list[str],
        weight_export_path: Path,
    ):
        model_name = MODEL_NAME_MAP[task_name]
        model_path = self._model_file_path(task_name)
        joblib.dump(model, model_path)

        metadata = {
            "task_name": task_name,
            "model_name": model_name,
            "model_alias": MODEL_ALIAS_MAP[task_name],
            "batch_name": self.batch_paths.batch_name,
            "weight_month": self.weight_month,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "create_date": self.create_date,
            "feature_names": features,
            "group_map": group_map,
            "zero_rule_groups": zero_rule_groups,
            "threshold": threshold,
            "metrics": metrics,
            "weight_files": {
                "weight_export_file": weight_export_path.name,
            },
            "scoring": {
                "total_score_method": "predict_proba_positive_class_times_100",
                "shap_decompose_method": "row_normalize_softmax_then_times_total_score",
                "raw_risk_method": "normalized_input_times_importance_norm_softmax_then_renormalize",
            },
            "preprocess": {
                "feature_fillna": 0.0,
                "feature_builder": "build_feature_table",
                "normalized_value_method": "score_day_quantile_0.01_0.99",
            },
        }
        metadata_path = self._metadata_file_path(task_name)
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info(f"模型文件已保存: {model_path.name}")
        logger.info(f"元数据已保存: {metadata_path.name}")
        logger.info(f"{model_name} 启用零分重分配分组: {', '.join(zero_rule_groups) if zero_rule_groups else '无'}")

    def _build_weight_export_df(self, task_results: list[dict[str, object]]) -> pd.DataFrame:
        rows = []
        for task_result in task_results:
            global_weight_df = task_result.get("global_weight_df")
            model_name = str(task_result.get("model_name", ""))
            model_alias = str(task_result.get("model_alias", ""))
            if not isinstance(global_weight_df, pd.DataFrame) or global_weight_df.empty:
                continue

            level_1_weight = float(LEVEL_1_WEIGHT_MAP.get(model_name, 0.0))
            group_weights = global_weight_df.groupby("二级类别")["三级全局权重"].sum().to_dict()

            for _, row in global_weight_df.iterrows():
                category = str(row["二级类别"])
                raw_feature_name = str(row["原始特征名称"])
                display_name = self._feature_display_name(raw_feature_name)
                feature_sql_name = self._feature_sql_name(category, display_name)

                level_2_weight = float(group_weights.get(category, 0.0))
                level_3_global_weight = float(row["三级全局权重"])
                level_3_local_weight = level_3_global_weight / level_2_weight if level_2_weight > 1e-12 else 0.0

                rows.append(
                    {
                        "quota_level": 3,
                        "parent_id": f"车辆画像-{model_alias}-{category}",
                        "parent_name": category,
                        "quota_id": f"车辆画像-{model_alias}-{category}-{display_name}",
                        "quota_name": f"{model_alias}_{category}_{display_name}",
                        "feature": f"{model_alias}_{feature_sql_name}",
                        "feature_name": display_name,
                        "weight_rate1": round(level_1_weight * 100, 4),
                        "weight_rate2": round(level_2_weight * 100, 4),
                        "weight_rate3": round(level_3_local_weight * 100, 4),
                        # "weight": round(level_3_global_weight * 100, 4), #修改
                        "weight": round(level_1_weight * level_2_weight * level_3_local_weight * 100, 4),

                        "start_time": f"{self.create_date} 00:00:00",
                    }
                )

        export_df = pd.DataFrame(
            rows,
            columns=[
                "quota_level",
                "parent_id",
                "parent_name",
                "quota_id",
                "quota_name",
                "feature",
                "feature_name",
                "weight_rate1",
                "weight_rate2",
                "weight_rate3",
                "weight",
                "start_time",
            ],
        )
        if export_df.empty:
            return export_df
        for column in ["weight_rate1", "weight_rate2", "weight_rate3" ,"weight"]:
            export_df[column] = pd.to_numeric(export_df[column], errors="coerce").fillna(0.0)
        return export_df.sort_values(["parent_id", "weight", "quota_name"], ascending=[True, False, True]).reset_index(drop=True)

    async def _save_weight_export_df(self, task_results: list[dict[str, object]]) -> Path:
        export_df = self._build_weight_export_df(task_results)
        output_path = self._weight_export_file_path()
        export_df.to_csv(output_path, index=False, encoding="utf-8-sig")
        await save_weights_dict(self.start_date,self.end_date,export_df.to_dict("records"))
        logger.info(f"权重导出表已保存: {output_path.name}")
        return output_path

    async def _run_task(self, task_name: str) -> dict[str, object]:
        """训练单个模型并返回该模型的三级全局权重结果。"""
        df = self.df_wide.copy()
        model_name = MODEL_NAME_MAP[task_name]
        model_alias = MODEL_ALIAS_MAP[task_name]

        if task_name == "energy":
            target_col = "Target_高能耗"
            mask = (df["指标_百公里能耗"] > 0) & (df["车辆运营_运营里程"] > 0) & (df["车辆运营_运营时长"] > 0)
            exclude = [
                "Target_高能耗",
                "Target_未来1天故障",
                "指标_百公里能耗",
                "故障_近7天每公里总次数",
                "车辆运营_线路站点数",
                "车辆运营_线路转弯点数",
                "车辆运营_运营里程",
            ]
        else:
            target_col = "Target_未来1天故障"
            mask = (df["指标_百公里能耗"] > 40) & (df["车辆运营_运营里程"] > 40) & (df["车辆运营_运营时长"] > (40.0 / 3600.0))
            exclude = [
                "Target_高能耗",
                "Target_未来1天故障",
                "指标_百公里能耗",
                "故障_近7天每公里总次数",
                "车辆运营_线路站点数",
                "车辆运营_线路转弯点数",
                "车辆运营_运营里程",
            ]

        df = df[mask].copy()
        logger.info(f"[{task_name.upper()}] 样本清洗后 {len(df)} 行")
        if df.empty or target_col not in df.columns:
            self._clear_task_artifacts(task_name)
            logger.warning(f"{model_name} 无可用训练样本")
            return {"task_name": task_name, "model_name": model_name, "model_alias": model_alias, "global_weight_df": pd.DataFrame()}
        if df[target_col].nunique(dropna=False) < 2:
            self._clear_task_artifacts(task_name)
            logger.warning(f"{model_name} 目标列只有单一类别")
            return {"task_name": task_name, "model_name": model_name, "model_alias": model_alias, "global_weight_df": pd.DataFrame()}

        df, features = self._prepare_features(df, exclude_cols=exclude)
        if not features:
            self._clear_task_artifacts(task_name)
            logger.warning(f"{model_name} 无可用特征")
            return {"task_name": task_name, "model_name": model_name, "model_alias": model_alias, "global_weight_df": pd.DataFrame()}

        X = df[features]
        y = df[target_col]
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=0.2,
            random_state=42,
            stratify=y,
        )

        pos_ratio = (len(y_train) - y_train.sum()) / (y_train.sum() + 1e-5)
        model = self._build_model(task_name, pos_ratio)
        model.fit(X_train, y_train)

        y_prob = model.predict_proba(X_test)[:, 1]
        threshold = self._find_best_threshold(y_test, y_prob, task_name)
        y_pred = (y_prob >= threshold).astype(int)
        metrics = {
            "AUC": float(roc_auc_score(y_test, y_prob)) if len(np.unique(y_test)) > 1 else 0.0,
            "Recall": float(recall_score(y_test, y_pred, zero_division=0)),
            "Precision": float(precision_score(y_test, y_pred, zero_division=0)),
            "F1": float(f1_score(y_test, y_pred, zero_division=0)),
        }
        logger.info(f"[{task_name.upper()}] 验证集指标(Thresh={threshold:.3f}): {metrics}")

        model.fit(X, y)
        _, importance_norm, importance_softmax = self._extract_importance_views(model, features)
        group_map = self._group_feature_map(features)
        zero_rule_groups = self._select_zero_rule_groups(group_map)

        global_weight_df = pd.DataFrame(
            {
                "原始特征名称": features,
                "特征名称": [f"{model_name}_{feature}" for feature in features],
                "三级全局权重": importance_norm,
                "importance_norm": importance_norm,
                "importance_norm_softmax": importance_softmax,
                "二级类别": [feature.split("_", 1)[0] if "_" in feature else "其他" for feature in features],
            }
        ).sort_values("三级全局权重", ascending=False).reset_index(drop=True)

        self._write_model_and_metadata(
            task_name,
            model,
            features,
            threshold,
            metrics,
            group_map,
            zero_rule_groups,
            self._weight_export_file_path(),
        )
        return {
            "task_name": task_name,
            "model_name": model_name,
            "model_alias": model_alias,
            "global_weight_df": global_weight_df,
        }

    async def run(self):
        """执行整月训练并输出一个 SQL 口径权重表、模型文件和元数据。"""
        await self.load_training_data()
        task_results = [await self._run_task("energy"), await self._run_task("fault")]
        await self._save_weight_export_df(task_results)
