import pandas as pd
import numpy as np
from collections import Counter
from imblearn.over_sampling import SMOTE
from sklearn.preprocessing import LabelEncoder

# 处理总行驶里程数据
async def pre_process_mileage_data():
    data=pd.read_csv('2023-2024年驾驶员总里程.csv')
    mileage_by_driver=data.groupby('工号').agg({
        '驾驶员':'first',  # 取第一个姓名（同一工号姓名应该相同）
        '总里程':'sum'
    }).reset_index()

    # 重命名列
    mileage_by_driver.columns=['driver_id','driver_name','行驶总里程']
    return mileage_by_driver

def calculate_accident_rate(data):
    """计算历史事故率"""
    data['历史事故次数']=data['历史事故次数']*1000/data['历史行驶总里程']
    data.rename(columns={'历史事故次数':'历史事故率'},inplace=True)
    return data

# ==================== 1. 数据加载与预处理 ====================
async def load_and_preprocess_data(data):
    """加载数据并进行基础清洗"""
    # data=pd.read_csv(filepath)
    data.columns=['driver_id','driver_name',
                  '违规使用N档','上坡不规范行为','下坡不规范行为','不文明鸣笛','不规范转弯',
                  '停站N档违规','停车不挂N档','全局超速','急减速','急加速','安全启动',
                  '区间超速','右转弯未刹车','左转弯未刹车','平路不规范行为','不规范开关门',
                  '急停','急刹车','不规范进站','熄火滑行','空档滑行','起步急加速',
                  '斑马线不文明礼让','路口大油门','斑马线超速','车辆未停稳开车门',
                  '进站违规制动','违规使用总电','违规使用手刹','违规使用空调',
                  '门开禁启开关','车辆起步不关车门','不规范出站','安全带行为','has_accident']

    behavior_cols=['违规使用N档','上坡不规范行为','下坡不规范行为','不文明鸣笛','不规范转弯',
                   '停站N档违规','停车不挂N档','全局超速','急减速','急加速','安全启动','区间超速',
                   '右转弯未刹车','左转弯未刹车','平路不规范行为','不规范开关门','急停','急刹车',
                   '不规范进站','熄火滑行','空档滑行','起步急加速','斑马线不文明礼让','路口大油门',
                   '斑马线超速','车辆未停稳开车门','进站违规制动','违规使用总电','违规使用手刹',
                   '违规使用空调','门开禁启开关','车辆起步不关车门','不规范出站','安全带行为']

    all_feature_cols=behavior_cols

    mask=(data[behavior_cols].sum(axis=1)==0)&(data['has_accident']==1)
    data=data[~mask]
    #data=data.dropna()

    return data,behavior_cols,all_feature_cols


def process_outliers(data,cols,fit=True,bounds=None):
    if fit:
        bounds={}
        for col in cols:

            Q1=data[col].quantile(0.001)
            Q3=data[col].quantile(0.999)
            lower_bound=Q1
            upper_bound=Q3
            # 计算在上下界范围内的数据的均值
            valid_data = data[col][(data[col] >= lower_bound) & (data[col] <= upper_bound)]
            mean_val = valid_data.mean() if not valid_data.empty else data[col].mean()
            data[col]=data[col].clip(lower=lower_bound,upper=upper_bound)
            bounds[col] = (lower_bound, upper_bound, data[col].median())

            # data[col]=data[col].apply(
            #     lambda x:np.nan if pd.notna(x) and (x<lower_bound or x>upper_bound) else x
            # )
            data[col]=data[col].fillna(data[col].median())

    else:
        for col in cols:
            lower,upper,fill_val=bounds[col]
            data[col]=data[col].clip(lower=lower,upper=upper)
            data[col]=data[col].fillna(fill_val)
            # data[col]=data[col].apply(lambda x:np.nan if pd.notna(x) and (x<lower or x>upper) else x)
            # data[col]=data[col].fillna(fill_val)
        return data

    return data, bounds




