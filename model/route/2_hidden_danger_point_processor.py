# 统计线路的急转弯风险点数量
import pandas as pd
from model.route import ClickHouse_query_data


def count_turning_points(line_hidden_danger_count_df, config):
    """
    统计每个线路急转弯点的出现次数
    """

    # 读取文件
    df = line_hidden_danger_count_df.copy()
    # 检查线路名称列是否存在
    if config['line_name_column'] not in df.columns:
        raise KeyError(f"列 '{config['line_name_column']}' 不存在于文件中")
    # 使用value_counts()统计每个线路出现的次数
    line_counts = df[config['line_name_column']].value_counts().reset_index()
    line_counts.columns = [config['line_name_column'], config['count_column']]



    print(f"\n统计结果 (共{len(line_counts)}条线路):")
    print(line_counts)

    return line_counts

async def main():
    # 加载配置
    CONFIG = {
        'line_name_column': 'line_name',  # 线路名称列
        'count_column': '急转弯点'  # 统计次数列名
    }
    config = CONFIG
    # 连接数据库并读取相应的数据表
    line_hidden_danger_count = await ClickHouse_query_data.main('ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_hidden_danger_point')
    try:
        # 执行统计
        result = count_turning_points(line_hidden_danger_count, config)

        print("\n统计完成!")

        # 显示前10条线路的统计结果
        print(f"\n前10条线路统计结果:")
        print(result.head(10))
        return result

    except FileNotFoundError:
        print(f"错误: 找不到输入文件 '{config['input_file']}'")
        print("请确保文件路径正确，并且文件存在。")
    except KeyError as e:
        print(f"错误: {str(e)}")
        print(
            f"请检查列名是否正确，可用列名: {list(pd.read_csv(config['input_file']).columns) if pd.read_csv(config['input_file'], nrows=0).empty == False else '文件无法读取'}")
    except Exception as e:
        print(f"处理过程中出现错误: {str(e)}")



if __name__ == "__main__":
    main()