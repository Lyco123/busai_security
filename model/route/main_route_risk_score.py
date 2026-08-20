import asyncio
import importlib
import json
import os
import uuid
from datetime import datetime, timedelta

from application.settings import route_api_url
from core.logger import logger
from core.clickhouse_connect import connect_to_clickhouse
from model.bus.crud import insert_moudle_log, update_moudle_log
from model.bus.schemas.bus_profile import ObsModuleLog
from model.route import crud
from model.route.schemas.route_profile import AbsRouteProfileMain, AbsRouteQuotaScoreSub
from services.ai_report_summary import report_main, send_report
from utils.compute import Compute
from utils.tools import get_shanghai_time

# 核心步骤：加载以数字开头的模块（模块名=文件名）
black_spot_processor = importlib.import_module("model.route.1_black_spot_processor")
hidden_danger_point_processor = importlib.import_module("model.route.2_hidden_danger_point_processor")
accident_forecast_handle_processor = importlib.import_module("model.route.3_accident_forecast_handle_processor")
ICcard_type_processor = importlib.import_module("model.route.4_ICcard_type_processor")
fault_analysis_week_processor = importlib.import_module("model.route.5_fault_analysis_week_processor")
triplog_energy_week_processor = importlib.import_module("model.route.6_triplog_energy_week_processor")
driver_behavior_week_processor = importlib.import_module("model.route.7_driver_behavior_week_processor")
bs_route_processor = importlib.import_module("model.route.8_bs_route_processor")
route_bridge_processor = importlib.import_module("model.route.8_1_route_bridge_processor")
route_school_mall_processor = importlib.import_module("model.route.9_route_school_mall_processor")
route_feature_km_calculator = importlib.import_module("model.route.10_route_feature_km_calculator")
route_score_calculator = importlib.import_module("model.route.12_route_score_calculator")

from model.route import a_route_accident_merger
from model.route import b_route_hidden_point_merger
from model.route import c_route_BalckSpot_merger
from model.route import d_route_school_hospital_merger
from model.route import d_1_route_bridge_merger
from model.route import e_route_ICcard_ratio_merger
from model.route import f_route_fault_mileage_merger
from model.route import g_route_driver_behavior_merger


async def route_cores(start_time):
    """
       数据库连接读取数据并处理，形成线路特征数量表
    """

    # start_time = '2026-01-19'
    end_date_ = datetime.strptime(start_time, '%Y-%m-%d')
    start_date_ = end_date_ - timedelta(days=6)
    end_date_str = end_date_.strftime('%Y%m%d')

    _id = str(uuid.uuid4())
    log_data = ObsModuleLog(
        ppartition=datetime.now().strftime('%Y%m%d'),
        id=_id,
        module_type='画像',
        module_name='线路画像',
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
    log_dict = log_data.to_dict()
    await insert_moudle_log(log_dict)

    # 黑点列表处理：提取route_id、映射event_name并生成透视表
    black_spot_pivot_df = await black_spot_processor.main()
    # 统计线路的急转弯风险点数量
    line_danger_count_df = await hidden_danger_point_processor.main()
    # 线路事故数统计
    line_accident_count_df = await  accident_forecast_handle_processor.main()
    # 生成线路POI统计透视表（固定4种类型，列名含"数量"后缀）
    line_school_mall_df = await route_school_mall_processor.main()
    # 生成刷卡类型透视表并计算老人刷卡比率及所有刷卡类型的总次数
    line_ICcard_old_ratio_df = await ICcard_type_processor.main(start_date_,6)
    # 不同线路的车辆故障总数统计
    line_fault_week_df = await fault_analysis_week_processor.main(start_date_,6)
    # 处理线路车辆里程数据，修正异常值并汇总每条线路的里程
    line_mileage_week_df = await triplog_energy_week_processor.main(start_date_,6)
    # 生成线路驾驶员预警行为透视表，统计每个route_id的不同report_type出现次数
    line_driver_behavior_week_df = await driver_behavior_week_processor.main(start_date_,6)
    # 读取线路临水临崖表，统计每个线路名称的临水临崖数量
    line_bridge_df = await route_bridge_processor.main()
    # 读取线路档案，取出指定列为线路基础表
    route_base_df = await bs_route_processor.main()

    """ 
    合并各个线路特征数量表，形成线路指标表
    """
    # 对线路基础表从线路事故统计表中匹配一列"事故数"
    route_accident_df = await a_route_accident_merger.main(route_base_df, line_accident_count_df)
    # 对线路基础表从线路转弯点统计表中匹配一列"急转弯点数量"
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
    # 对线路基础表从线路驾驶行为透视表中匹配10种驾驶行为
    route_driver_behavior_df = await g_route_driver_behavior_merger.main(route_fault_mileage_df, line_driver_behavior_week_df)

    """ 
    计算线路静态指标权重，并且计算线路各个指标风险得分及风险总分
    """
    # 计算线路特征表中'总故障次数'与10种驾驶行为列的千公里指标
    route_feature_km_df = await route_feature_km_calculator.main(start_date_,route_driver_behavior_df)
    # 计算线路的风险得分
    route_score_df = await route_score_calculator.main(start_date_,route_feature_km_df)
    print(route_score_df)  # route_score_df 是线路各个三级指标风险得分及风险总分表，为dataframe

    route_scores = route_score_df.to_dict('records')

    #保存线路指标
    await save(route_scores, start_time)
    remark="线路画像计算完成"
    await update_moudle_log(_id,remark)


def find_code_by_description(description):
    behavior_dict = {
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
    for key, value in behavior_dict.items():
        if value == description:
            return key
    return None

async def save(route_scores,start_time):
    # 使用异步上下文管理器方式
    try:
        async with await connect_to_clickhouse() as client:

            quota1_datas = await crud.Route(client).get_route_quota1(None,start_time)
            quota2_datas = await crud.Route(client).get_route_quota2(None,start_time)
            quota3_datas = await crud.Route(client).get_route_quota3(None,start_time)
            # 解析开始日期
            end_date_= datetime.strptime(start_time, '%Y-%m-%d')
            start_date_  = end_date_ - timedelta(days=6)
            end_date_str = end_date_.strftime('%Y%m%d')
            main_datas = []
            quota_scores = []
            profile_main = None
            for route_score in route_scores:
                main_id = str(uuid.uuid4())
                # if round(route_score['安全评分'])==64:
                #     print (f"安全评分:{route_score['安全评分']}")
                _evalutaion_type=await crud.Route(client).get_risk_value(route_score['安全评分'])
                profile_main = AbsRouteProfileMain(
                        ppartition=end_date_str,
                            id=main_id,
                            route_id=route_score['route_id'],
                            route_name=route_score['route_name'],
                            organ_id=route_score['organ_id'],
                            organ_name=route_score['organ_name'],
                            calculate_date=end_date_,#datetime.combine(get_shanghai_time().date(), datetime.min.time()),
                            evalutaion_type=_evalutaion_type,
                            score=round(route_score['安全评分'],2),
                            suggested_content="",
                            creator="system",
                            create_time=get_shanghai_time(),
                            updater="system",
                            update_time=get_shanghai_time(),
                            deleted="0"
                        )
                for m in quota1_datas:
                    weight_rate1 = float(m['weight_rate1'] / 100)
                    score_name = m['quota_name'] + '_换算值'  # 换算后数值
                    original_name = m['quota_name'] + '_得分'  # 全局风险值
                    risk_name = m['quota_name']
                    if weight_rate1==0:
                        _score=0
                    else:
                        _score=round(route_score[original_name] / weight_rate1, 6)
                    quota_score_1 = AbsRouteQuotaScoreSub(
                            ppartition=end_date_str,  # get_shanghai_time().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id=m['quota_id'],
                            quota_name=m['quota_name'],
                            score=_score,
                            weight_rate=weight_rate1,
                            # original_value=round(route_score[score_name],2)*weight_rate1,
                            original_value = round(route_score[original_name], 6),
                            risk_data="",
                            quota_level="1",
                            parent_id="线路画像",
                            creator="system",
                            create_time=get_shanghai_time(),
                            updater="system",
                            update_time=get_shanghai_time(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=end_date_,
                        )
                    quota_scores.append(quota_score_1.to_dict())
                for m in quota2_datas:
                    weight_rate2 = float(m['weight_rate2'] / 100)
                    weight_rate1 = float(m['weight_rate1'] / 100)
                    score_name = m['quota_name'] + '_换算值'  # 换算后数值
                    original_name = m['quota_name'] + '_得分'  # 全局风险值
                    risk_name = m['quota_name']
                    if weight_rate1*weight_rate2 == 0:
                        _score = 0
                    else:
                        _score = round(route_score[original_name] / (weight_rate1*weight_rate2), 6)
                    quota_score_1 = AbsRouteQuotaScoreSub(
                            ppartition=end_date_str,  # get_shanghai_time().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id=m['quota_id'],
                            quota_name=m['quota_name'],
                            score=_score,
                            weight_rate=weight_rate1*weight_rate2,
                            # original_value=round(route_score[score_name],2)*weight_rate1*weight_rate2,
                            original_value=round(route_score[original_name], 6),
                            risk_data="",
                            quota_level="2",
                            parent_id=m['parent_id'],
                            creator="system",
                            create_time=get_shanghai_time(),
                            updater="system",
                            update_time=get_shanghai_time(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=end_date_,
                        )
                    quota_scores.append(quota_score_1.to_dict())
                for x in quota3_datas:
                    weight_rate3 = float(x['weight_rate3'] / 100)
                    weight_rate2 = float(x['weight_rate2'] / 100)
                    weight_rate1 = float(x['weight_rate1'] / 100)
                    quota_name=find_code_by_description(x['quota_name'])
                    if quota_name is None:
                        quota_name=x['quota_name']
                        risk_name3=quota_name
                        if quota_name=='日故障总数':
                            risk_name3='总故障次数'
                            quota_name='总故障次数_千公里'
                    else:
                        risk_name3=quota_name
                        quota_name=quota_name+"_千公里"
                    score_name3 = quota_name + '_换算值'  # 换算后数值
                    original_name3 = quota_name + '_得分'  # 全局风险值
                    if weight_rate1 * weight_rate2 * weight_rate3 == 0:
                        _score = 0
                    else:
                        _score = round(route_score[original_name3] / (weight_rate1 * weight_rate2 * weight_rate3), 6)
                    if original_name3  in route_score:
                        quota_score_3 = AbsRouteQuotaScoreSub(
                                ppartition=end_date_str,  # get_shanghai_time().strftime("%Y%m%d"),
                                id=str(uuid.uuid4()),
                                main_id=main_id,
                                quota_id=x['quota_id'],
                                quota_name=x['quota_name'],
                                # score=_score,
                                score=round(route_score[score_name3], 6),
                                weight_rate=weight_rate1*weight_rate2*weight_rate3,
                                # original_value=round(route_score[score_name3], 2)*weight_rate1*weight_rate2*weight_rate3,
                                original_value=round(route_score[original_name3], 6),
                                risk_data=str(route_score[risk_name3]),
                                quota_level="3",
                                parent_id=x['parent_id'],
                                creator="system",
                                create_time=get_shanghai_time(),
                                updater="system",
                                update_time=get_shanghai_time(),
                                deleted="0",
                                start_time=start_date_,
                                end_time=end_date_,
                            )
                        quota_scores.append(quota_score_3.to_dict())
                if profile_main is not None:
                        main_datas.append(profile_main.to_dict())
            await crud.Route(client).save(main_datas, quota_scores)

    except Exception as e:
        logger.error("线路画像主程序执行出错", exc_info=True)
        print(f"线路画像主程序执行出错: {e}")
    print("数据库连接已关闭")


# 定义一个信号量，限制最大并发数为 10
SEMAPHORE = asyncio.Semaphore(5)


async def process_single_route(client, data, start_date_str):
    """
    处理单个线路的报告生成与入库逻辑
    """
    route_name = data.get('route_name', 'Unknown')
    route_id = data.get('id')
    payload = {
        "routeName": route_name,
        "ppartition": data.get('ppartition'),
    }

    logger.info(f"获取线路{route_name}：{start_date_str}总结报告 开始")

    try:
        # 调用报告生成接口
        result = await report_main(payload)
        print(f"获取线路{route_id}:{route_name}：{start_date_str}总结报告 结束")
        logger.info(f"获取线路{route_name}：{start_date_str}总结报告 结束")

        if result is not None:
            try:
                # 尝试解析 JSON 结果
                dict_result = json.loads(result)
                # 如果业务逻辑返回 success=False，记录警告并跳过入库
                if isinstance(dict_result, dict) and dict_result.get('success') == False:
                    logger.warning(f"线路{route_name}报告生成业务失败: {result}")
                    return
            except json.JSONDecodeError:
                # 如果解析失败，说明返回的可能不是标准JSON，或者是直接需要入库的数据
                # 或者 result 本身就是需要入库的非JSON格式数据，进入入库流程
                pass
            except Exception as parse_err:
                logger.error(f"线路{route_name}结果解析异常: {parse_err}")

            # 执行入库操作
            try:
                url = f"{route_api_url}/routeprofile/absRouteProfileMain/edit"
                insert_result = await send_report(result, url, route_id)
                logger.info(f"线路{route_name}总结报告入库成功，返回: {insert_result}")
            except Exception as e:
                logger.error(f"线路{route_name}入库报错: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"线路{route_name}处理过程中发生未预期错误: {e}", exc_info=True)


async def process_single_route_limited(client, data, start_date_str):
    """
    带限流控制的单个线路处理包装器
    """
    async with SEMAPHORE:
        return await process_single_route(client, data, start_date_str)


async def generate_reports_limited(start_date,reccount=None):

    try:
        # 注意：connect_to_clickhouse() 的具体实现需确保返回正确的异步上下文管理器
        async with await connect_to_clickhouse() as client:
            # 解析日期
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            _ppartition = start_date_obj.strftime('%Y%m%d')

            if reccount is None:
                reccount = 300

            # 获取线路列表
            route_list = await crud.Route(client).get_route_report(_ppartition, reccount)

            if not route_list:
                logger.info("未获取到任何线路数据，任务结束。")
                return

            tasks = []
            for data in route_list:
                # 创建协程对象，注意这里传入的是 start_date 字符串
                task = process_single_route_limited(client, data, start_date)
                tasks.append(task)

            logger.info(f"开始限流并发处理 {len(tasks)} 个线路报告 (最大并发: 10)...")

            # 并发执行，return_exceptions=True 防止单个任务失败导致整体崩溃
            await asyncio.gather(*tasks, return_exceptions=True)

            logger.info("所有线路报告处理完毕。")

    except Exception as e:
        logger.error(f"生成线路报告执行出错: {e}", exc_info=True)
    finally:
        print("数据库连接已关闭")


async def get_route_report(start_date:str,reccount=None):
    try:
        async with await connect_to_clickhouse() as client:
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
            _ppartition = start_date.strftime('%Y%m%d')
            if reccount is None:
                reccount = 300
            list = await crud.Route(client).get_route_report(_ppartition,reccount)
            for data in list:
                print(f"线路主表ID：{data['id']}")
                payload = {
                    "routeName": data["route_name"],
                    "ppartition": data["ppartition"],
                }
                logger.info(f"获取线路{data['route_name']}：{start_date}总结报告 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                try:
                    result=await report_main(payload)
                    # print(result)
                    logger.info(f"获取线路{data['route_name']}：{start_date}总结报告 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    if result is not None:
                        try:
                            dict=json.loads(result)
                            if  'success' in dict and dict['success']==False:
                                print(result)
                                logger.info(f"获取线路{data['route_name']}：{start_date}总结报告失败:{result}")
                                continue
                        except Exception as ex:
                            url=f"{route_api_url}/routeprofile/absRouteProfileMain/edit"
                            result=await send_report(result,url,data['id'])
                            logger.info(
                                f"线路{data['route_name']}：{start_date}总结报告入库 返回结果 {result}")
                except Exception as e:
                    logger.info(f"总结报告入库报错: {e}")


    except Exception as e:
        logger.info(f"生成线路报告执行出错: {e}")
        print(f"生成线路报告执行出错: {e}")
    print("数据库连接已关闭")

if __name__ == "__main__":
    # asyncio.run(route_cores("2026-05-03"))
    asyncio.run(get_route_report(start_date="2026-06-21"))

