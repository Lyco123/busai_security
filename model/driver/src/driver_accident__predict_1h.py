import asyncio

import joblib
from clickhouse_driver import client

#from driver_accident_data_process import load_and_preprocess_data,encode_and_handle_outliers,process_outliers
from model.driver.src.driver_accident_data_process_1h_predict import load_and_preprocess_data,encode_and_handle_outliers,process_outliers
import numpy as np
import pandas as pd
import uuid
from datetime import datetime, timedelta
import shap
from scipy.special import expit

from model.driver.crud import read_raw_sql, save_accident_weight, save_accident_score, save_accident_1h_weight, \
    save_accident_1h_score, Driver, get_accident_weights
from model.driver.src import driver_sql
from utils.tools import get_last_month_day


def cal_total_score(pred_prob):
    """
    计算总分
    """
    # 计算基础分
    base_scores = pred_prob * 100

    threshold=np.percentile(base_scores,80)
    
    # 初始化总分
    total_score = np.zeros_like(base_scores)
    
    # 处理后80%的情况：按排名拉长到 0-65 区间
    # mask_low = base_scores < threshold
    mask_low = base_scores < 65
    if np.any(mask_low):
        low_scores = base_scores[mask_low]
        # 获取排序后的索引（从小到大）
        sorted_indices = np.argsort(low_scores)
        n_low = len(low_scores)
        # 生成 0-50 之间的均匀分布值
        scaled_values = np.linspace(5, 65, n_low)
        # 根据原始排名分配新分数
        new_low_scores = np.zeros_like(low_scores)
        new_low_scores[sorted_indices] = scaled_values
        total_score[mask_low] = new_low_scores
    
    # 处理前20%的情况：按排名拉长到 65-100 区间
    # mask_high = base_scores >= threshold# 65
    mask_high = base_scores >= 65
    if np.any(mask_high):
        high_scores = base_scores[mask_high]
        # 获取排序后的索引（从小到大）
        sorted_indices = np.argsort(high_scores)
        n_high = len(high_scores)
        # 生成 50-100 之间的均匀分布值
        scaled_values = np.linspace(65, 100, n_high)
        # 根据原始排名分配新分数
        new_high_scores = np.zeros_like(high_scores)
        new_high_scores[sorted_indices] = scaled_values
        total_score[mask_high] = new_high_scores
        
    return total_score

def positive_process(x):
    """
    对输入 x 进行 Min-Max 归一化，将数据缩放到 [0, 1] 区间
    """
    x = np.asarray(x)
    min_val = np.min(x)
    max_val = np.max(x)
    
    # 防止除以零，如果最大值等于最小值，则返回全0或全1（取决于具体需求，这里返回0）
    if max_val - min_val == 0:
        return np.zeros_like(x, dtype=float)
    
    normalized_x = (x - min_val) / (max_val - min_val)
    return normalized_x

def softmax2(x):
    exp_x=np.exp(x-np.max(x))
    return exp_x/exp_x.sum()

def transform_feature_importance(importance_norm,feature_names,behavior_cols):

    behavior_importance=sum(importance_norm[col] for i,col in enumerate(feature_names) if col in behavior_cols)
    feat_importance_2={'不良行为':behavior_importance}

    feat_importance_3={}  # 3级指标权重
    for i,col in enumerate(feature_names):
        if col in behavior_cols:
            feat_importance_3[col]=importance_norm[col]/(behavior_importance+1e-8)

    return behavior_importance

def check_score(datas,behavior_cols,importance_norm,feature_names,final_scores,raw_scores):
    n_samples=len(list(final_scores.values())[0])

    # 找出需要重新分配分数的特征列
    zero_importance_cols=[col for i,col in enumerate(feature_names) if importance_norm[col]==0]

    # 找出 behavior_cols 中源数据为 0 的特征
    zero_data_behavior_cols=[]
    for col in behavior_cols:
        if np.all(datas[col]==0):
            zero_data_behavior_cols.append(col)

    # 合并所有需要清零的特征列
    zero_score_cols=list(set(zero_importance_cols+zero_data_behavior_cols))

    # 找出可以接收分数的特征列（重要性不为 0 且不是 behavior 中数据为 0 的列）
    valid_cols=[col for i,col in enumerate(feature_names)
                if importance_norm[col]!=0 and col not in zero_data_behavior_cols]

    if len(zero_score_cols)>0 and len(valid_cols)>0:
        # 计算所有需要清零的特征的总分数
        total_zero_score=np.zeros(n_samples)
        for col in zero_score_cols:
            total_zero_score+=final_scores[col]

        # 计算每个有效特征应分配的平均分数
        avg_score_per_col=total_zero_score/len(valid_cols)

        # 将需要清零的特征的分数平均分配给有效特征
        for col in valid_cols:
            final_scores[col]=final_scores[col]+avg_score_per_col
            raw_scores[col]=raw_scores[col]+avg_score_per_col/(importance_norm[col]+1e-8)

        # 将需要清零的特征的分数设为 0
        for col in zero_score_cols:
            final_scores[col]=np.zeros(n_samples)
            raw_scores[col]=np.zeros(n_samples)

    return final_scores,raw_scores

def scorecard_model(feature_names,X_input,datas,feat_importance,total_score,pred_prob,final_scores,behavior_cols):
    n_samples=X_input.shape[0]
    for i,col in enumerate(feature_names):
        feature_vals=X_input[:,i]
        datas[col]=feature_vals
        imp=feat_importance[col]  # 该特征的重要性

        # 该特征的理论贡献基数 = 重要性 × 总分
        # 这是该特征贡献的分数基准
        base_contribution=imp*total_score

        if col in behavior_cols:
            # 行为特征和违法特征：违规次数越多，得分越高
            mean_val=feature_vals.mean() if feature_vals.mean()>0 else 1
            normalized_val=np.clip(feature_vals/mean_val,0,5)
            final_scores[col]=base_contribution*normalized_val

    # ========== 关键：归一化确保可加性 ==========
    # 当前 final_scores 总和可能不等于 total_score，需要缩放
    current_sum=np.zeros(n_samples)
    for col in feature_names:
        current_sum+=final_scores[col]
    # 计算缩放因子（避免除零）
    scale_factor=total_score/(current_sum+1e-8)
    # 应用缩放，确保严格可加
    for col in feature_names:
        final_scores[col]=final_scores[col]*scale_factor
    # 裁剪到合理范围
    for col in feature_names:
        final_scores[col]=np.clip(final_scores[col],0,100)

    return final_scores

# ==================== 5. 核心：两层分数计算系统 ====================
async def calculate_two_layer_scores(model,X_input,feature_names,behavior_cols,calculation_type,start_time):
    """
    两层分数系统（修正版）：
    1. 总分细分：特征在最终总分中的实际贡献
    2. 原始分：去除特征重要性后的绝对风险

    逆向关系：原始分 = 总分细分 / 特征重要性
    """

    pred_prob=model.predict(X_input)

    total_score=cal_total_score(pred_prob)  # 最终总分（0-100）

    # # 使用shap方法计算得分
    # explainer=shap.TreeExplainer(model)
    # shap_values=explainer.shap_values(X_input)
    #
    # # 获取每个特征的 SHAP 值
    # shap_vals=positive_process(shap_values)
    # shap_vals=shap_vals/(shap_vals.sum(axis=1,keepdims=True)+1e-8)
    #
    # # 取shap_vals每列的平均值作为特征重要性
    # importance_norm = np.mean(shap_vals, axis=0)

    importance=model.feature_importance(importance_type='split')
    importance_norm={}
    for i,col in enumerate(feature_names):
        importance_norm[col]=np.round(importance[i]/importance.sum(),3)
    #importance_norm_softmax=softmax2(importance_norm)

    if calculation_type=='0':
        start_date=datetime.strptime(start_time.split(' ')[0], '%Y-%m-%d')
        quota_accident_quota_datas=await get_accident_weights('3', '驾驶员画像-事故小时风险', get_last_month_day(start_date).strftime('%Y-%m-%d'))
        importance_norm={}
        for quota in quota_accident_quota_datas:
            importance_norm[quota['quota_name']]=quota['weight_rate']
    # 转换各级指标权重
    behavior_importance=transform_feature_importance(importance_norm,feature_names,behavior_cols)

    datas={}  #  源数据值
    final_scores={} # 总分细分

    # 将 SHAP 值转换为分数贡献
    #shap_scores=np.round(shap_vals*total_score.reshape(-1, 1),1)

    # 使用评分卡模型计算得分
    final_scores=scorecard_model(feature_names,X_input,datas,importance_norm,total_score,pred_prob,final_scores,behavior_cols)

    raw_scores={}
    for i,col in enumerate(feature_names):
        datas[col]=X_input[:,i]
        if col in behavior_cols:
            raw_scores[col]=final_scores[col]/behavior_importance

    final_scores,raw_scores=check_score(datas,behavior_cols,importance_norm,feature_names,final_scores,raw_scores)

    return {
        'data':datas,  # 源数据值
        'final_scores':final_scores,  # 指标风险值
        'raw_scores':raw_scores,  # 指标转换后数值
        'feat_weights':importance_norm,  # 指标特征权重
    }

# ==================== 10. 演示预测 ====================
async def prediction_1h(start_time:str, end_time:str, calculation_type:str):
    """演示两层分数预测"""
    print("\n"+"="*90)
    print("评分系统")
    print("="*90)

    # 加载模型
    d_start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
    f_start_time = d_start_time-timedelta(days=d_start_time.day-1)
    s_start_time = f_start_time.strftime('%Y-%m-%d')
    model_data = joblib.load(f'model_1h_{s_start_time}.pkl')
    model=model_data['model']
    feature_names=model_data['feature_names']
    behavior_cols=model_data['behavior_cols']

    sql = driver_sql.predict_1h_sql(start_time,start_time)
    print(f"小时sql:{sql}")
    df = await read_raw_sql(sql)

    # 重新加载数据
    data,_,all_feature_cols,info_cols=await load_and_preprocess_data(df)
    # data=encode_and_handle_outliers(data,fit=False,encoders=encoders,modes=modes)
    # data=process_outliers(data,base_cols,is_health=False,fit=False,bounds=bounds_base)
    # data=process_outliers(data,behavior_cols,is_health=False,fit=False,bounds=bounds_behavior)
    # data=process_outliers(data,health_cols,is_health=True,fit=False,bounds=bounds_health)
    # data=process_outliers(data,illegal_cols,is_health=False,fit=False,bounds=bounds_illegal)

    info=data[info_cols].values

    X=data[all_feature_cols].values

    # 预测
    results=await calculate_two_layer_scores(
        model,X,feature_names,behavior_cols,calculation_type,start_time
    )

    # 保存权重
    if calculation_type == "1":
        await save_accident_1h_weight(results, start_time, end_time)
    else:
        await save_accident_1h_score(results, start_time, end_time,info,behavior_cols)

    return results

if __name__=="__main__":
    # 分数预测
    results = asyncio.run(prediction_1h('2026-06-01', '2026-06-01', "0"))
    # results=prediction()
#     # 将结果转换为DataFrame并保存为CSV
#     # 构建包含所有需要输出的数据的列表
#     records = []
#
#     # 获取样本数量
#     n_samples = len(results['data'].get(list(results['data'].keys())[0], []))
#
#     # 遍历每个样本
#     for i in range(n_samples):
#         record = {}
#
#         # 1. 输出源数据 (data)
#         for col, vals in results['data'].items():
#             record[f"data_{col}"] = vals[i] if isinstance(vals, np.ndarray) else vals
#
#         # 2. 输出各指标权重 (feat_weights)
#         # 一级权重
#         record["weight_level_1"] = results['feat_weights_1']
#         # 二级权重
#         for k, v in results['feat_weights_2'].items():
#             record[f"weight_level_2_{k}"] = v
#         # 三级权重
#         for k, v in results['feat_weights_3'].items():
#             record[f"weight_level_3_{k}"] = v
#         # 四级权重
#         for k, v in results['feat_weights_4'].items():
#             record[f"weight_level_4_{k}"] = v
#
#         # 3. 输出各 final 分数
#         # 一级 final
#         record["final_score_level_1"] = results['final_scores_1'][i] if isinstance(results['final_scores_1'], np.ndarray) else results['final_scores_1']
#         # 二级 final
#         for k, v in results['final_scores_2'].items():
#             record[f"final_score_level_2_{k}"] = v[i] if isinstance(v, np.ndarray) else v
#         # 三级 final
#         for k, v in results['final_scores_3'].items():
#             record[f"final_score_level_3_{k}"] = v[i] if isinstance(v, np.ndarray) else v
#         # 四级 final
#         for k, v in results['final_scores_4'].items():
#             record[f"final_score_level_4_{k}"] = v[i] if isinstance(v, np.ndarray) else v
#
#         # 4. 输出各 raw 分数
#         # 一级 raw
#         record["raw_score_level_1"] = results['raw_scores_1'][i] if isinstance(results['raw_scores_1'], np.ndarray) else results['raw_scores_1']
#         # 二级 raw
#         for k, v in results['raw_scores_2'].items():
#             record[f"raw_score_level_2_{k}"] = v[i] if isinstance(v, np.ndarray) else v
#         # 三级 raw
#         for k, v in results['raw_scores_3'].items():
#             record[f"raw_score_level_3_{k}"] = v[i] if isinstance(v, np.ndarray) else v
#         # 四级 raw
#         for k, v in results['raw_scores_4'].items():
#             record[f"raw_score_level_4_{k}"] = v[i] if isinstance(v, np.ndarray) else v
#
#         records.append(record)
#
#     df_results = pd.DataFrame(records)
#     df_results.to_csv('shap_score_results.csv', index=False, encoding='utf-8-sig')
#     print("结果已保存到 shap_score_results.csv")
