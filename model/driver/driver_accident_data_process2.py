import pandas as pd
import numpy as np
from collections import Counter
from imblearn.over_sampling import SMOTE
from sklearn.preprocessing import LabelEncoder

from model.driver.crud import get_ads_driver_mileage_yearly


# 处理总行驶里程数据
async def pre_process_mileage_data():
    # data1=pd.read_csv('2023-2024年驾驶员总里程.csv')
    data = await get_ads_driver_mileage_yearly()
    data['total_mileage'] = data['total_mileage'].to_numpy(dtype=float)
    mileage_by_driver=data.groupby('driver_code').agg({
        'driver_name':'first',  # 取第一个姓名（同一工号姓名应该相同）
        'total_mileage':'sum'
    }).reset_index()

    # 重命名列
    mileage_by_driver.columns=['司机id','司机名称','行驶总里程']
    return mileage_by_driver

def calculate_accident_rate(data):
    """计算历史事故率"""
    data['历史事故次数']=data['历史事故次数']*1000/data['历史行驶总里程']
    data.rename(columns={'历史事故次数':'历史事故率'},inplace=True)
    return data

# ==================== 1. 数据加载与预处理 ====================
async def load_and_preprocess_data(p_datas):
    """加载数据并进行基础清洗"""
    data=p_datas[:]

    data.columns=['司机名称','司机id','组织id','组织名称','性别','年龄','教育水平','驾龄','安全里程','日工时','历史事故次数',
                  '违规使用N档','上坡不规范行为','下坡不规范行为','不文明鸣笛','不规范转弯',
                  '停站N档违规','停车不挂N档','全局超速','急减速','急加速','安全启动',
                  '区间超速','右转弯未刹车','左转弯未刹车','平路不规范行为','不规范开关门',
                  '急停','急刹车','不规范进站','熄火滑行','空档滑行','起步急加速',
                  '斑马线不文明礼让','路口大油门','斑马线超速','车辆未停稳开车门',
                  '进站违规制动','违规使用总电','违规使用手刹','违规使用空调',
                  '门开禁启开关','车辆起步不关车门','不规范出站','安全带行为',
                  '车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警',
                  '前车碰撞预警','打电话','手长时间离开方向盘','严重疲劳驾驶识别',
                  '握方向盘不规范','驾驶姿势不端正','闯红灯','闯黄灯',
                  '违反交通标志标线','心率','酒精浓度','收缩压','舒张压','脉搏','血氧','体温','心理测评等级']

    mile_data=await pre_process_mileage_data()
    merged_data=data.merge(mile_data[['司机id','行驶总里程']],on='司机id',how='left')
    # merged_data['行驶总里程'].fillna(mile_data['行驶总里程'].median(),inplace=True)
    # 计算中位数
    median_val = mile_data['行驶总里程'].median()

    # 使用显式赋值代替 inplace=True
    merged_data['行驶总里程'] = merged_data['行驶总里程'].fillna(median_val)


    data['安全里程']=merged_data['行驶总里程']
    data.rename(columns={'安全里程':'历史行驶总里程'},inplace=True)

    data=calculate_accident_rate(data)

    data['历史安全行驶里程']=np.zeros(len(data))
    data['视频违规抽检率']=np.zeros(len(data))

    new_cols=['司机名称','司机id','组织id','组织名称','性别','年龄','教育水平','驾龄','历史行驶总里程','历史安全行驶里程','日工时','历史事故率',
                  '违规使用N档','上坡不规范行为','下坡不规范行为','不文明鸣笛','不规范转弯',
                  '停站N档违规','停车不挂N档','全局超速','急减速','急加速','安全启动',
                  '区间超速','右转弯未刹车','左转弯未刹车','平路不规范行为','不规范开关门',
                  '急停','急刹车','不规范进站','熄火滑行','空档滑行','起步急加速',
                  '斑马线不文明礼让','路口大油门','斑马线超速','车辆未停稳开车门',
                  '进站违规制动','违规使用总电','违规使用手刹','违规使用空调',
                  '门开禁启开关','车辆起步不关车门','不规范出站','安全带行为',
                  '车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警',
                  '前车碰撞预警','打电话','手长时间离开方向盘','严重疲劳驾驶识别',
                  '握方向盘不规范','驾驶姿势不端正','闯红灯','闯黄灯','违反交通标志标线','视频违规抽检率',
                  '心率','酒精浓度','收缩压','舒张压','脉搏','血氧','体温','心理测评等级']
    data=data[new_cols]

    base_cols=['性别','年龄','教育水平','驾龄','历史行驶总里程','历史安全行驶里程','日工时','历史事故率']
    behavior_cols=['违规使用N档','上坡不规范行为','下坡不规范行为','不文明鸣笛','不规范转弯',
                   '停站N档违规','停车不挂N档','全局超速','急减速','急加速','安全启动','区间超速',
                   '右转弯未刹车','左转弯未刹车','平路不规范行为','不规范开关门','急停','急刹车',
                   '不规范进站','熄火滑行','空档滑行','起步急加速','斑马线不文明礼让','路口大油门',
                   '斑马线超速','车辆未停稳开车门','进站违规制动','违规使用总电','违规使用手刹',
                   '违规使用空调','门开禁启开关','车辆起步不关车门','不规范出站','安全带行为',
                   '车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警','前车碰撞预警',
                   '打电话','手长时间离开方向盘','严重疲劳驾驶识别','握方向盘不规范','驾驶姿势不端正']
    health_cols=['心率','酒精浓度','收缩压','舒张压','脉搏','血氧','体温','心理测评等级']
    illegal_cols=['闯红灯','闯黄灯','违反交通标志标线','视频违规抽检率']

    info_cols=['司机名称','司机id','组织id','组织名称']

    all_feature_cols=base_cols+behavior_cols+illegal_cols+health_cols

    return data,base_cols,behavior_cols,health_cols,illegal_cols,all_feature_cols,info_cols


# ==================== 2. 特征编码与异常值处理 ====================
def encode_and_handle_outliers(data):
    le_gender=LabelEncoder()
    invalid_gender=~data['性别'].isin(['男','女'])
    if invalid_gender.any():
        data.loc[invalid_gender,'性别']=data['性别'].mode()[0]
    data['性别']=le_gender.fit_transform(data['性别'])

    valid_education_levels=['无','初中及以下','普高','中专','大学本科','大学专科','职高','中技']
    invalid_education=~data['教育水平'].isin(valid_education_levels)
    if invalid_education.any():
        data.loc[invalid_education,'教育水平']=data['教育水平'].mode()[0]

    ed_encoder=LabelEncoder()
    data['教育水平']=ed_encoder.fit_transform(data['教育水平'])

    valid_mental_levels=['重点关注','普通关注','中等关注']
    invalid_mental=~data['心理测评等级'].isin(valid_mental_levels)
    if invalid_mental.any():
        data.loc[invalid_mental,'心理测评等级']=data['心理测评等级'].mode().iloc[0]
    mental_encoder=LabelEncoder()
    data['心理测评等级']=mental_encoder.fit_transform(data['心理测评等级'])

    return data,le_gender,ed_encoder,mental_encoder


def process_outliers(data,cols,is_health=False):
    for col in cols:
        data[col] = pd.to_numeric(data[col], errors='coerce')
        if is_health:
            if col=='酒精浓度':
                data[col]=data[col].replace(-1,np.nan)
            else:
                data[col]=data[col].replace([-1,0],np.nan)

        Q1=data[col].quantile(0.01)
        Q3=data[col].quantile(0.99)

        if pd.isna(Q1) or pd.isna(Q3):
            continue

        IQR=Q3-Q1
        lower_bound=Q1-1.01*IQR
        upper_bound=Q3+1.01*IQR

        mask = data[col].notna() & ((data[col] < lower_bound) | (data[col] > upper_bound))
        data[col] = data[col].mask(mask, np.nan)

        # 填充均值
        mean_val = data[col].mean()
        if not pd.isna(mean_val):
            data[col] = data[col].fillna(mean_val)

        # data[col]=data[col].apply(
        #     lambda x:np.nan if pd.notna(x) and (x<lower_bound or x>upper_bound) else x
        # )
        # data[col]=data[col].fillna(data[col].mean())

    return data


# ==================== 3. 业务规则后处理 ====================
def apply_business_rules_direct(data,pred):
    """基于原始特征的硬规则后处理"""
    alcohol_high=data['酒精浓度'].values>20
    pred[alcohol_high]=np.minimum(pred[alcohol_high]+0.4,0.99)

    oxygen_low=data['血氧'].values<92
    pred[oxygen_low]=np.minimum(pred[oxygen_low]+0.25,0.95)

    heart_rate=data['心率'].values
    heart_abnormal=(heart_rate<50)|(heart_rate>120)
    pred[heart_abnormal]=np.minimum(pred[heart_abnormal]+0.15,0.95)

    severe_combo=(data['急加速'].values>5)&(data['急刹车'].values>5)&(data['疲劳预警'].values>0)
    pred[severe_combo]=np.minimum(pred[severe_combo]+0.3,0.98)

    return pred
