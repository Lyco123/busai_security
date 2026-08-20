import pandas as pd
from model.route import ClickHouse_query_data

def aggregate_tunnel_bridge_counts(df: pd.DataFrame, input_col_name: str, group_col_name: str) -> pd.DataFrame:
    """
    从线路桥梁隧道数量表中，根据线路名称分组统计桥隧数量总和

    参数:
    df (pd.DataFrame): 输入的数据框
    input_col_name (str): 输入数据框中桥隧数量列的名称
    group_col_name (str): 输入数据框中线路名称列的名称

    返回:
    pd.DataFrame: 包含线路名称和桥隧总数的数据
    """
    # 检查必要列是否存在
    required_columns = [group_col_name, input_col_name]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"输入数据框缺少必要列: {missing_columns}")

    # 将桥隧数量列转换为数值类型，非数值转换为NaN
    df[input_col_name] = pd.to_numeric(df[input_col_name], errors='coerce')

    # 删除桥隧数量为NaN的行
    df = df.dropna(subset=[input_col_name])
    # 按线路名称分组，对桥隧数量进行求和
    result = df.groupby(group_col_name)[input_col_name].sum().reset_index()

    return result



async def main():
    """
    参数:
    config (dict): 配置参数字典，默认使用 CONFIG
    """
    # 配置参数模块
    config = {
        'input_group_col': 'route_name',  # 输入文件中分组列的名称
        'input_value_col': 'quanlity',  # 输入文件中要汇总的列名称
        'output_group_col': '线路名称',  # 输出文件中分组列的名称
        'output_sum_col': '临水临崖数量'  # 输出文件中汇总列的名称
    }

    try:
        print("正在加载数据...")
        # 从CSV文件加载数据
        df = await ClickHouse_query_data.main('ods_route_risk_section')

        print(f"数据加载成功，共 {len(df)} 行")
        print(f"数据列: {list(df.columns)}")

        print("正在处理数据...")
        # 执行桥隧数量统计 - 按照输入文件中的'线路名称'列的唯一值来汇总'桥隧数量'列的值总和
        result = aggregate_tunnel_bridge_counts(df, config['input_value_col'], config['input_group_col'])
        result.columns = [config['output_group_col'], config['output_sum_col']]
        print(f"数据处理完成，共 {len(result)} 个唯一线路")

        print("\n处理完成！结果预览:")
        print(result.head(10))  # 显示前10行结果

        # 输出统计信息
        print(f"\n统计信息:")
        print(f"- 总线路数: {len(result)}")
        print(f"- 桥隧总数: {result.iloc[:, 1].sum()}")  # 第二列是汇总值
        print(f"- 平均每线路桥隧数: {result.iloc[:, 1].mean():.2f}")
        return result
    except FileNotFoundError as e:
        print(f"错误: {e}")
    except ValueError as e:
        print(f"数据错误: {e}")
    except Exception as e:
        print(f"处理过程中发生错误: {e}")


if __name__ == "__main__":
    result_df = main()