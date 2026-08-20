from datetime import datetime, timedelta

from model.route import ClickHouse_sql_query_data
import pandas as pd

"""从数据库中读取线路画像所有三级指标的名称与权重，输出线路所有指标及权重字典、 十种行为report 列表
该代码功能用于驾驶行为读取、千公里指标计算、每周线路评分计算功能函数
"""
async def main(_start_time):
    # 驾驶行为序号名称对应字典
    type_behavior_dict = {
                'report_type6': '起步急加速',
                'report_type8': '急加速',
                'report_type7': '急减速',
                'report_type9': '急刹车',
                'report_type15': '斑马线不文明礼让',
                'report_type14': '斑马线超速',
                'report_type18': '违规使用手刹',
                'report_type1': '停站N档违规',
                'report_type16': '违规使用N档',
                'report_type22': '不规范转弯',
                'report_type11': '车辆未停稳开车门',
                'report_type12': '车辆起步不关车门',
                'report_type5': '空档滑行',
                'report_type4': '熄火滑行',
                'report_type19': '不文明鸣笛',
                'report_type3': '安全带行为',
                'report_type21': '不规范进站',
                'report_type20': '不规范出站',
                'report_type10': '急停',
                'report_type13': '门开禁启开关',
                'report_type2': '停车不挂N档',
                'report_type17': '不规范开关门',
                'report_type23': '安全启动',
                'report_type24': '违规使用空调',
                'report_type25': '平路不规范行为',
                'report_type26': '上坡不规范行为',
                'report_type27': '下坡不规范行为',
                'report_type28': '违规使用总电',
                'report_type29': '路口大油门',
                'report_type30': '进站违规制动',
                'report_type33': '区间超速',
                'report_type34': '全局超速',
                'report_type36': '左转弯未刹车',
                'report_type37': '右转弯未刹车'
                # 'report_type32': '路口速度评价'
            }
    behavior_type_dict = {v: k for k, v in type_behavior_dict.items()}

    route_static_risk_quota = [
        '急转弯点数量', '斑马线数量', '左转弯数量', '右转弯数量', '上坡路段数量', '下坡路段数量', '事故黑点','总修正里程',
        '区域限速点数量', '行为黑点', '老人刷卡比率', '临水临崖数量', '学校数量', '商场数量', '体育馆数量', '医院数量',
        '刷卡总次数']
    route_bus_risk_quota = ['日故障总数']

    _start_date =_start_time+timedelta(days=6)
    _start_time_=_start_date.strftime('%Y-%m-%d')
    strwhere=""
    if _start_time_ is not None:
        strwhere = f" and '{_start_time_}' between start_time and end_time "

    route_feature_weight_sql = f""" select quota_name3,
            case when weight_rate1=0 then calculate_weight_rate1 else weight_rate1 end as calculate_weight_rate1,
            case when weight_rate2=0 then calculate_weight_rate2 else weight_rate2 end as calculate_weight_rate2,
            case when weight_rate3=0 then calculate_weight_rate3 else weight_rate3 end as calculate_weight_rate3 
            from ai_security.obs_quota_weight_configuration 
            where profile_type = '线路画像' and 
            start_time in (select max(start_time)
             from ai_security.obs_quota_weight_configuration where profile_type = '线路画像' and deleted != '1' {strwhere})
             """

    # 指标权重从数据库里读取, 不必在评分模型里计算权重
    df = await ClickHouse_sql_query_data.query_to_dataframe(route_feature_weight_sql)

    # 1. 定义需要参与计算的 3 个列名
    cols_to_multiply = ['calculate_weight_rate1', 'calculate_weight_rate2', 'calculate_weight_rate3']
    # 2. 确保这 3 列都是数值类型 (errors='coerce' 会将无法转换的值变为 NaN)
    for col in cols_to_multiply:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        else:
            # 如果列不存在，可以选择报错或跳过，这里选择抛出提示
            raise ValueError(f"列 '{col}' 不存在于 DataFrame 中")

    # 3. 计算乘积并生成新列 'weight_global'
    # axis=1 表示按行计算，skipna=True 表示如果某行有 NaN，结果通常为 NaN (也可根据需求填充)
    df['weight_global'] = (df[cols_to_multiply].prod(axis=1, skipna=False)) / 1000000

    # 取出名称和计算权重2列
    route_feature_weight_df = df[['quota_name3', 'weight_global']]
    route_feature_weight_df = route_feature_weight_df.copy()
    route_feature_weight_df['weight_global'] = pd.to_numeric(route_feature_weight_df['weight_global'],
                                                                 errors='coerce')
    # 只保留 'quota_name3' 第一次出现的行，后续重复的行将被丢弃
    route_feature_weight_df = route_feature_weight_df.drop_duplicates(subset=['quota_name3'], keep='first')

    # 取出线路静态风险指标17个的名称和计算权重
    route_static_feature_weight_df = route_feature_weight_df[
                                     route_feature_weight_df['quota_name3'].isin(route_static_risk_quota)]

    # 线路静态风险指标17个的名称和计算权重字典
    route_static_feature_weight_dict =  dict(zip(route_static_feature_weight_df['quota_name3'], route_static_feature_weight_df['weight_global']))

    # 取出线路车辆故障指标的名称和计算权重
    route_static_feature_weight_df = route_feature_weight_df[
                                     route_feature_weight_df['quota_name3'].isin(route_bus_risk_quota)]
    # 线路车辆故障指标名称和计算权重字典，并且改变车辆故障指标名称
    route_bus_weight_dict =  dict(zip(route_static_feature_weight_df['quota_name3'], route_static_feature_weight_df['weight_global']))
    route_bus_weight_dict['总故障次数_千公里'] = route_bus_weight_dict.pop('日故障总数')

    behavior_weight_df = route_feature_weight_df.copy()
    # 【新增】通过字典映射生成 report_type 列
    # 使用 map 函数将 quota_name3 的中文名称映射为 behavior_type_dict 中的英文键
    behavior_weight_df['report_type'] = behavior_weight_df['quota_name3'].map(behavior_type_dict)
    # 保留匹配成功的不良驾驶行为行，34种
    behavior_weight_df = behavior_weight_df.dropna(subset=['report_type'])
    # 取出10个权重最大的驾驶行为
    top_10_behavior_df = behavior_weight_df.nlargest(10, 'weight_global')
    # 将 report_type 列转换为列表
    top_10_report_type_list = top_10_behavior_df['report_type'].tolist()
    # 【新增】构建带"_千公里"后缀的权重字典, 键：report_type + "_千公里", 值：calculate_weight_rate3 的数值
    route_behavior_feature_weight_dict = {
        f"{row}_千公里": weight
        for row, weight in zip(
            top_10_behavior_df['report_type'],
            top_10_behavior_df['weight_global']
        )
    }

    # 合并字典
    line_quota_weights = {**route_static_feature_weight_dict, **route_bus_weight_dict, **route_behavior_feature_weight_dict}

    # 要输出线路所有三级指标及全局权重字典、 十种行为report 列表
    return line_quota_weights, top_10_report_type_list

if __name__ == '__main__':
    """
    获取线路所有指标及权重字典、 十种行为report 列表
    """
    line_quota_weights, top_10_report_type_list = main()
    print(line_quota_weights)
    # print(top_10_report_type_list)





