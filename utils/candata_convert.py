import time

import pandas as pd
import numpy as np
import json

# =======================================================
# 自定义函数：统计开启次数 (0->1)
# =======================================================
def count_actions(series):
    s = series.dropna()
    if len(s) < 2: return 0
    return (s.diff() == 1).sum()

async def data_convert(datas):
    # =======================================================
    # 1. 读取与清洗
    # =======================================================
    print("1. 读取数据...")
    # df = pd.read_csv('can_infos.csv')
    # df=pd.read_json(json.dumps(datas, ensure_ascii=False, indent=2)
    df = pd.DataFrame(datas)
    df['value']=pd.to_numeric(df['value'])
    df['data_time'] = pd.to_datetime(df['data_time'])

    # 日期
    start_date = '2025-11-30'
    end_date = '2025-12-31'

    # 1. 读取数据
    # 记录开始时间
    start_time = time.time()
    # df = pd.read_csv(input_file,
    #                  usecols=['obuid', 'id', 'value', 'report_time', 'insert_time', 'ppartition', 'data_time'],
    #                  dtype={'id': 'category', 'obuid': 'category', 'ppartition': 'category'})

    # 配置参数
    specified_ids = ['D129', 'D130', 'D30', 'D31', 'D34', 'D35', 'D47', 'D48']
    ids_max = ['D15', 'D26', 'D30', 'D34', 'D47', 'D48', 'D61', 'D71', 'D77', 'D84',
               'D98', 'D101', 'D107', 'D110', 'D113', 'D187']
    ids_min = ['D31', 'D35']
    ids_first = ['D129', 'D130']

    # 合并所有需要处理的ID
    required_ids = set(specified_ids + ids_max + ids_min + ids_first)

    # 定义聚合方式
    agg_methods = {}
    for id_val in required_ids:
        if id_val in ids_first:
            agg_methods[id_val] = 'first'
        elif id_val in ids_max:
            agg_methods[id_val] = 'max'
        elif id_val in ids_min:
            agg_methods[id_val] = 'min'
        else:
            agg_methods[id_val] = 'max'

    # 2. 只保留需要的ID
    df = df[df['id'].isin(required_ids)].copy()

    # 3. 时间转换和筛选
    df['report_time'] = pd.to_datetime(df['report_time'])
    df['insert_time'] = pd.to_datetime(df['insert_time'])
    df['data_time'] = pd.to_datetime(df['data_time'])

    df = df[(df['report_time'] >= start_date) & (df['report_time'] < end_date)].copy()

    if len(df) == 0:
        result = pd.DataFrame(columns=['obuid', 'data_start_time', 'data_end_time', 'data_duration_minutes',
                                       'report_time', 'insert_time', 'ppartition'] + list(required_ids))
        result.to_csv('非业务代码/零部件数据对接/can_stats_result.csv', index=False, encoding='utf-8-sig')
        print(f"处理完成，无数据")
        exit()

    # 4. 日期修正
    def correct_dates_vectorized(df):
        data_dates = df['data_time'].dt.date
        report_dates = df['report_time'].dt.date
        mask = data_dates != report_dates
        if mask.any():
            df.loc[mask, 'corrected_data_time'] = pd.to_datetime(
                report_dates[mask].astype(str) + ' ' + df.loc[mask, 'data_time'].dt.time.astype(str)
            )
        else:
            df['corrected_data_time'] = df['data_time']
        return df

    df = correct_dates_vectorized(df)

    # 5. 获取时间统计
    data_start_time = df['corrected_data_time'].min()
    data_end_time = df['corrected_data_time'].max()
    data_duration_minutes = (data_end_time - data_start_time).total_seconds() / 60
    original_report_start = df['report_time'].min()

    # 6. 数据清洗
    voltage_ids = {'D30', 'D31', 'D47'}
    temp_ids = {'D34', 'D35', 'D48'}
    fault_ids = {'D15', 'D26', 'D61', 'D71', 'D77', 'D84', 'D98', 'D101', 'D107', 'D110', 'D113', 'D187'}
    fixed_ids = {'D129', 'D130'}

    clean_values = {}
    for id_val in required_ids:
        id_mask = df['id'] == id_val
        if id_mask.any():
            id_values = df.loc[id_mask, 'value'].values
            if id_val in voltage_ids:
                cleaned = id_values[(id_values >= 1) & (id_values <= 5)]
            elif id_val in temp_ids:
                cleaned = id_values[(id_values >= -40) & (id_values <= 120)]
            elif id_val in fault_ids:
                cleaned = id_values[(id_values >= 0) & (id_values <= 255)]
            elif id_val in fixed_ids:
                cleaned = id_values[id_values >= 0]
            else:
                cleaned = id_values

            if len(cleaned) > 0:
                clean_values[id_val] = cleaned

    # 7. 聚合
    result_data = {}
    for id_val in required_ids:
        if id_val in clean_values:
            values = clean_values[id_val]
            agg_method = agg_methods[id_val]

            if agg_method == 'first':
                result_data[id_val] = values[0] if len(values) > 0 else np.nan
            elif agg_method == 'max':
                result_data[id_val] = np.max(values)
            elif agg_method == 'min':
                result_data[id_val] = np.min(values)
        else:
            result_data[id_val] = np.nan

    # 8. 创建结果
    result = pd.DataFrame([result_data])

    # 添加固定列
    latest_idx = df['insert_time'].idxmax()
    metadata = df.loc[latest_idx]

    result.insert(0, 'obuid', metadata.get('obuid', np.nan))
    result.insert(1, 'data_start_time', data_start_time)
    result.insert(2, 'data_end_time', data_end_time)
    result.insert(3, 'data_duration_minutes', data_duration_minutes)
    result.insert(4, 'report_time', original_report_start)
    result.insert(5, 'insert_time', metadata.get('insert_time', np.nan))
    result.insert(6, 'ppartition', metadata.get('ppartition', np.nan))

    # 9. 列排序
    fixed_cols = ['obuid', 'data_start_time', 'data_end_time', 'data_duration_minutes',
                  'report_time', 'insert_time', 'ppartition']
    data_cols = sorted([col for col in result.columns if col not in fixed_cols],
                       key=lambda x: (0, int(x[1:])) if x.startswith('D') and x[1:].isdigit() else (1, x))

    result = result[fixed_cols + data_cols]

    # result['data_time'] = pd.to_datetime(result['data_time'])
    # result['report_time'] = pd.to_datetime(result['report_time'])
    # result['insert_time'] = pd.to_datetime(result['insert_time'])

    return result


async def data_convert_new(datas):
    # =======================================================
    # 1. 配置参数
    # =======================================================
    # 保留的ID列表（根据配置表，只保留处理方式为“保留”的ID）
    ids_to_keep = [
        'D6', 'D15', 'D26', 'D28', 'D29', 'D30', 'D31', 'D34', 'D35',
        'D42', 'D44', 'D47', 'D48', 'D52', 'D53', 'D54', 'D55', 'D56', 'D59',
        'D61', 'D62', 'D63', 'D64', 'D65', 'D66', 'D71', 'D73', 'D74', 'D77',
        'D82', 'D83', 'D84', 'D98', 'D99', 'D100', 'D101', 'D102', 'D103',
        'D105', 'D106', 'D107', 'D110', 'D113', 'D129', 'D130'
    ]

    # 聚合规则定义，根据配置表的“聚合方式”设置
    ids_first = ['D129', 'D130']  # 固定信息类 -> first
    ids_max = [
        'D15', 'D26', 'D30', 'D34', 'D47', 'D48', 'D61', 'D71', 'D77', 'D84',
        'D98', 'D101', 'D107', 'D110', 'D113'
    ]  # 故障类和最大值类 -> max
    ids_min = ['D31', 'D35']  # 最小值类 -> min
    # 其余保留的ID默认为mean（数值监控类）

    # 通用无效值列表，用于数据清洗
    invalid_values = [
        4294967296.0, 4294967295.0, 65535, 65534, 255, 254, 125,  # 8-bit, 16-bit, 32-bit
        99999, 999999, 99999999, 99999999.0, 2147483647.0, 2147483648.0  # 其他占位符
    ]

    # =======================================================
    # 2. 数据读取与预处理
    # =======================================================
    print("读取数据...")
    # 读取原始数据
    df = pd.DataFrame(datas)
    df['value']=pd.to_numeric(df['value'])
    # 将时间列转换为datetime格式，便于后续时间过滤和重采样
    df['data_time'] = pd.to_datetime(df['data_time'])

    # 根据日期范围筛选数据（2025-11-30 至 2025-12-31）
    start_date = '2025-11-30'
    end_date = '2025-12-31'
    mask = (df['report_time'] >= start_date) & (df['report_time'] < end_date)
    df = df[mask].copy()

    # 只保留配置表中“处理方式”为“保留”的ID
    df = df[df['id'].isin(ids_to_keep)]

    # =======================================================
    # 3. 智能数据清洗
    # =======================================================
    print("数据清洗...")

    def clean_value_by_id(id_val, value):
        """
        根据ID类型对数值进行清洗，去除无效值并设置合理范围

        参数:
            id_val: ID名称，如'D30'
            value: 原始数值

        返回:
            清洗后的数值，超出合理范围或无效值将返回NaN
        """
        # 如果是NaN或通用无效值，直接返回NaN
        if pd.isna(value) or value in invalid_values:
            return np.nan

        # 单体电压 (D30, D31, D47) - 锂电池单体电压合理范围2.0-4.5V
        if id_val in ['D30', 'D31', 'D47']:
            return value if 2.0 <= value <= 4.5 else np.nan

        # 温度相关ID - 合理温度范围-40°C到120°C
        elif id_val in ['D34', 'D35', 'D48', 'D59', 'D64', 'D65', 'D83', 'D89', 'D91', 'D100', 'D106']:
            return value if -40 <= value <= 120 else np.nan

        # 总电压相关ID - 合理电压范围0-1000V
        elif id_val in ['D28', 'D42', 'D56', 'D66']:
            return value if 0 <= value <= 1000 else np.nan

        # 电流相关ID - 合理电流范围-500A到500A
        elif id_val in ['D29', 'D44']:
            return value if -500 <= value <= 500 else np.nan

        # 轮胎压力相关ID - 合理压力范围0-1500kPa
        elif id_val in ['D82', 'D102', 'D103']:
            return value if 0 <= value <= 1500 else np.nan

        # 转速相关ID - 合理转速范围0-20000rpm
        elif id_val in ['D52', 'D62', 'D99', 'D105']:
            return value if 0 <= value <= 20000 else np.nan

        # 转矩相关ID - 合理转矩范围-2000Nm到2000Nm
        elif id_val in ['D53', 'D63']:
            return value if -2000 <= value <= 2000 else np.nan

        # 车速 (D6) - 合理车速范围0-200km/h
        elif id_val == 'D6':
            return value if 0 <= value <= 200 else np.nan

        # 踏板开度 (D73, D74) - 合理百分比范围0-100%
        elif id_val in ['D73', 'D74']:
            return value if 0 <= value <= 100 else np.nan

        # 故障码/状态码相关ID - 合理范围0-255
        elif id_val in ['D15', 'D26', 'D61', 'D71', 'D77', 'D84', 'D98', 'D101', 'D107', 'D110', 'D113']:
            return value if 0 <= value <= 255 else np.nan

        # 固定信息 (D129, D130) - 应为非负值
        elif id_val in ['D129', 'D130']:
            return value if value >= 0 else np.nan

        # 其他ID，不进行范围限制，只清洗通用无效值
        else:
            return value

    # 应用清洗函数，逐行清洗数据
    df['value'] = df.apply(lambda row: clean_value_by_id(row['id'], row['value']), axis=1)

    # 确保所有配置的ID都出现在数据中，即使清洗后全为NaN
    # 这是为了保证输出结果包含所有预期的列
    for id in ids_to_keep:
        if id not in df['id'].values or df[df['id'] == id]['value'].notna().sum() == 0:
            # 创建占位行，确保该ID在透视表中出现
            sample_row = df.iloc[0].copy() if len(df) > 0 else pd.Series()
            sample_row['id'] = id
            sample_row['value'] = np.nan
            sample_row['data_time'] = df['data_time'].min() if len(df) > 0 else pd.Timestamp.now()
            df = pd.concat([df, pd.DataFrame([sample_row])], ignore_index=True)

    # =======================================================
    # 4. 数据聚合
    # =======================================================
    print("数据聚合...")

    # 创建数据透视表，将长表转换为宽表，每个ID为一列
    pivot_df = df.pivot_table(index='data_time', columns='id', values='value', aggfunc='first')

    # 再次确保所有配置的ID都在透视表中（双重检查）
    for id in ids_to_keep:
        if id not in pivot_df.columns:
            pivot_df[id] = np.nan

    # 根据配置表的聚合规则，为每个ID设置聚合函数
    agg_rules = {}
    for col in pivot_df.columns:
        if col in ids_first:
            agg_rules[col] = 'first'
        elif col in ids_max:
            agg_rules[col] = 'max'
        elif col in ids_min:
            agg_rules[col] = 'min'
        else:
            agg_rules[col] = 'mean'

    # 按5分钟频率重采样并应用聚合规则
    resampled = pivot_df.resample('5min').agg(agg_rules)

    # 元数据聚合：获取每个5分钟时间窗口的第一个obuid和report_time
    if 'obuid' in df.columns and 'report_time' in df.columns:
        meta_df = df.groupby(pd.Grouper(key='data_time', freq='5min')).agg({
            'ppartition': 'first',
            'obuid': 'first',
            'report_time': 'first',
            'insert_time': 'first',
        })
    else:
        # 如果数据中没有元数据列，创建空的DataFrame
        meta_df = pd.DataFrame(index=resampled.index)
        meta_df['ppartition'] =np.nan
        meta_df['obuid'] = np.nan
        meta_df['report_time'] = np.nan
        meta_df['insert_time'] = np.nan

    # 合并元数据和聚合数据
    result = pd.concat([meta_df, resampled], axis=1).reset_index()

    # 重命名索引列为data_time
    if 'index' in result.columns:
        result = result.rename(columns={'index': 'data_time'})

    # =======================================================
    # 5. 列排序与输出
    # =======================================================
    # 确定固定列的顺序
    fixed_cols = ['ppartition','obuid', 'data_time', 'report_time','insert_time'] if all(
        col in result.columns for col in ['ppartition','obuid', 'data_time', 'report_time','insert_time']) else ['data_time']

    # 获取数据列（非固定列）
    data_cols = [col for col in result.columns if col not in fixed_cols]

    def sort_key(col):
        """
        排序函数，用于对D列按数字大小排序
        """
        if isinstance(col, str) and col.startswith('D') and col[1:].isdigit():
            return (0, int(col[1:]))
        return (1, col)

    # 对数据列进行排序
    data_cols.sort(key=sort_key)

    # 按固定列在前，数据列在后的顺序重新排列列
    result = result[fixed_cols + data_cols]

    result['data_time'] = pd.to_datetime(result['data_time'])
    result['report_time'] = pd.to_datetime(result['report_time'])
    result['insert_time'] = pd.to_datetime(result['insert_time'])

    return result
    # # 输出到CSV文件
    # output_file = 'can_stats_result.csv'
    # result.to_csv(output_file, index=False, encoding='utf-8-sig', na_rep='NaN')
    #
    # print(f"处理完成！输出文件: {output_file}")
    # print(f"结果形状: {result.shape}")


if __name__ == "__main__":
    data_convert(None)