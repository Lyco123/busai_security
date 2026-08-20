import pandas as pd


def merge_line_features_with_water_road(feature_df, water_road_df, config):
    """
    将线路特征表和线路临水临崖数量表进行匹配合并
    """
    # 获取配置参数
    feature_route_col = config['feature_route_column']
    water_road_route_col = config['water_road_route_column']
    water_road_count_col = config['water_road_count_column']
    new_column_name = config['new_column_name']

    # 数据清洗：去除列名和内容的空格
    feature_df.columns = feature_df.columns.str.strip()
    water_road_df.columns = water_road_df.columns.str.strip()

    # 检查列是否存在
    if feature_route_col not in feature_df.columns:
        raise ValueError(f"线路特征表中不包含 '{feature_route_col}' 列。当前列: {list(feature_df.columns)}")
    if water_road_route_col not in water_road_df.columns:
        raise ValueError(f"临水临崖数量表中不包含 '{water_road_route_col}' 列。当前列: {list(water_road_df.columns)}")
    if water_road_count_col not in water_road_df.columns:
        raise ValueError(f"临水临崖数量表中不包含 '{water_road_count_col}' 列。当前列: {list(water_road_df.columns)}")

    # 1. 删除线路特征表中原有的 '临水临崖数量' 列
    original_count = len(feature_df)
    if new_column_name in feature_df.columns:
        print(f"删除线路特征表中原有的 '{new_column_name}' 列...")
        feature_df = feature_df.drop(columns=[new_column_name])
        print(f"删除后列数: {len(feature_df.columns)}")
    else:
        print(f"线路特征表中未找到 '{new_column_name}' 列，跳过删除步骤")

    # 2. 准备临水临崖数据
    temp_df = water_road_df[[water_road_route_col, water_road_count_col]].copy()
    temp_df.rename(columns={
        water_road_route_col: feature_route_col,  # 统一连接键列名
        water_road_count_col: new_column_name  # 目标列名
    }, inplace=True)

    print(f"准备合并的临水临崖数据前5行:")
    print(temp_df.head())
    print(f"临水临崖数据列名: {list(temp_df.columns)}")
    # 确保匹配列的数据类型一致
    feature_df[feature_route_col] = feature_df[feature_route_col].astype(str)
    temp_df[feature_route_col] = temp_df[feature_route_col].astype(str)

    print(f"特征表匹配列 '{feature_route_col}' 数据类型: {feature_df[feature_route_col].dtype}")
    print(f"临水临崖表匹配列 '{feature_route_col}' 数据类型: {temp_df[feature_route_col].dtype}")

    # 3. 执行左连接合并
    merged_df = feature_df.merge(temp_df, on=feature_route_col, how='left')

    # 4. 检查合并结果
    if new_column_name not in merged_df.columns:
        raise RuntimeError(f"合并失败！结果中未找到列 '{new_column_name}'。当前列: {list(merged_df.columns)}")

    # 5. 填充缺失值
    original_missing = merged_df[new_column_name].isna().sum()
    merged_df[new_column_name] = merged_df[new_column_name].fillna(0)

    print(f"\n合并完成:")
    print(f"- 原始特征表行数: {original_count}")
    print(f"- 删除列后特征表行数: {len(feature_df)}")
    print(f"- 合并后总行数: {len(merged_df)}")
    print(f"- 新增列: {new_column_name}")
    print(f"- 原始缺失值数量: {original_missing} (已填充为0)")
    print(f"- 数值范围: {merged_df[new_column_name].min()} ~ {merged_df[new_column_name].max()}")

    return merged_df


async def main(df1, df2):
    # 配置参数模块
    config = {
        'feature_route_column': 'route_name',  # 线路特征表中的线路列名
        'water_road_route_column': '线路名称',  # 临水临崖数量表中的线路列名
        'water_road_count_column': '临水临崖数量',  # 临水临崖数量表中的数量列名
        'new_column_name': '临水临崖数量'  # 合并后的新列名
    }

    # 读取数据
    feature_df = df1.copy()
    water_road_df = df2.copy()

    print(f"✓ 线路特征表: ({len(feature_df)}行)")
    print(f"  列名: {list(feature_df.columns[:5])}... (共{len(feature_df.columns)}列)")

    print(f"✓ 临水临崖表: ({len(water_road_df)}行)")
    print(f"  列名: {list(water_road_df.columns)}")

    # 执行合并
    result_df = merge_line_features_with_water_road(feature_df, water_road_df, config)
    return result_df


if __name__ == "__main__":
    print('1')