import asyncio
from datetime import datetime

import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import (roc_auc_score, f1_score, precision_recall_curve,
                             confusion_matrix, auc)

from core.clickhouse_connect import connect_to_clickhouse
from model.driver.src.driver_accident_data_process_1d_train import load_and_preprocess_data, encode_and_handle_outliers, process_outliers
import joblib
import warnings

from model.driver import crud
from model.driver.crud import read_raw_sql
from model.driver.src import driver_sql
from utils.logger import logger
from utils.tools import get_last_month_day

warnings.filterwarnings('ignore')


# ==================== 工具函数 ====================
def find_best_threshold(y_true, y_pred, metric='f1'):
    """
    在标签和预测概率上，找到使 F1 最大的阈值
    返回 (最佳阈值, 对应的F1值)
    """
    precision, recall, ths = precision_recall_curve(y_true, y_pred)
    f1_scores = 2 * precision * recall / (precision + recall + 1e-8)
    best_idx = np.argmax(f1_scores)
    return ths[best_idx], f1_scores[best_idx]


def evaluate_model_complete(y_true, y_pred, threshold=None, title="Model"):
    """
    完整评估模型，可指定阈值；若不指定则自动在 y_true 上寻找最佳 F1 阈值
    """
    if threshold is None:
        threshold, _ = find_best_threshold(y_true, y_pred)

    y_pred_bin = (y_pred >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred_bin).ravel()

    auc_score = roc_auc_score(y_true, y_pred)
    precision_curve, recall_curve, _ = precision_recall_curve(y_true, y_pred)
    pr_auc = auc(recall_curve, precision_curve)

    print(f"\n{'='*60}")
    print(f"=== {title} ===")
    print(f"阈值: {threshold:.4f}")
    print(f"AUC: {auc_score:.4f}   PR-AUC: {pr_auc:.4f}")
    print(f"TP={tp}  TN={tn}  FP={fp}  FN={fn}")
    print(f"Precision: {tp/(tp+fp+1e-8):.4f}")
    print(f"Recall:    {tp/(tp+fn+1e-8):.4f}")
    print(f"F1:        {2*tp/(2*tp+fp+fn+1e-8):.4f}")
    print(f"Accuracy:  {(tp+tn)/(tp+tn+fp+fn+1e-8):.4f}")
    print(f"{'='*60}")

    return {
        'threshold': threshold,
        'auc': auc_score,
        'pr_auc': pr_auc,
        'f1': 2*tp/(2*tp+fp+fn+1e-8),
        'precision': tp/(tp+fp+1e-8),
        'recall': tp/(tp+fn+1e-8),
        'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn
    }

async def data_init(start_time):
    try:
        async with await connect_to_clickhouse() as client:
            # 这里可以执行数据库操作
            end_date = datetime.strptime(start_time, "%Y-%m-%d")
            start_date = end_date
            end_date=end_date

            logger.info(f"驾驶员{start_date}--{end_date}事故风险权重数据准备 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("数据库连接成功")

            #初始化数据
            try:
              s_start_date = get_last_month_day(end_date).strftime("%Y-%m-%d")
              e_start_date = end_date.strftime("%Y-%m-%d")
              await crud.Driver(client).gen_tmp_table('tmp_driver_1d',driver_sql.train_tmp_driver_1d_sql(s_start_date,e_start_date))
              await crud.Driver(client).gen_tmp_table('tmp_driver_action_count_1d',driver_sql.train_tmp_driver_action_count_1d_sql_new(s_start_date,e_start_date))
              await crud.Driver(client).gen_tmp_table('tmp_driver_health_1d',driver_sql.train_tmp_driver_health_1d_sql_new(s_start_date,e_start_date))
              await crud.Driver(client).gen_tmp_table('tmp_driver_workhour_1d',driver_sql.train_tmp_driver_workhour_1d_new(s_start_date,e_start_date))

            except Exception as e:
                print(f"驾驶员计算权重数据存入临时表执行出错: {e}")
            logger.info(f"驾驶员计算权重{start_date}--{end_date}风险分数据准备 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.exception(f"驾驶员计算权重数据存入临时表执行出错{e}")
        print(f"驾驶员计算权重数据存入临时表执行出错: {e}")

# ==================== 主流程 ====================
async def main_week(start_time:str):
    print("="*90)
    print("驾驶员事故风险预测 - 优化版（阈值修复 + 手动权重 + 参数调优）")
    print("="*90)

    await data_init(start_time)
    # 1. 加载数据
    print("\n1. 加载数据...")
    sql = driver_sql.train_1d_sql_new(start_time, start_time)
    df = await read_raw_sql(sql)

    # 1. 加载数据
    print("\n1. 加载数据...")
    # data, base_cols, behavior_cols, health_cols, illegal_cols, all_feature_cols = \
    #     load_and_preprocess_data('7.01驾驶员权重训练数据.csv')
    data, base_cols, behavior_cols, health_cols, illegal_cols, all_feature_cols = await load_and_preprocess_data(df)
    print(f"总特征数: {len(all_feature_cols)}")

    # 2. 全局特征编码（fit 模式）
    print("\n2. 全局特征编码...")
    data, encoders, modes = encode_and_handle_outliers(data, fit=True)

    # 3. 分割数据集：先切测试集，再切验证集
    print("\n3. 数据分割（训练/验证/测试）...")
    X_train_val, X_test, y_train_val, y_test = train_test_split(
        data[all_feature_cols], data['has_accident'],
        test_size=0.2, random_state=40, stratify=data['has_accident']
    )
    X_train, X_valid, y_train, y_valid = train_test_split(
        X_train_val, y_train_val,
        test_size=0.2, random_state=42, stratify=y_train_val
    )

    # 4. 异常值截断（训练集计算边界，验证集和测试集复用）
    print("\n4. 异常值处理...")
    X_train, bounds_base = process_outliers(X_train, base_cols, is_health=False, fit=True)
    X_train, bounds_behavior = process_outliers(X_train, behavior_cols, is_health=False, fit=True)
    X_train, bounds_health = process_outliers(X_train, health_cols, is_health=True, fit=True)
    X_train, bounds_illegal = process_outliers(X_train, illegal_cols, is_health=False, fit=True)

    X_valid = process_outliers(X_valid, base_cols, is_health=False, fit=False, bounds=bounds_base)
    X_valid = process_outliers(X_valid, behavior_cols, is_health=False, fit=False, bounds=bounds_behavior)
    X_valid = process_outliers(X_valid, health_cols, is_health=True, fit=False, bounds=bounds_health)
    X_valid = process_outliers(X_valid, illegal_cols, is_health=False, fit=False, bounds=bounds_illegal)

    X_test = process_outliers(X_test, base_cols, is_health=False, fit=False, bounds=bounds_base)
    X_test = process_outliers(X_test, behavior_cols, is_health=False, fit=False, bounds=bounds_behavior)
    X_test = process_outliers(X_test, health_cols, is_health=True, fit=False, bounds=bounds_health)
    X_test = process_outliers(X_test, illegal_cols, is_health=False, fit=False, bounds=bounds_illegal)

    # 5. 转为 numpy 数组
    X_train = X_train.values
    y_train = y_train.values
    X_valid = X_valid.values
    y_valid = y_valid.values
    X_test = X_test.values
    y_test = y_test.values

    # 6. 计算样本权重（用于 scale_pos_weight）
    pos_weight = np.sum(y_train == 0) / np.sum(y_train == 1)
    print(f"\n正样本权重 scale_pos_weight: {pos_weight:.2f}")

    # 7. 优化后的参数（已移除 is_unbalance，启用手动 scale_pos_weight）
    params = {
        'boosting_type': 'gbdt',
        'objective': 'binary',
        'metric': 'average_precision',
        'num_leaves': 63,               # 适当增加复杂度
        'min_data_in_leaf': 80,         # 防止过拟合
        'learning_rate': 0.01,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'scale_pos_weight': pos_weight, # 关键：手动控制不平衡
        'reg_lambda': 3.0,              # L2 正则增强
        'reg_alpha': 1.5,               # L1 正则
        'verbose': -1,
        'random_state': 42,
    }

    # 8. 训练
    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_valid, label=y_valid, reference=train_data)

    print("\n8. 开始训练 LightGBM...")
    model = lgb.train(
        params,
        train_data,
        num_boost_round=5000,           # 足够大的轮次，靠 early stopping 停止
        valid_sets=[valid_data],
        callbacks=[
            lgb.early_stopping(200),    # 耐心值调大
            lgb.log_evaluation(100)
        ]
    )

    # 9. 在验证集上寻找最佳阈值
    print("\n9. 验证集上搜索最佳 F1 阈值...")
    valid_pred = model.predict(X_valid)
    best_th, best_val_f1 = find_best_threshold(y_valid, valid_pred)
    print(f"验证集最佳阈值: {best_th:.4f}，对应 F1: {best_val_f1:.4f}")

    # 10. 测试集评估
    print("\n10. 测试集评估（使用验证集最佳阈值）...")
    test_pred = model.predict(X_test)
    s_result=evaluate_model_complete(y_test, test_pred, threshold=best_th, title="Test Set")

    # 11. 特征重要性
    print("\n11. 特征重要性 Top 20:")
    importance = model.feature_importance(importance_type='split')
    feat_imp = pd.DataFrame({
        '特征': all_feature_cols,
        '重要性': importance,
        '归一化': importance / importance.sum()
    }).sort_values('重要性', ascending=False)
    print(feat_imp.head(20).to_string(index=False))

    # 12. 保存模型及所有附属对象（包含最佳阈值）
    model_data = {
        'model': model,
        'feature_names': all_feature_cols,
        'base_cols': base_cols,
        'behavior_cols': behavior_cols,
        'health_cols': health_cols,
        'illegal_cols': illegal_cols,
        'encoders': encoders,
        'modes': modes,
        'bounds_base': bounds_base,
        'bounds_behavior': bounds_behavior,
        'bounds_health': bounds_health,
        'bounds_illegal': bounds_illegal,
        'best_threshold': best_th,          # 推理时直接使用
    }
    dt_obj = datetime.strptime(start_time, '%Y-%m-%d')
    start_of_month = dt_obj.replace(day=1)
    start_ym_str = start_of_month.strftime('%Y-%m-%d')
    joblib.dump(model_data, f'model_1d_{start_ym_str}_optimized.pkl')
    print(f"\n模型已保存至 model_1d_{start_ym_str}_optimized.pkl")
    return s_result
    # （可选）返回对象供后续分析
    # return model_data, X_test, y_test, all_feature_cols


if __name__ == "__main__":
    # main()
    asyncio.run(main_week('2026-08-02'))