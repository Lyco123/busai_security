import asyncio

import pandas as pd
import numpy as np
from model.route import ClickHouse_query_data
from model.route import ClickHouse_sql_query_data
class CardPivotConfig:
    """刷卡数据透视表配置类"""

    def __init__(self):
        # 数据列
        self.line_column = 'linecode'  # 线路列名
        self.card_column = 'cardtype'  # 刷卡类型列名
        self.count_column = 'flow'  # 次数列名
        # 老人卡关键词
        self.elder_keyword = '老人'

        # 新增列名
        self.elder_total_column = '老人刷卡总次数'
        self.elder_ratio_column = '老人刷卡比率'

        # 配置选项
        self.decimal_places = 4  # 小数位数
        self.agg_function = 'sum'  # 聚合函数


def generate_card_pivot_table(route_card_type_df, config=None):
    """
    生成刷卡类型透视表并计算老人刷卡比率
    """
    if config is None:
        config = CardPivotConfig()

    # 读取数据
    df = route_card_type_df.copy()

    # 检查列是否存在
    required_cols = [config.line_column, config.card_column, config.count_column]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"缺少列: '{col}'")

    # 数据预处理
    df[config.line_column] = df[config.line_column].astype(str)
    df[config.card_column] = df[config.card_column].astype(str)
    df[config.count_column] = pd.to_numeric(df[config.count_column], errors='coerce').fillna(0)

    # 删除空值行
    df = df.dropna(subset=[config.line_column, config.card_column])
    df = df[(df[config.line_column] != 'nan') & (df[config.card_column] != 'nan')]

    print(f"处理后数据形状: {df.shape}")
    print(f"唯一线路数: {df[config.line_column].nunique()}")
    print(f"唯一刷卡类型数: {df[config.card_column].nunique()}")

    try:
        # 创建透视表 - 关键步骤
        pivot_table = pd.pivot_table(
            df,
            index=config.line_column,
            columns=config.card_column,
            values=config.count_column,
            aggfunc=config.agg_function,
            fill_value=0
        )

        print(f"透视表创建成功！")
        print(f"透视表形状: {pivot_table.shape}")
        print(f"透视表列数（刷卡类型数）: {len(pivot_table.columns)}")

        # 重置索引，将 linecode 转为普通列
        pivot_table = pivot_table.reset_index()


    except Exception as e:
        print(f"透视表创建失败: {e}")
        # 降级处理：手动创建透视表
        pivot_table = df.groupby([config.line_column, config.card_column])[config.count_column].sum().unstack(
            fill_value=0)
        pivot_table = pivot_table.reset_index()

    # 确保所有数据列都是数值类型
    for col in pivot_table.columns:
        if col != config.line_column:
            pivot_table[col] = pd.to_numeric(pivot_table[col], errors='coerce').fillna(0)

    # 查找包含"老人"的刷卡类型
    elder_columns = [col for col in pivot_table.columns
                     if col != config.line_column and config.elder_keyword in str(col)]

    print(f"包含'{config.elder_keyword}'的刷卡类型: {elder_columns}")

    # 计算老人刷卡总次数
    if elder_columns:
        pivot_table[config.elder_total_column] = pivot_table[elder_columns].sum(axis=1)
    else:
        pivot_table[config.elder_total_column] = 0

    # 计算所有刷卡类型的总次数
    original_card_columns = [col for col in pivot_table.columns
                             if col != config.line_column and col not in [config.elder_total_column]]
    pivot_table['刷卡总次数'] = pivot_table[original_card_columns].sum(axis=1)

    # 计算老人刷卡比率
    pivot_table[config.elder_ratio_column] = np.where(
        pivot_table['刷卡总次数'] > 0,
        pivot_table[config.elder_total_column] / pivot_table['刷卡总次数'],
        0
    ).round(config.decimal_places)

    return pivot_table


async def main(start_date:str,days):
    config = CardPivotConfig()
    #route_card_type_df = await ClickHouse_query_data.main('ads_line_cardtype_flow_daily')

    #sql1语句从clickhouse中获取线路不同刷卡次数数据
    sql1 =f"""SELECT linecode, cardtype, flow
    FROM
    ai_security.ads_line_cardtype_flow_daily
    WHERE
    parseDateTimeBestEffort(rundate) >= toDate('{start_date}') 
    AND
    parseDateTimeBestEffort(rundate) <= toDate('{start_date}') + INTERVAL {days} DAY"""

    route_card_type_df = await ClickHouse_sql_query_data.query_to_dataframe(sql1)

    try:
        result = generate_card_pivot_table(route_card_type_df, config)
        # 定义需要提取的列名列表
        cols_to_keep = ['linecode', '老人刷卡总次数', '刷卡总次数', '老人刷卡比率']
        # 提取列
        result_df = result[cols_to_keep]
        # 验证结果
        print("\n" + "=" * 50)
        print("最终结果验证:")
        print(f"结果形状: {result_df.shape}")
        print(f"列名: {list(result_df.columns)}")

        return result_df

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()