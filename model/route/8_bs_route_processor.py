import pandas as pd
import asyncio
from model.route import ClickHouse_query_data
def extract_and_filter_columns(bs_route_df, config):
    """
    读取线路档案表格，取出指定列，
    """
    # 读取线路档案
    df = bs_route_df.copy()

    print(f"线路档案形状: {df.shape}")
    print(f"线路档案列名: {list(df.columns)}")

    # 检查指定的列是否都存在于数据中
    missing_columns = [col for col in config['selected_columns'] if col not in df.columns]
    if missing_columns:
        raise KeyError(f"以下列在文件中不存在: {missing_columns}")

    if config['filter_column'] not in df.columns:
        raise KeyError(f"过滤列 '{config['filter_column']}' 在文件中不存在")

    # 提取指定列数据
    extracted_df = df[config['selected_columns']]

    print(f"\n提取的指定列数据 (列名: {config['selected_columns']}):")
    print(f"提取前数据形状: {extracted_df.shape}")

    # 删除指定列为空的行
    # print(f"删除 '{config['filter_column']}' 列为空的行...")
    # filtered_df = extracted_df.dropna(subset=[config['filter_column']])
    #
    # print(f"删除空值后数据形状: {filtered_df.shape}")
    # print(f"删除了 {extracted_df.shape[0] - filtered_df.shape[0]} 行空值数据")

    return extracted_df


async def main():
    # 加载配置
    CONFIG = {
        'selected_columns': ['route_id', 'route_name', 'organ_id', 'mileage'],  # 指定要提取的列名
        'filter_column': 'mileage'  # 用于删除空值的列名
    }
    config = CONFIG
    # 连接数据库并读取相应的数据表
    bs_route_df = await ClickHouse_query_data.main('canbus.ods_jituan_bs_route')
    bs_organ_df = await ClickHouse_query_data.main('canbus.ods_jituan_bs_organ')
    try:
        # 执行数据提取和过滤
        result = extract_and_filter_columns(bs_route_df, config)
        # 3. 【新增】准备机构数据用于合并
        # 确保机构表只包含需要的列，避免列名冲突
        organ_subset = bs_organ_df[['organ_id', 'organ_name']]

        # 4. 【新增】执行左连接 (Left Join)
        # on='organ_id': 匹配键
        # how='left': 保留 result 中的所有行，匹配不到的 organ_name 为 NaN
        final_df = pd.merge(result, organ_subset, on='organ_id', how='left')

        print("\n数据提取、过滤及机构名称匹配完成!")
        print(f"最终数据形状：{final_df.shape}")
        print(final_df.head())
        print("\n数据提取和过滤完成!")
        return final_df
    except FileNotFoundError:
        print("请确保文件路径正确，并且文件存在。")
    except KeyError as e:
        print(f"错误: {str(e)}")
        print("请检查指定的列名是否正确。")
    except Exception as e:
        print(f"处理过程中出现错误: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())