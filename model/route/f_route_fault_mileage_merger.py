import pandas as pd

from core.logger import logger


def merge_multiple_tables(route_feature_df, fault_df, mileage_df,
                          route_id_col='route_id', fault_count_col='总故障次数',
                          corrected_mileage_col='总修正里程'):
    """
    将线路故障统计表和线路里程表与线路特征表进行匹配合并
    route_id_col: route_id列名 (默认: 'route_id')
    fault_count_col: 故障次数列名 (默认: '总故障次数')
    corrected_mileage_col: 修正里程列名 (默认: '总修正里程')
    """

    # 读取线路特征表
    try:
        feature_df = route_feature_df.copy()
        print(f"成功读取线路特征表，共 {len(feature_df)} 行数据")
    except Exception as e:
        raise ValueError(f"读取线路特征表失败: {str(e)}")

    # 检查线路特征表是否包含route_id列
    if route_id_col not in feature_df.columns:
        raise ValueError(f"线路特征表缺少'{route_id_col}'列")

    # 确保route_id列是字符串类型
    feature_df[route_id_col] = feature_df[route_id_col].astype(str)

    # 读取线路故障统计表
    try:
        fault_df = fault_df.copy()
        print(f"成功读取线路故障统计表，共 {len(fault_df)} 行数据")
    except Exception as e:
        raise ValueError(f"读取线路故障统计表失败: {str(e)}")

    # 检查线路故障统计表是否包含必要的列
    missing_fault_cols = []
    if route_id_col not in fault_df.columns:
        missing_fault_cols.append(route_id_col)
    if fault_count_col not in fault_df.columns:
        missing_fault_cols.append(fault_count_col)

    if missing_fault_cols:
        raise ValueError(f"线路故障统计表缺少必要列: {', '.join(missing_fault_cols)}")

    # 确保故障统计表的route_id列是字符串类型
    fault_df[route_id_col] = fault_df[route_id_col].astype(str)
    # 确保故障次数列是数值类型
    fault_df[fault_count_col] = pd.to_numeric(fault_df[fault_count_col], errors='coerce').fillna(0).astype(int)

    # 读取线路里程表
    try:
        mileage_df = mileage_df.copy()
        print(f"成功读取线路里程表，共 {len(mileage_df)} 行数据")
    except Exception as e:
        raise ValueError(f"读取线路里程表失败: {str(e)}")

    # 检查线路里程表是否包含必要的列
    missing_mileage_cols = []
    if route_id_col not in mileage_df.columns:
        missing_mileage_cols.append(route_id_col)
    if corrected_mileage_col not in mileage_df.columns:
        missing_mileage_cols.append(corrected_mileage_col)

    if missing_mileage_cols:
        raise ValueError(f"线路里程表缺少必要列: {', '.join(missing_mileage_cols)}")

    # 确保里程表的route_id列是字符串类型
    mileage_df[route_id_col] = mileage_df[route_id_col].astype(str)
    # 确保修正里程列是数值类型
    mileage_df[corrected_mileage_col] = pd.to_numeric(mileage_df[corrected_mileage_col], errors='coerce').fillna(0)

    # 创建故障次数映射字典
    fault_mapping = dict(zip(fault_df[route_id_col], fault_df[fault_count_col]))

    # 创建修正里程映射字典
    corrected_mileage_mapping = dict(zip(mileage_df[route_id_col], mileage_df[corrected_mileage_col]))

    # 以线路特征表为基础，添加故障次数列
    feature_df['总故障次数'] = feature_df[route_id_col].map(fault_mapping).fillna(0).astype(int)

    # 以线路特征表为基础，添加修正里程列
    feature_df['总修正里程'] = feature_df[route_id_col].map(corrected_mileage_mapping).fillna(0)

    # 统计匹配情况
    fault_matched_count = (feature_df['总故障次数'] != 0).sum()
    fault_unmatched_count = len(feature_df) - fault_matched_count

    corrected_mileage_matched_count = (feature_df['总修正里程'] != 0).sum()
    corrected_mileage_unmatched_count = len(feature_df) - corrected_mileage_matched_count

    print(f"线路特征表总行数: {len(feature_df)}")
    print(f"总故障次数匹配成功: {fault_matched_count}, 匹配失败: {fault_unmatched_count}")
    print(f"总修正里程匹配成功: {corrected_mileage_matched_count}, 匹配失败: {corrected_mileage_unmatched_count}")

    try:
        print(feature_df.head())
    except Exception as e:
        raise ValueError(f"保存文件失败: {str(e)}")

    return feature_df


async def main(df1, df2, df3):

    # 配置参数模块
    CONFIG = {
        'route_id_col': 'route_id',  # route_id列名
        'fault_count_col': '总故障次数',  # 故障次数列名
        'corrected_mileage_col': '总修正里程'  # 修正里程列名
    }
    try:
        # 执行多表合并
        result_df = merge_multiple_tables(
            df1, df2, df3,
            CONFIG['route_id_col'], CONFIG['fault_count_col'], CONFIG['corrected_mileage_col']
        )
        # 显示统计结果
        print(f"总线路数: {len(result_df)}")
        print(f"总故障次数列统计: 平均={result_df['总故障次数'].mean():.2f}, 总和={result_df['总故障次数'].sum()}")
        print(f"总修正里程列统计: 平均={result_df['总修正里程'].mean():.2f}, 总和={result_df['总修正里程'].sum():.2f}")

    except Exception as e:
        print(f"\n错误: {str(e)}")
        print("请检查配置参数和输入文件路径")
        logger.exception(f"请检查配置参数和输入文件路径: {str(e)}")
    return result_df


# 主程序
if __name__ == "__main__":
    print('1')

