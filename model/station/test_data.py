# import asyncio
# import uuid
# from datetime import datetime, timedelta
#
# import numpy as np
# import pandas as pd
#
# from core.clickhouse_connect import connect_to_clickhouse
# from model.station import crud
# from model.station.schemas.bus_station_profile import AbsBusStationQuotaScoreSub, AbsBusStationProfileMain
#
#
# def calculate_two_layer_scores(X,X_input,feature_names,dim_names,dim_features):
#
#     n_samples=X_input.shape[0]
#     final_scores={}
#     weights=[0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.1, 0.1]
#
#     raw_scores={}
#     for col in feature_names:
#         raw_scores[col]=np.random.uniform(0,100,n_samples)
#         raw_scores[col]=np.clip(raw_scores[col],0,100)
#
#     for i, col in enumerate(feature_names):
#         final_scores[col]=raw_scores[col]*weights[i]
#
#     dim_raw_scores={}
#     dim_final_scores={}
#     dim_weights={}
#     for dim in dim_names:
#         dim_feats=dim_features[dim]
#         dim_final_list=[final_scores[feat] for feat in dim_feats if feat in final_scores]
#         dim_weight_sum=0
#         for feat in dim_feats:
#             if feat in feature_names:
#                 idx=feature_names.index(feat)
#                 dim_weight_sum+=weights[idx]
#         dim_weights[dim]=dim_weight_sum
#         if dim_final_list:
#             dim_final_scores[dim]=np.sum(dim_final_list,axis=0)
#             dim_raw_scores[dim]=dim_final_scores[dim]/dim_weights[dim]
#         else:
#             dim_final_scores[dim]=np.zeros(n_samples)
#             dim_raw_scores[dim]=np.zeros(n_samples)
#
#
#     total_score=np.zeros(n_samples)
#     for col in feature_names:
#         total_score+=final_scores[col]
#     total_score=np.clip(total_score,0,100)
#
#
#     return {
#         'driver_name':X.iloc[:,0], # 司机名称
#         'driver_id':X.iloc[:,1],  # 司机ID
#         'organ_id':X.iloc[:,2],  # 机构ID
#         'organ_name':X.iloc[:,3],  # 机构名称
#         'final_scores':final_scores,  # 总分细分
#         'raw_scores':raw_scores,  # 原始分
#         'feat_weights':weights,  #  特征权重
#         'total_score':total_score,  # 总分
#         'dim_raw_scores':dim_raw_scores, # 维度原始分
#         'dim_final_scores':dim_final_scores, # 维度总分
#         'dim_weights':dim_weights # 维度权重
#     }
#
#
# # ==================== 10. 演示预测 ====================
# async def bus_station_cores():
#     try:
#         async with await connect_to_clickhouse() as client:
#             quota2_datas = await crud.BusStation(client).get_bus_station_quota2('交通安全')
#             quota3_datas = await crud.BusStation(client).get_bus_station_quota3('交通安全')
#             quota3_dict={}
#             for quota in quota3_datas:
#                 quota3_dict[quota['quota_name']]=quota['parent_name']
#
#             date_range = pd.date_range(start="2025-12-01", end="2025-12-28")
#             start_times = ['2025-12-01', '2025-12-08', '2025-12-15', '2025-12-22']
#             for start_time in start_times:
#                 results1=await prediction()
#
#                 # 解析开始日期
#                 start_date_ = datetime.strptime(start_time, '%Y-%m-%d')
#                 # 计算结束日期
#                 end_date_ = start_date_ + timedelta(days=6)
#
#                 start_date_str = end_date_.strftime('%Y%m%d')
#
#                 ppartition = start_date_str  # datetime.now().strftime('%Y%m%d')
#                 bus_station_profile_main_datas = await crud.BusStation(client).get_abs_bus_station_profile_main(ppartition)
#                 bus_station_ids = []
#                 if bus_station_profile_main_datas:
#                     for d in bus_station_profile_main_datas:
#                         bus_station_ids.append(d['bus_station_id'])
#                 main_datas = []
#                 quota_scores = []
#                 profile_main = None
#                 info=results1['driver_name'].tolist()
#                 info_name=results1['driver_id'].tolist()
#                 info_organ=results1['organ_id'].tolist()
#                 info_organ_name = results1['organ_name'].tolist()
#
#                 for i in range(len(results1['total_score'])):
#                     if info[i] in bus_station_ids:
#                         x = bus_station_ids.index(info[i])
#                         main_id = bus_station_profile_main_datas[x]['id']
#                         profile_main = None
#                     else:
#                         main_id = str(uuid.uuid4())
#                         profile_main = AbsBusStationProfileMain(
#                             ppartition=start_date_str,
#                             id=main_id,
#                             bus_station_id=info[i],
#                             bus_station_name=info_name[i],
#                             organ_id=info_organ[i],
#                             organ_name=info_organ_name[i],
#                             calculate_date=datetime.combine(datetime.now().date(), datetime.min.time()),
#                             evalutaion_type="",
#                             score=0,
#                             suggested_content="",
#                             creator="system",
#                             create_time=datetime.now(),
#                             updater="system",
#                             update_time=datetime.now(),
#                             deleted="0"
#                         )
#
#                     quota_score_1 = AbsBusStationQuotaScoreSub(
#                         ppartition=start_date_str,#datetime.now().strftime("%Y%m%d"),
#                         id=str(uuid.uuid4()),
#                         main_id=main_id,
#                         quota_id="站场画像-交通安全",
#                         quota_name="交通安全",
#                         score=round(results1['total_score'][i], 2),
#                         weight_rate=0.33,
#                         original_value=round(results1['total_score'][i], 2)*0.33,
#                         risk_data="",
#                         quota_level="1",
#                         parent_id="站场画像",
#                         creator="system",
#                         create_time=datetime.now(),
#                         updater="system",
#                         update_time=datetime.now(),
#                         deleted="0",
#                         start_time=start_date_,
#                         end_time=end_date_,
#                     )
#                     quota_scores.append(quota_score_1.to_dict())
#                     for x in quota2_datas:
#                         quota_score_2 = AbsBusStationQuotaScoreSub(
#                             ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
#                             id=str(uuid.uuid4()),
#                             main_id=main_id,
#                             quota_id=x['quota_id'],
#                             quota_name=x['quota_name'],
#                             score=round(results1['dim_raw_scores'][x['quota_name']][i], 1),
#                             weight_rate=results1['dim_weights'][x['quota_name']],
#                             original_value=round(results1['dim_final_scores'][x['quota_name']][i], 1),
#                             risk_data="",
#                             quota_level=x['quota_level'],
#                             parent_id=x['parent_id'],
#                             creator="system",
#                             create_time=datetime.now(),
#                             updater="system",
#                             update_time=datetime.now(),
#                             deleted="0",
#                             start_time=start_date_,
#                             end_time=end_date_,
#                         )
#                         quota_scores.append(quota_score_2.to_dict())
#                         for j, feat in enumerate(results1['final_scores']):
#                             if quota3_dict[feat]==x['quota_name']:
#                                 quota_score_3 = AbsBusStationQuotaScoreSub(
#                                 ppartition=start_date_str,#datetime.now().strftime("%Y%m%d"),
#                                     id=str(uuid.uuid4()),
#                                     main_id=main_id,
#                                     quota_id=x['quota_id']+'-'+ feat,
#                                     quota_name=feat,
#                                     score=round(results1['raw_scores'][feat][j], 2),
#                                     weight_rate=round(results1['feat_weights'][j], 2),
#                                     original_value=round(results1['final_scores'][feat][j], 2),
#                                     risk_data="",
#                                     quota_level="3",
#                                     parent_id=x['quota_id'] ,
#                                     creator="system",
#                                     create_time=datetime.now(),
#                                     updater="system",
#                                     update_time=datetime.now(),
#                                     deleted="0",
#                                     start_time=start_date_,
#                                     end_time=end_date_,
#                                 )
#                                 quota_scores.append(quota_score_3.to_dict())
#                     if profile_main is not None:
#                         main_datas.append(profile_main.to_dict())
#                 await crud.BusStation(client).save(main_datas, quota_scores)
#     except Exception as e:
#         print(f"站场画像主程序执行出错: {e}")
#     print("数据库连接已关闭")
# # ==================== 10. 演示预测 ====================
#
# async def bus_station_cores2():
#     try:
#         async with await connect_to_clickhouse() as client:
#             start_times = ['2025-12-01', '2025-12-08', '2025-12-15', '2025-12-22']
#             for start_time in start_times:
#                 results1,results2=await prediction2()
#                 # 解析开始日期
#                 start_date_ = datetime.strptime(start_time, '%Y-%m-%d')
#                 # 计算结束日期
#                 end_date_ = start_date_ + timedelta(days=6)
#
#                 start_date_str = end_date_.strftime('%Y%m%d')
#                 ppartition=start_date_str
#                 bus_station_profile_main_datas = await crud.BusStation(client).get_abs_bus_station_profile_main(ppartition)
#                 bus_station_ids = []
#                 if bus_station_profile_main_datas:
#                     for d in bus_station_profile_main_datas:
#                         bus_station_ids.append(d['bus_station_id'])
#                 main_datas = []
#                 quota_scores = []
#                 profile_main = None
#                 info = results1['driver_name'].tolist()
#                 for i in range(len(results1['total_score'])):
#                         # if info[i][1]!='63000398':
#                         #     continue
#                     if info[i] in bus_station_ids:
#                         x = bus_station_ids.index(info[i])
#                         main_id = bus_station_profile_main_datas[x]['id']
#                     profile_main = None
#                     quota_score_1 = AbsBusStationQuotaScoreSub(
#                         ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
#                         id=str(uuid.uuid4()),
#                         main_id=main_id,
#                         quota_id="站场画像-三防安全",
#                         quota_name="三防安全",
#                         score=round(results1['total_score'][i], 2),
#                         weight_rate=0.33,
#                         original_value=round(results1['total_score'][i], 2) * 0.33,
#                         risk_data="",
#                         quota_level="1",
#                         parent_id="站场画像",
#                         creator="system",
#                         create_time=datetime.now(),
#                         updater="system",
#                         update_time=datetime.now(),
#                         deleted="0",
#                         start_time=start_date_,
#                         end_time=start_date_,
#                     )
#                     quota_scores.append(quota_score_1.to_dict())
#                     for j, feat in enumerate(results1['final_scores']):
#                         quota_score_3 = AbsBusStationQuotaScoreSub(
#                             ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
#                             id=str(uuid.uuid4()),
#                             main_id=main_id,
#                             quota_id="站场画像-三防安全-" + feat,
#                             quota_name=feat,
#                             score=round(results1['raw_scores'][feat][j], 2),
#                             weight_rate=round(results1['feat_weights'][j], 2),
#                             original_value=round(results1['final_scores'][feat][j], 2),
#                             risk_data="",
#                             quota_level="2",
#                             parent_id="驾驶员画像-三防安全",
#                             creator="system",
#                             create_time=datetime.now(),
#                             updater="system",
#                             update_time=datetime.now(),
#                             deleted="0",
#                             start_time=start_date_,
#                             end_time=start_date_,
#                         )
#                         quota_scores.append(quota_score_3.to_dict())
#                     if profile_main is not None:
#                         main_datas.append(profile_main.to_dict())
#
#                         # 保存驾驶员事故风险数据
#
#                 info = results2['driver_name'].tolist()
#                 for i in range(len(results2['total_score'])):
#                     # if info[i][1]!='63000398':
#                     #     continue
#                     if info[i] in bus_station_ids:
#                         x = bus_station_ids.index(info[i])
#                         main_id = bus_station_profile_main_datas[x]['id']
#                         profile_main = None
#                     quota_score_1 = AbsBusStationQuotaScoreSub(
#                         ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
#                         id=str(uuid.uuid4()),
#                         main_id=main_id,
#                         quota_id="站场画像-消防安全",
#                         quota_name="消防安全",
#                         score=round(results2['total_score'][i], 2),
#                         weight_rate=0.33,
#                         original_value=round(results2['total_score'][i], 2) * 0.33,
#                         risk_data="",
#                         quota_level="1",
#                         parent_id="站场画像",
#                         creator="system",
#                         create_time=datetime.now(),
#                         updater="system",
#                         update_time=datetime.now(),
#                         deleted="0",
#                         start_time=start_date_,
#                         end_time=start_date_,
#                     )
#                     quota_scores.append(quota_score_1.to_dict())
#                     for j, feat in enumerate(results2['final_scores']):
#                         quota_score_3 = AbsBusStationQuotaScoreSub(
#                             ppartition=start_date_str,  # datetime.now().strftime("%Y%m%d"),
#                             id=str(uuid.uuid4()),
#                             main_id=main_id,
#                             quota_id="站场画像-消防安全-" + feat,
#                             quota_name=feat,
#                             score=round(results2['raw_scores'][feat][j], 2),
#                             weight_rate=round(results2['feat_weights'][j], 2),
#                             original_value=round(results2['final_scores'][feat][j], 2),
#                             risk_data="",
#                             quota_level="2",
#                             parent_id="站场画像-消防安全",
#                             creator="system",
#                             create_time=datetime.now(),
#                             updater="system",
#                             update_time=datetime.now(),
#                             deleted="0",
#                             start_time=start_date_,
#                             end_time=start_date_,
#                         )
#                         quota_scores.append(quota_score_3.to_dict())
#                     if profile_main is not None:
#                         main_datas.append(profile_main.to_dict())
#
#                 await crud.BusStation(client).save(main_datas, quota_scores)
#     except Exception as e:
#         print(f"站场画像主程序执行出错: {e}")
#     print("数据库连接已关闭")
# async def prediction():
#     try:
#         async with (await connect_to_clickhouse() as client):
#             """演示三层分数预测"""
#             print("\n" + "=" * 90)
#             print("评分系统")
#             print("=" * 90)
#
#             datas = await crud.BusStation(client).get_ods_jituan_bs_bus_park()
#             data = pd.DataFrame(datas)
#             """演示两层分数预测"""
#             print("\n"+"="*90)
#             print("评分系统")
#             print("="*90)
#
#
#             complaints_cols=[]
#             dim1=[]
#             quota3=await crud.BusStation(client).get_bus_station_quota3('交通安全')
#             for s in quota3:
#                 complaints_cols.append(s['quota_name'])
#             quota2 = await crud.BusStation(client).get_bus_station_quota2('交通安全')
#             for s in quota2:
#                 dim1.append(s['quota_name'])
#             dim_features1={}
#             for s in quota2:
#                 m=[]
#                 for n in quota3:
#                     if n['parent_id']==s['quota_id']:
#                         m.append(n['quota_name'])
#                         dim_features1[s['quota_name']]=m
#
#             # complaints_cols = ['车辆技术', '安全管理', '服务质量']
#             # safe_cols=['安全启动','违规使用N档','全局超速','斑马线超速','斑马线不文明礼让','区间超速','右转弯未刹车','左转弯未刹车']
#             # dim1=['维度1','维度2','维度3']
#             # dim2=['维度1','维度2','维度3']
#             # dim_features1={'维度1':['车辆技术'],'维度2':['安全管理'],'维度3':['服务质量']}
#             # dim_features2={'维度1':['安全启动','违规使用N档','全局超速'],'维度2':['斑马线超速','斑马线不文明礼让','区间超速'],'维度3':['右转弯未刹车','左转弯未刹车']}
#
#             X=data.iloc[:,:4]
#             X1=data.iloc[:, :3].values
#             X2=data.iloc[:,3:11].values
#
#
#             # 预测
#             results1=calculate_two_layer_scores(
#                 X,X1,complaints_cols,dim1,dim_features1
#             )
#             print("\n" + "="*90)
#
#             return results1
#     except Exception as e:
#         print(f"站场画像分数主程序执行出错: {e}")
#         print("数据库连接已关闭")
#
# async def prediction2():
#     try:
#         async with await connect_to_clickhouse() as client:
#             """演示两层分数预测"""
#             print("\n"+"="*90)
#             print("评分系统")
#             print("="*90)
#
#             # 重新加载数据
#             # data=pd.read_csv('alldriver.csv')
#             datas = await crud.BusStation(client).get_ods_jituan_bs_bus_park()
#             data = pd.DataFrame(datas)
#
#             complaints_cols=['场站地势','临水临崖','场地设施','应急设施设备','监控设备']
#             safe_cols=['充电车数','风险隐患','消防水源','消防设备']
#
#             X=data.iloc[:,:4]
#             X1=data.iloc[:, :3].values
#             X2=data.iloc[:,3:11].values
#
#
#             # 预测
#             results1=calculate_two_layer_scores2(
#                 X,X1,complaints_cols
#             )
#
#             results2=calculate_two_layer_scores2(
#                 X,X2,safe_cols
#             )
#             return results1,results2
#     except Exception as e:
#         print(f"驾驶员画像事故风险分数主程序执行出错: {e}")
#     print("数据库连接已关闭")
#
# def calculate_two_layer_scores2(X,X_input,feature_names):
#
#     n_samples=X_input.shape[0]
#     final_scores={}
#     if len(feature_names)==5:
#         weights=[0.2,0.2,0.2,0.2,0.2]
#     else:
#         weights=[0.25,0.25,0.25,0.25]
#
#     raw_scores={}
#     for col in feature_names:
#         raw_scores[col]=np.random.uniform(0,100,n_samples)
#         raw_scores[col]=np.clip(raw_scores[col],0,100)
#
#     for i, col in enumerate(feature_names):
#         final_scores[col]=raw_scores[col]*weights[i]
#
#     total_score=np.zeros(n_samples)
#     for col in feature_names:
#         total_score+=final_scores[col]
#     total_score=np.clip(total_score,0,100)
#
#
#     return {
#         'driver_name':X.iloc[:,0], # 司机名称
#         'driver_id':X.iloc[:,1],  # 司机ID
#         'organ_id':X.iloc[:,2],  # 机构ID
#         'organ_name':X.iloc[:,3],  # 机构名称
#         'final_scores':final_scores,  # 总分细分
#         'raw_scores':raw_scores,  # 原始分
#         'feat_weights':weights,  #  特征权重
#         'total_score':total_score,  # 总分
#     }
# if __name__=="__main__":
#     # 分数预测
#     asyncio.run(bus_station_cores2())
#     # asyncio.run(bus_station_cores())
#     # asyncio.run(prediction())