import pandas as pd


def clean_behavior_data(file_df, select_type, select_route):
    # 加载交通事故数据
    df = file_df

    df['longitude'] = pd.to_numeric(df['longitude'])
    df['latitude'] = pd.to_numeric(df['latitude'])
    # 检查必要列
    required_cols = ['longitude', 'latitude', 'report_type', 'route_id', 'organ_id']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"数据必须包含'{col}'列")
    # 筛选路线、类型
    if (select_route is not None) and (select_type is not None):
        df = df[df['route_id'] == select_route]
        df = df[df['report_type'] == select_type]
    else:
        return pd.DataFrame([])

    # 删除缺失值、保留聚类所需的经纬度数据
    df = df.dropna(subset=required_cols)
    df = df[['longitude', 'latitude']]
    df_clean = df.copy()
    df_clean = df_clean[(df_clean['longitude'] >= 109) & (df_clean['longitude'] <= 118) &
                        (df_clean['latitude'] >= 20) & (df_clean['latitude'] <= 26)]
    return df_clean


def clean_accident_data(file_df, select_route, select_type):
    # 加载交通事故数据
    df = file_df

    # 检查必要列
    required_cols = ['longitude', 'latitude', 'accident_types', 'route_id', 'organ_id', 'weight']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"数据必须包含'{col}'列")
    # 筛选路线、类型
    if select_route is not None:
        df = df[df['route_id'] == select_route]
    if select_type is not None:
        df = df[df['accident_types'].apply(lambda x: select_type in x)]
    else:
        return pd.DataFrame()

    # 保留聚类所需的经纬度数据、删除缺失值
    df = df.dropna(subset=required_cols)
    df_clean = df[['longitude', 'latitude', 'weight']].copy()

    # 检查坐标范围是否合理（广东省大致经度范围: 约109°E - 118°E，纬度范围: 约20°N - 26°N)
    df_clean['longitude'] = pd.to_numeric(df_clean['longitude'])
    df_clean['latitude'] = pd.to_numeric(df_clean['latitude'])
    df_clean = df_clean[(df_clean['longitude'] >= 109) & (df_clean['longitude'] <= 118) &
                        (df_clean['latitude'] >= 20) & (df_clean['latitude'] <= 26)]

    return df_clean


def classify_single(desc):
    """
    基于关键词匹配的单条事故描述的分类逻辑。类型列表： "1客伤", "2伤人", "3车损", "4其他"
    """
    # 车损关键词
    vehicle_keywords = ["追尾", '碰刮', '刮碰', "碰括", '刮烂', '碰撞', "无人受伤", "无人员受伤", '小车']

    # 客伤关键词
    passenger_positive = ["乘客", '客伤']

    # 伤人关键词
    person_positive = ['骑车者', '自行车驾驶员', '环卫工人']

    types = []

    # 1. 客伤：只要出现关键词就添加
    has_pass_pos = any(kw in desc for kw in passenger_positive)
    if has_pass_pos:
        types.append(1)

    # 2. 伤人：只要出现关键词就添加
    has_pers_pos = any(kw in desc for kw in person_positive)
    if has_pers_pos:
        types.append(2)

    # 3. 车损：只要出现关键词就添加
    if any(kw in desc for kw in vehicle_keywords):
        types.append(3)

    # 4. 如果以上都没有，则为“其他”
    if not types:
        types.append(4)

    return types


def add_accident_types(df):
    """
    为 DataFrame 添加事故类型列
    """
    if 'detail' not in df.columns:
        raise ValueError(f"DataFrame 中缺少列: 'detail'")

    # 基于经纬度数据判断是否有重复行
    df_new = df.drop_duplicates(subset=['longitude', 'latitude', 'route_id'], keep='first')

    accident_types = []
    for val in df_new['detail']:
        description = str(val)
        accident_types.append(classify_single(description))

    df_new['accident_types'] = accident_types
    return df_new


def clean_behavior_data_with_weight(file_df, select_route, coef=1):
    required_cols = ['longitude', 'latitude', 'report_type', 'route_id', 'organ_id', 'weight']

    # 检查
    for col in required_cols:
        if col not in file_df.columns:
            raise ValueError(f"数据必须包含'{col}'列")
    if select_route is None:
        return pd.DataFrame(columns=['longitude', 'latitude', 'weight'])

    # 筛选路线、去除空行、权重修正
    df = file_df[file_df['route_id'] == select_route].copy()
    df.dropna(subset=required_cols, inplace=True)
    df['weight'] = df['weight'] * coef

    # 将经纬度统一为数值类型、去重
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df.dropna(subset=['longitude', 'latitude', 'weight'], inplace=True)
    df.drop_duplicates(
        subset=['longitude', 'latitude', 'route_id', 'report_type'],
        keep='first',
        inplace=True
    )
    df = df[['longitude', 'latitude', 'weight']]
    df_clean = df.query(
        "longitude >= 109 and longitude <= 118 and latitude >= 20 and latitude <= 26"
    )
    return df_clean
