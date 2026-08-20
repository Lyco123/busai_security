import pandas as pd

def join_additional_data(mileage_accident_turning_table_df, black_spot_table_df, config):
    """
    基于线路编号-里程-事故数_急转弯点数量的route_id列与线路编码-黑点透视表的route_id列把两张表进行连接，
    要把线路编码-黑点透视表的['上坡路段数量', '下坡路段数量', '区域限速点数量', '右转弯数量', '左转弯数量', '斑马线数量', '事故黑点', '自定义黑点', '行为黑点']这些列连接为线路编号-里程-事故数_急转弯点数量.csv的新列，
    然后根据route_id列的匹配来填入相应的值，匹配失败的，新列填入0
    """
    # 读取线路编号-里程-事故数_急转弯点数量表
    main_df = mileage_accident_turning_table_df.copy()

    # 检查route_id列是否存在
    if config['route_id_column'] not in main_df.columns:
        raise KeyError(f"线路编号-里程-事故数_急转弯点数表中不存在列 '{config['route_id_column']}'")

    # 读取线路编码-黑点透视表
    black_spot_df = black_spot_table_df.copy()

    # 检查route_id列是否存在
    if config['route_id_column'] not in black_spot_df.columns:
        raise KeyError(f"线路编码-黑点透视表中不存在列 '{config['route_id_column']}'")

    # 检查所有需要的列是否存在
    missing_columns = [col for col in config['additional_columns'] if col not in black_spot_df.columns]
    if missing_columns:
        raise KeyError(f"线路编码-黑点透视表中不存在以下列: {missing_columns}")

    # 统一数据类型为字符串
    print(f"\n统一 '{config['route_id_column']}' 列的数据类型为字符串...")

    main_df[config['route_id_column']] = main_df[config['route_id_column']].astype(str)
    black_spot_df[config['route_id_column']] = black_spot_df[config['route_id_column']].astype(str)

    print(
        f"线路编号-里程-事故数_急转弯点数量表 '{config['route_id_column']}' 列数据类型: {main_df[config['route_id_column']].dtype}")
    print(
        f"线路编码-黑点透视表 '{config['route_id_column']}' 列数据类型: {black_spot_df[config['route_id_column']].dtype}")

    # 为所有需要添加的列初始化为0
    for col in config['additional_columns']:
        main_df[col] = 0

    # 从黑点表中选择需要的列
    black_spot_subset = black_spot_df[[config['route_id_column']] + config['additional_columns']].copy()

    # 创建一个临时的合并结果
    merged_result = pd.merge(
        main_df,
        black_spot_subset,
        left_on=config['route_id_column'],
        right_on=config['route_id_column'],
        how='left',
        suffixes=('', '_right')
    )

    # 将匹配到的值填入主表
    for col in config['additional_columns']:
        right_col = col + '_right'
        if right_col in merged_result.columns:
            # 将匹配到的值填入主表，未匹配到的保持为0
            main_df[col] = merged_result[right_col].fillna(0)



    # 显示各列的非零值数量
    print(f"\n各列非零值数量（不是匹配数量，而是实际特征值）:")
    for col in config['additional_columns']:
        non_zero_count = (main_df[col] != 0).sum()
        print(f"- {col}列非零值数量: {non_zero_count}")

    return main_df


async def main(df1, df2):
    # 加载配置
    CONFIG = {
        'route_id_column': 'route_id',  # route_id列名
        'additional_columns': [  # 需要添加的列名
            '上坡路段数量', '下坡路段数量', '区域限速点数量', '右转弯数量', '左转弯数量', '斑马线数量', '事故黑点', '自定义黑点', '行为黑点'
        ]
    }

    config = CONFIG
    try:
        # 执行连接
        result_df = join_additional_data(df1, df2, config)

        print("\n连接完成!")

        # 显示连接结果摘要
        print(f"\n连接结果摘要:")
        matched_count = ((result_df[config['additional_columns']] != 0).any(axis=1)).sum()
        unmatched_count = ((result_df[config['additional_columns']] == 0).all(axis=1)).sum()
        print(f"基于route_id匹配成功的记录数: {matched_count}")
        print(f"基于route_id匹配失败的记录数: {unmatched_count}")

        for col in config['additional_columns']:
            non_zero_count = (result_df[col] != 0).sum()
            print(f"- {col}: {non_zero_count}")
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