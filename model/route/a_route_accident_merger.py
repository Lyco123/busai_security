import pandas as pd

def match_accident_data(mileage_table_df, accident_table_df, config):
    """
    对线路编号-里程文件增加一列"事故数"，
    然后把线路编号-里程的route_name列与线路事故统计表的line_name列进行匹配，
    匹配上的，就在线路编号-里程"事故数"列里填入线路事故统计表里对应的"事故数"列值。
    线路编号-里程的route_name列里没匹配成功的，对应的事故数"列里填入0
    """

    # 读取线路编号-里程表
    mileage_df = mileage_table_df.copy()

    # 检查route_name列是否存在
    if config['route_name_column'] not in mileage_df.columns:
        raise KeyError(f"线路编号-里程表中不存在列 '{config['route_name_column']}'")

    # 读取线路事故统计表
    accident_df = accident_table_df.copy()

    # 检查line_name和事故数列是否存在
    if config['line_name_column'] not in accident_df.columns:
        raise KeyError(f"线路事故统计表中不存在列 '{config['line_name_column']}'")

    if config['accident_count_column'] not in accident_df.columns:
        raise KeyError(f"线路事故统计表中不存在列 '{config['accident_count_column']}'")

    # 统一数据类型为字符串
    print(f"\n统一 '{config['route_name_column']}' 和 '{config['line_name_column']}' 列的数据类型为字符串...")

    mileage_df[config['route_name_column']] = mileage_df[config['route_name_column']].astype(str)
    accident_df[config['line_name_column']] = accident_df[config['line_name_column']].astype(str)

    print(
        f"线路编号-里程表 '{config['route_name_column']}' 列数据类型: {mileage_df[config['route_name_column']].dtype}")
    print(f"线路事故统计表 '{config['line_name_column']}' 列数据类型: {accident_df[config['line_name_column']].dtype}")

    # 显示前几个值以检查数据
    print(f"\n线路编号-里程表前5个route_name值:")
    print(mileage_df[config['route_name_column']].head())

    print(f"\n线路事故统计表前5个line_name值:")
    print(accident_df[config['line_name_column']].head())

    # 创建新的事故数列并初始化为0
    mileage_df[config['new_accident_count_column']] = 0

    # 建立映射字典
    accident_mapping = dict(zip(accident_df[config['line_name_column']], accident_df[config['accident_count_column']]))

    # 根据映射更新事故数列
    for idx, route_name in enumerate(mileage_df[config['route_name_column']]):
        if route_name in accident_mapping:
            mileage_df.at[idx, config['new_accident_count_column']] = accident_mapping[route_name]

    # 确保所有未匹配的值都是0
    mileage_df[config['new_accident_count_column']] = mileage_df[config['new_accident_count_column']].fillna(0)

    # 统计匹配结果
    total_routes = len(mileage_df)
    matched_routes = (mileage_df[config['new_accident_count_column']] != 0).sum()
    unmatched_routes = total_routes - matched_routes

    print(f"- 总记录数: {total_routes}")
    print(f"- 成功匹配记录数: {matched_routes}")
    print(f"- 未匹配记录数: {unmatched_routes}")

    # 如果匹配失败，检查可能的匹配问题
    if matched_routes == 0:
        print(f"\n所有记录匹配失败，正在检查可能的原因...")

        # 检查是否有完全相同的值
        mileage_set = set(mileage_df[config['route_name_column']].unique())
        accident_set = set(accident_df[config['line_name_column']].unique())

        common_values = mileage_set.intersection(accident_set)
        print(f"完全相同的值数量: {len(common_values)}")

        if len(common_values) > 0:
            print(f"完全相同的值示例: {list(common_values)[:10]}")
        else:
            print("没有完全相同的值")

        # 检查是否有相似值（去除空格等）
        mileage_clean = mileage_df[config['route_name_column']].str.strip()
        accident_clean = accident_df[config['line_name_column']].str.strip()

        mileage_clean_set = set(mileage_clean.unique())
        accident_clean_set = set(accident_clean.unique())

        common_clean_values = mileage_clean_set.intersection(accident_clean_set)
        print(f"去除空格后的相同值数量: {len(common_clean_values)}")

        if len(common_clean_values) > 0:
            print(f"去除空格后的相同值示例: {list(common_clean_values)[:10]}")

    return mileage_df


async def main(df1, df2):
    # 加载配置
    CONFIG = {
        'route_name_column': 'route_id',  # route_name列名
        'line_name_column': 'line_code',  # line_name列名
        'accident_count_column': '事故数',  # 事故数列名
        'new_accident_count_column': '事故数'  # 新增事故数列名
    }
    config = CONFIG

    try:
        # 执行匹配
        result_df = match_accident_data(df1, df2, config)

        # 显示匹配结果摘要
        print(f"\n匹配结果摘要:")
        print(f"事故数匹配成功数量: {result_df[result_df[config['new_accident_count_column']] != 0].shape[0]}")
        print(f"事故数匹配失败数量: {result_df[result_df[config['new_accident_count_column']] == 0].shape[0]}")
        return result_df

    except FileNotFoundError as e:
        print(f"错误: 找不到文件 - {str(e)}")
        print("请确保文件路径正确，并且文件存在。")
    except KeyError as e:
        print(f"错误: {str(e)}")
        print("请检查列名是否正确。")
    except Exception as e:
        print(f"处理过程中出现错误: {str(e)}")

if __name__ == "__main__":
    print('1')