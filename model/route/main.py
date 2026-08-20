import asyncio
import uuid
from datetime import datetime

import pandas as pd
from clickhouse_driver import Client
from typing import Optional, List, Dict, Any, Union
import logging

from core.logger import logger
from core.clickhouse_connect import connect_to_clickhouse
from model.route import crud
from model.route.schemas.route_profile import AbsRouteQuotaScoreSub, AbsRouteProfileMain
from utils.tools import get_shanghai_time


# async def gen_route_score_sample():
#     # 使用异步上下文管理器方式
#     try:
#         async with await connect_to_clickhouse() as client:
#             """演示两层分数预测"""
#             print("\n"+"="*90)
#             print("线路测试数据开始时间：" + get_shanghai_time().strftime("%Y-%m-%d %H:%M:%S"))
#
#             quota1_datas = await crud.Route(client).get_route_quota1()
#             quota2_datas = await crud.Route(client).get_route_quota2()
#             quota3_datas = await crud.Route(client).get_route_quota3()
#             quota_datas = quota1_datas + quota2_datas + quota3_datas
#
#             route_profile_main_datas=await crud.Route(client).get_ods_jituan_bs_route()
#             main_datas=[]
#             quota_scores=[]
#             for d in route_profile_main_datas:
#                 main_id = str(uuid.uuid4())
#                 profile_main = AbsRouteProfileMain(
#                     ppartition=get_shanghai_time().strftime("%Y%m%d"),
#                     id=main_id,
#                     route_id=d['route_id'],
#                     route_name=d['route_name'],
#                     organ_id=d['organ_id'],
#                     organ_name=d['organ_name'],
#                     calculate_date=datetime.combine(get_shanghai_time().date(), datetime.min.time()),
#                     evalutaion_type="",
#                     score=0,
#                     suggested_content="",
#                     creator="system",
#                     create_time=get_shanghai_time(),
#                     updater="system",
#                     update_time=get_shanghai_time(),
#                     deleted="0"
#                 )
#
#                 for quota1 in quota_datas:
#                     quota_score_1=AbsRouteQuotaScoreSub(
#                         ppartition=get_shanghai_time().strftime("%Y%m%d"),
#                         id=str(uuid.uuid4()),
#                         main_id=main_id,
#                         quota_id=quota1['quota_id'],
#                         quota_name=quota1['quota_name'],
#                         score=9.99,
#                         weight_rate=9.99,
#                         original_value=9.99,
#                         risk_data="9.99",
#                         quota_level=quota1['quota_level'],
#                         parent_id=quota1['parent_id'],
#                         creator="system",
#                         create_time=get_shanghai_time(),
#                         updater="system",
#                         update_time=get_shanghai_time(),
#                         deleted="0",
#                     )
#                     quota_scores.append(quota_score_1.to_dict())
#                 main_datas.append(profile_main.to_dict())
#             # 保存线路画像分数数据
#             await crud.Route(client).save(main_datas, quota_scores)
#
#             logger.info("驾驶员事故风险 评分系统结束时间：" + get_shanghai_time().strftime("%Y-%m-%d %H:%M:%S"))
#             # return main_datas,quota_scores
#     except Exception as e:
#         logger.error("驾驶员事故风险主程序执行出错", exc_info=True)
#         print(f"驾驶员画像主程序执行出错: {e}")
#     print("数据库连接已关闭")

