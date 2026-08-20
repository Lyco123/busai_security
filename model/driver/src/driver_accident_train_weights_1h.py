import asyncio
import warnings
from datetime import datetime
import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import ParameterSampler, train_test_split

from model.driver.src.driver_accident_data_process_1h_train import load_and_preprocess_data

from model.driver import crud
from model.driver.crud import read_raw_sql
from model.driver.src import driver_sql
from utils.logger import logger
from utils.tools import get_last_month_day
from core.clickhouse_connect import connect_to_clickhouse

warnings.filterwarnings("ignore")

DATA_FILE = "1h-1780295847866.csv"
MODEL_FILE = "model_1h.pkl"
MIN_REQUIRED_RECALL = 0.70
THRESHOLD_SELECTION_RECALL = 0.82
N_PARAM_SEARCH = 30
RANDOM_STATE = 42


def choose_threshold_by_recall(y_true, y_score, target_recall=THRESHOLD_SELECTION_RECALL):
    """Pick the threshold with highest precision while recall >= target_recall."""
    precision, recall, thresholds = precision_recall_curve(y_true, y_score)

    if len(thresholds) == 0:
        return {
            "threshold": 0.5,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "target_met": False,
        }

    candidates = []
    for threshold, p, r in zip(thresholds, precision[:-1], recall[:-1]):
        f1 = 2 * p * r / (p + r + 1e-8)
        candidates.append(
            {
                "threshold": float(threshold),
                "precision": float(p),
                "recall": float(r),
                "f1": float(f1),
                "target_met": bool(r >= target_recall),
            }
        )

    valid_candidates = [item for item in candidates if item["target_met"]]
    if valid_candidates:
        return max(
            valid_candidates,
            key=lambda item: (
                item["precision"],
                item["recall"],
                item["threshold"],
                item["f1"],
            ),
        )

    return max(candidates, key=lambda item: (item["recall"], item["precision"], item["f1"]))


def build_param_search_space(pos_weight):
    weight_values = sorted(
        {
            max(1.0, pos_weight * 0.5),
            max(1.0, pos_weight * 0.75),
            pos_weight,
            pos_weight * 1.25,
            pos_weight * 1.5,
            pos_weight * 2.0,
        }
    )

    return {
        "num_leaves": [7, 15, 31, 63],
        "max_depth": [3, 4, 5, 6, 8, -1],
        "learning_rate": [0.01, 0.02, 0.03, 0.05, 0.08],
        "feature_fraction": [0.6, 0.7, 0.8, 0.9, 1.0],
        "bagging_fraction": [0.6, 0.7, 0.8, 0.9, 1.0],
        "bagging_freq": [1, 3, 5],
        "min_data_in_leaf": [10, 20, 30, 50, 80],
        "reg_lambda": [0.0, 0.5, 1.0, 2.0, 5.0],
        "reg_alpha": [0.0, 0.2, 0.5, 1.0, 2.0],
        "min_gain_to_split": [0.0, 0.01, 0.05, 0.1],
        "scale_pos_weight": weight_values,
    }


def train_lgb_model(params, x_train, y_train, x_valid, y_valid, log_eval=False):
    train_data = lgb.Dataset(x_train, label=y_train)
    valid_data = lgb.Dataset(x_valid, label=y_valid, reference=train_data)

    return lgb.train(
        params,
        train_data,
        num_boost_round=5000,
        valid_sets=[valid_data],
        callbacks=[
            lgb.early_stopping(100, verbose=log_eval),
            lgb.log_evaluation(100 if log_eval else 0),
        ],
    )


def tune_model_and_threshold(
    x_train,
    y_train,
    x_valid,
    y_valid,
    target_recall=THRESHOLD_SELECTION_RECALL,
    n_iter=N_PARAM_SEARCH,
):
    pos_weight = np.sum(y_train == 0) / np.sum(y_train == 1)
    base_params = {
        "boosting_type": "gbdt",
        "objective": "binary",
        "metric": "average_precision",
        "verbose": -1,
        "random_state": RANDOM_STATE,
        "feature_pre_filter": False,
    }
    sampled_params = list(
        ParameterSampler(
            build_param_search_space(pos_weight),
            n_iter=n_iter,
            random_state=RANDOM_STATE,
        )
    )

    best = None
    print(
        f"\n4. Dynamic hyperparameter and threshold search: "
        f"{len(sampled_params)} trials, threshold selection recall >= {target_recall:.2f} "
        f"(minimum required recall > {MIN_REQUIRED_RECALL:.2f})"
    )

    for i, params_part in enumerate(sampled_params, 1):
        params = {**base_params, **params_part}
        model = train_lgb_model(params, x_train, y_train, x_valid, y_valid)
        valid_prob = model.predict(x_valid, num_iteration=model.best_iteration)
        threshold_info = choose_threshold_by_recall(y_valid, valid_prob, target_recall)
        ap = average_precision_score(y_valid, valid_prob)
        auc_score = roc_auc_score(y_valid, valid_prob)
        score = (
            int(threshold_info["target_met"]),
            threshold_info["precision"],
            threshold_info["recall"],
            ap,
            auc_score,
        )

        if best is None or score > best["score"]:
            best = {
                "score": score,
                "model": model,
                "params": params,
                "threshold_info": threshold_info,
                "average_precision": float(ap),
                "auc": float(auc_score),
            }

        print(
            f"trial {i:02d}/{len(sampled_params)} | "
            f"valid_precision={threshold_info['precision']:.4f} "
            f"valid_recall={threshold_info['recall']:.4f} "
            f"threshold={threshold_info['threshold']:.6f} "
            f"AP={ap:.4f}"
        )

    return best


def evaluate_model_complete(y_true, y_score, title="Model", threshold=0.5):
    precision, recall, thresholds = precision_recall_curve(y_true, y_score)
    f1_scores = 2 * precision * recall / (precision + recall + 1e-8)
    best_idx = f1_scores.argmax() if len(f1_scores) > 0 else 0
    best_f1_threshold = thresholds[best_idx] if len(thresholds) > best_idx else 0.5

    y_pred_bin = (y_score >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred_bin).ravel()

    print(f"\n{'=' * 60}")
    print(f"=== {title} ===")
    print(f"{'=' * 60}")
    print(f"AUC: {roc_auc_score(y_true, y_score):.4f}")
    print(f"TP={tp} TN={tn} FP={fp} FN={fn}")
    print(f"Precision: {tp / (tp + fp + 1e-8):.4f}")
    print(f"Recall: {tp / (tp + fn + 1e-8):.4f}")
    print(f"Accuracy: {(tp + tn) / (tp + tn + fp + fn + 1e-8):.4f}")
    print(f"{'=' * 60}")

    result_string = (
        f"=== {title} ===\n"
        f"AUC: {roc_auc_score(y_true, y_score):.4f}\n"
        f"TP={tp} TN={tn} FP={fp} FN={fn}\n"
        f"Precision: {tp / (tp + fp + 1e-8):.4f}\n"
        f"Recall: {tp / (tp + fn + 1e-8):.4f}\n"
        f"Accuracy: {(tp + tn) / (tp + tn + fp + fn + 1e-8):.4f}\n"
    )
    return result_string

async def data_init(start_time):
    try:
        async with await connect_to_clickhouse() as client:
            # 这里可以执行数据库操作
            end_date = datetime.strptime(start_time, "%Y-%m-%d")
            start_date = end_date
            end_date=end_date

            logger.info(f"驾驶员{start_date}--{end_date}事故小时风险权重数据准备 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("数据库连接成功")

            #初始化数据
            try:
              s_start_date = get_last_month_day(end_date).strftime("%Y-%m-%d")
              e_start_date = end_date.strftime("%Y-%m-%d")
              await crud.Driver(client).gen_tmp_table('tmp_driver_1h',driver_sql.train_tmp_driver_1h_sql(s_start_date,e_start_date))
              await crud.Driver(client).gen_tmp_table('tmp_driver_action_count_1h',driver_sql.train_tmp_driver_action_count_1h_sql(s_start_date,e_start_date))

            except Exception as e:
                print(f"驾驶员计算事故小时权重数据存入临时表执行出错: {e}")
            logger.info(f"驾驶员{start_date}--{end_date}事故小时风险数据准备 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.exception(f"驾驶员计算小时风险权重数据准备存入临时表执行出错{e}")
        print(f"驾驶员计算小时风险权重数据存入临时表执行出错: {e}")

async def accident_train_1h_main(start_time:str):
    print("=" * 90)
    print("Driver accident risk model - dynamic hyperparameter and threshold tuning")
    print("=" * 90)

    await data_init(start_time)

    print("\n1. Loading data...")
    sql = driver_sql.train_1h_sql(start_time,start_time)
    df = await read_raw_sql(sql)
    data, behavior_cols, all_feature_cols = await load_and_preprocess_data(df)
    print(f"feature count: {len(all_feature_cols)}")
    print(data["has_accident"].value_counts().rename("count").to_string())

    print("\n2. Splitting data...")
    x_train, x_test, y_train, y_test = train_test_split(
        data[all_feature_cols],
        data["has_accident"],
        test_size=0.2,
        random_state=40,
        stratify=data["has_accident"],
    )

    x_train, x_valid, y_train, y_valid = train_test_split(
        x_train,
        y_train,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=y_train,
    )

    print("\n3. Preparing arrays...")
    x_train = x_train.values
    y_train = y_train.values
    x_valid = x_valid.values
    y_valid = y_valid.values
    x_test = x_test.values
    y_test = y_test.values

    best = tune_model_and_threshold(
        x_train,
        y_train,
        x_valid,
        y_valid,
        target_recall=THRESHOLD_SELECTION_RECALL,
        n_iter=N_PARAM_SEARCH,
    )
    model = best["model"]
    best_threshold = best["threshold_info"]["threshold"]

    pred_prob = model.predict(x_test, num_iteration=model.best_iteration)
    s_result=evaluate_model_complete(
        y_test,
        pred_prob,
        "Dynamic tuned model",
        threshold=best_threshold,
    )

    print("\nFeature importance Top 15:")
    importance = model.feature_importance(importance_type="split")
    importance_sum = importance.sum()
    feat_imp = pd.DataFrame(
        {
            "feature": all_feature_cols,
            "importance": importance,
            "normalized": importance / importance_sum if importance_sum else 0,
        }
    ).sort_values("importance", ascending=False)
    print(feat_imp.head(15).to_string(index=False))

    model_data = {
        "model": model,
        "threshold": best_threshold,
        "min_required_recall": MIN_REQUIRED_RECALL,
        "threshold_selection_recall": THRESHOLD_SELECTION_RECALL,
        "best_params": best["params"],
        "validation_metrics": {
            "precision": best["threshold_info"]["precision"],
            "recall": best["threshold_info"]["recall"],
            "f1": best["threshold_info"]["f1"],
            "average_precision": best["average_precision"],
            "auc": best["auc"],
        },
        "feature_names": all_feature_cols,
        "behavior_cols": behavior_cols,
    }
    # joblib.dump(model_data, MODEL_FILE)
    # print(f"\nModel saved to {MODEL_FILE}")
    dt_obj = datetime.strptime(start_time, '%Y-%m-%d')
    start_of_month = dt_obj.replace(day=1)
    start_ym_str = start_of_month.strftime('%Y-%m-%d')

    joblib.dump(model_data,f'model_1h_{start_ym_str}.pkl')
    print(f"\n模型已保存至model_1h_{start_ym_str}.pkl")

    return s_result


if __name__ == "__main__":
    asyncio.run(accident_train_1h_main('2026-07-01'))
