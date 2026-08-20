import numpy as np
import pandas as pd


def haversine(lon1, lat1, lon2, lat2):
    R = 6371000
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)
    a = np.sin(delta_phi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c


def _assign_nearest_base(base_lons, base_lats, check_lons, check_lats, base_chunk, check_chunk):
    N = len(base_lons)
    M = len(check_lons)
    min_dist = np.full(M, np.inf, dtype=np.float64)
    min_idx = np.full(M, -1, dtype=np.int64)

    for b_start in range(0, N, base_chunk):
        b_end = min(b_start + base_chunk, N)
        b_lon = base_lons[b_start:b_end].reshape(1, -1)
        b_lat = base_lats[b_start:b_end].reshape(1, -1)

        for c_start in range(0, M, check_chunk):
            c_end = min(c_start + check_chunk, M)
            c_lon = check_lons[c_start:c_end].reshape(-1, 1)
            c_lat = check_lats[c_start:c_end].reshape(-1, 1)

            dists = haversine(b_lon, b_lat, c_lon, c_lat)  # (块检查点数, 块基准点数)

            # 每个检查点在当前基准点块内的最小距离及对应局部索引
            col_min = dists.min(axis=1)  # (check_chunk,)
            col_arg = dists.argmin(axis=1)  # 局部索引
            global_idx = col_arg + b_start  # 转换为全局基准点索引

            # 更新全局最小距离和最近基准点索引
            mask = col_min < min_dist[c_start:c_end]
            min_dist[c_start:c_end][mask] = col_min[mask]
            min_idx[c_start:c_end][mask] = global_idx[mask]

    return min_dist, min_idx


def count_unique_per_base(base_lons, base_lats, check_lons, check_lats, bins, base_chunk=500, check_chunk=500):
    N = len(base_lons)
    M = len(check_lons)
    thresholds = bins[1:]  # 例如 [50, 100, 200, 500]
    K = len(bins)  # 区间个数 = len(thresholds) + 1
    counts = np.zeros((N, K), dtype=np.int64)

    # 1. 为每个检查点找到最近基准点及距离
    min_dist, min_idx = _assign_nearest_base(
        base_lons, base_lats,
        check_lons, check_lats,
        base_chunk=base_chunk,
        check_chunk=check_chunk
    )

    # 2. 按基准点分组，统计累积区间内的点数
    for i in range(N):
        mask = (min_idx == i)
        d = min_dist[mask]
        if len(d) == 0:
            continue

        # 将距离映射到区间索引 (0 ~ K-1)
        bin_idx = np.searchsorted(thresholds, d, side='left')  # side='left' 使 <th 为0
        bc = np.bincount(bin_idx, minlength=K)  # bc[0]: <thresholds[0] 的个数, bc[1]: [th0, th1), ...

        # 转换为累积计数
        if K == 1:  # bins=[0] 无意义，但健壮处理
            continue
        elif K == 2:  # 只有一个阈值，两列：<th 和 >=th
            counts[i, 0] = bc[0]
            counts[i, 1] = bc[1]
        else:
            cum = np.cumsum(bc)
            counts[i, 0] = bc[0]
            # 中间列为累积和，对应 <thresholds[1], <thresholds[2], ...
            counts[i, 1:-1] = cum[1:-1]
            counts[i, -1] = bc[-1]  # >= 最后一个阈值

    return counts


def base_centric_match_summary(df_pred, df_acc, bins):
    if bins[0] != 0:
        raise ValueError("bins 必须以 0 开头，例如 [0, 50, 100, 200, 500]")

    base_lons = df_pred['longitude'].values
    base_lats = df_pred['latitude'].values
    N = len(base_lons)

    # 自动生成标签（代表 <threshold 的列名）
    thresholds = bins[1:]
    labels = [f"{th}m" for th in thresholds]
    if len(labels) != len(bins) - 1:
        raise ValueError("labels 长度必须等于 len(bins)-1")

    summary_data = []
    details_dict = {}

    check_lons = df_acc['longitude'].values
    check_lats = df_acc['latitude'].values

    # 计算唯一匹配矩阵（每基准点各区间点数）
    counts = count_unique_per_base(
        base_lons, base_lats,
        check_lons, check_lats,
        bins
    )

    df_detail2 = pd.DataFrame()
    df_detail2['基准点序号'] = np.arange(1, N + 1)
    df_detail2['longitude'] = base_lons
    df_detail2['latitude'] = base_lats
    for j, lab in enumerate(labels):
        df_detail2[lab] = (counts[:, j] != 0).astype(int)
    df_detail2['总匹配数'] = counts.sum(axis=1)
    details_dict['fpath'] = df_detail2

    # --- 汇总信息（由于已去重，直接求和即可得到唯一匹配点总数） ---
    total_in_check = len(check_lons)
    row = {
        # 'file': idx,
        'acc_num': total_in_check,
        'black': N,
    }
    for j, lab in enumerate(labels):
        row[f'{lab}'] = int(counts[:, j].sum())
    summary_data.append(row)

    df_summary = pd.DataFrame(summary_data)
    return df_summary, details_dict


def show_average_per_base(df, black_col='black', acc_col='acc_num', the_type='', value_cols=None) -> pd.DataFrame:
    if value_cols is None:
        # 自动识别：既非 file_col 也非 black_col，且是数值类型（排除像“基准点平均匹配数”这样的文本列）
        excluded = {black_col, acc_col}
        value_cols = [c for c in df.columns if c not in excluded and np.issubdtype(df[c].dtype, np.number)]

    df_avg = df[[black_col, acc_col]].copy()
    for col in value_cols:
        if the_type == '平均黑点覆盖事故数':
            df_avg[col] = df[col] / df[black_col]
        else:
            df_avg[col] = df[col] / df[acc_col]
    return df_avg


def result_indicators_analysis(pred_df, true_acc_df):
    all_data = []  # 存储所有参与输出的数值行
    all_data2 = []  # 存储所有参与输出的数值行
    distance_bins = [0, 500, 1000, 1500, 2000, 3000]  # 区间边界
    total_correct = {'500m': 0, '1000m': 0, '1500m': 0, '2000m': 0, '3000m': 0}
    total_samples = 0  # 累计总行数

    df_sum, dict_details = base_centric_match_summary(df_pred=pred_df, df_acc=true_acc_df, bins=distance_bins)

    df_avg = show_average_per_base(df=df_sum, the_type='平均黑点覆盖事故数')
    sub_df = df_avg[['black', 'acc_num', '500m', '1000m', '1500m', '2000m', '3000m']]
    all_data.append(sub_df)  # 只保留数值列

    df_avg2 = show_average_per_base(df_sum, the_type='覆盖率')
    sub_df2 = df_avg2[['black', 'acc_num', '500m', '1000m', '1500m', '2000m', '3000m']]
    all_data2.append(sub_df2)  # 只保留数值列

    for _, df_det in dict_details.items():
        # 累加每个距离范围的正确数（1 的个数）
        for dist in total_correct.keys():
            total_correct[dist] += df_det[dist].sum()  # 直接对列求和（0/1）
        total_samples += len(df_det)  # 累计总行数

    # 循环结束后，计算全部数值列的平均值并输出一行

    # 平均黑点覆盖事故数
    avg_row = pd.concat(all_data).mean().to_frame().T

    # 黑点覆盖率
    avg_row2 = pd.concat(all_data2).mean().to_frame().T
    avg_row2 = avg_row2[['500m', '1000m', '1500m', '2000m', '3000m']] * 100
    avg_row2 = avg_row2.round(2)

    # 精确率
    out_list = []
    for dist in total_correct.keys():
        accuracy = total_correct[dist] / total_samples if total_samples > 0 else 0
        out_list.append((round(accuracy * 100, 2)))
    new_row_df = pd.DataFrame([out_list], columns=avg_row2.columns)

    # print(avg_row.to_string(index=False, header=False, float_format='%.2f'), end=" ")
    # print(avg_row2.to_string(index=False, header=False, float_format='%.2f'), end=" ")
    # print(new_row_df.to_string(index=False, header=False, float_format='%.2f'))

    # result_indicators = pd.concat([avg_row, avg_row2, new_row_df], ignore_index=True)
    # result_indicators = result_indicators.ffill()
    # result_indicators.insert(loc=0, column='indicators', value=['平均黑点覆盖事故数', '覆盖率', '准确率'])
    result_indicators = pd.concat([avg_row, new_row_df], ignore_index=True)
    result_indicators = result_indicators.ffill()
    list1, list2 = result_indicators.values.tolist()
    return list1, list2


if __name__ == "__main__":
    # pred_df = pd.read_csv('4month_data/acc_month1.csvout.csv')
    # true_acc_df = pd.read_csv('4month_data/acc_month1.csv')
    # ddd = accident_result_analysis(pred_df=pred_df, true_acc_df=true_acc_df)
    # print(ddd.to_string())
    pass
