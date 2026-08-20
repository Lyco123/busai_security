import asyncio
import importlib
import os
import uuid
from datetime import datetime, timedelta
from application.settings import route_profile_static_risk_weight, route_profile_dynamic_risk_weight
from core.logger import logger
from core.clickhouse_connect import connect_to_clickhouse
from model.bus.crud import insert_moudle_log, update_moudle_log
from model.bus.schemas.bus_profile import ObsModuleLog
from model.route import crud
from model.route.main_route_risk_score import find_code_by_description
from utils.compute import Compute
from utils.tools import get_next_month_day, get_shanghai_time, get_last_month_day

# 核心步骤：加载以数字开头的模块（模块名=文件名）
black_spot_processor = importlib.import_module("model.route.1_black_spot_processor")
hidden_danger_point_processor = importlib.import_module("model.route.2_hidden_danger_point_processor")
accident_forecast_handle_processor = importlib.import_module("model.route.3_accident_forecast_handle_processor")
ICcard_type_processor = importlib.import_module("model.route.4_ICcard_type_processor")
fault_analysis_week_processor = importlib.import_module("model.route.5_fault_analysis_week_processor")
triplog_energy_week_processor = importlib.import_module("model.route.6_triplog_energy_week_processor")
driver_behavior_top10_weight_calculator = importlib.import_module("model.route.7_1_read_driver_behavior_top10_weight")
bs_route_processor = importlib.import_module("model.route.8_bs_route_processor")
route_bridge_processor = importlib.import_module("model.route.8_1_route_bridge_processor")
route_school_mall_processor = importlib.import_module("model.route.9_route_school_mall_processor")
lightGBM_weight_calculator = importlib.import_module("model.route.11_lightGBM_weight_calculator")
from model.route import a_route_accident_merger
from model.route import b_route_hidden_point_merger
from model.route import c_route_BalckSpot_merger
from model.route import d_route_school_hospital_merger
from model.route import d_1_route_bridge_merger
from model.route import e_route_ICcard_ratio_merger
from model.route import f_route_fault_mileage_merger


async def route_quota_weight_main(start_time:str):
    """
       数据库连接读取数据并处理，形成线路特征数量表
    """
    # start_time =  get_shanghai_time().strftime('%Y-%m-%d')
    _id=str(uuid.uuid4())
    log_data=ObsModuleLog(
        ppartition=datetime.now().strftime('%Y%m%d'),
        id=_id,
        module_type='权重',
        module_name='线路权重',
        pid=str(os.getpid()),
        remark='',
        calculate_date=start_time,
        end_time=datetime.now(),
        start_time=datetime.now(),
        creator='system',
        create_time=datetime.now(),
        updater='system',
        update_time=datetime.now(),
        deleted="0"
    )
    log_dict=log_data.to_dict()
    await insert_moudle_log(log_dict,"obs_module_weight_log")

    start_time=start_time
    start_date_ = datetime.strptime(start_time, '%Y-%m-%d')
    end_date_ = get_next_month_day(start_date_)- timedelta(days=1)
    end_date_str = end_date_.strftime('%Y%m%d')
    start_time_data= start_date_ - timedelta(days=7)
    # 黑点列表处理：提取route_id、映射event_name并生成透视表
    black_spot_pivot_df = await black_spot_processor.main()
    # 统计线路的急转弯风险点数量
    line_danger_count_df = await hidden_danger_point_processor.main()
    # 线路事故数统计
    line_accident_count_df = await accident_forecast_handle_processor.main()
    # 生成线路POI统计透视表（固定4种类型，列名含"数量"后缀）
    line_school_mall_df = await route_school_mall_processor.main()
    # 生成刷卡类型透视表并计算老人刷卡比率及所有刷卡类型的总次数
    line_ICcard_old_ratio_df = await ICcard_type_processor.main(start_time_data,6)
    # 不同线路的车辆故障总数统计

    line_fault_week_df =  await fault_analysis_week_processor.main(start_time_data,6)
    # 处理线路车辆里程数据，修正异常值并汇总每条线路的里程
    line_mileage_week_df =  await triplog_energy_week_processor.main(start_time_data,6)
    # 读取线路临水临崖表，统计每个线路名称的临水临崖数量
    line_bridge_df = await route_bridge_processor.main()
    # 读取线路档案，取出指定列为线路基础表
    route_base_df = await bs_route_processor.main()

    """ 
    合并各个线路特征数量表，形成线路指标表
    """
    # 对线路基础表从线路事故统计表中匹配一列"事故数"
    route_accident_df = await a_route_accident_merger.main(route_base_df, line_accident_count_df)
    # 对线路基础表从线路转弯点统计表中匹配一列"急转弯点数"
    route_hidden_point_df = await b_route_hidden_point_merger.main(route_accident_df, line_danger_count_df)
    # 对线路基础表从黑点列表中匹配'上坡路段数量', '下坡路段数量', '区域限速点数量', '右转弯数量', '左转弯数量', '斑马线数量', '事故黑点', '自定义黑点', '行为黑点'
    route_black_spot_df = await c_route_BalckSpot_merger.main(route_hidden_point_df, black_spot_pivot_df)
    # 对线路基础表从线路poi统计表中匹配POI（学校数量, 商场数量, 体育馆数量, 医院数量）
    route_school_hospital_df = await d_route_school_hospital_merger.main(route_black_spot_df, line_school_mall_df)
    # 对线路基础表从线路刷卡透视表中匹配老人刷卡比率列和刷卡总次数列
    route_ICcard_ratio_df = await e_route_ICcard_ratio_merger.main(route_school_hospital_df, line_ICcard_old_ratio_df)
    # 对线路基础表从线路临水临崖统计表中匹配'临水临崖数量'
    route_bridge_df = await d_1_route_bridge_merger.main(route_ICcard_ratio_df, line_bridge_df)
    # 对线路基础表从线路故障统计表和线路里程表匹配'总故障次数','总修正里程'
    route_fault_mileage_df = await f_route_fault_mileage_merger.main(route_bridge_df, line_fault_week_df,
                                                               line_mileage_week_df)
    """ 
    计算线路静态指标权重，并且计算线路各个指标风险得分及风险总分
    """
    # LightGBM回归分析计算静态指标权重, 17个指标权重之和为1
    line_weights, results  = await lightGBM_weight_calculator.main(route_fault_mileage_df)

    # 从数据库中取出10种权重最大的驾驶行为的type，传入CONFIG
    report_type_columns_list, driver_weights = await driver_behavior_top10_weight_calculator.main(start_time)
    # 示例 driver_weights = {  10个指标权重之和为1
    #     'report_type16_千公里': 0.0860, 'report_type18_千公里': 0.0769, 'report_type21_千公里': 0.0633, 'report_type22_千公里': 0.1222, 'report_type23_千公里': 0.2127,
    #     'report_type24_千公里': 0.0589, 'report_type28_千公里': 0.0769, 'report_type34_千公里': 0.0633, 'report_type8_千公里': 0.0905, 'report_type9_千公里': 0.1493
    # }
    bus_weights = {'总故障次数_千公里': 1}

    # 合并线路、行为、车辆故障权重字典
    route_feature_weight_dict = {**line_weights, **bus_weights, **driver_weights}

    score1_keys = ['急转弯点数量', '斑马线数量', '左转弯数量', '右转弯数量', '上坡路段数量',
         '下坡路段数量', '区域限速点数量', '临水临崖数量']
    # 计算总和
    line_1_weight_sum = sum(
        route_feature_weight_dict.get(key, 0)
        for key in score1_keys
    )

    score2_keys = ['学校数量', '商场数量', '体育馆数量', '医院数量', '老人刷卡比率',
                '刷卡总次数', '总修正里程']
    # 计算总和
    line_2_weight_sum = sum(
        route_feature_weight_dict.get(key, 0)
        for key in score2_keys
    )

    score3_keys = ['行为黑点', '事故黑点']
    # 计算总和
    line_3_weight_sum = sum(
        route_feature_weight_dict.get(key, 0)
        for key in score3_keys
    )

    # 计算静态风险的三级级指标局部权重
    # 枚举 score1_keys 中的元素，索引为 i，键名为 key
    for i, key in enumerate(score1_keys):
        # 获取当前键对应的原值，如果键不存在则默认为 0
        original_value = route_feature_weight_dict.get(key, 0)
        # 修改值为原值的 1/10
        route_feature_weight_dict[key] = original_value / line_1_weight_sum

    for i, key in enumerate(score2_keys):
        # 获取当前键对应的原值，如果键不存在则默认为 0
        original_value = route_feature_weight_dict.get(key, 0)
        # 修改值为原值的 1/10
        route_feature_weight_dict[key] = original_value / line_2_weight_sum

    # 2. 根据总和是否为 0 进行差异化处理
    if line_3_weight_sum == 0:
        # 若总和为 0，将所有相关项设为 0，避免后续除以 0
        for key in score3_keys:
            route_feature_weight_dict[key] = 0.0
    else:
        # 若总和不为 0，执行归一化 (原值 / 总和) 或其他除法逻辑
        for key in score3_keys:
            original_val = route_feature_weight_dict.get(key, 0)
            route_feature_weight_dict[key] = original_val / line_3_weight_sum

    route_feature_weight_dict['线形路况'] = line_1_weight_sum / (line_1_weight_sum + line_2_weight_sum + line_3_weight_sum)   # 计算二级指标线形路况局部权重
    route_feature_weight_dict['人口密集区域'] = line_2_weight_sum / (line_1_weight_sum + line_2_weight_sum + line_3_weight_sum) # 计算二级指标人口密集区域局部权重
    route_feature_weight_dict['线路黑点'] = line_3_weight_sum / (line_1_weight_sum + line_2_weight_sum + line_3_weight_sum)     # 计算二级指标线路黑点局部权重
    # 计算一级指标静态风险权重
    route_feature_weight_dict['静态风险'] = route_profile_static_risk_weight # 默认参数

    # 计算二级指标驾驶不良行为、车辆故障总数权重
    route_feature_weight_dict['驾驶不良行为'] = 0.9 # 默认参数
    route_feature_weight_dict['车辆故障总数'] = 0.1 # 默认参数
    route_feature_weight_dict['动态风险'] = route_profile_dynamic_risk_weight # 默认参数

    # 输出模型拟合效果指标
    print("\n测试集的预测值平均绝对误差", results['test_mae'])
    print("测试集的模型拟合系数", results['test_r2'])
    remark=f"""测试集的预测值平均绝对误差:{results['test_mae']},测试集的模型拟合系数:{results['test_r2']}"""
    #保存指标权重
    await save_weights(route_feature_weight_dict,start_time)

    await update_moudle_log(_id,remark,"obs_module_weight_log")
    return route_feature_weight_dict

async def save_weights(route_quota_weight_dicts,start_time):
    # 使用异步上下文管理器方式
    try:
        async with await connect_to_clickhouse() as client:
            # 解析开始日期
            start_date_ = datetime.strptime(start_time, '%Y-%m-%d')
            quota_name3_datas = await crud.Route(client).get_quota_name3_datas(None,get_last_month_day(start_date_).strftime('%Y-%m-%d'))
            end_date_ = get_next_month_day(start_date_)-timedelta(days=1)
            end_date_str = end_date_.strftime('%Y%m%d')
            unit="次数"
            for x in quota_name3_datas:
                quota_name = find_code_by_description(x['quota_name3'])
                if quota_name is None:
                    quota_name = x['quota_name3']
                    if quota_name == '日故障总数':
                        quota_name = '总故障次数_千公里'
                        unit="次数/千公里"
                else:
                    quota_name = quota_name + "_千公里"
                    unit="次数/千公里"
                quota_name1=x['quota_name1']
                quota_name2=x['quota_name2']
                if quota_name in route_quota_weight_dicts:
                    x['id'] = str(uuid.uuid4())
                    converted_weight = Compute.safe_float_conversion(route_quota_weight_dicts[quota_name])
                    if converted_weight is not None:
                        calculate_weight = Compute.scientific_to_percentage(converted_weight)
                    else:
                        calculate_weight = 0.00
                    x['calculate_weight_rate1'] = Compute.scientific_to_percentage(route_quota_weight_dicts[quota_name1])
                    x['calculate_weight_rate2'] = Compute.scientific_to_percentage(route_quota_weight_dicts[quota_name2])
                    x['calculate_weight_rate3'] = calculate_weight
                    # x['quoa_unit3'] = unit
                    x['start_time'] = start_date_
                    x['end_time'] = end_date_
                    x['creator'] = "system"
                    x['create_time'] = get_shanghai_time()
                    x['updater'] = "system"
                    x['update_time'] = get_shanghai_time()
                else:
                    x['id'] = str(uuid.uuid4())
                    calculate_weight = 0.00
                    x['calculate_weight_rate1'] = Compute.scientific_to_percentage(route_quota_weight_dicts[quota_name1])
                    x['calculate_weight_rate2'] = Compute.scientific_to_percentage(route_quota_weight_dicts[quota_name2])
                    x['calculate_weight_rate3'] = calculate_weight
                    x['start_time'] = start_date_
                    x['end_time'] = end_date_
                    x['creator'] = "system"
                    x['create_time'] = get_shanghai_time()
                    x['updater'] = "system"
                    x['update_time'] = get_shanghai_time()
                # 保存权重
            await crud.Route(client).save_weights(quota_name3_datas)

    except Exception as e:
        logger.error("线路画像-保存线路权重执行出错", exc_info=True)
        print(f"线路画像-保存线路权重执行出错: {e}")
    print("数据库连接已关闭")

if __name__ == "__main__":
    dict123 = asyncio.run(route_quota_weight_main('2026-03-01'))
    print("\n--- 一二三级指标权重字典 ---")
    print(dict123)

