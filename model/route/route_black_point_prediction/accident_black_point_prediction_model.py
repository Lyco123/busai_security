import asyncio
import os
import uuid
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
import warnings

from model.bus.crud import insert_moudle_log, update_moudle_log
from model.bus.schemas.bus_profile import ObsModuleLog
from model.route.route_black_point_prediction.basic_DBSCAN_model import DBSCAN_predict_with_weight
from model.route.route_black_point_prediction.black_point_merge_model import merge_close_points
from core.clickhouse_connect import connect_to_clickhouse
from model.route import crud
from model.route.route_black_point_prediction.road_shape_recognition_model import classify_road_shape
from model.route.route_black_point_prediction.black_point_data_preprocessor import clean_accident_data
from model.route.route_black_point_prediction.black_point_data_preprocessor import clean_behavior_data_with_weight
from model.route.route_black_point_prediction.black_point_data_preprocessor import add_accident_types
from model.route.route_black_point_prediction.output_data_processor import filter_output_black_points
from model.route.route_black_point_prediction.get_cluster_center_point import find_peaks_clustering_with_weight
from model.route.route_black_point_prediction.get_cluster_center_point import count_acc_cluster_size_nearby
from model.route.route_black_point_prediction.black_point_indicators import result_indicators_analysis
from core.logger import logger
from utils.tools import get_shanghai_time, get_last_month_day
import application.settings

warnings.filterwarnings('ignore')


def black_points_predict_model(df_clean, eps_meter, min_sample, selected_route, selected_type, selected_distance,
                               road_coef, organ_id):
    if df_clean.empty:
        return pd.DataFrame()
    # 判断道路线形
    # print("0", get_shanghai_time().strftime("%Y-%m-%d %H:%M:%S.%f"))
    # is_straight = classify_road_shape(df_clean)
    is_straight = True
    # 根据道路线形进行系数修正
    if is_straight:
        labels = DBSCAN_predict_with_weight(df_clean, int(eps_meter * road_coef['straight_coef']['eps_coef']),
                                            int(min_sample * road_coef['straight_coef']['min_sample_coef']))
    else:
        labels = DBSCAN_predict_with_weight(df_clean, int(eps_meter * road_coef['turn_coef']['eps_coef']),
                                            int(min_sample * road_coef['turn_coef']['min_sample_coef']))
    peak_points = find_peaks_clustering_with_weight(df_clean, labels)  # 得到小簇的行为黑点
    # 合并相邻黑点
    peak_points_merge = merge_close_points(df=peak_points, distance_threshold=selected_distance)
    # 添加route_id、behavior_type、organ_id字段
    peak_points_merge['route_id'] = selected_route
    peak_points_merge['report_type'] = selected_type
    peak_points_merge['organ_id'] = organ_id
    output_peak_points = peak_points_merge.copy()
    return output_peak_points


async def accident_black_main(start_date: str):
    _id = str(uuid.uuid4())
    log_data = ObsModuleLog(
        ppartition=datetime.now().strftime('%Y%m%d'),
        id=_id,
        module_type='黑点',
        module_name='事故黑点',
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
            print("线路事故黑点预测 开始时间：" + get_shanghai_time().strftime("%Y-%m-%d %H:%M:%S"))
            logger.info("数据库连接成功")

            min_meter = application.settings.acc_min_meter  # 最小样本间隔
            min_spot = application.settings.acc_min_spot  # 最小样本数
            distance_threshold = application.settings.acc_distance_threshold  # 黑点合并距离（单位：m）
            behavior_coef = application.settings.acc_behavior_coef  # 等效事故权重
            max_black_num = application.settings.max_black_num_acc  # 最大输出黑点数
            max_reject_days = application.settings.max_reject_days_acc  # 已拒绝黑点不再重复推荐的持续时间

            road_shape_coef = {
                'straight_coef': {'eps_coef': 1, 'min_sample_coef': 1},
                'turn_coef': {'eps_coef': 1, 'min_sample_coef': 1}}  # 直线/曲线道路修正系数

            start_times = [start_date]
            for start_time in start_times:
                # 解析结束日期
                end_date_ = datetime.strptime(start_time, '%Y-%m-%d')
                # 计算开始日期
                start_date_ = get_last_month_day(end_date_)
                end_date_ = end_date_ - timedelta(days=1)
                start_date_str = start_date_.strftime('%Y%m%d')
                end_date_str = end_date_.strftime('%Y%m%d')

                n = 3  # 需要3个月前的起始时间节点
                year = start_date_.year
                month = start_date_.month
                total_months = year * 12 + month - n  # 计算总月份数并减去 n
                new_year = total_months // 12
                new_month = total_months % 12 + 1
                new_start_date_ = datetime(new_year, new_month, 1)  # 月初固定为1号
                new_start_date_str = new_start_date_.strftime('%Y%m%d')  # 月初固定为1号

                # 输入数据（集团事故数据(带经纬度位置)
                df = await crud.Route(client).get_accident_data("", new_start_date_str, end_date_str)
                df = add_accident_types(df)
                df['weight'] = 1
                type_list = list(min_spot.keys())
                route__list = df['route_id'].unique()
                route_organ_id_dict = df.groupby('route_id')['organ_id'].first().to_dict()

                # 输入违规行为数据
                df_behavior = await crud.Route(client).get_black_datas("", start_date_str, end_date_str)
                df_behavior = pd.DataFrame(df_behavior)

                data_for_test = {}
                db_weight = await crud.Route(client).get_weigths_datas("", start_date_str, end_date_str)
                weight_rate = []
                behavior_type_code = []
                for weight in db_weight:
                    weight_rate.append(float(weight['weight_rate']))
                    behavior_type_code.append(weight['behavior_type_code'])
                data_for_test['weight_rate'] = weight_rate
                data_for_test['behavior_type_code'] = behavior_type_code
                df_weight = pd.DataFrame(data_for_test)

                total = df_weight['weight_rate'].sum()
                if total != 0:  # 避免除以 0
                    df_weight['weight'] = df_weight['weight_rate'] / total  # 归一化到 [0,1]，总和为1
                else:
                    df_weight['weight'] = 0
                df_behavior = df_behavior.merge(df_weight, left_on='report_type', right_on='behavior_type_code',
                                                how='left')
                pd.set_option('display.max_columns', None)
                df_behavior['weight'] = df_behavior['weight'].fillna(0)  # 将缺失的权重填充为 0

                type_coef = {}
                for i in [1, 2, 3, 4]:
                    temp_df = df[df['accident_types'].apply(lambda x: i in x)]
                    type_coef[i] = len(temp_df) / len(df) / behavior_coef

                peak_points_list = []
                from tqdm import tqdm
                for route_id in tqdm(route__list, 'route'):
                    for accident_type in type_list:
                        df1 = clean_accident_data(file_df=df, select_type=accident_type, select_route=route_id)
                        df2 = clean_behavior_data_with_weight(file_df=df_behavior, select_route=route_id,
                                                              coef=type_coef[accident_type])
                        df_clean = pd.concat([df1, df2], axis=0, ignore_index=True)
                        # print(accident_type, len(df_clean))

                        if len(df_clean) < 2:
                            continue
                        else:
                            min_spots = min_spot[accident_type]
                            peak_points = black_points_predict_model(df_clean=df_clean,
                                                                     eps_meter=min_meter[accident_type],
                                                                     min_sample=min_spots,
                                                                     selected_route=route_id,
                                                                     selected_type=accident_type,
                                                                     selected_distance=distance_threshold,
                                                                     road_coef=road_shape_coef,
                                                                     organ_id=route_organ_id_dict[route_id]
                                                                     )
                            if not peak_points.empty:
                                # per_list, acc_list = result_indicators_analysis(peak_points, df1)
                                # peak_points['avg_per_list'] = [per_list] * len(peak_points)
                                # peak_points['avg_acc_list'] = [acc_list] * len(peak_points)
                                peak_points_list.append(peak_points)
                if peak_points_list:
                    black_points = pd.concat(peak_points_list, axis=0, ignore_index=True)
                else:
                    black_points = pd.DataFrame()

                # 按簇大小筛选前2n个，靠预测点附近事故数大小筛选前n个
                black_points = black_points.sort_values('cluster_size', ascending=False, ignore_index=True).head(
                    max_black_num * 2)
                black_points = count_acc_cluster_size_nearby(black_points, df, distance_threshold)
                black_points = black_points.sort_values('now_size', ascending=False, ignore_index=True).head(
                    max_black_num)
                black_points['old_size'] = -1
                # black_points.to_csv('acc_output.csv')
                # ee
                # print(black_points.to_string())

                # =========从数据库中取出黑表数据、max_reject_days天内的拒绝数据、还没有接受或不接受的黑点数据，合并为filter_black_point_df=========
                one_month_ago = end_date_ - pd.Timedelta(days=max_reject_days)  # 一个月前的时间点
                end_date_str1 = end_date_.strftime('%Y-%m-%d')
                one_month_ago_str = one_month_ago.strftime('%Y-%m-%d')

                datas = await crud.Route(client).get_black_points_prediction("1", one_month_ago_str, end_date_str1, "2")
                accept_df = pd.DataFrame(datas)

                datas = await crud.Route(client).get_black_points_prediction("2", one_month_ago_str, end_date_str1, "2")
                month_reject_df = pd.DataFrame(datas)

                datas = await crud.Route(client).get_black_points_prediction("0", one_month_ago_str, end_date_str1, "2")
                wait_accept_df = pd.DataFrame(datas)

                # 合并黑点列表数据和1个月内的拒绝数据
                filter_black_point_df = pd.concat([accept_df, month_reject_df, wait_accept_df], axis=0,
                                                  ignore_index=True)
                # //////////////////////////////////////////////////////////////////////////////////////////////////

                # 过滤掉上述事故黑点
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
                #     'avg_acc_mean(%)': avg_acc_list,
                # })
                # new_df = new_df[new_df['---'] != 'all_acc_num']
                # new_df.set_index('---', inplace=True)
                # new_df = new_df.T
                # new_df['black_num'] = len(filtered_black_points)
                # acc_output_indicators = new_df
                # print(acc_output_indicators)

                # 更新已有事故黑点近3个月附近发生的事故数
                all_acc_black_datas = await crud.Route(client).get_black_points_prediction("1", '', '', "2")
                all_acc_black_df = pd.DataFrame(all_acc_black_datas)
                all_acc_black_df['old_size'] = all_acc_black_df['now_size']
                new_all_acc_black_df = count_acc_cluster_size_nearby(all_acc_black_df, df, distance_threshold)


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
                filtered_black_points['start_time'] = new_start_date_
                filtered_black_points['end_time'] = end_date_
                filtered_black_points['black_type'] = "2"

                black_points_dict = filtered_black_points.to_dict('records')
                for b in black_points_dict:
                    b['id'] = str(uuid.uuid4())
                black_point_datas = black_points_dict

                # 保存事故黑点
                if black_point_datas != []:
                    await crud.Route(client).save_black_points(black_point_datas)
                    print("线路事故黑点预测 结束时间：" + get_shanghai_time().strftime("%Y-%m-%d %H:%M:%S"))

                #更新已有事故黑点近3个月附近发生的事故数
                if not new_all_acc_black_df.empty:
                    await crud.Route(client).update_black_points(new_all_acc_black_df.to_dict('records'))
                    print("更新已有事故黑点近3个月附近发生的事故数 结束时间：" + get_shanghai_time().strftime("%Y-%m-%d %H:%M:%S"))


    except Exception as e:
        logger.exception(f"线路事故黑点预测主程序执行出错")  # 等价于logger.exception
        logger.error(f"线路事故黑点预测主程序执行出错:{e}", exc_info=True)
        print(f"线路事故黑点预测: {e}")
    finally:
        import gc
        gc.collect()
    print("数据库连接已关闭")

    remark = '线路事故黑点计算完成'
    await update_moudle_log(_id, remark)


if __name__ == "__main__":
    asyncio.run(accident_black_main("2026-05-01"))
