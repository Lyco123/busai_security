import asyncio
import os
import uuid
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
import warnings

import application.settings
from model.bus.crud import insert_moudle_log, update_moudle_log
from model.bus.schemas.bus_profile import ObsModuleLog
from model.route.route_black_point_prediction.basic_DBSCAN_model import DBSCAN_predict
from model.route.route_black_point_prediction.black_point_merge_model import merge_close_points
from core.clickhouse_connect import connect_to_clickhouse
from model.route import crud
from model.route.route_black_point_prediction.road_shape_recognition_model import classify_road_shape
from model.route.route_black_point_prediction.black_point_data_preprocessor import clean_behavior_data
from model.route.route_black_point_prediction.output_data_processor import filter_output_black_points
from model.route.route_black_point_prediction.get_cluster_center_point import find_peaks_clustering
from model.route.route_black_point_prediction.get_cluster_center_point import count_cluster_size_nearby
from model.route.route_black_point_prediction.black_point_indicators import result_indicators_analysis

from core.logger import logger
from utils.tools import get_shanghai_time, get_last_month_day

warnings.filterwarnings('ignore')


def black_points_predict_model(df_clean, eps_meter, min_sample, selected_route, selected_type, selected_distance,
                               road_coef, organ_id):
    if df_clean.empty:
        return pd.DataFrame()

    # 先使用非常广泛（也不要太宽泛）DBSCAN的参数进行聚类，分割出不同的小簇,
    labels = DBSCAN_predict(df_clean, int(eps_meter * 10), int(min_sample * 1))

    unique_labels = set(labels)
    peak_points = pd.DataFrame()  # 记录返回值
    for label in unique_labels:
        if label != -1:  # 跳过噪声点label=-1
            cluster_points = df_clean[labels == label]  # 分割出的不同的小簇

            # is_straight = identify_road_shape(cluster_points)  # 判断这个小簇对应的道路线形
            # is_straight = classify_road_shape(cluster_points)  # 判断这个小簇对应的道路线形
            is_straight = True  # 关闭道路线形判断

            # 根据道路线形进行系数修正
            if is_straight:
                cluster_labels = DBSCAN_predict(cluster_points, int(eps_meter * road_coef['straight_coef']['eps_coef']),
                                                int(min_sample * road_coef['straight_coef']['min_sample_coef']))
            else:
                cluster_labels = DBSCAN_predict(cluster_points, int(eps_meter * road_coef['turn_coef']['eps_coef']),
                                                int(min_sample * road_coef['turn_coef']['min_sample_coef']))

            cluster_peak_points = find_peaks_clustering(cluster_points, cluster_labels)  # 得到小簇的行为黑点
            peak_points = pd.concat([peak_points, cluster_peak_points], axis=0, ignore_index=True)

    # 合并相邻黑点，添加route_id、behavior_type字段
    peak_points_merge = merge_close_points(df=peak_points, distance_threshold=selected_distance)

    peak_points_merge['route_id'] = selected_route
    peak_points_merge['report_type'] = selected_type
    peak_points_merge['organ_id'] = organ_id
    output_peak_points = peak_points_merge.copy()
    return output_peak_points


async def behavior_black_main(start_date: str):
    _id = str(uuid.uuid4())
    log_data = ObsModuleLog(
        ppartition=datetime.now().strftime('%Y%m%d'),
        id=_id,
        module_type='黑点',
        module_name='行为黑点',
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

    try:
        async with await connect_to_clickhouse() as client:
            # 这里可以执行数据库操作
            print("线路行为黑点预测 开始时间：" + get_shanghai_time().strftime("%Y-%m-%d %H:%M:%S"))
            logger.info("数据库连接成功")

            min_meter = application.settings.behavior_min_meter  # 最小样本间隔,不同行为类型取值值不同，键表示行为类型（34种），值表示对应类型的最小样本间隔取值
            min_spots_coef = application.settings.min_spots_coef  # 最小样本数系数,键表示行为类型（34种），值表示对应行为类型系数。黑点最小样本数取值=类型样本总数x最小样本数系数
            Min_Behavior_Sample = application.settings.behavior_Min_Behavior_Sample  # 行为黑点的最小违规行为次数
            distance_threshold = application.settings.behavior_distance_threshold  # 黑点合并距离（单位：m）
            max_black_num = application.settings.max_black_num_behavior  # 最大输出黑点数
            max_reject_days = application.settings.max_reject_days_behavior  # 已拒绝黑点不再重复推荐的持续时间

            road_shape_coef = {
                'straight_coef': {'eps_coef': 1, 'min_sample_coef': 1},
                'turn_coef': {'eps_coef': 1, 'min_sample_coef': 1}}  # 直线/曲线道路修正系数

            # 输入数据（驾驶行为表ods_communication_driver_behavior+其他表，以确保有route_id等字段，
            # 例如v_ods_communication_driver_behavior_week_20251231，但最好要有1个月的数据）
            # df = load_behavior_data(file_path='100130_driver_behavior.csv')
            # start_times = ['2025-12-29', '2026-11-08', '2025-12-15', '2025-12-22']
            start_times = [start_date]
            for start_time in start_times:
                # 解析开始日期
                end_date_ = datetime.strptime(start_time, '%Y-%m-%d')
                # 计算结束日期
                start_date_ = get_last_month_day(end_date_)
                end_date_ = end_date_ - timedelta(days=1)
                # end_date_ = start_date_
                start_date_str = start_date_.strftime('%Y%m%d')
                end_date_str = end_date_.strftime('%Y%m%d')

                df = await crud.Route(client).get_black_datas("", start_date_str, end_date_str)
                # df=pd.read_csv('all_data_1_day.csv')
                # datas = await crud.Route(client).get_driver_behavior_route_coordinates()
                # df = pd.DataFrame(df)

                # 基于经纬度数据判断是否有重复
                df = df.drop_duplicates(subset=['longitude', 'latitude', 'route_id', 'report_type'], keep='first')
                type_list = list(min_spots_coef.keys())
                route__list = df['route_id'].unique()
                route_organ_id_dict = df.groupby('route_id')['organ_id'].first().to_dict()

                peak_points_list = []
                from tqdm import tqdm
                for route_id in tqdm(route__list, 'route'):
                    for behavior_type in type_list:
                        df_clean = clean_behavior_data(file_df=df, select_type=behavior_type, select_route=route_id)
                        # print(behavior_type, len(df_clean))

                        if len(df_clean) < Min_Behavior_Sample:
                            # print('行为点数量不足')
                            continue
                        else:
                            min_spots = int(len(df_clean) * min_spots_coef[behavior_type])
                            peak_points = black_points_predict_model(df_clean=df_clean,
                                                                     eps_meter=min_meter[behavior_type],
                                                                     min_sample=min_spots,
                                                                     selected_route=route_id,
                                                                     selected_type=behavior_type,
                                                                     selected_distance=distance_threshold,
                                                                     road_coef=road_shape_coef,
                                                                     organ_id=route_organ_id_dict[route_id])
                            if not peak_points.empty:
                                # per_list, acc_list = result_indicators_analysis(peak_points, df_clean)
                                # peak_points['avg_per_list'] = [per_list] * len(peak_points)
                                # peak_points['avg_acc_list'] = [acc_list] * len(peak_points)
                                peak_points_list.append(peak_points)

                if peak_points_list:
                    black_points = pd.concat(peak_points_list, axis=0, ignore_index=True)
                    black_points = black_points[black_points['cluster_size'] >= Min_Behavior_Sample].reset_index()
                else:
                    black_points = pd.DataFrame()

                # 按簇大小筛选前2n个，靠预测点附近行为数大小筛选前n个
                black_points = black_points.sort_values('cluster_size', ascending=False, ignore_index=True).head(
                    max_black_num * 2)
                black_points = count_cluster_size_nearby(black_points, df, distance_threshold)
                black_points = black_points.sort_values('now_size', ascending=False, ignore_index=True).head(
                    max_black_num)
                black_points['old_size'] = -1
                # black_points.to_csv('beh_output_sample.csv')
                # ee
                # print(black_points.to_string())

                # =========从数据库中取出黑表数据、max_reject_days天内的拒绝数据、还没有接受或不接受的黑点数据，合并为filter_black_point_df=========
                one_month_ago = end_date_ - pd.Timedelta(days=max_reject_days)  # 一个月前的时间点
                end_date_str1 = end_date_.strftime('%Y-%m-%d')
                one_month_ago_str = one_month_ago.strftime('%Y-%m-%d')

                datas = await crud.Route(client).get_black_points_prediction("1", one_month_ago_str, end_date_str1, "1")
                accept_df = pd.DataFrame(datas)

                datas = await crud.Route(client).get_black_points_prediction("2", one_month_ago_str, end_date_str1, "1")
                month_reject_df = pd.DataFrame(datas)

                datas = await crud.Route(client).get_black_points_prediction("0", one_month_ago_str, end_date_str1, "1")
                wait_accept_df = pd.DataFrame(datas)

                # 合并已接受黑点列表数据、1个月内的拒绝黑点数据、还没有接受或不接受的黑点数据
                filter_black_point_df = pd.concat([accept_df, month_reject_df, wait_accept_df], axis=0,
                                                  ignore_index=True)
                # //////////////////////////////////////////////////////////////////////////////////////////////////

                # 过滤掉上述行为黑点
                filtered_black_points = filter_output_black_points(filter_df=filter_black_point_df,
                                                                   new_df=black_points,
                                                                   dist_threshold=distance_threshold)

                # 计算指标情况
                # per_arr = np.array(filtered_black_points['avg_per_list'].tolist())  # 形状 (n, 7)
                # acc_arr = np.array(filtered_black_points['avg_acc_list'].tolist())  # 形状 (n, 7)
                # filtered_black_points = filtered_black_points.drop(columns=['avg_per_list', 'avg_acc_list'])
                # avg_per_list = per_arr.mean(axis=0).tolist()
                # avg_acc_list = acc_arr.mean(axis=0).tolist()
                # new_df = pd.DataFrame({
                #     '---': ['black_num', 'all_acc_num', '500m', '1000m', '1500m', '2000m', '3000m'],
                #     'avg_per_mean(point)': avg_per_list,
                #     'avg_acc_mean(%)': avg_acc_list
                # })
                # new_df = new_df[new_df['---'] != 'all_acc_num']
                # new_df.set_index('---', inplace=True)
                # new_df = new_df.T
                # new_df['black_num'] = len(filtered_black_points)
                # behavior_output_indicators = new_df
                # print(behavior_output_indicators)

                # 更新已有行为黑点近1个月附近发生的违规行为数
                all_beh_black_datas = await crud.Route(client).get_black_points_prediction("1", '', '', "1")
                all_beh_black_df = pd.DataFrame(all_beh_black_datas)
                all_beh_black_df['old_size'] = all_beh_black_df['now_size']
                new_all_beh_black_df = count_cluster_size_nearby(all_beh_black_df, df, distance_threshold)

                if 'latitude' in filtered_black_points:
                    filtered_black_points['latitude'] = pd.to_numeric(filtered_black_points['latitude']).astype(str)
                if 'longitude' in filtered_black_points:
                    filtered_black_points['longitude'] = pd.to_numeric(filtered_black_points['longitude']).astype(str)
                if 'cluster_size' in filtered_black_points:
                    filtered_black_points['cluster_size'] = pd.to_numeric(filtered_black_points['cluster_size']).astype(
                        'int64')
                if 'now_size' in filtered_black_points:
                    filtered_black_points['now_size'] = pd.to_numeric(filtered_black_points['now_size']).astype('int64')
                if 'old_size' in filtered_black_points:
                    filtered_black_points['old_size'] = pd.to_numeric(filtered_black_points['old_size']).astype('int64')
                filtered_black_points['calculate_date'] = end_date_
                filtered_black_points['accept_statu'] = "0"
                filtered_black_points['creator'] = "system"
                filtered_black_points['create_time'] = get_shanghai_time()
                filtered_black_points['updater'] = "system"
                filtered_black_points['update_time'] = get_shanghai_time()
                filtered_black_points['deleted'] = "0"
                filtered_black_points['start_time'] = start_date_
                filtered_black_points['end_time'] = end_date_
                filtered_black_points['black_type'] = "1"

                black_points_dict = filtered_black_points.to_dict('records')
                for b in black_points_dict:
                    b['id'] = str(uuid.uuid4())
                    b.pop('index')
                black_point_datas = black_points_dict

                # 保存行为黑点
                if black_point_datas != []:
                    await crud.Route(client).save_black_points(black_point_datas)
                    print("线路行为黑点预测 结束时间：" + get_shanghai_time().strftime("%Y-%m-%d %H:%M:%S"))

                # 更新已有事故黑点近3个月附近发生的事故数
                if not new_all_beh_black_df.empty:
                    await crud.Route(client).update_black_points(new_all_beh_black_df.to_dict('records'))
                    print("更新已有事故黑点近3个月附近发生的事故数 结束时间：" + get_shanghai_time().strftime(
                        "%Y-%m-%d %H:%M:%S"))


    except Exception as e:
        logger.exception(f"线路事故黑点预测主程序执行出错")  # 等价于logger.exception
        # logger.error("线路行为黑点预测主程序执行出错", exc_info=True)
        print(f"线路事故黑点主程序执行出错: {e}")
    finally:
        import gc
        gc.collect()
    print("数据库连接已关闭")

    remark = '线路行为黑点计算完成'
    await update_moudle_log(_id, remark)


if __name__ == "__main__":
    asyncio.run(behavior_black_main("2026-04-01"))
