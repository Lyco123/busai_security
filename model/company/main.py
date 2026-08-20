import asyncio
import os
import uuid
import numpy as np
import pandas as pd

from core.logger import logger
from core.clickhouse_connect import connect_to_clickhouse
from datetime import datetime, timedelta

from model.bus.crud import insert_moudle_log, update_moudle_log
from model.bus.schemas.bus_profile import ObsModuleLog
from model.company import crud
from model.company.crud import save_company_weights_data
from model.company.schemas.accident_profile import AbsAccidentQuotaScoreSub, AbsAccidentProfileMain
from model.company.schemas.company_profile import AbsCompanyProfileMain, AbsCompanyQuotaScoreSub
from services.ai_report_summary import report_main


async def company_main(start_date:str):
    try:
        async with await connect_to_clickhouse() as client:
            # start_times = ['2025-12-29','2026-01-05', '2026-01-12', '2026-01-19']
            start_times = [start_date]
            for start_time in start_times:
                # 解析开始日期
                end_date_ = datetime.strptime(start_time, '%Y-%m-%d')
                # 计算结束日期
                start_date_ = end_date_ - timedelta(days=6)
                # 格式化为YYYYMMDD格式
                start_date_str = start_date_.strftime('%Y%m%d')
                end_date_str = end_date_.strftime('%Y%m%d')
                ppartition = start_date_str  # datetime.now().strftime('%Y%m%d')

                sqlwheres={}
                sqlwheres['driver']="'安全评价','服务态度','能耗风险','事故风险'"
                sqlwheres['route']="'静态风险','动态风险'"
                sqlwheres['vehicle']="'故障风险','能耗风险'"
                sqlwheres['station'] = "'划定区域','路边区域'"
                sqlwheres['profile_type']='单位画像'
                sqlwheres['driver_quota_name']='驾驶员风险'
                sqlwheres['route_quota_name'] = '线路风险'
                sqlwheres['vehicle_quota_name'] = '车辆风险'
                sqlwheres['station_quota_name'] = '站场风险'
                total_scores = await crud.Company(client).get_company_total_scores(sqlwheres, start_date_str,end_date_str,start_date)
                #一级指标
                company_quota1_scores = await crud.Company(client).get_company_quota1_scores(sqlwheres, start_date_str, end_date_str,start_date)
                #二级指标+三级指标
                #驾驶员画像平均值
                drivers_avg_scors=await crud.Company(client).get_drivers_avg_scores("",start_date_str,end_date_str)
                #线路风险平均值
                route_avg_scors=await crud.Company(client).get_route_company_avg_scores("",start_date_str,end_date_str)
                #车辆风险平均值
                bus_avg_scors = await crud.Company(client).get_bus_avg_scores("", start_date_str, end_date_str)
                # 站场风险平均值
                station_avg_scors = await crud.Company(client).get_bus_station_avg_scores("", start_date_str,
                                                                                          end_date_str)

                main_datas = []
                quota_scores = []
                profile_main = None
                for c in total_scores:
                    main_id = str(uuid.uuid4())
                    _evalutaion_type = await crud.Company(client).get_risk_value(c['score'])
                    profile_main = AbsCompanyProfileMain(
                        ppartition=end_date_str,
                        id=main_id,
                        organ_id=c['organ_id'],
                        organ_name=c['organ_name'],
                        calculate_date=end_date_,
                        evalutaion_type=_evalutaion_type,
                        score=round(c['score'],2),
                        suggested_content="",
                        creator="system",
                        create_time=datetime.now(),
                        updater="system",
                        update_time=datetime.now(),
                        deleted="0"
                    )
                    #所有风险
                    filter_company_quota1_scores=  [d for d in company_quota1_scores if d.get("organ_id") == c['organ_id']]
                    for f in filter_company_quota1_scores:
                        quota_score_1 = AbsCompanyQuotaScoreSub(
                            ppartition=end_date_str,#datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id=f['company_quota_id'],
                            quota_name=f['company_quota_name'],
                            score=round(f['score'], 6),
                            weight_rate=round(float(f['weight_rate']), 6),
                            original_value=round(f['score']*float(f['weight_rate']), 6),
                            risk_data='',
                            quota_level="1",
                            parent_id="单位画像",
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=end_date_,
                        )
                        quota_scores.append(quota_score_1.to_dict())
                    filtered_data_drivers=[]
                    filtered_data_route=[]
                    filtered_data_bus=[]
                    if drivers_avg_scors is not None:
                        filtered_data_drivers = [d for d in drivers_avg_scors if d.get("organ_id") == c['organ_id']]
                    if route_avg_scors is not None:
                        filtered_data_route = [d for d in route_avg_scors if d.get("organ_id") == c['organ_id']]
                    if bus_avg_scors is not None:
                        filtered_data_bus = [d for d in bus_avg_scors if d.get("organ_id") == c['organ_id']]
                    if station_avg_scors is not None:
                        filtered_data_bus_station = [d for d in station_avg_scors if d.get("organ_id") == c['organ_id']]
                    filtered_data=filtered_data_drivers + filtered_data_route + filtered_data_bus + filtered_data_bus_station
                    for d in filtered_data:
                        if d['risk_data']!='':
                            m_risk_data = str(d['risk_data'])
                        else:
                            m_risk_data=''
                        quota_score_3 = AbsCompanyQuotaScoreSub(
                            ppartition=end_date_str,#datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id=d['company_quota_id'],
                            quota_name=d['quota_name'],
                            score=round(d['score'], 6),
                            weight_rate=round(d['weight_rate'], 6),
                            original_value=round(d['original_value'], 6),
                            risk_data=m_risk_data,
                            quota_level=d['quota_level'],
                            parent_id=d["company_parent_id"],
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=end_date_,
                        )
                        quota_scores.append(quota_score_3.to_dict())

                    if profile_main is not None:
                        main_datas.append(profile_main.to_dict())

                await crud.Company(client).save(main_datas, quota_scores)
    except Exception as e:
        print(f"单位画像分数主程序执行出错: {e}")
    print("数据库连接已关闭")
# ==================== 10. 演示预测 ====================



async def accident_main(start_date:str):
    try:
        async with await connect_to_clickhouse() as client:
            # '2025-12-01',
            # start_times = ['2025-12-29','2026-01-05', '2026-01-12', '2026-01-19']
            start_times = [start_date]
            for start_time in start_times:
                # 解析开始日期
                end_date_= datetime.strptime(start_time, '%Y-%m-%d')
                # 计算结束日期
                start_date_ = end_date_ - timedelta(days=6)
                # 格式化为YYYYMMDD格式
                start_date_str = start_date_.strftime('%Y%m%d')
                end_date_str = end_date_.strftime('%Y%m%d')
                ppartition = start_date_str  # datetime.now().strftime('%Y%m%d')

                sqlwheres = {}
                sqlwheres['driver'] = "'事故风险'"
                sqlwheres['route'] = "'静态风险','动态风险'"
                sqlwheres['vehicle'] = "'故障风险'"
                sqlwheres['station'] = "'划定区域','路边区域'"
                sqlwheres['profile_type']='事故画像'
                sqlwheres['driver_quota_name']='驾驶员事故风险'
                sqlwheres['route_quota_name'] = '线路事故风险'
                sqlwheres['vehicle_quota_name'] = '车辆故障风险'
                sqlwheres['station_quota_name'] = '站场风险'
                total_scores = await crud.Company(client).get_company_total_scores(sqlwheres, start_date_str,
                                                                                   end_date_str,start_date)

                company_quota1_scores = await crud.Company(client).get_company_quota1_station_scores(sqlwheres, start_date_str,
                                                                                             end_date_str,start_date)
                # 驾驶员画像平均值
                drivers_avg_scors = await crud.Company(client).get_drivers_avg_scores(" and quota_id like '驾驶员画像-事故风险-%%' ", start_date_str, end_date_str)
                # 线路风险平均值
                route_avg_scors = await crud.Company(client).get_route_avg_scores("", start_date_str, end_date_str)
                # 车辆风险平均值
                bus_avg_scors = await crud.Company(client).get_bus_avg_scores(" and quota_id like '车辆画像-故障风险-%%' ", start_date_str, end_date_str)

                main_datas = []
                quota_scores = []
                profile_main = None
                for c in total_scores:
                    main_id = str(uuid.uuid4())
                    _evalutaion_type=await crud.Company(client).get_risk_value(c['score'])
                    profile_main = AbsAccidentProfileMain(
                        ppartition=end_date_str,
                        id=main_id,
                        organ_id=c['organ_id'],
                        organ_name=c['organ_name'],
                        calculate_date=end_date_,
                        evalutaion_type=_evalutaion_type,
                        score=round(c['score'],2),
                        suggested_content="",
                        creator="system",
                        create_time=datetime.now(),
                        updater="system",
                        update_time=datetime.now(),
                        deleted="0"
                    )
                    # 所有风险
                    filter_company_quota1_scores = [d for d in company_quota1_scores if
                                                    d.get("organ_id") == c['organ_id']]
                    for f in filter_company_quota1_scores:
                        quota_score_1 = AbsAccidentQuotaScoreSub(
                            ppartition=end_date_str,  # datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id=f['company_quota_id'].replace('单位画像','事故画像').replace('车辆风险','车辆故障风险').replace('线路风险','线路事故风险').replace('驾驶员风险','驾驶员事故风险'),
                            quota_name=f['company_quota_name'].replace('单位画像','事故画像').replace('车辆风险','车辆故障风险').replace('线路风险','线路事故风险').replace('驾驶员风险','驾驶员事故风险'),
                            score=round(f['score'], 6),
                            weight_rate=round(float(f['weight_rate']), 6),
                            original_value=round(f['score']*float(f['weight_rate']), 6),
                            risk_data='',
                            quota_level="1",
                            parent_id="事故画像",
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=end_date_,
                        )
                        quota_scores.append(quota_score_1.to_dict())
                    filtered_data_drivers=[]
                    filtered_data_route=[]
                    filtered_data_bus=[]
                    if drivers_avg_scors is not None:
                        filtered_data_drivers = [d for d in drivers_avg_scors if d.get("organ_id") == c['organ_id']]
                    if route_avg_scors is not None:
                        filtered_data_route = [d for d in route_avg_scors if d.get("organ_id") == c['organ_id']]
                    if bus_avg_scors is not None:
                        filtered_data_bus = [d for d in bus_avg_scors if d.get("organ_id") == c['organ_id']]
                    filtered_data = filtered_data_drivers + filtered_data_route + filtered_data_bus
                    for d in filtered_data:
                        if d['risk_data']!='':
                            m_risk_data = str(d['risk_data'])
                        else:
                            m_risk_data=''
                        quota_score_3 = AbsAccidentQuotaScoreSub(
                            ppartition=end_date_str,  # datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id=d['company_quota_id'].replace('单位画像','事故画像').replace('车辆风险','车辆故障风险').replace('线路风险','线路事故风险').replace('驾驶员风险','驾驶员事故风险').replace('-事故风险','').replace('-故障风险',''),
                            quota_name=d['quota_name'].replace('单位画像','事故画像').replace('车辆风险','车辆故障风险').replace('线路风险','线路事故风险').replace('驾驶员风险','驾驶员事故风险').replace('-事故风险','').replace('-故障风险',''),
                            score=round(d['score'], 6),
                            weight_rate=round(d['weight_rate'], 6),
                            original_value=round(d['original_value'], 6),
                            risk_data=m_risk_data,
                            quota_level=d['quota_level'],
                            parent_id=d["company_parent_id"].replace('单位画像','事故画像').replace('车辆风险','车辆故障风险').replace('线路风险','线路事故风险').replace('驾驶员风险','驾驶员事故风险').replace('-事故风险','').replace('-故障风险',''),
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=end_date_,
                        )
                        quota_scores.append(quota_score_3.to_dict())
                    if profile_main is not None:
                        main_datas.append(profile_main.to_dict())

                await crud.Company(client).save_accident(main_datas, quota_scores)
    except Exception as e:
        logger.exception(f"事故画像分数主程序执行出错: {e}")
        print(f"事故画像分数主程序执行出错: {e}")
    print("数据库连接已关闭")

async def company_score_main(start_time):
    _id = str(uuid.uuid4())
    log_data = ObsModuleLog(
        ppartition=datetime.now().strftime('%Y%m%d'),
        id=_id,
        module_type='画像',
        module_name='单位画像',
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
    remark=''
    try:
        await company_main(start_time)
        await accident_main(start_time)
        remark = '单位画像、事故画像计算完成'
    except Exception as e:
        remark = f'计算失败:{e}'
        logger.exception(f"单位画像、事故画像计算失败: {e}")

    await update_moudle_log(_id, remark)

async def  company_weights_main(start_time:str):
    _id = str(uuid.uuid4())
    log_data = ObsModuleLog(
        ppartition=datetime.now().strftime('%Y%m%d'),
        id=_id,
        module_type='权重',
        module_name='单位权重',
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
    remark = ''
    try:
        company_weights = {'驾驶员风险': 0.25,
                            '车辆风险': 0.25,
                            '线路风险': 0.25,
                            '站场风险': 0.25,
                            '驾驶员事故风险': 0.4,
                            '车辆故障风险': 0.3,
                            '线路事故风险': 0.3}

        await save_company_weights_data(start_time, company_weights)
        remark = '计算成功'
    except Exception as e:
        remark = f'计算失败:{e}'
        logger.exception(f"单位权重计算失败: {e}")
    await update_moudle_log(_id, remark)

async def get_company_report(start_date:str):
    try:
        async with await connect_to_clickhouse() as client:
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
            _ppartition = start_date.strftime('%Y%m%d')
            list = await crud.Company(client).get_company_report(_ppartition)
            for data in list:
                payload = {
                    "organName": data["organ_name"],
                    "ppartition": data["ppartition"],
                }
                logger.info(f"获取单位{data['organ_name']}：{start_date}总结报告 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                result=await report_main(payload)
                logger.info(f"获取单位{data['organ_name']}：{start_date}总结报告 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(result)
    except Exception as e:
        logger.info(f"生成单位报告执行出错: {e}")
        print(f"生成单位报告执行出错: {e}")
    print("数据库连接已关闭")

async def get_accident_report(start_date:str):
    try:
        async with (await connect_to_clickhouse() as client):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
            _ppartition = start_date.strftime('%Y%m%d')
            list = await crud.Company(client).get_accident_report(_ppartition)
            for data in list:
                # accident_Date= datetime.strptime(data["accident_time"], "%Y%m%d%H%M%S")
                _accident_Date = data["accident_time"].strftime("%Y%m%d%H%M%S")
                payload = {
                    "type":"accident",
                    "driverName": data["employee_name"],
                    "accidentDate": _accident_Date,
                }
                logger.info(f"获取驾驶员{data['employee_name']}：{data['accident_time']}事故总结报告 开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                result=await report_main(payload)
                logger.info(f"获取驾驶员{data['employee_name']}：{data['accident_time']}事故总结报告 结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(result)
    except Exception as e:
        logger.info(f"生成驾驶员事故报告执行出错: {e}")
        print(f"生成驾驶员事故报告执行出错: {e}")
    print("数据库连接已关闭")

if __name__=="__main__":
    # 分数预测
    asyncio.run(get_accident_report("2026-06-15"))
    # asyncio.run(accident_main())
    # asyncio.run(company_weights_main("2026-01-01"))
