from model.route import ClickHouse_sql_query_data
import pandas as pd


"""
从数据库中ai_security.obs_quota_weight_configuration 取出34种驾驶行为的名称和权重，匹配上report_type列
输出权重前十的report_10type_list(列表）, report_10type_weight_dict(加“_千公里”后，权重字典），
只用于每月的线路指标权重计算
"""

async def main(_start_time:str):
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
                #'report_type32': '路口速度评价'
            }
        behavior_type_dict = {v: k for k, v in type_behavior_dict.items()}
        # 定义驾驶员不良行为权重查询 SQL 语句
        strwhere = ""
        if _start_time is not None:
                strwhere = f" and '{_start_time}' between start_time and end_time "
        my_sql = f"""
        select * from ai_security.obs_quota_weight_configuration 
        where quota_id2='驾驶员画像-事故风险-不良行为'
        and start_time in (
            select max(start_time) from ai_security.obs_quota_weight_configuration 
            where quota_id2='驾驶员画像-事故风险-不良行为' and deleted!='1' {strwhere}
        )
        """

        # 通过sql语句查询'驾驶员画像-事故风险-不良行为'中45中行为的权重
        df = await ClickHouse_sql_query_data.query_to_dataframe(my_sql)
        # 取出名称和计算权重2列
        behavior_weight_df = df[['quota_name3', 'calculate_weight_rate3']]
        # 只保留 'quota_name3' 第一次出现的行，后续重复的行将被丢弃
        behavior_weight_df = behavior_weight_df.drop_duplicates(subset=['quota_name3'], keep='first')

        behavior_weight_df = behavior_weight_df.copy()
        # 【新增】通过字典映射生成 report_type 列
        # 使用 map 函数将 quota_name3 的中文名称映射为 behavior_type_dict 中的英文键
        behavior_weight_df['report_type'] = behavior_weight_df['quota_name3'].map(behavior_type_dict)

        # 保留匹配成功的行
        behavior_weight_df = behavior_weight_df.dropna(subset=['report_type'])
        behavior_weight_df['calculate_weight_rate3'] = pd.to_numeric(behavior_weight_df['calculate_weight_rate3'], errors='coerce')
        top_10_behavior_df = behavior_weight_df.nlargest(10, 'calculate_weight_rate3')

        # 第一步：确保DataFrame是独立副本，避免警告
        top_10_behavior_df = top_10_behavior_df.copy()
        # 第二步：计算calculate_weight_rate3列的总和
        total_weight = top_10_behavior_df['calculate_weight_rate3'].sum()
        # 第三步：计算每个值占总和的比例，生成新列normal_weight
        # 增加防除零判断（避免总和为0时报错）
        if total_weight != 0:
                top_10_behavior_df['normal_weight'] = top_10_behavior_df['calculate_weight_rate3'] / total_weight
        else:
                # 若总和为0，比例设为0（可根据需求调整）
                top_10_behavior_df['normal_weight'] = 0.0
        # （可选）将比例保留4位小数，便于查看
        top_10_behavior_df['normal_weight'] = top_10_behavior_df['normal_weight'].round(5)

        # 【新增】将 report_type 列转换为列表
        top_10_report_type_list = top_10_behavior_df['report_type'].tolist()
        print("\n--- 权重前十的 report_type 列表 ---")
        print(top_10_report_type_list)

        # 【新增】构建带"_千公里"后缀的权重字典
        # 键：report_type + "_千公里"
        # 值：calculate_weight_rate3 的数值
        top_10_report_type_weight_dict = {
            f"{row}_千公里": weight
            for row, weight in zip(
                top_10_behavior_df['report_type'],
                top_10_behavior_df['normal_weight']
            )
        }

        return top_10_report_type_list, top_10_report_type_weight_dict


if __name__ == '__main__':

        """示例数据测试代码功能"""
        # 配置参数模块
        CONFIG = {
                'feature_columns': [
                        '急转弯点数量', '斑马线数量', '左转弯数量', '右转弯数量', '上坡路段数量', '下坡路段数量',
                        '事故黑点', '总修正里程',
                        '区域限速点数量', '行为黑点', '老人刷卡比率', '临水临崖数量', '学校数量', '商场数量',
                        '体育馆数量', '医院数量', '刷卡总次数',
                        '总故障次数_千公里'
                ],  # 特征列名列表
                'weights': {}  # 各特征的权重字典（权重和=1.0）
        }
        # LightGBM回归分析计算静态指标权重
        line_weights = {}

        # 从数据库中取出10种权重最大的驾驶行为的type，传入CONFIG['report_type_columns']
        report_type_columns_list, driver_weights = main()

        # 【新增】为列表中每个元素添加 "_千公里" 后缀
        report_type_top10_list = [f"{col}_千公里" for col in report_type_columns_list]
        CONFIG['feature_columns'] = CONFIG.get('feature_columns', []) + report_type_top10_list
        # driver_weights = {
        #     'report_type16_千公里': 0.0860, 'report_type18_千公里': 0.0769, 'report_type21_千公里': 0.0633, 'report_type22_千公里': 0.1222, 'report_type23_千公里': 0.2127,
        #     'report_type24_千公里': 0.0589, 'report_type28_千公里': 0.0769, 'report_type34_千公里': 0.0633, 'report_type8_千公里': 0.0905, 'report_type9_千公里': 0.1493
        # }

        bus_weights = {'总故障次数_千公里': 1}

        # 定义系数
        static_coefficient = 0.7
        dynamic_coefficient = 0.3
        bus_coefficient = dynamic_coefficient / 10

        # 乘以系数
        scaled_line_weights = {key: value * static_coefficient for key, value in line_weights.items()}
        scaled_driver_weights = {key: value * dynamic_coefficient for key, value in driver_weights.items()}
        scaled_bus_weights = {key: value * bus_coefficient for key, value in bus_weights.items()}

        # 合并字典
        CONFIG['weights'] = {**scaled_line_weights, **scaled_bus_weights, **scaled_driver_weights}
        print(CONFIG)




