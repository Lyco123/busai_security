import asyncio

import joblib
from numba.core.dispatcher import LiftedCode
from pyparsing import Empty

from core.clickhouse_connect import connect_to_clickhouse
from model.driver.crud import get_accident_weights
from model.driver.driver_accident_data_process2 import load_and_preprocess_data,encode_and_handle_outliers,process_outliers
import shap
import numpy as np
import pandas as pd

from model.driver import crud
from model.driver.schemas.driver_profile import AbsDriverProfileMain, AbsDriverQuotaScoreSub
import uuid
from datetime import datetime, timedelta
from core.logger import logger
from utils.compute import Compute
from utils.tools import get_next_month_day, get_last_month_day


def cal_total_score(pred_prob):
    """
    计算总分
    """
    # 计算基础分
    base_scores = pred_prob * 100
    
    # 初始化总分
    total_score = np.zeros_like(base_scores)
    
    # 处理基础分 < 50 的情况：按排名拉长到 0-50 区间
    mask_low = base_scores < 50
    if np.any(mask_low):
        low_scores = base_scores[mask_low]
        # 获取排序后的索引（从小到大）
        sorted_indices = np.argsort(low_scores)
        n_low = len(low_scores)
        # 生成 0-50 之间的均匀分布值
        scaled_values = np.linspace(0, 50, n_low)
        # 根据原始排名分配新分数
        new_low_scores = np.zeros_like(low_scores)
        new_low_scores[sorted_indices] = scaled_values
        total_score[mask_low] = new_low_scores
    
    # 处理基础分 >= 50 的情况：按排名拉长到 50-100 区间
    mask_high = base_scores >= 50
    if np.any(mask_high):
        high_scores = base_scores[mask_high]
        # 获取排序后的索引（从小到大）
        sorted_indices = np.argsort(high_scores)
        n_high = len(high_scores)
        # 生成 50-100 之间的均匀分布值
        scaled_values = np.linspace(50, 100, n_high)
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
    # health_importance=safe_sum_importance(importance_norm, feature_names, health_cols)
    health_importance=sum(importance_norm.get(col,0) for i,col in enumerate(feature_names) if col in health_cols)
    illegal_importance=sum(importance_norm.get(col,0) for i,col in enumerate(feature_names) if col in illegal_cols)
    behavior_importance=sum(importance_norm.get(col,0) for i,col in enumerate(feature_names) if col in behavior_cols)
    base_importance=sum(importance_norm.get(col,0) for i,col in enumerate(feature_names) if col in base_cols)
    feat_importance_2={'健康风险':health_importance,'不良行为':behavior_importance,'违法违章':illegal_importance,
                       '其他风险':base_importance}

    feat_importance_3={}  # 3级指标权重
    for i,col in enumerate(feature_names):
        if col in health_cols:  # 有4级指标特殊处理
            if col=='心理测评等级':
                feat_importance_3['精神状态']=importance_norm.get(col,0)/(health_importance+1e-8)
                feat_importance_3['生理状态']=1-feat_importance_3['精神状态']
            else:
                continue
        elif col in illegal_cols:
            feat_importance_3[col]=importance_norm.get(col,0)/(illegal_importance+1e-8)
        elif col in behavior_cols:
            feat_importance_3[col]=importance_norm.get(col,0)/(behavior_importance+1e-8)
        elif col in base_cols:
            feat_importance_3[col]=importance_norm.get(col,0)/(base_importance+1e-8)

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
                exp_factor=np.clip(1.5-0.15*np.log(driving_years+1),0.8,1.5)
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
        #从表中取权重
        if hour=="1":
            feat_importance_1 = 1
            _id='驾驶员画像-事故小时风险'
        else:
            _id = '驾驶员画像-事故风险'
            feat_importance_1 = await get_accident_weights('1',_id,_start_time)
        feat_importance_2_data=await get_accident_weights('2',_id,_start_time)
        for data in feat_importance_2_data:
            if data['quota_name'] in feat_importance_2:
                feat_importance_2[data['quota_name']]=float(data['weight_rate'])
        feat_importance_3_data=await get_accident_weights('3',_id,_start_time)
        for data in feat_importance_3_data:
            if data['quota_name'] in feat_importance_3:
                feat_importance_3[data['quota_name']]=float(data['weight_rate'])
        feat_importance_4_data=await get_accident_weights('4',_id,_start_time)
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
        if hour=="1":
            feat_importance_1 = 1
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
    final_scores_3['生理状态']=sum(final_scores[col] for col in physiological_cols)
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


#准备中间数据
async def driver_weights_data_init():
    try:
        async with await connect_to_clickhouse() as client:
            # 这里可以执行数据库操作
            logger.info("驾驶员事故风险数据准备 开始时间：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            logger.info("数据库连接成功")


    except Exception as e:
        logger.error("驾驶员事故风险数据准备程序报错", exc_info=True)
        print(f"驾驶员能耗风险数据准备程序报错: {e}")

#保存事故风险权重
async def driver_accident_weights(_start_time:str,hour=None):
    """<UNK>"""
    try:
        async with await connect_to_clickhouse() as client:
            # 解析开始日期
            if hour == "1":
                start_date = datetime.strptime(_start_time, '%Y-%m-%d %H:%M:%S')
            else:
                start_date = datetime.strptime(_start_time, '%Y-%m-%d')
            # 权重有效结束日期
            end_date = get_next_month_day(start_date)  # + timedelta(days=30)

            #数据日期
            start_data_time = get_last_month_day(start_date)
            if hour=="1":
                _start_time_str = start_data_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                _start_time_str = start_data_time.strftime('%Y-%m-%d')

            results,feature_names,_,_,_,_,_ = await prediction(_start_time_str,"1",hour,_start_time)

            if hour=="1":
                quota_accident_quota_datas = await crud.Driver(client).get_driver_accident_quota_datas("驾驶员画像-事故小时风险",get_last_month_day(start_date).strftime('%Y-%m-%d'))
                start_date=datetime.strptime(_start_time.split(' ')[0], '%Y-%m-%d')
                end_date = get_next_month_day(start_date)-timedelta(days=1)
            else:
                quota_accident_quota_datas = await crud.Driver(client).get_driver_accident_quota_datas("驾驶员画像-事故风险",get_last_month_day(start_date).strftime('%Y-%m-%d'))
                end_date = end_date - timedelta(days=1)
            for d_quota_name3 in quota_accident_quota_datas:
                    d_quota_name3['id'] = str(uuid.uuid4())
                    d_quota_name3['calculate_weight_rate1'] = Compute.scientific_to_percentage(results['feat_weights_1'])
                    x = d_quota_name3.get('quota_name2')
                    converted_weight2 = Compute.safe_float_conversion(results['feat_weights_2'][x])
                    if converted_weight2 is not None:
                        calculate_weight2 = Compute.scientific_to_percentage(converted_weight2)
                    else:
                        calculate_weight2 = 0.00
                    d_quota_name3['calculate_weight_rate2'] = calculate_weight2
                    x = d_quota_name3.get('quota_name3')
                    if x in results['feat_weights_3']:
                        converted_weight3 = Compute.safe_float_conversion(results['feat_weights_3'][x])
                        if converted_weight3 is not None:
                            calculate_weight3 = Compute.scientific_to_percentage(converted_weight3)
                        else:
                            calculate_weight3 = 0.00
                        d_quota_name3['calculate_weight_rate3']=calculate_weight3
                    x = d_quota_name3.get('quota_name4')
                    if x!="-" and x!="" :
                        if x in results['feat_weights_4']:
                            converted_weight4 = Compute.safe_float_conversion(results['feat_weights_4'][x])
                            if converted_weight4 is not None:
                                calculate_weight4 = Compute.scientific_to_percentage(converted_weight4)
                            else:
                                calculate_weight4 = 0.00
                            d_quota_name3['calculate_weight_rate4'] = calculate_weight4
                    d_quota_name3['start_time'] = start_date #datetime.combine(datetime.now().date(), datetime.min.time())
                    d_quota_name3['end_time'] = end_date #datetime.combine(datetime.now().date() + timedelta(weeks=1),datetime.min.time())
                    d_quota_name3['creator'] = "system"
                    d_quota_name3['create_time'] = datetime.now()
                    d_quota_name3['updater'] = "system"
                    d_quota_name3['update_time'] = datetime.now()
            # 保存权重
            await crud.Driver(client).save_weights(quota_accident_quota_datas)
    except Exception as e:
        logger.error("保存驾驶员事故风险权重主程序执行出错", exc_info=True)
        print(f"保存驾驶员事故风险权重主程序执行出错: {e}")
    finally:
        import gc
        gc.collect()
    print("数据库连接已关闭")

# ==================== 10. 演示预测 ====================
#计算驾驶员事故风险分数
async def driver_accident_cores(start_time:str):
    try:
        async with await connect_to_clickhouse() as client:
            driver_weights_quota4 = await crud.Driver(client).get_driver_quota4('驾驶员画像-事故风险',start_time)
            # date_range = pd.date_range(start="2026-01-03", end="2026-01-31")
            date_range =[start_time]
            for date in date_range:
                # start_date_ = date.to_pydatetime()
                start_date_ = datetime.strptime(date, '%Y-%m-%d')
                start_date = start_date_.strftime('%Y-%m-%d')  # 转为字符串
                results, feature_names,info,base_cols,behavior_cols,health_cols,illegal_cols = await prediction(start_date,"0",None,start_time)
                # 格式化为YYYYMMDD格式
                start_date_str = start_date_.strftime('%Y%m%d')
                ppartition = start_date_str #datetime.now().strftime('%Y%m%d')
                driver_profile_main_datas = await crud.Driver(client).get_abs_driver_profile_main(ppartition)
                driver_ids = []
                if driver_profile_main_datas:
                    for d in driver_profile_main_datas:
                        driver_ids.append(d['driver_id'])
                main_datas = []
                quota_scores = []
                profile_main = None
                for i in range(len(info)):
                    # if info[i][1]!='66009787':
                    #     continue
                    if info[i][1] in driver_ids:
                        x = driver_ids.index(info[i][1])
                        main_id = driver_profile_main_datas[x]['id']
                        profile_main = None
                    else:
                        main_id = str(uuid.uuid4())
                        if info[i][2] is None:
                            d_organ_id = ""
                        else:
                            d_organ_id = info[i][2]
                        if info[i][3] is None:
                            d_organ_name = ""
                        else:
                            d_organ_name = info[i][3]
                        profile_main = AbsDriverProfileMain(
                            ppartition=start_date_str,#datetime.now().strftime("%Y%m%d"),
                            id=main_id,
                            driver_id=info[i][1],
                            driver_name=info[i][0],
                            organ_id=d_organ_id,
                            organ_name=d_organ_name,
                            calculate_date=start_date_, #datetime.combine(datetime.now().date(), datetime.min.time()),
                            evalutaion_type="",
                            score=0,
                            suggested_content="",
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            route_rank=0,
                            route_acc_rank=0,
                            route_total=0,
                            route_rate=0.00
                        )
                    quota_score_1 = AbsDriverQuotaScoreSub(
                        ppartition=start_date_str,#datetime.now().strftime("%Y%m%d"),
                        id=str(uuid.uuid4()),
                        main_id=main_id,
                        quota_id="驾驶员画像-事故风险",
                        quota_name="事故风险",
                        score=round(float(results['raw_scores_1'][i]), 6),
                        weight_rate=round(float(results['feat_weights_1']),6),
                        original_value=round(float(results['final_scores_1'][i]), 6),
                        risk_data="",
                        quota_level="1",
                        parent_id="驾驶员画像",
                        creator="system",
                        create_time=datetime.now(),
                        updater="system",
                        update_time=datetime.now(),
                        deleted="0",
                        start_time=start_date_,
                        end_time=start_date_,
                    )
                    quota_scores.append(quota_score_1.to_dict())
                    for x in ['其他风险', '健康风险', '违法违章', '不良行为']:
                        quota_score_2 = AbsDriverQuotaScoreSub(
                            ppartition=start_date_str,#datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id="驾驶员画像-事故风险-" + x,
                            quota_name=x,
                            score=round(float(results['raw_scores_2'][x][i]), 6),
                            weight_rate=round(round(float(results['feat_weights_1']),6)*round(float(results['feat_weights_2'][x]),6),6),
                            original_value=round(float(results['final_scores_2'][x][i]),6),
                            risk_data="",
                            quota_level="2",
                            parent_id="驾驶员画像-事故风险",
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=start_date_,
                        )
                        quota_scores.append(quota_score_2.to_dict())
                        if x == '其他风险':
                            feat_cols = base_cols
                        elif x == '健康风险':
                            feat_cols = ['生理状态','精神状态']
                        elif x == '不良行为':
                            feat_cols = behavior_cols
                        elif x == '违法违章':
                            feat_cols = illegal_cols
                        for j, feat in enumerate(feat_cols):
                            if feat in results['data']:
                                _risk_data=str(results['data'][feat][i])
                            else:
                                _risk_data=""
                            quota_score_3 = AbsDriverQuotaScoreSub(
                                ppartition=start_date_str,#datetime.now().strftime("%Y%m%d"),
                                id=str(uuid.uuid4()),
                                main_id=main_id,
                                quota_id="驾驶员画像-事故风险-" + x + "-" + feat,
                                quota_name=feat,
                                score=round(float(results['raw_scores_3'][feat][i]), 6),
                                # weight_rate=round(results['feat_weights'][j], 5),
                                # original_value=round(results['final_scores'][feat][i], 1),
                                weight_rate=round(round(float(results['feat_weights_1']),6)*round(float(results['feat_weights_2'][x]),6)*round(float(results['feat_weights_3'][feat]),6),6),
                                original_value=round(float(results['final_scores_3'][feat][i]), 6),
                                risk_data=_risk_data,
                                quota_level="3",
                                parent_id="驾驶员画像-事故风险-" + x,
                                creator="system",
                                create_time=datetime.now(),
                                updater="system",
                                update_time=datetime.now(),
                                deleted="0",
                                start_time=start_date_,
                                end_time=start_date_,
                            )
                            quota_scores.append(quota_score_3.to_dict())
                    for quota in driver_weights_quota4:
                        if quota['quota_name'] in results['final_scores_4']:
                            quota_score_4= AbsDriverQuotaScoreSub(
                                ppartition=start_date_str,#datetime.now().strftime("%Y%m%d"),
                                id=str(uuid.uuid4()),
                                main_id=main_id,
                                quota_id=quota['quota_id'],
                                quota_name=quota['quota_name'],
                                score=round(float(results['raw_scores_4'][quota['quota_name']][i]), 6),
                                weight_rate=round(round(float(results['feat_weights_1']),6)*round(float(results['feat_weights_2'][quota['quota_name2']]),6)*
                                            round(float(results['feat_weights_3'][quota['quota_name3']]),6)*
                                            round(float(results['feat_weights_4'][quota['quota_name']]),6),6),
                                original_value=round(float(results['final_scores_4'][quota['quota_name']][i]), 6),
                                risk_data=str(results['data'][quota['quota_name']][i]),
                                quota_level="4",
                                parent_id=quota['parent_id'],
                                creator="system",
                                create_time=datetime.now(),
                                updater="system",
                                update_time=datetime.now(),
                                deleted="0",
                                start_time=start_date_,
                                end_time=start_date_,
                            )
                            quota_scores.append(quota_score_4.to_dict())
                    if profile_main is not None:
                        main_datas.append(profile_main.to_dict())
                    # 保存驾驶员事故风险数据
                await crud.Driver(client).save(main_datas, quota_scores)
            # df_export=pd.DataFrame(all_records)
            # df_export.to_csv('two_layer_scores.csv',index=False,encoding='utf-8-sig')
            # print(f"已导出 {len(df_export)} 条记录到 two_layer_scores.csv")
            # print("\nCSV列说明:")
            # print("  - 原始分(0-100): 特征的绝对风险水平（独立评分）")
            # print("  - 转化系数: 该样本的原始分→总分细分的缩放比例")
            # print("  - 总分细分: 该特征在最终总分中的实际贡献")
            # print("  - 关系: 原始分 × 转化系数 = 总分细分")
    except Exception as e:
        logger.exception(f"驾驶员画像事故风险分数主程序执行出错:{e}")
        print(f"驾驶员画像事故风险分数主程序执行出错: {e}")
    print("数据库连接已关闭")

async def driver_accident_hour_cores(_start_time:str):
    try:
        async with await connect_to_clickhouse() as client:
            driver_weights_quota4 = await crud.Driver(client).get_driver_quota4('驾驶员画像-事故小时风险',_start_time)
            # start_date_ = datetime.strptime(_start_time, '%Y-%m-%d %H:00:00')
            dt_obj = datetime.strptime(_start_time, '%Y-%m-%d %H:%M:%S')
            start_date_ = dt_obj.replace(minute=0, second=0, microsecond=0)
            results, feature_names,info,base_cols,behavior_cols,health_cols,illegal_cols = await prediction(_start_time,"0","1",_start_time)
            # 格式化为YYYYMMDD格式
            start_date_str = start_date_.strftime('%Y%m%d%H')
            ppartition = start_date_str #datetime.now().strftime('%Y%m%d')
            driver_profile_hour_main_datas = await crud.Driver(client).get_abs_driver_profile_hour_main(ppartition)
            driver_ids = []
            if driver_profile_hour_main_datas:
                for d in driver_profile_hour_main_datas:
                    driver_ids.append(d['driver_id'])
            main_datas = []
            quota_scores = []
            profile_main = None
            for i in range(len(info)):
                # if info[i][1]!='63000398':
                #     continue
                if info[i][1] in driver_ids:
                    x = driver_ids.index(info[i][1])
                    main_id = driver_profile_hour_main_datas[x]['id']
                    profile_main = None
                else:
                    main_id = str(uuid.uuid4())
                    if info[i][2] is None:
                        d_organ_id = ""
                    else:
                        d_organ_id = info[i][2]
                    if info[i][3] is None:
                        d_organ_name = ""
                    else:
                        d_organ_name = info[i][3]
                    profile_main = AbsDriverProfileMain(
                        ppartition=start_date_str,#datetime.now().strftime("%Y%m%d"),
                        id=main_id,
                        driver_id=info[i][1],
                        driver_name=info[i][0],
                        organ_id=d_organ_id,
                        organ_name=d_organ_name,
                        calculate_date=start_date_, #datetime.combine(datetime.now().date(), datetime.min.time()),
                        evalutaion_type="",
                        score=0,
                        suggested_content="",
                        creator="system",
                        create_time=datetime.now(),
                        updater="system",
                        update_time=datetime.now(),
                        deleted="0",
                        route_rank = 0,
                        route_acc_rank = 0,
                        route_total = 0,
                        route_rate = 0.00
                    )
                quota_score_1 = AbsDriverQuotaScoreSub(
                    ppartition=start_date_str,#datetime.now().strftime("%Y%m%d"),
                    id=str(uuid.uuid4()),
                    main_id=main_id,
                    quota_id="驾驶员画像-事故小时风险",
                    quota_name="事故小时风险",
                    score=round(float(results['raw_scores_1'][i]), 6),
                    weight_rate=float(results['feat_weights_1']),
                    original_value=round(float(results['final_scores_1'][i]), 6),
                    risk_data="",
                    quota_level="1",
                    parent_id="驾驶员画像",
                    creator="system",
                    create_time=datetime.now(),
                    updater="system",
                    update_time=datetime.now(),
                    deleted="0",
                    start_time=start_date_,
                    end_time=start_date_,
                )
                profile_main.score=round(float(results['raw_scores_1'][i]))
                quota_scores.append(quota_score_1.to_dict())
                for x in ['其他风险', '健康风险', '违法违章', '不良行为']:
                    quota_score_2 = AbsDriverQuotaScoreSub(
                        ppartition=start_date_str,#datetime.now().strftime("%Y%m%d"),
                        id=str(uuid.uuid4()),
                        main_id=main_id,
                        quota_id="驾驶员画像-事故小时风险-" + x,
                        quota_name=x,
                        score=round(float(results['raw_scores_2'][x][i]), 6),
                        weight_rate=float(results['feat_weights_1'])*float(results['feat_weights_2'][x]),
                        original_value=round(float(results['final_scores_2'][x][i]),6),
                        risk_data="",
                        quota_level="2",
                        parent_id="驾驶员画像-事故小时风险",
                        creator="system",
                        create_time=datetime.now(),
                        updater="system",
                        update_time=datetime.now(),
                        deleted="0",
                        start_time=start_date_,
                        end_time=start_date_,
                    )
                    quota_scores.append(quota_score_2.to_dict())
                    if x == '其他风险':
                        feat_cols = base_cols
                    elif x == '健康风险':
                        feat_cols = ['生理状态','精神状态']
                    elif x == '不良行为':
                        feat_cols = behavior_cols
                    elif x == '违法违章':
                        feat_cols = illegal_cols
                    for j, feat in enumerate(feat_cols):
                        if feat in results['data']:
                            _risk_data=str(results['data'][feat][i])
                        else:
                            _risk_data=""
                        quota_score_3 = AbsDriverQuotaScoreSub(
                            ppartition=start_date_str,#datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id="驾驶员画像-事故小时风险-" + x + "-" + feat,
                            quota_name=feat,
                            score=round(float(results['raw_scores_3'][feat][i]), 6),
                            # weight_rate=round(results['feat_weights'][j], 5),
                            # original_value=round(results['final_scores'][feat][i], 1),
                            weight_rate=float(results['feat_weights_1'])*float(results['feat_weights_2'][x])*float(results['feat_weights_3'][feat]),
                            original_value=round(float(results['final_scores_3'][feat][i]), 6),
                            risk_data=_risk_data,
                            quota_level="3",
                            parent_id="驾驶员画像-事故小时风险-" + x,
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=start_date_,
                        )
                        quota_scores.append(quota_score_3.to_dict())
                for quota in driver_weights_quota4:
                    if quota['quota_name'] in results['final_scores_4']:
                        quota_score_4= AbsDriverQuotaScoreSub(
                            ppartition=start_date_str,#datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id=quota['quota_id'],
                            quota_name=quota['quota_name'],
                            score=round(float(results['raw_scores_4'][quota['quota_name']][i]), 6),
                            weight_rate=float(results['feat_weights_1'])*float(results['feat_weights_2'][quota['quota_name2']])*
                                        float(results['feat_weights_3'][quota['quota_name3']])*
                                        float(results['feat_weights_4'][quota['quota_name']]),
                            original_value=round(float(results['final_scores_4'][quota['quota_name']][i]), 6),
                            risk_data=str(results['data'][quota['quota_name']][i]),
                            quota_level="4",
                            parent_id=quota['parent_id'],
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=start_date_,
                        )
                        quota_scores.append(quota_score_4.to_dict())
                if profile_main is not None:
                    main_datas.append(profile_main.to_dict())
                    # 保存驾驶员事故风险数据
            await crud.Driver(client).save_hour(main_datas, quota_scores)

    except Exception as e:
        logger.exception(f"驾驶员画像一小时事故风险分数主程序执行出错:{e}")
        print(f"驾驶员画像一小时事故风险分数主程序执行出错: {e}")
    print("数据库连接已关闭")


async def prediction(start_time_str: str,calculation_type:str,hour=None,_start_time:str=None) -> dict | None:
    # 使用异步上下文管理器方式
    try:
        async with await connect_to_clickhouse() as client:
            """演示两层分数预测"""
            print("\n"+"="*90)
            print("驾驶员事故风险 评分系统开始时间：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            # 加载模型
            if hour=="1":
                model_data = joblib.load('single_model_two_layer_1hour.pkl')
            else:
                model_data=joblib.load('single_model_two_layer.pkl')
            model=model_data['model']
            feature_names=model_data['feature_names']
            base_cols=model_data['base_cols']
            behavior_cols=model_data['behavior_cols']
            health_cols=model_data['health_cols']
            illegal_cols=model_data['illegal_cols']

            if hour=="1":
                _pd_datas = await crud.Driver(client).get_drivers_hour_datas(start_time_str)
            else:
                _pd_datas= await crud.Driver(client).get_drivers_day_datas(start_time_str)

            if _pd_datas.empty:
                raise ValueError(f"{start_time_str}事故风险评分宽表为空，无法输出评分结果")

            # _pd_datas = pd.DataFrame(_p_datas)
            if 'route_id' in _pd_datas.columns:
                _pd_datas.drop('route_id', axis=1, inplace=True)
            # 重新加载数据
            data,base_cols,behavior_cols,health_cols,illegal_cols,all_feature_cols,info_cols=await load_and_preprocess_data(_pd_datas)
            data,_,_,_=encode_and_handle_outliers(data)
            data=process_outliers(data,base_cols,is_health=False)
            data=process_outliers(data,behavior_cols,is_health=False)
            data=process_outliers(data,health_cols,is_health=True)
            data=process_outliers(data,illegal_cols,is_health=False)

            info=data[info_cols].values

            X=data[all_feature_cols].values

            # 取前3个样本演示
            X_demo=X[:]

            # 预测
            results=await calculate_two_layer_scores(
                model,X_demo,feature_names,
                base_cols,behavior_cols,health_cols,illegal_cols,calculation_type,hour,_start_time
            )
            return results,feature_names,info,base_cols,behavior_cols,health_cols,illegal_cols
    except Exception as e:
        logger.exception(f"驾驶员事故风险主程序执行出错{e}")
        print(f"驾驶员画像主程序执行出错: {e}")
    print("数据库连接已关闭")


# async def gen_driver_score_sample():
#     # 使用异步上下文管理器方式
#     try:
#         async with await connect_to_clickhouse() as client:
#             """演示两层分数预测"""
#             print("\n"+"="*90)
#             print("驾驶员测试数据开始时间：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
#
#             quota1_datas = await crud.Driver(client).get_driver_quota1()
#             quota2_datas = await crud.Driver(client).get_driver_quota2()
#             quota3_datas = await crud.Driver(client).get_driver_quota3()
#             quota4_datas = await crud.Driver(client).get_driver_quota4()
#             quota_datas = quota1_datas + quota2_datas + quota3_datas + quota4_datas
#
#             driver_profile_main_datas=await crud.Driver(client).get_abs_driver_profile_main('20260226')
#             quota_scores=[]
#             for d in driver_profile_main_datas:
#                 main_id=d['id']
#                 for quota1 in quota_datas:
#                     quota_score_1=AbsDriverQuotaScoreSub(
#                         ppartition=datetime.now().strftime("%Y%m%d"),
#                         id=str(uuid.uuid4()),
#                         main_id=main_id,
#                         quota_id=quota1['quota_id'],
#                         quota_name=quota1['quota_name'],
#                         score=9.99,
#                         weight_rate=9.99,
#                         original_value=9.99,
#                         risk_data="9.99",
#                         quota_level=quota1['quota_level'],
#                         parent_id=quota1['parent_id'],
#                         creator="system",
#                         create_time=datetime.now(),
#                         updater="system",
#                         update_time=datetime.now(),
#                         deleted="0",
#                     )
#                     quota_scores.append(quota_score_1.to_dict())
#             # 保存驾驶员事故风险数据
#             await crud.Driver(client).save([], quota_scores)
#
#             logger.info("驾驶员事故风险 评分系统结束时间：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
#             # return main_datas,quota_scores
#     except Exception as e:
#         logger.error("驾驶员事故风险主程序执行出错", exc_info=True)
#         print(f"驾驶员画像主程序执行出错: {e}")
#     print("数据库连接已关闭")


def safe_sum_importance(importance_norm, feature_names, health_cols):
    """
    安全地计算重要性总和，避免KeyError错误
    """
    # 步骤1: 检查输入参数类型
    if not isinstance(importance_norm, (dict, pd.Series)):
        raise TypeError("importance_norm必须是字典或pandas Series类型")

    # 步骤2: 检查feature_names是否为列表
    if not isinstance(feature_names, list):
        feature_names = list(feature_names)

    # 步骤3: 检查health_cols是否为列表
    if not isinstance(health_cols, (list, set)):
        health_cols = list(health_cols)

    # 步骤4: 创建安全的列名映射
    # 确保所有列名都是字符串类型
    safe_health_cols = [str(col) for col in health_cols]
    safe_feature_names = [str(name) for name in feature_names]

    # 步骤5: 找出在health_cols中的feature_names索引
    valid_indices = []
    for i, col in enumerate(safe_feature_names):
        if col in safe_health_cols:
            valid_indices.append(i)

    # 步骤6: 安全访问importance_norm
    total_sum = 0
    for i in valid_indices:
        try:
            # 使用列名而不是索引访问
            col_name = safe_feature_names[i]
            if col_name in importance_norm:
                total_sum += importance_norm[col_name]
            else:
                print(f"警告: 列名 '{col_name}' 在importance_norm中不存在")
        except Exception as e:
            print(f"访问索引 {i} 时出错: {e}")

    return total_sum

if __name__=="__main__":
    # 分数预测
    # asyncio.run(prediction())
    asyncio.run(driver_accident_cores("2026-04-27"))
    # asyncio.run(driver_accident_weights("2026-01-01"))
    # asyncio.run(gen_driver_score_sample())