import pandas as pd

def match_turning_point_data(mileage_accident_table_df, turning_point_table_df, config):
    """
    对线路编号-里程-事故数表增加一列"急转弯点数量"，
    然后把线路编号-里程-事故数的route_name列与线路转弯点统计表的line_name列进行匹配，
    匹配上的，就在线路编号-里程-事故数"急转弯点数量"列里填入线路转弯点统计表里对应的"急转弯点"列值。
    线路编号-里程-事故数的route_name列里没匹配成功的，对应的"急转弯点数量"列里填入0
    """
    # 读取线路编号-里程-事故数表
    mileage_accident_df = mileage_accident_table_df.copy()

    # 检查route_name列是否存在
    if config['route_name_column'] not in mileage_accident_df.columns:
        raise KeyError(f"线路编号-里程-事故数表中不存在列 '{config['route_name_column']}'")

    # 读取线路转弯点统计表
    turning_point_df = turning_point_table_df.copy()

    # 检查line_name和急转弯点列是否存在
    if config['line_name_column'] not in turning_point_df.columns:
        raise KeyError(f"线路转弯点统计表中不存在列 '{config['line_name_column']}'")

    if config['turning_point_column'] not in turning_point_df.columns:
        raise KeyError(f"线路转弯点统计表中不存在列 '{config['turning_point_column']}'")

    # 统一数据类型为字符串
    print(f"\n统一 '{config['route_name_column']}' 和 '{config['line_name_column']}' 列的数据类型为字符串...")

    mileage_accident_df[config['route_name_column']] = mileage_accident_df[config['route_name_column']].astype(str)
    turning_point_df[config['line_name_column']] = turning_point_df[config['line_name_column']].astype(str)

    # 显示前几个值以检查数据
    print(f"\n线路编号-里程-事故数表前5个route_name值:")
    print(mileage_accident_df[config['route_name_column']].head())

    print(f"\n线路转弯点统计表前5个line_name值:")
    print(turning_point_df[config['line_name_column']].head())

    # 创建新的急转弯点数量列并初始化为0
    mileage_accident_df[config['new_turning_point_column']] = 0

    # 建立映射字典
    turning_point_mapping = dict(
        zip(turning_point_df[config['line_name_column']], turning_point_df[config['turning_point_column']]))

    # 根据映射更新急转弯点数量列
    for idx, route_name in enumerate(mileage_accident_df[config['route_name_column']]):
        if route_name in turning_point_mapping:
            mileage_accident_df.at[idx, config['new_turning_point_column']] = turning_point_mapping[route_name]

    # 确保所有未匹配的值都是0
    mileage_accident_df[config['new_turning_point_column']] = mileage_accident_df[
        config['new_turning_point_column']].fillna(0)

    # 统计匹配结果
    total_routes = len(mileage_accident_df)
    matched_routes = (mileage_accident_df[config['new_turning_point_column']] != 0).sum()
    unmatched_routes = total_routes - matched_routes

    print(f"- 总记录数: {total_routes}")
    print(f"- 成功匹配记录数: {matched_routes}")
    print(f"- 未匹配记录数: {unmatched_routes}")

    # 如果匹配失败，检查可能的匹配问题
    if matched_routes == 0:
        print(f"\n所有记录匹配失败，正在检查可能的原因...")

        # 检查是否有完全相同的值
        mileage_set = set(mileage_accident_df[config['route_name_column']].unique())
        turning_point_set = set(turning_point_df[config['line_name_column']].unique())

        common_values = mileage_set.intersection(turning_point_set)
        print(f"完全相同的值数量: {len(common_values)}")

        if len(common_values) > 0:
            print(f"完全相同的值示例: {list(common_values)[:10]}")
        else:
            print("没有完全相同的值")

        # 检查是否有相似值（去除空格等）
        mileage_clean = mileage_accident_df[config['route_name_column']].str.strip()
        turning_point_clean = turning_point_df[config['line_name_column']].str.strip()

        mileage_clean_set = set(mileage_clean.unique())
        turning_point_clean_set = set(turning_point_clean.unique())

        common_clean_values = mileage_clean_set.intersection(turning_point_clean_set)
        print(f"去除空格后的相同值数量: {len(common_clean_values)}")

        if len(common_clean_values) > 0:
            print(f"去除空格后的相同值示例: {list(common_clean_values)[:10]}")

    # 显示匹配后的前几行数据
    print(mileage_accident_df.head(10))

    return mileage_accident_df


async def main(df1, df2):
    # 加载配置
    CONFIG = {
        'route_name_column': 'route_name',  # route_name列名
        'line_name_column': 'line_name',  # line_name列名
        'turning_point_column': '急转弯点',  # 急转弯点列名
        'new_turning_point_column': '急转弯点数量'  # 新增急转弯点数列名
    }
    config = CONFIG

    try:
        # 执行匹配
        result_df = match_turning_point_data(df1, df2, config)

        # 显示匹配结果摘要
        print(f"\n匹配结果摘要:")
        print(f"急转弯点数量匹配成功数量: {result_df[result_df[config['new_turning_point_column']] != 0].shape[0]}")
        print(f"急转弯点数量匹配失败数量: {result_df[result_df[config['new_turning_point_column']] == 0].shape[0]}")
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