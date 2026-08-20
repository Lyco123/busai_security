import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, time

import pandas as pd
from clickhouse_driver import Client
from fastapi import Depends
from gridfs.grid_file_shared import EMPTY
from rich.status import Status

from core import sql_config
from core.exception import CustomException
from core.logger import logger

from core.clickhouse_connect import connect_to_clickhouse
from core.clickhouse_manage import ClickHouseManage
from model.bus.crud import insert_moudle_log, update_moudle_log
from model.bus.schemas.bus_profile import ObsModuleLog

from model.driver import crud
from model.driver.calculate_driver_energy_scores import calculate_driver_energy_scores
from model.driver.calculate_energy_behavior_weights import calculate_energy_behavior_weights
from model.driver.crud import delete_driver_datas, delete_driver_main_datas, delete_driver_weights_datas, read_raw_sql, \
    delete_warning_driver_1d
from model.driver.driver_accident_calculate_scores import driver_accident_weights, driver_accident_cores, \
    driver_accident_hour_cores
from model.driver.driver_accident_train_weights import accident_weights_main, accident_weights_1hour_main
from model.driver.driver_attitude_score import driver_attitude_scores_main, driver_attitude_weight_main
from model.driver.driver_calculate_safety_scores import driver_safety_cores_main, driver_safety_weight_main
from model.driver.schemas import driver_profile
from model.driver.schemas.driver_profile import AbsDriverProfileMain, AbsDriverQuotaScoreSub
# from model.driver.driver_attitude_score import score_drivers
import uuid

from model.driver.src import driver_sql
from model.driver.src.driver_accident__predict_1d import prediction
from model.driver.src.driver_accident__predict_1d_new import prediction_week
from model.driver.src.driver_accident__predict_1h import prediction_1h
from model.driver.src.driver_accident_train_weights_1d import accident_train_1d_main
from model.driver.src.driver_accident_train_weights_1d_new import main_week
from model.driver.src.driver_accident_train_weights_1h import accident_train_1h_main
from model.schemas.weight_configuration import ObsQuotaWeightConfiguration
from services.ai_report_summary import report_main, send_report
from utils.compute import Compute
from utils.tools import get_last_month_day, get_next_month_day, get_shanghai_time, NumpyEncoder


#驾驶行为数据汇总，可每天执行一次
async def driver_behavior_data_init(start_date,end_date):
    try:
        async with await connect_to_clickhouse() as client:
            # 这里可以执行数据库操作
            logger.info(f"驾驶员{start_date}行为数据汇总准备 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("数据库连接成功")

            #初始化数据
            #一周行为数存入临时表
            try:
                #保留三个月的数据
                _start_time=datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y%m%d")
                _d_start_time=datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=150)
                _d_start_time=_d_start_time.strftime("%Y%m%d")
                strwhere=f" ppartition < '{_d_start_time}' "
                result = await crud.Driver(client).delete_data_by_where("ods_communication_driver_behavior_month",strwhere)
                result = await crud.Driver(client).delete_data_by_where("abs_driver_behavior_sum",strwhere)
                result =await crud.Driver(client).get_data_sql_dict(f"select count(*) as reccount from ods_communication_driver_behavior_month where ppartition='{_start_time}'")
                if (result[0]['reccount'] <=0 ):
                    result=await crud.Driver(client).insert_driver_behavior_month(start_date,end_date)
                result = await crud.Driver(client).get_data_sql_dict(
                        f"select count(*) as reccount from abs_driver_behavior_sum where ppartition='{_start_time}'")
                if (result[0]['reccount'] <= 0):
                    driver_behavior_week_datas=await crud.Driver(client).get_driver_behavior_week_datas(start_date,end_date)
            except Exception as e:
                print(f"一周行为数存入临时表执行出错: {e}")
            logger.info(f"驾驶员{start_date}行为数据汇总准备 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.exception(f"驾驶员能耗风险数据准备程序报错{e}")
        print(f"驾驶员能耗风险数据准备程序报错: {e}")

#驾驶行为数据汇总，可每天执行一次
async def driver_behavior_data_month_init(start_date,end_date):
    try:
        async with await connect_to_clickhouse() as client:
            # 这里可以执行数据库操作
            logger.info(f"驾驶员{start_date}行为月数据准备 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("数据库连接成功")

            #初始化数据
            #一周行为数存入临时表
            try:
                driver_behavior_week_datas=await crud.Driver(client).get_driver_behavior_data_month_init(start_date,end_date)
            except Exception as e:
                print(f"一周行为数存入临时表执行出错: {e}")
            logger.info(f"驾驶员{start_date}行为月数据准备 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.exception(f"驾驶员能耗风险数据准备程序报错{e}")
        print(f"驾驶员能耗风险数据准备程序报错: {e}")

#计算驾驶员权重生成中间表
async def driver_weight_data_init(start_time:str):
    try:
        async with await connect_to_clickhouse() as client:
            # 这里可以执行数据库操作
            end_date = datetime.strptime(start_time, "%Y-%m-%d")
            start_date = get_last_month_day(end_date)
            end_date=end_date-timedelta(days=1)
            start_time_str = start_date.strftime("%Y%m%d")
            end_time_str = end_date.strftime("%Y%m%d")

            logger.info(f"驾驶员{start_date}--{end_date}风险权重数据准备 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("数据库连接成功")

            #初始化数据
            #一周行为数存入临时表
            try:

              await crud.Driver(client).gen_abs_rand_window(start_time_str,end_time_str)
              await crud.Driver(client).gen_abs_all_30m_bhv_with_traffic(start_time_str,end_time_str)
              await crud.Driver(client).gen_abs_health_wide(start_time_str,end_time_str)
              await crud.Driver(client).gen_abs_workhour_wide(start_time_str,end_time_str)

              await crud.Driver(client).gen_abs_all_1HOUR_bhv_with_traffic(start_time_str, end_time_str)

            except Exception as e:
                print(f"驾驶员计算权重全年数据存入临时表执行出错: {e}")
            logger.info(f"驾驶员{start_date}--{end_date}风险权重数据准备 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.exception(f"驾驶员计算权重全年数据存入临时表执行出错{e}")
        print(f"驾驶员计算权重全年数据存入临时表执行出错: {e}")


#计算能耗风险权重
async def driver_energy_weights(_start_time:str):
    """使用示例"""
    # 使用异步上下文管理器方式
    try:
        async with await connect_to_clickhouse() as client:
            # 这里可以执行数据库操作
            logger.info("驾驶员能耗风险权重 开始时间：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            logger.info("数据库连接成功")

            # 解析开始日期
            start_date = datetime.strptime(_start_time, '%Y-%m-%d')
            # 权重有效结束日期
            end_date = get_next_month_day(start_date)  # + timedelta(days=30)
            # 格式化为YYYYMMDD格式
            start_date_str = start_date.strftime('%Y%m%d')
            end_date_str = end_date.strftime('%Y%m%d')

            #进行驾驶员能耗驾驶行为权重计算数据位上个月一个月数据
            start_data_time=get_last_month_day(start_date)
            start_date_data_str = start_data_time.strftime('%Y%m%d')
            end_date_data_str = (start_date-timedelta(days=1)).strftime('%Y%m%d')
            df_energy_weights = await crud.Driver(client).get_energy_datas_streaming(start_date_data_str,end_date_data_str)
            if df_energy_weights.empty:
                raise ValueError(f"{start_date_data_str}-{end_date_data_str}能耗风险权重宽表为空，无法输出权重结果")
            # df_energy_weights = await crud.Driver(client).get_datas_streaming("v_ods_communication_driver_bus_behavior_energy_report_ads_driver_workhouse_week")
            # 进行驾驶员能耗驾驶行为权重计算（时间跨度为一个月，每条数据为每人每天每辆车的驾驶行为次数、总能耗、总里程、客流量）
            # 权重字典驾驶行为使用中文格式，而非type_1格式
            # df_energy_weights = pd.DataFrame(datas)

            energy_weights,remark = await calculate_energy_behavior_weights(df_energy_weights)
            end_date=end_date-timedelta(days=1)
            # 保存权重到权重表
            energy_weights_datas = []
            quota_name3_datas = await crud.Driver(client).get_energy_quota_name3_datas("",get_last_month_day(start_date).strftime('%Y-%m-%d'))
            for d_quota_name3 in quota_name3_datas:
                d_quota_name3['id'] = str(uuid.uuid4())
                converted_weight = Compute.safe_float_conversion(energy_weights.get(d_quota_name3.get('quota_name3')))
                if converted_weight is not None:
                    calculate_weight = Compute.scientific_to_percentage(converted_weight)
                else:
                    calculate_weight = 0.00
                d_quota_name3['calculate_weight_rate1'] = 30
                d_quota_name3['calculate_weight_rate2'] = 100
                d_quota_name3['calculate_weight_rate3'] = calculate_weight
                # d_quota_name3['quoa_unit3'] = "次数"
                # d_quota_name3['start_time'] = datetime.combine(datetime.now().date(), datetime.min.time())
                # d_quota_name3['end_time'] = datetime.combine(datetime.now().date() + timedelta(weeks=1),
                #                                              datetime.min.time())
                d_quota_name3['start_time']=start_date
                d_quota_name3['end_time']=end_date
                d_quota_name3['creator'] = "system"
                d_quota_name3['create_time'] = get_shanghai_time()
                d_quota_name3['updater'] = "system"
                d_quota_name3['update_time'] = get_shanghai_time()

            # 保存权重
            await crud.Driver(client).save_weights(quota_name3_datas)
            return remark
    except Exception as e:
        logger.exception(f"驾驶员驾驶员能耗风险权重执行出错:{e}")
        print(f"驾驶员驾驶员能耗风险权重执行出错: {e}")
    finally:
        import gc
        gc.collect()



#计算驾驶员能耗风险分数
async def driver_energy_cores(_start_time:str):
    """使用示例"""
    # 使用异步上下文管理器方式
    try:
        async with await connect_to_clickhouse() as client:
            # 这里可以执行数据库操作
            logger.info("驾驶员能耗风险计算分数 开始时间：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            logger.info("数据库连接成功")


            #取出最新能耗权
            quota_name3_datas = await crud.Driver(client).get_energy_quota_name3_datas_calu("驾驶员画像-能耗风险",_start_time)
            if quota_name3_datas is None:
                raise CustomException("能耗权重查找失败，未查找到对应数据", code=Status.HTTP_404_NOT_FOUND)

            weights_datas = {}
            global_weight = 0.3
            for weight in quota_name3_datas:
                if weight['quota_level']=='1':
                    global_weight=Compute.percentage_to_number(weight['weight_rate'])
                weights_datas[weight['quota_name']]=Compute.percentage_to_number(weight['weight_rate'])

            # start_times = pd.date_range(start="2026-01-01", end="2026-01-31")
            start_times = [_start_time]
            for start_time in start_times:
                # start_time = start_time.to_pydatetime()
                start_date = datetime.strptime(start_time, '%Y-%m-%d')
                # 计算结束日期
                end_date=start_date
                # end_date = start_date + timedelta(days=6)
                # 格式化为YYYYMMDD格式
                start_date_str = start_date.strftime('%Y%m%d')
                end_date_str = end_date.strftime('%Y%m%d')
                # datas = await crud.Driver(client).get_energy_sum_datas(start_date_str,end_date_str)
                # #进行驾驶员评分（时间跨度为周一到周日，每条数据为每个驾驶员每条线路上一周的驾驶行为次数、总里程）
                # df_energy_grades = pd.DataFrame(datas)
                sql = driver_sql.predict_1d_sql(start_date_str, start_date_str)
                df_energy_grades = await read_raw_sql(sql)

                # df_energy_grades=await crud.Driver(client).get_drivers_day_datas(start_date_str)
                #results格式：'employee_id', 'employee_name', 'route_id', 'route_name','organ_name', 'total_mileage', 'weighted_total_score', 'rank',34种驾驶行为分数
                # results = await calculate_driver_energy_scores(df_energy_grades, energy_weights)
                #计算分数
                if df_energy_grades.empty:
                    raise ValueError(f"{start_date_str}评分宽表为空，无法输出评分结果")
                results = await calculate_driver_energy_scores(df_energy_grades, weights_datas,global_weight)
                energy_datas=results.to_dict('records')

                # ppartition = datetime.now().strftime('%Y%m%d')
                ppartition=end_date_str
                driver_profile_main_datas = await crud.Driver(client).get_abs_driver_profile_main(ppartition)
                driver_ids = []
                if driver_profile_main_datas:
                    for d in driver_profile_main_datas:
                        driver_ids.append(d['driver_id'])

                main_datas=[]
                quota_scores = []
                for data in energy_datas:
                    # print(data['employee_id'])
                    if data['employee_id'] in driver_ids:
                        x = driver_ids.index(data['employee_id'])
                        main_id = driver_profile_main_datas[x]['id']
                        profile_main = None
                    else:
                        main_id= str(uuid.uuid4())
                        profile_main=AbsDriverProfileMain(
                            ppartition=ppartition,#datetime.now().strftime("%Y%m%d"),
                            id = main_id,
                            driver_id = data['employee_id'],
                            driver_name = data['employee_name'],
                            organ_id = data['organ_id'],
                            organ_name = data['organ_name'],
                            calculate_date = end_date,
                            evalutaion_type = "",
                            score = 0,
                            suggested_content = "",
                            creator = "system",
                            create_time = datetime.now(),
                            updater = "system",
                            update_time = datetime.now(),
                            deleted = "0",
                            route_acc_rank = 0,
                            route_rank = 0,
                            route_total = 0,
                            route_rate = 0.00
                        )
                    quota_score = AbsDriverQuotaScoreSub(
                        ppartition=ppartition,#datetime.now().strftime("%Y%m%d"),
                        id=str(uuid.uuid4()),
                        main_id=main_id,
                        quota_id="驾驶员画像-能耗风险",
                        quota_name="能耗风险",
                        score=data['weighted_total_score'],
                        weight_rate=data['global_weight'],
                        original_value=data['global_total_score'],
                        risk_data="",
                        quota_level="1",
                        parent_id="驾驶员画像",
                        creator="system",
                        create_time=datetime.now(),
                        updater="system",
                        update_time=datetime.now(),
                        deleted="0",
                        start_time=start_date,
                        end_time=end_date,
                    )
                    quota_scores.append(quota_score.to_dict())
                    quota_score = AbsDriverQuotaScoreSub(
                        ppartition=ppartition,#datetime.now().strftime("%Y%m%d"),
                        id=str(uuid.uuid4()),
                        main_id=main_id,
                        quota_id="驾驶员画像-能耗风险-不良行为",
                        quota_name="不良行为",
                        score=data['weighted_total_score'],
                        weight_rate=data['global_weight'],
                        original_value=data['global_total_score'],  #全局能耗分数
                        risk_data="",
                        quota_level="2",
                        parent_id="驾驶员画像-能耗风险",
                        creator="system",
                        create_time=datetime.now(),
                        updater="system",
                        update_time=datetime.now(),
                        deleted="0",
                        start_time=start_date,
                        end_time=end_date,
                    )
                    quota_scores.append(quota_score.to_dict())
                    for quota3_data in quota_name3_datas:
                        if quota3_data['quota_level']=='3':
                            score_name3=quota3_data['quota_name']+'_score'   #换算后数值
                            weight_rate3=quota3_data['quota_name']+'_global_weight'  #全局权重
                            original_name3=quota3_data['quota_name']+'_global_score'  #全局风险值
                            risk_name3 = quota3_data['quota_name'] + '_rate'  # 风险数据值-原始值
                            if score_name3 in data:
                                quota_score = AbsDriverQuotaScoreSub(
                                    ppartition=ppartition,#datetime.now().strftime("%Y%m%d"),
                                    id=str(uuid.uuid4()),
                                    main_id=main_id,
                                    quota_id=quota3_data['quota_id'],
                                    quota_name=quota3_data['quota_name'],
                                    score=data[score_name3],
                                    weight_rate=data[weight_rate3],
                                    original_value=data[original_name3],
                                    risk_data=str(data[risk_name3]),
                                    quota_level=quota3_data['quota_level'],
                                    parent_id=quota3_data['parent_id'],
                                    creator="system",
                                    create_time=datetime.now(),
                                    updater="system",
                                    update_time=datetime.now(),
                                    deleted="0",
                                    start_time=start_date,
                                    end_time=end_date,
                                )
                                quota_scores.append(quota_score.to_dict())
                    if profile_main is not None:
                        main_datas.append(profile_main.to_dict())

                #保存能耗风险数据
                await crud.Driver(client).save(main_datas,quota_scores)
                return df_energy_grades
                logger.info("驾驶员能耗风险计算分数 结束时间：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            #保存司机画像数据
            # insert_datas=[]
            # await save(client,insert_datas)
    except Exception as e:
        logger.exception(f"驾驶员能耗风险计算分数执行出错{e}")
        print(f"驾驶员能耗风险计算分数执行出错: {e}")
    finally:
        import gc
        gc.collect()
    print("数据库连接已关闭")

async def driver_weights_main(start_date_time:str):
    start_time=datetime.now()
    _start_time=datetime.strftime(start_time,"%Y-%m-%d")
    _start_time=start_date_time

    _id=str(uuid.uuid4())
    log_data=ObsModuleLog(
        ppartition=datetime.now().strftime('%Y%m%d'),
        id=_id,
        module_type='权重',
        module_name='驾驶员-能耗风险',
        pid=str(os.getpid()),
        remark='',
        calculate_date=start_date_time,
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
    # 计算驾驶员能耗风险权重
    logger.info(f"删除{_start_time}驾驶员权重数据 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await delete_driver_weights_datas(_start_time)
    logger.info(f"删除{_start_time}驾驶员权重数据 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    remark_energy=''
    try:
        logger.info(f"准备{_start_time}驾驶员能耗风险权重 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        remark_energy=await driver_energy_weights(_start_time)
        logger.info(f"{_start_time}驾驶员能耗风险权重计算完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.exception(f"{_start_time}驾驶员能耗风险权重执行出错：{e}")
        print(f"{_start_time}驾驶员能耗风险权重执行出错: {e}")
    finally:
        import gc
        gc.collect()

    remark=remark_energy
    await update_moudle_log(_id,remark,"obs_module_weight_log")

    # 计算驾驶员事故风险权重
    _id = str(uuid.uuid4())
    log_data = ObsModuleLog(
        ppartition=datetime.now().strftime('%Y%m%d'),
        id=_id,
        module_type='权重',
        module_name='驾驶员-事故风险',
        pid=str(os.getpid()),
        remark='',
        calculate_date=start_date_time,
        end_time=datetime.now(),
        start_time=datetime.now(),
        creator='system',
        create_time=datetime.now(),
        updater='system',
        update_time=datetime.now(),
        deleted="0"
    )
    log_dict = log_data.to_dict()
    await insert_moudle_log(log_dict, "obs_module_weight_log")
    remark_accident={}
    try:
        logger.info(f"准备{_start_time}驾驶员风险权重 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        remark_accident=await accident_train_1d_main(_start_time)
        await prediction(_start_time,_start_time,"1")
        logger.info(f"{_start_time}驾驶员权重计算完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.exception(f"{_start_time}驾驶员事故风险权重执行出错：{e}")
        print(f"{_start_time}驾驶员事故风险权重执行出错: {e}")
    finally:
        import gc
        gc.collect()

    remark=json.dumps(remark_accident,cls=NumpyEncoder, ensure_ascii=False)
    await update_moudle_log(_id,remark,"obs_module_weight_log")

    try:
        logger.info(f"准备{_start_time}驾驶员安全评价、服务态度权重 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        await driver_safety_weight_main(_start_time)
        await driver_attitude_weight_main(_start_time)
        logger.info(f"{_start_time}驾驶员安全评价、服务态度权重计算完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.exception(f"{_start_time}驾驶员安全评价、服务态度权重执行出错：{e}")
        print(f"{_start_time}驾驶员安全评价、服务态度权重执行出错: {e}")
    finally:
        import gc
        gc.collect()

        # 计算驾驶员事故风险权重
    _id = str(uuid.uuid4())
    log_data = ObsModuleLog(
        ppartition=datetime.now().strftime('%Y%m%d'),
        id=_id,
        module_type='权重',
        module_name='驾驶员-事故小时风险',
        pid=str(os.getpid()),
        remark='',
        calculate_date=start_date_time,
        end_time=datetime.now(),
        start_time=datetime.now(),
        creator='system',
        create_time=datetime.now(),
        updater='system',
        update_time=datetime.now(),
        deleted="0"
    )
    log_dict = log_data.to_dict()
    await insert_moudle_log(log_dict, "obs_module_weight_log")
    remark_accident = {}

    try:
        logger.info(f"准备{_start_time}驾驶员事故小时风险权重 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        # await driver_weights_1hour_main(_start_time)
        remark_accident=await accident_train_1h_main(_start_time)
        current_time = datetime.now()
        _start_time_str = _start_time+ " " + current_time.strftime("%H:%M:%S")

        await prediction_1h(_start_time_str,_start_time_str,"1")
        logger.info(f"{_start_time}驾驶员事故小时风险权重计算完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.exception(f"{_start_time}驾驶员事故小时风险权重执行出错：{e}")
        print(f"{_start_time}驾驶员事故风险权重执行出错: {e}")
    finally:
        import gc
        gc.collect()

    remark = json.dumps(remark_accident, cls=NumpyEncoder, ensure_ascii=False)
    await update_moudle_log(_id, remark, "obs_module_weight_log")

    # 计算驾驶员一周事故风险权重
    _id = str(uuid.uuid4())
    log_data = ObsModuleLog(
        ppartition=datetime.now().strftime('%Y%m%d'),
        id=_id,
        module_type='权重',
        module_name='驾驶员-一周事故风险',
        pid=str(os.getpid()),
        remark='',
        calculate_date=start_date_time,
        end_time=datetime.now(),
        start_time=datetime.now(),
        creator='system',
        create_time=datetime.now(),
        updater='system',
        update_time=datetime.now(),
        deleted="0"
    )
    log_dict = log_data.to_dict()
    await insert_moudle_log(log_dict, "obs_module_weight_log")
    remark_accident = {}
    try:
        logger.info(f"准备{_start_time}驾驶员一周风险权重 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        remark_accident = await main_week(_start_time)
        await prediction_week(_start_time, _start_time, "1")
        logger.info(f"{_start_time}驾驶员一周权重计算完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.exception(f"{_start_time}驾驶员事故风险权重执行出错：{e}")
        print(f"{_start_time}驾驶员事故风险权重执行出错: {e}")
    finally:
        import gc
        gc.collect()

    remark = json.dumps(remark_accident, cls=NumpyEncoder, ensure_ascii=False)
    await update_moudle_log(_id, remark, "obs_module_weight_log")

async def driver_weights_1hour_main(start_date_time:str):
    start_time=datetime.now()
    _start_time=datetime.strftime(start_time,"%Y-%m-%d")
    _start_time=start_date_time
    try:
        logger.info(f"准备{_start_time}驾驶员风险权重 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        await accident_weights_1hour_main(_start_time)
        current_time = datetime.now()
        now_hour_time = current_time.strftime("%H:%M:%S")
        _start_time_str = _start_time + " " + now_hour_time
        await driver_accident_weights(_start_time_str,"1")
        logger.info(f"{_start_time}驾驶员权重计算完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.exception(f"{_start_time}驾驶员事故风险权重执行出错：{e}")
        print(f"{_start_time}驾驶员事故风险权重执行出错: {e}")
    finally:
        import gc
        gc.collect()

async def driver_score_main(start_date:str,end_date:str):
    #计算驾驶员能耗风险分数(一天一次，改成按天计算)
    start_date_ = start_date
    _start_time = start_date
    start_time=datetime.strptime(_start_time,'%Y-%m-%d')
    _start_time_str=start_time.strftime('%Y%m%d')

    _id = str(uuid.uuid4())
    log_data = ObsModuleLog(
        ppartition=datetime.now().strftime('%Y%m%d'),
        id=_id,
        module_type='画像',
        module_name='驾驶员画像',
        pid=str(os.getpid()),
        remark='',
        calculate_date=start_date,
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

    logger.info(f"准备{_start_time}驾驶行为汇总数据 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await driver_behavior_data_init(_start_time,_start_time)
    logger.info(f"准备{_start_time}驾驶行为汇总数据 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    logger.info(f"删除{_start_time}驾驶员画像数据 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await delete_driver_datas(_start_time_str)
    logger.info(f"删除{_start_time}驾驶员画像数据 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


    logger.info(f"准备{_start_time}驾驶员能耗风险分数 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    df =await driver_energy_cores(_start_time)
    logger.info(f"{_start_time}驾驶员能耗风险分数计算完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    #计算驾驶员事故风险(一天一次)
    logger.info(f"准备{_start_time}驾驶员事故风险分数 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await prediction(_start_time,_start_time,"0")
    logger.info(f"{_start_time}驾驶员事故风险分数计算完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    #计算驾驶员服务态度
    logger.info(f"准备{_start_time}驾驶员服务态度分数 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await driver_attitude_scores_main(_start_time)
    logger.info(f"{_start_time}驾驶员服务态度分数计算完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 计算驾驶员安全评价
    logger.info(f"准备{_start_time}驾驶员安全评价分数 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await driver_safety_cores_main(_start_time)
    logger.info(f"{_start_time}驾驶员安全评价分数计算完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 计算驾驶员总分
    logger.info(f"准备{_start_time}驾驶员总分 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await update_driver_scores_main(_start_time)
    logger.info(f"{_start_time}驾驶员总分计算完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 导入高风险驾驶员预警
    logger.info(f"导入{_start_time}高风险驾驶员预警 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await import_warning_driver(_start_time)
    logger.info(f"导入{_start_time}高风险驾驶员预警完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    import gc
    gc.collect()

    remark="驾驶员画像计算完成"
    await update_moudle_log(_id,remark)

async def driver_score_hour_main(start_date:str):
    date_range = pd.date_range(start=start_date, end=start_date)
    for date in date_range:
            # 定义格式字符串
            format_str = "%Y-%m-%d %H:%M:%S"
            current_time = datetime.now()
            start_date=start_date+" "+current_time.strftime("%H:%M:%S")
            _start_time_ = datetime.strptime(start_date, format_str)
            now_hour_time = (_start_time_ - timedelta(hours=1)).strftime(format_str)
            start_date_ = date.to_pydatetime()
            # _start_time_str = start_date_.strftime("%Y-%m-%d")+" "+now_hour_time
            _start_time_str=now_hour_time
            # _end_time_str = start_date_.strftime("%Y-%m-%d") + " " + current_time.strftime("%H:%M:%S")
            _end_time_str=_start_time_.strftime(format_str)
            # 定义格式字符串
            format_str = "%Y-%m-%d %H:%M:%S"
            # 使用 strptime 将字符串转换为日期对象
            _start_time_=datetime.strptime(_start_time_str, format_str)
            # _last_time_ =_start_time_- timedelta(hours=1)

            _id = str(uuid.uuid4())
            log_data = ObsModuleLog(
                ppartition=datetime.now().strftime('%Y%m%d'),
                id=_id,
                module_type='画像',
                module_name='驾驶员小时画像',
                pid=str(os.getpid()),
                remark='',
                calculate_date=start_date,
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

            #计算驾驶员事故风险(一天一次)
            logger.info(f"准备{_start_time_}驾驶员一小时事故风险分数 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            await prediction_1h(_start_time_str,_end_time_str,"0")
            logger.info(f"{_start_time_}驾驶员一小时事故风险分数计算完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            remark = "驾驶员小时画像计算完成"
            await update_moudle_log(_id, remark)

            import gc
            gc.collect()

async def driver_score_hour_main_day(start_date:str,e_times:int):
    date_range = pd.date_range(start=start_date, end=start_date)
    for date in date_range:
            # 定义格式字符串
            format_str = "%Y-%m-%d %H:%M:%S"
            times=process_hourly_data(start_date,e_times)
            for time in times:
                current_time=time.strftime(format_str)
                # current_time = datetime.now()
                # start_date=start_date+" "+current_time.strftime("%H:%M:%S")
                # start_date=time
                _start_time_=time
                # _start_time_ = datetime.strptime(start_date, format_str)
                now_hour_time = (_start_time_ - timedelta(hours=1)).strftime(format_str)
                start_date_ = date.to_pydatetime()
                # _start_time_str = start_date_.strftime("%Y-%m-%d")+" "+now_hour_time
                _start_time_str=now_hour_time
                # _end_time_str = start_date_.strftime("%Y-%m-%d") + " " + current_time.strftime("%H:%M:%S")
                _end_time_str=_start_time_.strftime(format_str)
                # 定义格式字符串
                format_str = "%Y-%m-%d %H:%M:%S"
                # 使用 strptime 将字符串转换为日期对象
                _start_time_=datetime.strptime(_start_time_str, format_str)
                # _last_time_ =_start_time_- timedelta(hours=1)

                _id = str(uuid.uuid4())
                log_data = ObsModuleLog(
                    ppartition=datetime.now().strftime('%Y%m%d'),
                    id=_id,
                    module_type='画像',
                    module_name='驾驶员小时画像',
                    pid=str(os.getpid()),
                    remark='',
                    calculate_date=start_date,
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

                #计算驾驶员事故风险(一天一次)
                logger.info(f"准备{_start_time_}驾驶员一小时事故风险分数 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                # await driver_accident_hour_cores(_start_time_str)
                await prediction_1h(_start_time_str,_end_time_str,"0")
                logger.info(f"{_start_time_}驾驶员一小时事故风险分数计算完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                # # 计算驾驶员总分
                # logger.info(f"准备{_start_time}驾驶员总分 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                # asyncio.run(update_driver_scores_main(_start_time))
                # logger.info(f"{_start_time}驾驶员总分计算完成 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                remark = "驾驶员小时画像计算完成"
                await update_moudle_log(_id, remark)

                import gc
                gc.collect()

def process_hourly_data(start_date:str,s_times:int):
    # 1. 获取“当天”的日期对象
    # 注意：如果当前时间是 2026-07-27 23:18，today() 返回 2026-07-27
    today =  datetime.strptime(start_date, "%Y-%m-%d")

    # 2. 定义起始时间：当天 01:00:00
    start_time = datetime.combine(today, time(1, 0, 0))

    # 3. 定义结束时间：第二天 00:00:00
    next_day = today + timedelta(days=1)
    end_time =datetime.combine(next_day, time(0, 0, 0))

    # 4. 初始化当前时间指针
    current_time = start_time

    print(f"开始处理，时间范围: {start_time} 至 {end_time}")

    times=[]
    i=1
    # 5. 循环遍历每个整点
    while current_time <= end_time:
        # --- 在此处编写你的业务逻辑 ---
        # 例如：查询数据库、打印日志等
        print(f"正在处理时间点: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        if i==s_times:
            times.append(current_time)
            break
        if s_times==0:
            times.append(current_time)
        # 6. 时间递增 1 小时
        current_time += timedelta(hours=1)
        i=i+1
    return times

async def update_driver_scores_main(_start_time:str):
    try:
        async with await connect_to_clickhouse() as client:
            # date_range = pd.date_range(start="2026-01-01", end="2026-01-01")
            date_range = [_start_time]
            for date in date_range:
                start_date=datetime.strptime(date,"%Y-%m-%d")
                start_time = start_date.strftime('%Y-%m-%d')
                _ppartition=start_date.strftime('%Y%m%d')

                list = await crud.Driver(client).get_driver_scores(_ppartition)
                await delete_driver_main_datas(_ppartition)
                await crud.Driver(client).save(list, [])
                # manager = ClickHouseManage(client, "abs_driver_profile_main")
                # data={}
                # for item in list:
                #     data['evalutaion_type']=await crud.Driver(client).get_risk_value(item['score'])
                #     data['score'] = item['score']
                #     await manager.put_data(item['id'],data)

    except Exception as e:
        print(f"驾驶安全评价执行出错: {e}")
    print("数据库连接已关闭")


async def import_warning_driver(_start_time:str):
    try:
        async with await connect_to_clickhouse() as client:
            # date_range = pd.date_range(start="2026-01-01", end="2026-01-01")
            date_range = [_start_time]
            for date in date_range:
                start_date=datetime.strptime(date,"%Y-%m-%d")
                _ppartition=start_date.strftime('%Y%m%d')
                list = await crud.Driver(client).get_warning_driver_1d(_ppartition)
                await crud.Driver(client).save_warning("abs_warning_driver_profile", list)

    except Exception as e:
        print(f"保存1日预警驾驶员出错: {e}")
    print("数据库连接已关闭")

async def get_driver_report(start_date:str):
    try:
        async with await connect_to_clickhouse() as client:
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
            _ppartition = start_date.strftime('%Y%m%d')
            list = await crud.Driver(client).get_driver_report(_ppartition)
            for data in list:
                payload = {
                    "driverName": data["driver_name"],
                    "ppartition": data["ppartition"],
                }
                logger.info(f"获取驾驶员{data['driver_name']}：{start_date}总结报告 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                result=await report_main(payload)
                logger.info(f"获取驾驶员{data['driver_name']}：{start_date}总结报告 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(result)
    except Exception as e:
        logger.info(f"生成驾驶员报告执行出错: {e}")
        print(f"生成驾驶员报告执行出错: {e}")
    print("数据库连接已关闭")

async def get_driver_wide_data(start_date:str):
    try:
        async with await connect_to_clickhouse() as client:
            # 这里可以执行数据库操作
            end_date = datetime.strptime(start_date, "%Y-%m-%d")
            start_date = end_date
            end_date=end_date

            logger.info(f"驾驶员{start_date}一周数据准备 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("数据库连接成功")

            #初始化数据
            try:
              await crud.Driver(client).gen_tmp_table('tmp_driver_wide_data',sql_config.tmp_driver_wide_data_sql(start_date))

            except Exception as e:
                print(f"驾驶员计算分数一周数据存入临时表执行出错: {e}")
            logger.info(f"驾驶员{start_date}一周数据准备 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.exception(f"驾驶员计算一周数据存入临时表执行出错{e}")
        print(f"驾驶员计算一周数据存入临时表执行出错: {e}")




if __name__ == "__main__":
    # asyncio.run(driver_energy_weights('2026-03-01'))
    # asyncio.run(driver_weights_main('2026-05-01'))
    # asyncio.run(driver_accident_weights('2026-05-01'))
    # asyncio.run(driver_weights_1hour_main('2026-05-01'))
    # asyncio.run(driver_score_main('2026-06-01','2026-06-01'))
    # asyncio.run(driver_energy_cores('2026-02-09'))
    # asyncio.run(prediction('2026-06-01','2026-06-01',"0"))
    # asyncio.run(get_driver_report("2026-06-13"))
    asyncio.run(import_warning_driver("2026-08-05"))
    # asyncio.run(driver_score_hour_main('2026-06-01'))
    # asyncio.run(driver_behavior_data_init('2025-08-01','2025-08-01'))
    # date_range = pd.date_range(start="2026-03-16", end="2026-04-22")
    # for date in date_range:
    #     start_time = date.to_pydatetime()
    #     start_time_str=start_time.strftime("%Y-%m-%d")
    #     asyncio.run(driver_behavior_data_init(start_time_str,start_time_str))
