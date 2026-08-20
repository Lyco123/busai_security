# @File           : views.py
# @IDE            : PyCharm
# @desc           : 简要说明
import json
import logging
from datetime import datetime, timedelta

import pandas as pd
import pytz
from clickhouse_driver import Client
from fastapi import APIRouter, Request,Depends
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates

from apps.vadmin.system import crud
from core.database import clickhouse_getter
from model.company.main import company_weights_main, company_main, accident_main
from model.driver.main import driver_behavior_data_init, driver_weight_data_init, driver_weights_main, \
    driver_score_main, driver_behavior_data_month_init, driver_score_hour_main, driver_score_hour_main_day, \
    get_driver_wide_data
from model.driver.src.driver_accident__predict_1d_new import prediction_week
from model.driver.src.driver_accident_train_weights_1d_new import main_week
from model.driver.src.generate_weekly_driver_list import main_warning
from model.route.main_route_quota_weight_month import route_quota_weight_main
from model.route.main_route_risk_score import route_cores, get_route_report, generate_reports_limited
from model.route.route_black_point_prediction.accident_black_point_prediction_model import accident_black_main
from model.route.route_black_point_prediction.behavior_black_point_prediction_model import behavior_black_main
from model.station.score_roadside_stations import station_score_main, station_all_weights_main
from model.vehicle.app_score_update import vehicle_score_main
from model.vehicle.app_weight_update import vehicle_weight_main
from utils.response import SuccessResponse, ErrorResponse
import random
import utils.get_canInfo
from utils.tools import get_shanghai_time, get_next_month_day, get_last_month_day

app = APIRouter()


# 配置模板目录
templates = Jinja2Templates(directory="templates")

###########################################################
#    图表数据
###########################################################

# @app.get("/getCanData", response_class=HTMLResponse)
# async def getCanData(request: Request,db: Client = Depends(clickhouse_getter)):
#     print("解压开始时间：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
#     datas = await crud.Canpacking(db).get_can_limit1()
#     if len(datas)>0:
#         can_info = {
#             "obuid": datas[0]['obuid'],
#             "can": datas[0]['can'],
#             "reportTime": datas[0]['report_time'].strftime("%Y-%m-%d %H:%M:%S"),
#             "ppartition": datas[0]['ppartition'],
#         }
#         return templates.TemplateResponse("can_decrypt.html", {"request": request, "cans": can_info})

@app.get("/logsData", response_class=HTMLResponse)
async def getLogsData(request: Request,db: Client = Depends(clickhouse_getter)):
    print("读取日志文件：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    datas = await crud.Canpacking(db).get_logs()
    logsinfo=[]
    if len(datas)>0:
        for data in datas:
            info = {
                "moduleName": data['module_name'],
                "calculateDate": data['calculate_date'],
                "remark": data['remark'],
                "startTime": data['start_time'].strftime("%Y-%m-%d %H:%M:%S"),
                "endTime": data['end_time'].strftime("%Y-%m-%d %H:%M:%S")
            }
            logsinfo.append(info)
        return templates.TemplateResponse("module_log.html", {"request": request, "logs": logsinfo})
#

#
# @app.post("/submit-can")
# async def submit_can(request: Request,db: Client = Depends(clickhouse_getter)):
#     body = await request.json()
#     json_data = body.get("json")
#     reporttime= body.get("reporttime")
#     ppartition= body.get("ppartition")
#     obuid=body.get("obuid")
#     print("解压开始时间1：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
#     await utils.get_canInfo.to_cancsv_ck(db,json.loads(json_data),obuid,reporttime,ppartition)
#     print("解压结束时间1：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
#     data = 'ok'
#     return SuccessResponse(data)


@app.get("/random/number", summary="获取随机整数")
async def get_random_number():
    now_shanghai = get_shanghai_time()
    print(now_shanghai)
    return SuccessResponse(random.randint(500, 20000))


@app.post("/api/driver_ehavior_data_init", summary="驾驶行为月明细、数据汇总")
async def gen_driver_behavior_data_init(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_time = body_str.get("start_date_time")
    end_time = body_str.get("end_date_time")
    date_range = pd.date_range(start=start_time, end=end_time)
    for date in date_range:
        start_time = date.to_pydatetime()
        start_time = start_time.strftime("%Y-%m-%d")
        end_time = start_time
        await driver_behavior_data_init(start_time,end_time)
    data="ok"
    return SuccessResponse(data)


@app.post("/api/driver_weight_data_init", summary="驾驶员画像权重中间表生成")
async def gen_driver_weight_data_init(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    date_time=body_str.get("start_date_time")
    await driver_weight_data_init(date_time)
    data = "ok"
    return SuccessResponse(data)

@app.post("/api/driver_weights_main", summary="驾驶员画像权重生成")
async def gen_driver_weights_main(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_time=body_str.get("start_date_time")
    try:
        await driver_weights_main(start_time)
        data = "ok"
        return SuccessResponse(data)
    except Exception as e:
        data = f"{e}"
        return ErrorResponse(data)

@app.post("/api/route_quota_weight_main", summary="线路权重生成")
async def gen_route_quota_weight_main(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    date_time=body_str.get("start_date_time")
    try:
        await route_quota_weight_main(date_time)
        data = "ok"
        return SuccessResponse(data)
    except Exception as e:
        data = f"{e}"
        return ErrorResponse(data)

@app.post("/api/vehicle_weight_main", summary="车辆权重生成")
async def gen_vehicle_weight_main(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    create_date = body_str.get("start_date")
    start_date = datetime.strptime(create_date, "%Y-%m-%d")
    start_date_ = get_last_month_day(start_date)
    end_date =  start_date-timedelta(days=1)
    start_date_ =start_date_.strftime("%Y-%m-%d")
    end_date_=end_date.strftime("%Y-%m-%d")
    try:
        await vehicle_weight_main(start_date_,end_date_,create_date)
        data = "ok"
        return SuccessResponse(data)
    except Exception as e:
        data = f"{e}"
        return ErrorResponse(data)


@app.post("/api/company_weight_main", summary="单位、事故权重生成")
async def gen_company_weight_main(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_date = body_str.get("start_date")
    try:
        await company_weights_main(start_date)
        data = "ok"
        return SuccessResponse(data)
    except Exception as e:
        data = f"{e}"
        return ErrorResponse(data)

@app.post("/api/driver_score_main", summary="计算驾驶员画像分数")
async def gen_driver_score_main(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_date = body_str.get("start_date")
    end_date = body_str.get("end_date")
    date_range = pd.date_range(start=start_date, end=end_date)
    try:
        for date in date_range:
            start_time = date.to_pydatetime()
            start_time_str = start_time.strftime("%Y-%m-%d")
            await driver_score_main(start_time_str,start_time_str)
        data = "ok"
        return SuccessResponse(data)
    except Exception as e:
        data = f"{e}"
        return ErrorResponse(data)

@app.post("/api/route_score_main", summary="计算线路画像分数")
async def gen_route_score_main(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_date = body_str.get("start_date")
    try:
        await route_cores(start_date)
        data = "ok"
        return SuccessResponse(data)
    except Exception as e:
        data = f"{e}"
        return ErrorResponse(data)


@app.post("/api/vehicle_score_main", summary="计算车辆画像分数")
async def gen_vehicle_score_main(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_date = body_str.get("start_date")
    end_date= body_str.get("end_date")
    date_range = pd.date_range(start=start_date, end=end_date)
    try:
        for date in date_range:
            start_time = date.to_pydatetime()
            start_time_str = start_time.strftime("%Y-%m-%d")
            await vehicle_score_main(start_time_str, start_time_str)
        data = "ok"
        return SuccessResponse(data)
    except Exception as e:
        data = f"{e}"
        return ErrorResponse(data)

@app.post("/api/company_main", summary="计算单位画像分数")
async def gen_company_main(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_date = body_str.get("start_date")
    try:
        await company_main(start_date)
        data = "ok"
        return SuccessResponse(data)
    except Exception as e:
        data = f"{e}"
        return ErrorResponse(data)

@app.post("/api/accident_main", summary="计算事故画像分数")
async def gen_accident_main(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_date = body_str.get("start_date")
    try:
        await accident_main(start_date)
        data = "ok"
        return SuccessResponse(data)
    except Exception as e:
        data = f"{e}"
        return ErrorResponse(data)

@app.post("/api/behavior_black_main", summary="计算行为黑点")
async def gen_behavior_black_main(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_date = body_str.get("start_date")
    try:
        await behavior_black_main(start_date)
        data = "ok"
        return SuccessResponse(data)
    except Exception as e:
        data = f"{e}"
        return ErrorResponse(data)

@app.post("/api/accident_black_main", summary="计算事故黑点")
async def gen_accident_black_main(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_date = body_str.get("start_date")
    try:
        await accident_black_main(start_date)
        data = "ok"
        return SuccessResponse(data)
    except Exception as e:
        data = f"{e}"
        return ErrorResponse(data)

@app.post("/api/driver_score_hour_main", summary="计算驾驶员1小时事故风险")
async def gen_driver_score_hour_main(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_date = body_str.get("start_date")
    await driver_score_hour_main(start_date)
    data = "ok"
    return SuccessResponse(data)

@app.post("/api/driver_score_hour_main_day", summary="计算驾驶员一天的1小时事故风险")
async def gen_driver_score_hour_main(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_date = body_str.get("start_date")
    e_times = body_str.get("e_times")
    await driver_score_hour_main_day(start_date,e_times)
    data = "ok"
    return SuccessResponse(data)

@app.post("/api/driver_score_week", summary="计算驾驶员一周事故风险")
async def gen_driver_score_week_main(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_date = body_str.get("start_date")
    # await main_warning(start_date)
    await prediction_week(start_date,start_date,"0")
    data = "ok"
    return SuccessResponse(data)

@app.post("/api/driver_weight_week", summary="计算驾驶员一周事故风险权重")
async def gen_driver_weight_week_main(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_date = body_str.get("start_date")
    remark_accident = await main_week(start_date)
    await prediction_week(start_date, start_date, "1")
    data = remark_accident
    return SuccessResponse(data)

@app.post("/api/bus_station_score_main", summary="计算站场画像分数")
async def bus_station_score_main(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_date = body_str.get("start_date")
    try:
        await station_score_main(start_date)
        data = "ok"
        return SuccessResponse(data)
    except Exception as e:
        data = f"{e}"
        return ErrorResponse(data)

@app.post("/api/bus_station_weight_main", summary="计算站场权重")
async def bus_station_weight_main(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_date = body_str.get("start_date")
    try:
        await station_all_weights_main(start_date)
        data = "ok"
        return SuccessResponse(data)
    except Exception as e:
        data = f"{e}"
        return ErrorResponse(data)

@app.post("/api/gen_route_report", summary="生成线路总结报告")
async def gen_route_report(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_date = body_str.get("start_date")
    reccount= body_str.get("reccount")
    try:
        await generate_reports_limited(start_date,reccount)
        # await get_route_report(start_date,reccount)
        data = "ok"
        return SuccessResponse(data)
    except Exception as e:
        data = f"{e}"
        return ErrorResponse(data)

@app.post("/api/gen_driver_wide_data", summary="获取驾驶员一周的宽表数据")
async def gen_driver_wide_data(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_date = body_str.get("start_date")
    try:
        await get_driver_wide_data(start_date)
        data = "ok"
        return SuccessResponse(data)
    except Exception as e:
        data = f"{e}"
        return ErrorResponse(data)


@app.post("/api/gen_driver_wide_data", summary="消息推送")
async def gen_driver_wide_data(request: Request):
    body_byte = await request.body()
    body_str = json.loads(body_byte.decode('utf-8'))
    start_date = body_str.get("start_date")
    try:
        await get_driver_wide_data(start_date)
        data = "ok"
        return SuccessResponse(data)
    except Exception as e:
        data = f"{e}"
        return ErrorResponse(data)








