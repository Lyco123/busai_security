import asyncio
import json
from datetime import datetime

import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split,StratifiedKFold
from sklearn.metrics import (roc_auc_score,f1_score,precision_recall_curve,
                             confusion_matrix,auc,average_precision_score)
from sklearn.utils import shuffle

from core.clickhouse_connect import connect_to_clickhouse
from model.driver.src.driver_accident_data_process_1d_train import load_and_preprocess_data,encode_and_handle_outliers,process_outliers
import joblib
import warnings
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from model.driver import crud
from model.driver.crud import read_raw_sql
from model.driver.src import driver_sql
from utils.logger import logger
from utils.tools import get_last_month_day

warnings.filterwarnings('ignore')

# ==================== 8. 模型评估（完整版） ====================
def evaluate_model_complete(y_true,y_pred,title="Model"):
    """完整的模型评估，包含所有指标"""
    precision,recall,ths=precision_recall_curve(y_true,y_pred)
    f1_scores=2*precision*recall/(precision+recall+1e-8)
    best_idx=f1_scores.argmax() if len(f1_scores)>0 else 0
    best_th=ths[best_idx] if len(ths)>best_idx else 0.05

    threshold=np.percentile(y_pred,80)
    y_pred_bin=(y_pred>=threshold).astype(int)

    # 混淆矩阵
    tn,fp,fn,tp=confusion_matrix(y_true,y_pred_bin).ravel()

    print(f"\n{'='*60}")
    print(f"=== {title} ===")
    print(f"{'='*60}")
    print(f'AUC: {roc_auc_score(y_true,y_pred):.4f}')
    print(f'TP={tp} TN={tn} FP={fp} FN={fn}')
    print(f'Precision: {tp/(tp+fp+1e-8):.4f}')
    print(f'Recall: {tp/(tp+fn+1e-8):.4f}')
    print(f'Accuracy: {(tp+tn)/(tp+tn+fp+fn+1e-8):.4f}')
    # print(f'PR-AUC: {auc(recall,precision):.4f}')
    # print(f"预测概率范围: [{y_pred.min():.4f}, {y_pred.max():.4f}]")
    print(f"{'='*60}")

    return {
        'best_threshold':best_th,
        'auc':roc_auc_score(y_true,y_pred),
        'f1':f1_score(y_true,y_pred_bin),
        'precision':tp/(tp+fp+1e-8),
        'recall':tp/(tp+fn+1e-8),
        'pr_auc':auc(recall,precision),
        'tp':tp,'tn':tn,'fp':fp,'fn':fn
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
              await crud.Driver(client).gen_tmp_table('tmp_driver_action_count_1d',driver_sql.train_tmp_driver_action_count_1d_sql(s_start_date,e_start_date))
              await crud.Driver(client).gen_tmp_table('tmp_driver_health_1d',driver_sql.train_tmp_driver_health_1d_sql(s_start_date,e_start_date))
              await crud.Driver(client).gen_tmp_table('tmp_driver_workhour_1d',driver_sql.train_tmp_driver_workhour_1d(s_start_date,e_start_date))

            except Exception as e:
                print(f"驾驶员计算权重数据存入临时表执行出错: {e}")
            logger.info(f"驾驶员计算权重{start_date}--{end_date}风险分数据准备 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.exception(f"驾驶员计算权重数据存入临时表执行出错{e}")
        print(f"驾驶员计算权重数据存入临时表执行出错: {e}")

async def data_init_new(start_time):
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
              await crud.Driver(client).gen_tmp_table('tmp_driver_1d_new',driver_sql.train_tmp_driver_1d_sql_new(e_start_date,e_start_date))
              await crud.Driver(client).gen_tmp_table('tmp_driver_action_count_1d_new',driver_sql.train_tmp_driver_action_count_1d_sql_new(e_start_date,e_start_date))
              await crud.Driver(client).gen_tmp_table('tmp_driver_health_1d_new',driver_sql.train_tmp_driver_health_1d_sql_new(e_start_date,e_start_date))
              await crud.Driver(client).gen_tmp_table('tmp_driver_workhour_1d_new',driver_sql.train_tmp_driver_workhour_1d_new(e_start_date,e_start_date))
              sql = driver_sql.train_1d_sql(start_time, start_time)
              await crud.Driver(client).gen_tmp_table('tmp_driver_wide_1d_new',sql)

            except Exception as e:
                print(f"驾驶员计算权重数据存入临时表执行出错: {e}")
            logger.info(f"驾驶员计算权重{start_date}--{end_date}风险分数据准备 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.exception(f"驾驶员计算权重数据存入临时表执行出错{e}")
        print(f"驾驶员计算权重数据存入临时表执行出错: {e}")


# ==================== 9. 主流程 ====================
async def accident_train_1d_main(start_time:str):
    print("="*90)
    print("驾驶员事故风险预测 - 单模型两层评分系统")
    print("="*90)

    await data_init(start_time)
    # 1. 加载数据
    print("\n1. 加载数据...")
    sql = driver_sql.train_1d_sql(start_time,start_time)
    df = await read_raw_sql(sql)

    data, base_cols, behavior_cols, health_cols, illegal_cols, all_feature_cols = await load_and_preprocess_data(df)
    # data,base_cols,behavior_cols,health_cols,illegal_cols,all_feature_cols=load_and_preprocess_data('1d-1780468914759.csv')
    print(f"总特征数: {len(all_feature_cols)}")

    # 2. 特征编码
    data,encoders,modes=encode_and_handle_outliers(data,fit=True)


    # 5. 数据分割
    print("\n3. 数据分割...")
    X_train,X_test,y_train,y_test=train_test_split(
        data[all_feature_cols],data['has_accident'],test_size=0.2,random_state=40,stratify=data['has_accident'])

    # 2. 再从训练集中分离出验证集(占训练集的15%，即总样本的10.5%)
    X_train,X_valid,y_train,y_valid=train_test_split(
        X_train,y_train,test_size=0.2,random_state=42,stratify=y_train
    )

    # 3. 处理异常值
    print("\n2. 处理异常值...")
    X_train,bounds_base=process_outliers(X_train,base_cols,is_health=False,fit=True)
    X_train,bounds_behavior=process_outliers(X_train,behavior_cols,is_health=False,fit=True)
    X_train,bounds_health=process_outliers(X_train,health_cols,is_health=True,fit=True)
    X_train,bounds_illegal=process_outliers(X_train,illegal_cols,is_health=False,fit=True)

    X_valid=process_outliers(X_valid,base_cols,is_health=False,fit=False,bounds=bounds_base)
    X_valid=process_outliers(X_valid,behavior_cols,is_health=False,fit=False,bounds=bounds_behavior)
    X_valid=process_outliers(X_valid,health_cols,is_health=True,fit=False,bounds=bounds_health)
    X_valid=process_outliers(X_valid,illegal_cols,is_health=False,fit=False,bounds=bounds_illegal)

    X_test=process_outliers(X_test,base_cols,is_health=False,fit=False,bounds=bounds_base)
    X_test=process_outliers(X_test,behavior_cols,is_health=False,fit=False,bounds=bounds_behavior)
    X_test=process_outliers(X_test,health_cols,is_health=True,fit=False,bounds=bounds_health)
    X_test=process_outliers(X_test,illegal_cols,is_health=False,fit=False,bounds=bounds_illegal)

    # 4. 准备数据
    X_train=X_train.values
    y_train=y_train.values
    X_valid=X_valid.values
    y_valid=y_valid.values
    X_test=X_test.values
    y_test=y_test.values

    # 参数设置
    pos_weight=np.sum(y_train==0)/np.sum(y_train==1)
    params={
        'boosting_type':'gbdt',
        'objective':'binary',
        'is_unbalance':True,
        'metric': ['average_precision'],
        'num_leaves':45,
        #'max_depth':8,
        'learning_rate':0.01,
        'feature_fraction':0.7,
        'bagging_fraction':0.7,
        'bagging_freq':3,
        #'scale_pos_weight':pos_weight,
        'min_data_in_leaf':50,
        'reg_lambda': 2.0,
        'reg_alpha': 1.0,
        'verbose':-1,
        'random_state':42,
    }

    train_data=lgb.Dataset(X_train,label=y_train)

    model=lgb.train(
        params,
        train_data,
        num_boost_round=2000,
        valid_sets=[lgb.Dataset(X_valid,label=y_valid)],
        callbacks=[lgb.early_stopping(100),lgb.log_evaluation(100)]
    )

    pred_prob=model.predict(X_test)

    s_result=evaluate_model_complete(y_test,pred_prob,"单一模型")




    # 8. 特征重要性
    print("\n6. 特征重要性 Top 15:")
    importance=model.feature_importance(importance_type='split')
    feat_imp=pd.DataFrame({
        '特征':all_feature_cols,
        '重要性':importance,
        '归一化':importance/importance.sum(),
    }).sort_values('重要性',ascending=False)
    print(feat_imp.to_string(index=False))


    # 9. 保存模型
    model_data={
        'model':model,
        'feature_names':all_feature_cols,
        'base_cols':base_cols,
        'behavior_cols':behavior_cols,
        'health_cols':health_cols,
        'illegal_cols':illegal_cols,
        'encoders':encoders,
        'modes':modes,
        'bounds_base':bounds_base,
        'bounds_behavior':bounds_behavior,
        'bounds_health':bounds_health,
        'bounds_illegal':bounds_illegal,
    }

    dt_obj = datetime.strptime(start_time, '%Y-%m-%d')
    start_of_month = dt_obj.replace(day=1)
    start_ym_str = start_of_month.strftime('%Y-%m-%d')

    joblib.dump(model_data,f'model_1d_{start_ym_str}.pkl')
    print(f"\n模型已保存至model_1d_{start_ym_str}.pkl")
    return s_result

    # return model_data,X_test,y_test,all_feature_cols,base_cols,behavior_cols,health_cols,illegal_cols

async def accident_train_1d_main_new(start_time:str):
    print("="*90)
    print("驾驶员事故风险预测 - 单模型两层评分系统")
    print("="*90)

    await data_init_new(start_time)
    # 1. 加载数据
    print("\n1. 加载数据...")
    sql = driver_sql.train_1d_sql(start_time,start_time)


    # df = await read_raw_sql(sql)


if __name__=="__main__":

    # 训练模型
    # asyncio.run(accident_train_1d_main('2026-07-20'))

    asyncio.run(accident_train_1d_main_new('2026-07-26'))
