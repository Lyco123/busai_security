import pandas as pd
import numpy as np
from collections import Counter
from imblearn.over_sampling import SMOTE
from sklearn.preprocessing import LabelEncoder

from model.driver.crud import read_raw_sql


# 处理总行驶里程数据
async def pre_process_mileage_data():
    data = await read_raw_sql("select ppartition,organ_name,driver_code as `工号` ,driver_name as `驾驶员`,total_mileage as `总里程` from ads_driver_mileage_yearly")

    # data=pd.read_csv('2023-2024年驾驶员总里程.csv')
    mileage_by_driver=data.groupby('工号').agg({
        '驾驶员':'first',  # 取第一个姓名（同一工号姓名应该相同）
        '总里程':'sum'
    }).reset_index()

    # 重命名列
    mileage_by_driver.columns=['driver_id','driver_name','行驶总里程']
    return mileage_by_driver

def calculate_accident_rate(data):
    """计算历史事故率"""
    data['历史事故次数'] = pd.to_numeric(data['历史事故次数'], errors='coerce').fillna(0)
    data['历史行驶总里程'] = pd.to_numeric(data['历史行驶总里程'], errors='coerce').fillna(0)


    data['历史事故次数'] = (data['历史事故次数'] * 1000).div(data['历史行驶总里程'], fill_value=0)

    # data['历史事故次数']=data['历史事故次数']*1000/data['历史行驶总里程']
    data.rename(columns={'历史事故次数':'历史事故率'},inplace=True)
    return data

# ==================== 1. 数据加载与预处理 ====================
async def load_and_preprocess_data(data):
    """加载数据并进行基础清洗"""
    # data=pd.read_csv(filepath)

    data.columns=['driver_id','driver_name','性别','年龄','教育水平','驾龄','安全里程','日工时','历史事故次数',
                  '违规使用N档','上坡不规范行为','下坡不规范行为','不文明鸣笛','不规范转弯',
                  '停站N档违规','停车不挂N档','全局超速','急减速','急加速','安全启动',
                  '区间超速','右转弯未刹车','左转弯未刹车','平路不规范行为','不规范开关门',
                  '急停','急刹车','不规范进站','熄火滑行','空档滑行','起步急加速',
                  '斑马线不文明礼让','路口大油门','斑马线超速','车辆未停稳开车门',
                  '进站违规制动','违规使用总电','违规使用手刹','违规使用空调',
                  '门开禁启开关','车辆起步不关车门','不规范出站','安全带行为',
                  '车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警',
                  '前车碰撞预警','打电话','手长时间离开方向盘','严重疲劳驾驶识别',
                  '握方向盘不规范','驾驶姿势不端正','闯红灯','闯黄灯','违反交通标志标线',
                  '心率','酒精浓度','收缩压','舒张压','脉搏','血氧','体温','心理测评等级',
                  'has_accident']

    mile_data=await pre_process_mileage_data()
    merged_data=data.merge(mile_data[['driver_id','行驶总里程']],on='driver_id',how='left')
    merged_data['行驶总里程'].fillna(merged_data['行驶总里程'].median(), inplace=True)
    data['安全里程']=merged_data['行驶总里程']
    data.rename(columns={'安全里程':'历史行驶总里程'}, inplace=True)

    data=calculate_accident_rate(data)
    #
    data['历史安全行驶总里程']=np.zeros(len(data))
    data['视频抽检违规率']=np.zeros(len(data))

    new_cols=['driver_id','driver_name','性别','年龄','教育水平','驾龄','历史行驶总里程','历史安全行驶总里程','日工时','历史事故率',
              '违规使用N档','上坡不规范行为','下坡不规范行为','不文明鸣笛','不规范转弯',
              '停站N档违规','停车不挂N档','全局超速','急减速','急加速','安全启动',
              '区间超速','右转弯未刹车','左转弯未刹车','平路不规范行为','不规范开关门',
              '急停','急刹车','不规范进站','熄火滑行','空档滑行','起步急加速',
              '斑马线不文明礼让','路口大油门','斑马线超速','车辆未停稳开车门',
              '进站违规制动','违规使用总电','违规使用手刹','违规使用空调',
              '门开禁启开关','车辆起步不关车门','不规范出站','安全带行为',
              '车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警',
              '前车碰撞预警','打电话','手长时间离开方向盘','严重疲劳驾驶识别',
              '握方向盘不规范','驾驶姿势不端正','闯红灯','闯黄灯','违反交通标志标线','视频抽检违规率',
              '心率','酒精浓度','收缩压','舒张压','脉搏','血氧','体温','心理测评等级',
              'has_accident']
    data=data[new_cols]

    base_cols=['性别','年龄','教育水平','驾龄','历史行驶总里程','历史安全行驶总里程','日工时','历史事故率']
    behavior_cols=['违规使用N档','上坡不规范行为','下坡不规范行为','不文明鸣笛','不规范转弯',
                   '停站N档违规','停车不挂N档','全局超速','急减速','急加速','安全启动','区间超速',
                   '右转弯未刹车','左转弯未刹车','平路不规范行为','不规范开关门','急停','急刹车',
                   '不规范进站','熄火滑行','空档滑行','起步急加速','斑马线不文明礼让','路口大油门',
                   '斑马线超速','车辆未停稳开车门','进站违规制动','违规使用总电','违规使用手刹',
                   '违规使用空调','门开禁启开关','车辆起步不关车门','不规范出站','安全带行为',
                   '车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警','前车碰撞预警',
                   '打电话','手长时间离开方向盘','严重疲劳驾驶识别','握方向盘不规范','驾驶姿势不端正']
    health_cols=['心率','酒精浓度','收缩压','舒张压','脉搏','血氧','体温','心理测评等级']
    illegal_cols=['闯红灯','闯黄灯','违反交通标志标线','视频抽检违规率']

    all_feature_cols=base_cols+behavior_cols+illegal_cols+health_cols

    mask=(data[behavior_cols].sum(axis=1)==0)&(data['has_accident']==1)
    data=data[~mask]
    # data=data.dropna()

    return data,base_cols,behavior_cols,health_cols,illegal_cols,all_feature_cols


# ==================== 2. 特征编码与异常值处理 ====================
def encode_and_handle_outliers(data,fit,encoders=None,modes=None):
    if fit:
        modes={}

        le_encoder={
            '男': 0,
            '女': 1
        }
        invalid_gender=~data['性别'].isin(['男','女'])
        if invalid_gender.any():
            data.loc[invalid_gender,'性别']=data['性别'].mode()[0]
        modes['性别']=data['性别'].mode()[0]
        data['性别']=data['性别'].map(le_encoder)

        ed_encoder={
            '无': 0,
            '初中及以下': 1,
            '普高': 2,
            '中专':3,
            '大学本科':4,
            '大学专科':5,
            '职高':6,
            '中技':7
        }
        valid_education_levels=['无','初中及以下','普高','中专','大学本科','大学专科','职高','中技']
        invalid_education=~data['教育水平'].isin(valid_education_levels)
        if invalid_education.any():
            data.loc[invalid_education,'教育水平']=data['教育水平'].mode()[0]
        modes['教育水平']=data['教育水平'].mode()[0]
        data['教育水平']=data['教育水平'].map(ed_encoder)

        me_encoder={
            '重点关注': 0,
            '普通关注': 1,
            '中等关注': 2
        }
        valid_mental_levels=['重点关注','普通关注','中等关注']
        invalid_mental=~data['心理测评等级'].isin(valid_mental_levels)

        mode_vals=data['心理测评等级'].mode()

        if not mode_vals.empty:
            fill_value = mode_vals.iloc[0]
        else:
            fill_value = np.nan

        if invalid_mental.any():
            # data.loc[invalid_mental,'心理测评等级']=data['心理测评等级'].mode()[0]

            data.loc[invalid_mental, '心理测评等级'] = fill_value
        # modes['心理测评等级']=data['心理测评等级'].mode()[0]
        modes['心理测评等级']=fill_value
        data['心理测评等级'] = data['心理测评等级'].map(me_encoder)

    else:
        le_gender,le_edu,le_me=encoders
        data['性别']=data['性别'].apply(lambda x:x if x in le_gender else modes['性别'])
        data['性别']=data['性别'].map(le_gender)
        data['教育水平']=data['教育水平'].apply(lambda x:x if x in le_edu else modes['教育水平'])
        data['教育水平']=data['教育水平'].map(le_edu)
        data['心理测评等级']=data['心理测评等级'].apply(lambda x:x if x in le_me else modes['心理测评等级'])
        data['心理测评等级']=data['心理测评等级'].map(le_me)
        return data

    return data,(le_encoder,ed_encoder,me_encoder),modes


def process_outliers(data,cols,is_health=False,fit=True,bounds=None):
    if fit:
        bounds={}
        for col in cols:
            if is_health:
                data[col]=pd.to_numeric(data[col],errors='coerce')
                if col=='酒精浓度':
                    data[col] = data[col].apply(lambda x: np.nan if pd.notna(x) and x < 0 else x)
                else:
                    data[col] = data[col].apply(lambda x: np.nan if pd.notna(x) and x <= 0 else x)

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
            if is_health:
                data[col]=pd.to_numeric(data[col],errors='coerce')
                if col=='酒精浓度':
                    data[col]=data[col].replace(-1,np.nan)
                else:
                    data[col]=data[col].replace([-1,0],np.nan)
            data[col]=data[col].clip(lower=lower,upper=upper)
            data[col]=data[col].fillna(fill_val)
            # data[col]=data[col].apply(lambda x:np.nan if pd.notna(x) and (x<lower or x>upper) else x)
            # data[col]=data[col].fillna(fill_val)
        return data

    return data, bounds




