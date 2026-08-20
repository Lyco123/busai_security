from model.route import ClickHouse_query_data
import pandas as pd
import os
import sys

def generate_poi_pivot_table(route_poi_df, code_col, type_col, count_col):
    """
    生成线路POI统计透视表（固定4种类型，列名含"数量"后缀）

        df: 原始DataFrame
        code_col: 线路标识列名（字符串）
        type_col: POI类型列名（字符串）
        count_col: POI数量列名（字符串）

    返回:
        DataFrame: 5列 ['lcode', '学校数量', '商场数量', '体育馆数量', '医院数量']
    """
    df = route_poi_df.copy()
    # 固定4种POI类型
    target_types = ['学校', '商场', '体育馆', '医院']
    target_columns = [f'{t}数量' for t in target_types]  # ['学校数量', '商场数量', '体育馆数量', '医院数量']

    # 1. 数据清洗与验证
    required_cols = [code_col, type_col, count_col]
    if not all(col in df.columns for col in required_cols):
        missing = [col for col in required_cols if col not in df.columns]
        raise ValueError(f"缺失必要列: {missing}. 请检查输入数据列名")

    df_clean = df[required_cols].copy()

    # 删除关键列缺失的行
    df_clean = df_clean.dropna(subset=[code_col, type_col])

    # 处理POI类型：字符串标准化（去空格）+ 过滤目标类型
    if df_clean[type_col].dtype == object:
        df_clean[type_col] = df_clean[type_col].str.strip()
    df_clean = df_clean[df_clean[type_col].isin(target_types)]

    # 处理数量列：转数值，异常值转0
    df_clean[count_col] = pd.to_numeric(df_clean[count_col], errors='coerce').fillna(0)

    # 2. 生成透视表（核心：按线路聚合，对数量求和）
    pivot_df = df_clean.pivot_table(
        index=code_col,
        columns=type_col,
        values=count_col,
        aggfunc='sum',
        fill_value=0,
        observed=True
    )

    # 3. 重命名列：添加"数量"后缀
    pivot_df.columns = [f'{col}数量' for col in pivot_df.columns]

    # 4. 补全缺失的POI类型列（填充0）
    for col in target_columns:
        if col not in pivot_df.columns:
            pivot_df[col] = 0

    # 5. 重置索引并规范列名
    pivot_df = pivot_df.reset_index()
    pivot_df = pivot_df.rename(columns={code_col: 'lcode'})  # 统一输出列名为"lcode"

    # 6. 严格按指定顺序排列列
    final_columns = ['lcode'] + target_columns
    pivot_df = pivot_df[final_columns]

    # 7. 验证输出结构
    if pivot_df.shape[1] != 5:
        raise RuntimeError(f"输出列数异常: 期望5列，实际{pivot_df.shape[1]}列")
    if list(pivot_df.columns) != final_columns:
        raise RuntimeError(f"列顺序错误: 期望{final_columns}, 实际{list(pivot_df.columns)}")

    return pivot_df


# ==================== 主程序 ====================
async def main():
    CONFIG = {
        # 列名映射配置（根据实际数据调整）
        'code_col': 'line_code',  # 原始数据中线路标识列名
        'type_col': 'type_name',  # 原始数据中POI类型列名
        'count_col': 'quantity'  # 原始数据中POI数量列名
    }
    # 连接数据库并读取相应的数据表
    line_school_mall_df = await ClickHouse_query_data.main('v_abs_densely_populated_line_route')

    # 读取数据
    try:
        df = line_school_mall_df
        print(f"\n✓ 成功读取数据: {len(df)} 行 × {len(df.columns)} 列")
        print(f"  原始列名: {list(df.columns)}")
    except Exception as e:
        print(f"\n 读取文件失败: {str(e)}")
        return 1

    # 3. 生成透视表
    try:
        result_df = generate_poi_pivot_table(
            df,
            code_col=CONFIG['code_col'],
            type_col=CONFIG['type_col'],
            count_col=CONFIG['count_col']
        )
        print(f"\n✓ 透视表生成成功: {len(result_df)} 条线路 × {len(result_df.columns)} 列")
        print(f"  输出列名: {list(result_df.columns)}")
    except Exception as e:
        print(f"\n生成透视表失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

    # 显示统计摘要
    print(f"  - 总线路数: {len(result_df)}")
    print(f"  - 学校总数: {result_df['学校数量'].sum():.0f}")
    print(f"  - 商场总数: {result_df['商场数量'].sum():.0f}")
    print(f"  - 体育馆总数: {result_df['体育馆数量'].sum():.0f}")
    print(f"  - 医院总数: {result_df['医院数量'].sum():.0f}")

    # 6. 显示示例数据
    print("\n 前5行示例:")
    print(result_df.head().to_string(index=False))
    return result_df


# ==================== 程序入口 ====================
if __name__ == "__main__":
    df = main()
