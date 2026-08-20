import pandas as pd
from starlette import status

from core.exception import CustomException


def merge_behavior_pivot_to_feature(feature_df, behavior_df, route_id_col='route_id'):
    """
    将线路驾驶行为透视表与线路特征表进行匹配合并
    route_id_col: route_id列名 (默认: 'route_id')
    """

    # 读取线路特征表
    try:
        feature_df = feature_df.copy()
        print(f"成功读取线路特征表，共 {len(feature_df)} 行数据")
    except Exception as e:
        raise ValueError(f"读取线路特征表失败: {str(e)}")

    # 检查线路特征表是否包含route_id列
    if route_id_col not in feature_df.columns:
        raise ValueError(f"线路特征表缺少'{route_id_col}'列")

    # 确保route_id列是字符串类型
    feature_df[route_id_col] = feature_df[route_id_col].astype(str)

    # 读取线路驾驶行为透视表
    try:
        behavior_df = behavior_df.copy()
        print(f"成功读取线路驾驶行为透视表，共 {len(behavior_df)} 行数据")
    except Exception as e:
        raise ValueError(f"读取线路驾驶行为透视表失败: {str(e)}")

    # 检查线路驾驶行为透视表是否包含route_id列
    if route_id_col not in behavior_df.columns:
        raise ValueError(f"线路驾驶行为透视表缺少'{route_id_col}'列")

    # 确保驾驶行为透视表的route_id列是字符串类型
    behavior_df[route_id_col] = behavior_df[route_id_col].astype(str)

    # 获取驾驶行为透视表中除route_id外的所有列
    behavior_columns = [col for col in behavior_df.columns if col != route_id_col]
    print(f"驾驶行为透视表中的其他列: {behavior_columns}")

    # 创建一个字典，键为route_id，值为该行所有其他列的数据
    behavior_dict = {}
    for _, row in behavior_df.iterrows():
        route_id = row[route_id_col]
        behavior_values = {}
        for col in behavior_columns:
            try:
                # 尝试转换为数值，如果失败则保持原样
                val = pd.to_numeric(row[col], errors='coerce')
                if pd.isna(val):
                    behavior_values[col] = 0
                else:
                    behavior_values[col] = val
            except:
                behavior_values[col] = 0
        behavior_dict[route_id] = behavior_values

    # 为线路特征表添加驾驶行为透视表中的所有列，并初始化为0
    for col in behavior_columns:
        feature_df[col] = 0

    # 遍历线路特征表的每一行，查找匹配的驾驶行为数据
    matched_count = 0
    unmatched_count = 0

    for idx, route_id in enumerate(feature_df[route_id_col]):
        if route_id in behavior_dict:
            # 匹配成功，填充对应的驾驶行为数据
            for col in behavior_columns:
                feature_df.at[idx, col] = behavior_dict[route_id].get(col, 0)
            matched_count += 1
        else:
            # 匹配失败，保持初始化的0值
            unmatched_count += 1

    print(f"线路特征表总行数: {len(feature_df)}")
    print(f"驾驶行为数据匹配成功: {matched_count}, 匹配失败: {unmatched_count}")
    print(f"新增驾驶行为列数: {len(behavior_columns)}")

    try:
        print(f"合并表示例 (前5行):")
        print(feature_df.head())
    except Exception as e:
        raise ValueError(f"保存文件失败: {str(e)}")
    return feature_df


async def main(df1, df2):
    # 配置参数模块
    CONFIG = {
        'route_id_col': 'route_id'  # route_id列名
    }
    try:
        # 执行驾驶行为透视表合并
        result_df = merge_behavior_pivot_to_feature(
            df1, df2, CONFIG['route_id_col'])

        # 显示统计结果
        print(f"总线路数: {len(result_df)}")
        original_cols = [col for col in result_df.columns if col != CONFIG['route_id_col']]
        behavior_cols = original_cols  # 修改：不再排除之前的列，显示所有新增列
        print(f"新增列数: {len(behavior_cols)}")
        print(f"新增列名: {', '.join(behavior_cols)}")
        return result_df
    except Exception as e:
        print(f"\n错误: {str(e)}")
        print("请检查配置参数")
        print("特别注意: 确保两个表都包含route_id列")
        raise CustomException(f"merge_behavior_pivot_to_feature:{str(e)}", code=status.HTTP_404_NOT_FOUND)


# 主程序
if __name__ == "__main__":
    print('1')

