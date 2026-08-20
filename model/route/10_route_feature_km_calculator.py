import pandas as pd
import importlib
from starlette import status


from core.exception import CustomException

driver_behavior_top10_weight_calculator = importlib.import_module("model.route.13_read_route_quota_weight")
import warnings
warnings.filterwarnings('ignore', category=FutureWarning, module='pandas')

def calculate_per_thousand_km_metrics(route_basic_feature_df, target_columns, mileage_col='总修正里程'):
    """
    计算线路特征表中指定列的千公里指标
    target_columns: 要计算千公里指标的列名列表
    mileage_col: 里程列名 (默认: '总修正里程')
    """

    # 读取数据
    try:
        df = route_basic_feature_df.copy()
        print(f"成功读取文件，共 {len(df)} 行数据，{len(df.columns)} 列")
    except Exception as e:
        raise ValueError(f"读取文件失败: {str(e)}")

    # 检查必要列是否存在
    if mileage_col not in df.columns:
        raise ValueError(f"缺少里程列: '{mileage_col}'")

    # 检查所有目标列是否存在
    missing_cols = [col for col in target_columns if col not in df.columns]
    if missing_cols:
        raise ValueError(f"缺少必要列: {missing_cols}")

    # 确保里程列是数值类型
    df[mileage_col] = pd.to_numeric(df[mileage_col], errors='coerce')

    # 检查是否有里程为0或负数的情况
    zero_mileage_mask = (df[mileage_col] <= 0) | (df[mileage_col].isna())
    zero_mileage_count = zero_mileage_mask.sum()
    if zero_mileage_count > 0:
        print(f"警告: 发现 {zero_mileage_count} 行里程为0或负数或空值，这些行的千公里指标将设为0")

    # 为每个目标列计算千公里指标
    for col in target_columns:
        # 将目标列转换为数值类型
        df[col] = pd.to_numeric(df[col], errors='coerce')

        # 计算千公里指标：(原值 / 里程) * 1000
        new_col_name = f"{col}_千公里"
        df[new_col_name] = 0.0  # 初始化新列

        # 只对里程大于0的行进行计算
        valid_mask = (df[mileage_col] > 0) & (df[mileage_col].notna()) & (df[col].notna())
        calculated_values = ((df.loc[valid_mask, col] / df.loc[valid_mask, mileage_col]) * 1000).round(5)
        df.loc[valid_mask, new_col_name] = calculated_values
        print(f"已计算列 '{col}' 的千公里指标，新列名为 '{new_col_name}'")

    print(f"\n千公里指标计算完成，共新增 {len(target_columns)} 列")

    try:
        # 显示包含新列的示例
        sample_cols = [f'{col}_千公里' for col in target_columns[:5]]  # 取前5个新列
        display_cols = [col for col in df.columns[:5]] + sample_cols  # 原始前5列+新列
        # print(df[display_cols].head().to_markdown(index=False))
    except Exception as e:
        raise ValueError(f"保存文件失败: {str(e)}")

    return df

async def main(start_time,route_behavior_feature_df):
    # 配置参数模块
    CONFIG = {
        'target_columns': [
            '总故障次数'  # 示例列名1
        ],  # 要计算千公里指标的11个列名
        'mileage_col': '总修正里程'  # 里程列名
    }

    # 从线路画像所有指标权重数据库中取出10种权重最大的驾驶行为的report_type，传入CONFIG['report_type_columns']
    dict1, report_type_columns_list = await driver_behavior_top10_weight_calculator.main(start_time)
    CONFIG['target_columns'] = CONFIG.get('target_columns', []) + report_type_columns_list

    try:
        # 执行千公里指标计算
        result_df = calculate_per_thousand_km_metrics(
            route_behavior_feature_df,
            CONFIG['target_columns'],
            CONFIG['mileage_col']
        )

        # 显示统计结果
        print("\n统计结果:")
        km_cols = [col for col in result_df.columns if '_千公里' in col]
        print(f"新增千公里指标列数: {len(km_cols)}")
        print("任务执行成功!")
        return result_df

    except Exception as e:
        print(f"\n错误: {str(e)}")
        raise CustomException("calculate_per_thousand_km_metrics:{e}", code=status.HTTP_404_NOT_FOUND)

# 主程序
# if __name__ == "__main__":
#     main()

