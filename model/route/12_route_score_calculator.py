import pandas as pd
import numpy as np
from sklearn.preprocessing import RobustScaler
import importlib
from scipy.stats import rankdata
from starlette import status

from core.exception import CustomException

read_route_quota_weight = importlib.import_module("model.route.13_read_route_quota_weight")

def standardize_features(df, columns):
    """
       使用零值分离法 + 排名百分位法 进行特征标准化
       逻辑：
       1. 分离零值，零值保持为0。
       2. 对非零值计算百分位排名 (0-1)。
       3. 该排名直接作为 0-1 区间的标准化值。
          (注：百分位排名天然满足：最小值接近0，最大值接近1。
           若需严格对应“前1%为100分制下的100”，在0-1制下即为1.0。
           此方法比RobustScaler更能反映相对位置，且不受极端值数值大小的影响，只受排名影响)
       """
    standardized_df = df.copy()
    scalers = {}

    for col in columns:
        # 获取原始数据
        data = df[col].values

        # 检查是否存在非零值
        # 原代码逻辑：non_zero_mask 排除了 NaN 和 <=0 的值
        non_zero_mask = (data > 0) & (~np.isnan(data))
        has_non_zero = np.any(non_zero_mask)

        # 创建标准化结果数组，初始化为0 (零值和NaN暂时都为0，NaN后续可单独处理如果需要)
        standardized_values = np.zeros_like(data, dtype=float)

        if has_non_zero:
            # 步骤1：分离非零值
            non_zero_values = data[non_zero_mask]

            # 步骤2：计算百分位排名 (Rank-based Normalization)
            # method='average' 处理相同值的情况，pct=True 直接返回 0-1 之间的百分位
            # 结果范围: (0, 1]。最小值排名不为0而是 1/N，最大值是 1.0
            ranks_pct = rankdata(non_zero_values, method='average') / len(non_zero_values)

            # 步骤3：映射到 0-1 区间
            # 百分位排名本身就是 0-1 之间的数，可以直接作为标准化值
            # 如果希望最小值严格为0，最大值严格为1，可以做 MinMax 变换，但排名法通常直接使用 pct
            # 这里直接使用百分位排名，它反映了“超过百分之多少的数据”
            minmax_scaled = ranks_pct

            # 步骤4：回填还原
            standardized_values[non_zero_mask] = minmax_scaled

            # 如果有 NaN 值，它们在 non_zero_mask 中为 False，所以保持为初始化时的 0
            # 保存 scaler 信息（记录排名相关的统计量，虽然排名法不需要 fit 参数，但为了接口一致）
            scalers[col] = {
                'method': 'rank_percentile',
                'count': len(non_zero_values)
            }
        else:
            # 全零列或没有有效非零值
            scalers[col] = None

        # 添加标准化列
        standardized_df[f'{col}_标准化'] = standardized_values

    return standardized_df, scalers

def calculate_safety_score(df, feature_columns, weights):
    """
    计算线路安全评分（使用0-1标准化值）
    """
    score_components = {}
    total_score = np.zeros(len(df))

    for col in feature_columns:
        weight = weights[col]  # 使用用户提供的权重
        standardized_col = f'{col}_标准化'

        # 计算指标得分：标准化值 × 权重（三级指标权重之和为100）
        component_score = df[standardized_col] * weight * 100
        score_components[col] = component_score
        total_score += component_score

    # 每条线路的总分即为所有指标得分之和（不需要额外归一化，因为已经标准化至0-1区间）
    final_scores = total_score  # 总分范围理论上是0到100（当所有指标都达到最大值时）

    # 确保总分不超过100（虽然理论上不应该超过）
    final_scores = np.clip(final_scores, 0, 100)

    return final_scores, score_components


def calculate_line_safety_scores(route_feature_df, feature_columns, weights):
    """
    计算线路安全评分的主函数
    feature_columns: 特征列名列表
    weights: 各特征的权重字典（权重和=1）
    """
    print(f"特征列数: {len(feature_columns)}")

    # 读取数据
    try:
        df = route_feature_df.copy()
        print(f"成功读取文件，共 {len(df)} 行数据，{len(df.columns)} 列")
    except Exception as e:
        raise ValueError(f"读取文件失败: {str(e)}")

    # 检查所有特征列是否存在
    missing_cols = [col for col in feature_columns if col not in df.columns]
    if missing_cols:
        raise ValueError(f"以下特征列不存在于文件中: {missing_cols}")

    # 标准化特征至0-1区间
    standardized_df, scalers = standardize_features(df, feature_columns)

    # 计算安全评分
    safety_scores, score_components = calculate_safety_score(standardized_df, feature_columns, weights)

    # 添加安全评分到DataFrame
    standardized_df['安全评分'] = safety_scores.round(3)

    # 添加各指标得分
    for col, scores in score_components.items():
        standardized_df[f'{col}_得分'] = scores.round(3)
    # 对所有 _标准化 列进行换算，生成 _换算值 列
    for col in feature_columns:
        standardized_col = f'{col}_标准化'
        if standardized_col in standardized_df.columns:
            standardized_df[f'{col}_换算值'] = standardized_df[standardized_col] * 100

    try:
        # 显示评分统计
        print(f"\n结果表示例 (前5行):")
        display_cols = ['安全评分'] + [f'{col}_标准化' for col in feature_columns[3:6]] + [f'{col}_换算值' for col in feature_columns[3:6]] + [f'{col}_得分' for col in feature_columns[3:6]]
        print(standardized_df[display_cols].head().to_markdown(index=False))

    except Exception as e:
        raise ValueError(f"保存文件失败: {str(e)}")

    return standardized_df


async def main(start_time,df):
    # 配置参数模块
    CONFIG = {
        'feature_columns': [],  # 特征列名列表
        'weights': {}  # 各特征的权重字典（权重和=1.0）
    }
    # 示例 'feature_columns': [
    #     '急转弯点数量', '斑马线数量', '左转弯数量', '右转弯数量', '上坡路段数量', '下坡路段数量', '事故黑点',
    #     '总修正里程', '区域限速点数量', '行为黑点', '老人刷卡比率', '临水临崖数量', '学校数量', '商场数量', '体育馆数量', '医院数量',
    #     '刷卡总次数','总故障次数_千公里'......]

    line_quota_weights, report_type_10_list = await read_route_quota_weight.main(start_time)  #line_quota_weights为线路所有三级指标的全局权重。和为1

    CONFIG['weights'] = line_quota_weights
    CONFIG['feature_columns'] = list(line_quota_weights.keys())

    try:
        # 执行安全评分计算
        result_df = calculate_line_safety_scores(
            df,
            CONFIG['feature_columns'],
            CONFIG['weights']
        )
        total_weight = sum(CONFIG['weights'].values())
        print(f"总权重: {total_weight}")

        # 计算线形路况_得分
        route_conditions_cols = ['急转弯点数量_得分', '斑马线数量_得分', '左转弯数量_得分', '右转弯数量_得分', '上坡路段数量_得分',
                                 '下坡路段数量_得分', '区域限速点数量_得分', '临水临崖数量_得分']
        if route_conditions_cols:
            result_df['线形路况_得分'] = result_df[route_conditions_cols].sum(axis=1)

        # 计算人口密集区域_得分
        route_densely_cols = ['学校数量_得分', '商场数量_得分', '体育馆数量_得分', '医院数量_得分', '老人刷卡比率_得分',
                                 '刷卡总次数_得分', '总修正里程_得分']
        if route_densely_cols:
            result_df['人口密集区域_得分'] = result_df[route_densely_cols].sum(axis=1)

        # 计算线路黑点_得分
        route_black_spot_cols = ['行为黑点_得分', '事故黑点_得分']
        if route_black_spot_cols:
            result_df['线路黑点_得分'] = result_df[route_black_spot_cols].sum(axis=1)
        # 计算静态风险_得分
        result_df['静态风险_得分'] = result_df[['线形路况_得分', '人口密集区域_得分', '线路黑点_得分']].sum(axis=1)

        # 计算线路驾驶不良行为_得分
        route_behavior_cols = [f"{col}_千公里_得分" for col in report_type_10_list]
        if route_behavior_cols:
            result_df['驾驶不良行为_得分'] = result_df[route_behavior_cols].sum(axis=1)

        # 计算线路车辆故障总数_得分
        result_df['车辆故障总数_得分'] = result_df['总故障次数_千公里_得分']
        # 计算动态风险_得分
        route_dynamic_cols = ['驾驶不良行为_得分', '车辆故障总数_得分']
        if route_dynamic_cols:
            result_df['动态风险_得分'] = result_df[route_dynamic_cols].sum(axis=1)

        # 显示详细统计结果
        print("\n详细统计结果:")
        print(f"总线路数: {len(result_df)}")
        print(f"安全评分范围: {result_df['安全评分'].min():.2f} - {result_df['安全评分'].max():.2f}")
        print(f"平均安全评分: {result_df['安全评分'].mean():.2f}")
        print("任务执行成功!")
        return result_df  # 只输出1000多条线路各级指标的全局得分及总分、指标原始值、三级指标标准化、三级指标换算值
    except Exception as e:
        print(f"\n错误: {str(e)}")
        print("请检查配置参数和输入文件路径")
        raise CustomException(f"calculate_per_thousand_km_metrics:{str(e)}", code=status.HTTP_404_NOT_FOUND)


# 主程序
if __name__ == "__main__":
    print('11')

