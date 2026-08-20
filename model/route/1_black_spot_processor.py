# 黑点列表处理：提取route_id、映射event_name并生成透视表
import pandas as pd
import numpy as np
from model.route import ClickHouse_query_data


def process_csv_file(black_spot_df, config):
    """
    1. 从指定列提取route_id（#之前的部分）
    2. 映射event_type到event_name
    3. 生成route_id的统计透视表
    """
    # 读取数据库文件
    df = black_spot_df.copy()

    def extract_route_id(value):
        """提取#之前的部分，如果没有#则返回原值"""
        if pd.isna(value):
            return value
        str_value = str(value)
        if '#' in str_value:
            return str_value.split('#')[0]
        else:
            return str_value

    df[config['route_id_column']] = df[config['id_column']].apply(extract_route_id)

    # 2. 处理event_type列：映射到event_name
    event_mapping = {
       '1': '斑马线数量',
        '2': '左转弯数量',
        '3': '右转弯数量',
        '6': '上坡路段数量',
        '7': '下坡路段数量',
        '8': '事故黑点',
        '9': '行为黑点',
        '10': '自定义黑点',
        '17': '区域限速点数量'
    }

    # 如果event_type列存在，进行映射
    if config['event_type_column'] in df.columns:
        df[config['event_name_column']] = df[config['event_type_column']].map(event_mapping)

        # 检查是否有未映射的值
        unmapped_values = df[config['event_type_column']][df[config['event_name_column']].isna()].unique()
        if len(unmapped_values) > 0:
            print(f"警告: 以下{config['event_type_column']}值没有对应的映射: {unmapped_values}")

        print(f"{config['event_type_column']} 映射完成，共 {len(df)} 行数据")
    else:
        print(f"警告: 未找到 '{config['event_type_column']}' 列，跳过映射")
        df[config['event_name_column']] = np.nan

    # 3. 生成以route_id为分组的统计透视表
    print(f"\n生成 {config['route_id_column']} 的统计透视表...")

    # 统计每个route_id的记录数量
    route_stats = df[config['route_id_column']].value_counts().to_frame('count')
    route_stats.index.name = config['route_id_column']

    print("\nRoute ID 统计表:")
    print(route_stats)

    # 生成route_id和event_name的交叉透视表
    if config['event_name_column'] in df.columns:
        pivot_table = pd.crosstab(
            index=df[config['route_id_column']],
            columns=df[config['event_name_column']],
            margins=False,  # 添加总计行和列
        )
        # 【新增】将索引重置为普通列
        pivot_table = pivot_table.reset_index()
        print(f"\n{config['route_id_column']} vs {config['event_name_column']} 透视表:")
        print(pivot_table)
    else:
        pivot_table = None
        print(f"\n无法生成透视表，因为 {config['event_name_column']} 列不存在")


    return  pivot_table


async def main():
    # 加载配置
    CONFIG = {
        'id_column': 'route_ids',  # 包含#的列名
        'event_type_column': 'event_type',  # event_type列名
        'route_id_column': 'route_id',  # 新增route_id列名
        'event_name_column': 'event_name'  # 新增event_name列名
    }
    config = CONFIG

    # 连接数据库并读取相应的数据表
    event_black_spot_df = await ClickHouse_query_data.main('ads_event_black_spot')

    try:
        # 处理文件
        black_spot_pivot_table = process_csv_file(event_black_spot_df, config)
        # print(black_spot_pivot_table.columns)
        print("\n处理完成!")
        return black_spot_pivot_table
    except FileNotFoundError:
        print("请确保文件路径正确，并且文件存在。")
    except KeyError as e:
        print(f"错误: 列 '{e.args[0]}' 不存在于文件中")
        print("请检查列名是否正确。")
    except Exception as e:
        print(f"处理过程中出现错误: {str(e)}")


if __name__ == "__main__":
    main()