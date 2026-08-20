import asyncio
import json

import joblib
from pandas import DataFrame

from model.driver.src.driver_accident_data_process_1d_predict import load_and_preprocess_data,encode_and_handle_outliers,process_outliers
import numpy as np
import pandas as pd
import uuid
from datetime import datetime, timedelta
import shap
from scipy.special import expit

from model.driver.crud import read_raw_sql, save_accident_weight, save_accident_score, get_accident_weights, \
    save_accident_weight_new, save_accident_score_new, get_accident_weights_new, update_driver_scores_main_new
from model.driver.src import driver_sql
from model.driver.src.generate_weekly_driver_list import main_warning


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
    mask_low = base_scores < threshold
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
    mask_high = base_scores >= threshold #65
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

def transform_feature_importance(importance_norm,feature_names,base_cols,behavior_cols,health_cols,illegal_cols,physiological_cols,mental_cols):

    health_importance=sum(importance_norm[col] for i,col in enumerate(feature_names) if col in health_cols)
    illegal_importance=sum(importance_norm[col] for i,col in enumerate(feature_names) if col in illegal_cols)
    behavior_importance=sum(importance_norm[col] for i,col in enumerate(feature_names) if col in behavior_cols)
    base_importance=sum(importance_norm[col] for i,col in enumerate(feature_names) if col in base_cols)
    feat_importance_2={'健康风险':health_importance,'不良行为':behavior_importance,'违法违章':illegal_importance,
                       '其他风险':base_importance}

    feat_importance_3={}  # 3级指标权重
    for i,col in enumerate(feature_names):
        if col in health_cols:  # 有4级指标特殊处理
            if col=='心理测评等级':
                feat_importance_3['精神状态']=importance_norm[col]/(health_importance+1e-8)
                feat_importance_3['生理状态']=1-feat_importance_3['精神状态']
            else:
                continue
        elif col in illegal_cols:
            feat_importance_3[col]=importance_norm[col]/(illegal_importance+1e-8)
        elif col in behavior_cols:
            feat_importance_3[col]=importance_norm[col]/(behavior_importance+1e-8)
        elif col in base_cols:
            feat_importance_3[col]=importance_norm[col]/(base_importance+1e-8)

    psy_feat_importance_norm={}  # 4级指标权重
    for i,col in enumerate(feature_names):
        if col in physiological_cols:
            psy_feat_importance_norm[col]=importance_norm[col]/((feat_importance_3['生理状态']+1e-8)*health_importance)

    men_feat_importance_norm={}  # 4级指标权重
    for i,col in enumerate(feature_names):
        if col in mental_cols:
            men_feat_importance_norm[col]=importance_norm[col]/((feat_importance_3['精神状态']+1e-8)*health_importance)

    feat_importance_4={k:(psy_feat_importance_norm.get(k,0)+men_feat_importance_norm.get(k,0)) for k in
                       set(psy_feat_importance_norm)|set(men_feat_importance_norm)}

    return health_importance,illegal_importance,behavior_importance,base_importance,men_feat_importance_norm,psy_feat_importance_norm,feat_importance_2,feat_importance_3,feat_importance_4

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

def scorecard_model(feature_names,X_input,datas,feat_importance,total_score,pred_prob,final_scores,behavior_cols,health_cols,illegal_cols,base_cols):
    n_samples=X_input.shape[0]
    for i,col in enumerate(feature_names):
        feature_vals=X_input[:,i]
        datas[col]=feature_vals
        imp=feat_importance[col]  # 该特征的重要性

        # 该特征的理论贡献基数 = 重要性 × 总分
        # 这是该特征贡献的分数基准
        base_contribution=imp*total_score

        mean_val=feature_vals.mean()
        std_val=feature_vals.std()+1e-8

        if col in ['性别','教育水平','心理测评等级']:
            # 类别特征：不同取值有不同风险
            unique_vals=np.unique(feature_vals)
            scores=np.zeros(n_samples)

            for uv in unique_vals:
                mask=feature_vals==uv
                avg_risk=pred_prob[mask].mean() if mask.sum()>0 else pred_prob.mean()
                # 该取值下的总分细分 = 基数 × 风险系数
                # 系数范围 0.5 ~ 1.5（根据 avg_risk 0~1 调整）
                risk_factor=0.5+avg_risk  # 0.5~1.5
                scores[mask]=base_contribution[mask]*risk_factor

            final_scores[col]=scores

        elif col in behavior_cols or col in illegal_cols:
            # 行为特征和违法特征：违规次数越多，得分越高
            mean_val=feature_vals.mean() if feature_vals.mean()>0 else 1
            normalized_val=np.clip(feature_vals/mean_val,0,5)
            final_scores[col]=base_contribution*normalized_val

        elif col in health_cols:
            if col=='酒精浓度':
                high_alcohol=feature_vals>20
                # 超标时贡献翻倍，正常时0
                final_scores[col]=np.where(high_alcohol,base_contribution*2.0,0)
            else:
                deviation=np.abs(feature_vals-mean_val)/std_val
                normalized_dev=np.clip(deviation/3,0,1)
                # 偏离越大，贡献越高（1.0 ~ 1.5倍）
                final_scores[col]=base_contribution*(1.0+0.5*normalized_dev)

        elif col in base_cols:
            if col=='年龄':
                # 年龄：偏离35岁（最佳驾驶年龄）越远风险越高
                optimal_age=35
                age_deviation=np.abs(feature_vals-optimal_age)
                # 标准化偏离程度，假设30岁偏离为正常范围
                normalized_dev=np.clip(age_deviation/30,0,2)
                # 年轻/年老风险更高（0.8 ~ 1.5倍）
                final_scores[col]=base_contribution*(0.8+0.35*normalized_dev)
            elif col=='驾龄':
                # 驾龄：越短风险越高（非线性关系），使用对数变换：新手风险高，老手趋于平稳
                driving_years=np.maximum(feature_vals,0.1)  # 避免0
                # 驾龄系数：0.1年->1.5倍, 10年->1.0倍, 30年->0.8倍

                driving_years_np = np.asarray(driving_years, dtype=np.float64)
                exp_factor = np.clip(1.5 - 0.15 * np.log(driving_years_np + 1), 0.8, 1.5)
                final_scores[col]=base_contribution*exp_factor
            elif col=='历史事故率':
                # 事故率：直接关联风险，事故率越高得分越高（线性关系）
                mean_val=feature_vals.mean() if feature_vals.mean()>0 else 1
                normalized_val=np.clip(feature_vals/mean_val,0,5)
                final_scores[col]=base_contribution*normalized_val
            elif col=='日工时':
                # 日工时：越多风险越高
                mean_val=feature_vals.mean() if feature_vals.mean()>0 else 1
                normalized_val=np.clip(feature_vals/mean_val,0,5)
                final_scores[col]=base_contribution*normalized_val
            else:
                # 其他基础特征，默认：偏离均值越大风险越高
                deviation=np.abs(feature_vals-mean_val)/std_val
                normalized_dev=np.clip(deviation/2,0,1)
                final_scores[col]=base_contribution*(0.9+0.2*normalized_dev)

    # ========== 关键：归一化确保可加性 ==========
    # 当前 final_scores 总和可能不等于 total_score，需要缩放
    current_sum=np.zeros(n_samples)
    # for col in feature_names:
        # current_sum+=final_scores[col]
    for col in feature_names:
        current_sum += pd.to_numeric(final_scores[col], errors='coerce')

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
async def calculate_two_layer_scores(model, X_input, feature_names, base_cols, behavior_cols, health_cols, illegal_cols,calculation_type,hour=None,_start_time=None):
    """
    两层分数系统（修正版）：
    1. 总分细分：特征在最终总分中的实际贡献
    2. 原始分：去除特征重要性后的绝对风险

    逆向关系：原始分 = 总分细分 / 特征重要性
    """
    physiological_cols=['心率','酒精浓度','收缩压','舒张压','脉搏','血氧','体温']
    mental_cols=['心理测评等级']

    pred_prob=model.predict(X_input)

    total_score=cal_total_score(pred_prob)  # 最终总分（0-100）

    # 对于日工时为0的司机，分数设置为0
    total_score[X_input[:,6]==0]=0
    X_input[X_input[:,6]==0]=0

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


    # 转换各级指标权重
    health_importance,illegal_importance,behavior_importance,base_importance,men_feat_importance_norm,psy_feat_importance_norm,feat_importance_2,feat_importance_3,feat_importance_4=transform_feature_importance(importance_norm,feature_names,base_cols,behavior_cols,health_cols,illegal_cols,physiological_cols,mental_cols)
    #health_imp,illegal_imp,behavior_imp,base_imp,men_feat_imp,psy_feat_imp,feat_imp_2,feat_imp_3,feat_imp_4=transform_feature_importance(importance_norm_softmax,feature_names,base_cols,behavior_cols,health_cols,illegal_cols,physiological_cols,mental_cols)

    if calculation_type=='0':
        _id='驾驶员画像-事故风险'
        feat_importance_1 = await get_accident_weights_new('1',_id,_start_time)
        feat_importance_2_data=await get_accident_weights_new('2',_id,_start_time)
        for data in feat_importance_2_data:
            if data['quota_name'] in feat_importance_2:
                feat_importance_2[data['quota_name']]=float(data['weight_rate'])
        feat_importance_3_data=await get_accident_weights_new('3',_id,_start_time)
        for data in feat_importance_3_data:
            if data['quota_name'] in feat_importance_3:
                feat_importance_3[data['quota_name']]=float(data['weight_rate'])
        feat_importance_4_data=await get_accident_weights_new('4',_id,_start_time)
        for data in feat_importance_4_data:
            if data['quota_name'] in feat_importance_4:
                feat_importance_4[data['quota_name']]=float(data['weight_rate'])
        for col in health_cols:
            if col=='心理测评等级':
                importance_norm[col]=np.round(
                    feat_importance_4[col]*feat_importance_3['精神状态']*feat_importance_2['健康风险'],3)
            else:
                importance_norm[col]=np.round(
                    feat_importance_4[col]*feat_importance_3['生理状态']*feat_importance_2['健康风险'],3)
        for col in base_cols:
            importance_norm[col]=np.round(feat_importance_3[col]*feat_importance_2['其他风险'],3)
        for col in behavior_cols:
            importance_norm[col]=np.round(feat_importance_3[col]*feat_importance_2['不良行为'],3)
        for col in illegal_cols:
            importance_norm[col]=np.round(feat_importance_3[col]*feat_importance_2['违法违章'],3)
        health_importance,illegal_importance,behavior_importance,base_importance,men_feat_importance_norm,psy_feat_importance_norm,feat_importance_2,feat_importance_3,feat_importance_4=transform_feature_importance(
            importance_norm,feature_names,base_cols,behavior_cols,health_cols,illegal_cols,physiological_cols,
            mental_cols)
    else:
        feat_importance_1=0.25

    datas={}  #  源数据值
    final_scores={} # 总分细分

    # 将 SHAP 值转换为分数贡献
    #shap_scores=np.round(shap_vals*total_score.reshape(-1, 1),1)

    # 使用评分卡模型计算得分
    final_scores=scorecard_model(feature_names,X_input,datas,importance_norm,total_score,pred_prob,final_scores,behavior_cols,health_cols,illegal_cols,base_cols)

    raw_scores={}
    for i,col in enumerate(feature_names):
        datas[col]=X_input[:,i]
        if col in health_cols:
            if col == '心理测评等级':
                raw_scores[col]=final_scores[col]/health_importance/feat_importance_3['精神状态']/men_feat_importance_norm[col]
            else:
                raw_scores[col]=final_scores[col]/health_importance/feat_importance_3['生理状态']/psy_feat_importance_norm[col]
        if col in illegal_cols:
            raw_scores[col]=final_scores[col]/illegal_importance/feat_importance_3[col]
        if col in behavior_cols:
            raw_scores[col]=final_scores[col]/behavior_importance/feat_importance_3[col]
        if col in base_cols:
            raw_scores[col]=final_scores[col]/base_importance/feat_importance_3[col]

    final_scores,raw_scores=check_score(datas,behavior_cols,importance_norm,feature_names,final_scores,raw_scores)

    final_scores_4={k:v for k,v in final_scores.items() if k in feat_importance_4}
    final_scores_3={k:v for k,v in final_scores.items() if k in feat_importance_3}
    final_scores_3['精神状态']=final_scores['心理测评等级']
    # final_scores_3['生理状态']=np.sum(final_scores[col] for col in physiological_cols)
    # 推荐写法：直接对选中的列进行行求和 (axis=1)
    # final_scores_3['生理状态'] = final_scores[physiological_cols].sum(axis=1)
    final_scores_3['生理状态'] = sum(final_scores[col] for col in physiological_cols)

    raw_scores_4={k:v for k,v in raw_scores.items() if k in feat_importance_4}
    raw_scores_3={k:v for k,v in raw_scores.items() if k in feat_importance_3}
    raw_scores_3['精神状态']=raw_scores_4['心理测评等级']
    raw_scores_3['生理状态']=final_scores_3['生理状态']/feat_importance_3['生理状态']


    psy_list=[]
    for col in mental_cols:
        raw_scores_3['精神状态']=raw_scores_4[col]*men_feat_importance_norm[col]
    for col in physiological_cols:
        psy_list.append(raw_scores_4[col]*psy_feat_importance_norm[col])
    raw_scores_3['生理状态']=sum(psy_list)

    raw_scores_2={}
    raw_scores_2['其他风险']=sum(raw_scores_3[col]*feat_importance_3[col] for col in feature_names if col in base_cols)
    raw_scores_2['违法违章']=sum(raw_scores_3[col]*feat_importance_3[col] for col in feature_names if col in illegal_cols)
    raw_scores_2['不良行为']=sum(raw_scores_3[col]*feat_importance_3[col] for col in feature_names if col in behavior_cols)
    raw_scores_2['健康风险']=raw_scores_3['精神状态']*feat_importance_3['精神状态']+raw_scores_3['生理状态']*feat_importance_3['生理状态']

    final_scores_2={}
    final_scores_2['其他风险']=raw_scores_2['其他风险']*base_importance
    final_scores_2['违法违章']=raw_scores_2['违法违章']*illegal_importance
    final_scores_2['不良行为']=raw_scores_2['不良行为']*behavior_importance
    final_scores_2['健康风险']=raw_scores_2['健康风险']*health_importance

    total_score=np.clip(final_scores_2['健康风险']+final_scores_2['其他风险']+final_scores_2['违法违章']+final_scores_2['不良行为'],0.0,100.0)

    # feat_importance_1=0.25
    raw_scores_1=total_score
    final_scores_1=raw_scores_1*feat_importance_1

    final_scores_2={k:v*feat_importance_1 for k,v in final_scores_2.items()}
    final_scores_3={k:v*feat_importance_1 for k,v in final_scores_3.items()}
    final_scores_4={k:v*feat_importance_1 for k,v in final_scores_4.items()}

    return {
        'data':datas,  # 源数据值
        'final_scores_4':final_scores_4,  # 四级指标风险值
        'raw_scores_4':raw_scores_4,  # 四级指标转换后数值
        'final_scores_3':final_scores_3,  # 三级指标风险值
        'raw_scores_3':raw_scores_3,  # 三级指标转换后数值
        'final_scores_2':final_scores_2,  # 二级指标风险值
        'raw_scores_2':raw_scores_2,  # 二级指标转换后数值
        'final_scores_1':final_scores_1,  # 一级指标风险值
        'raw_scores_1':raw_scores_1,  # 一级指标转换后数值
        'feat_weights_4':feat_importance_4,  # 四级指标特征权重
        'feat_weights_3':feat_importance_3,  #  三级指标特征权重
        'feat_weights_2':feat_importance_2, #  二级指标特征权重
        'feat_weights_1':feat_importance_1, #  一级指标特征权重
    }



# ==================== 10. 演示预测 ====================
async def prediction_week(start_time:str, end_time:str,calculation_type:str):
    """演示两层分数预测"""
    print("\n"+"="*90)
    print("评分系统")
    print("="*90)

    # 加载模型
    d_start_time = datetime.strptime(start_time, '%Y-%m-%d')
    f_start_time = d_start_time-timedelta(days=d_start_time.day-1)
    s_start_time = f_start_time.strftime('%Y-%m-%d')
    model_data = joblib.load(f'model_1d_{s_start_time}_optimized.pkl')
    # model_data=joblib.load(f'model_1d_{s_start_time}.pkl')
    model=model_data['model']
    feature_names=model_data['feature_names']
    base_cols=model_data['base_cols']
    behavior_cols=model_data['behavior_cols']
    health_cols=model_data['health_cols']
    illegal_cols=model_data['illegal_cols']
    encoders=model_data['encoders']
    modes=model_data['modes']
    bounds_base=model_data['bounds_base']
    bounds_behavior=model_data['bounds_behavior']
    bounds_health=model_data['bounds_health']
    bounds_illegal=model_data['bounds_illegal']

    # 重新加载数据
    print("\n1. 加载数据...")
    # if df.empty:
    if calculation_type == '1':
        if datetime.now().strftime("%Y-%m-%d")==start_time:
            _data_date=datetime.strptime(start_time,"%Y-%m-%d")-timedelta(days=2)
            _data_date_str=_data_date.strftime("%Y-%m-%d")
            sql=driver_sql.predict_1d_sql_new(_data_date_str,_data_date_str)
        else:
            sql = driver_sql.predict_1d_sql_new(start_time, start_time)
    else:
        sql = driver_sql.predict_1d_sql_new(start_time,start_time)

    # sql = driver_sql.predict_1d_sql_new(start_time,start_time)
    print(f"周sql:{sql}")
    df = await read_raw_sql(sql)
    df = df.drop(columns=['route_id', 'work_hour'])

    data,_,_,_,_,all_feature_cols,info_cols=await load_and_preprocess_data(df)
    data=encode_and_handle_outliers(data,fit=False,encoders=encoders,modes=modes)
    data=process_outliers(data,base_cols,is_health=False,fit=False,bounds=bounds_base)
    data=process_outliers(data,behavior_cols,is_health=False,fit=False,bounds=bounds_behavior)
    data=process_outliers(data,health_cols,is_health=True,fit=False,bounds=bounds_health)
    data=process_outliers(data,illegal_cols,is_health=False,fit=False,bounds=bounds_illegal)

    info=data[info_cols].values

    X=data[all_feature_cols].values


    # 预测
    results=await calculate_two_layer_scores(
        model,X,feature_names,
        base_cols,behavior_cols,health_cols,illegal_cols,calculation_type,None,start_time
    )

    #保存权重
    if calculation_type=="1":
        await save_accident_weight_new(results,start_time,end_time)
    else:
        await save_accident_score_new(results, start_time, end_time, info,base_cols, behavior_cols, illegal_cols)
        await update_driver_scores_main_new(start_time)
        await main_warning(start_time)
    return results

if __name__=="__main__":
    # 分数预测
    results=asyncio.run(prediction_week('2026-08-02','2026-08-02',"0"))
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
