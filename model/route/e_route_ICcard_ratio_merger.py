import pandas as pd

def match_old_ratio_and_total_swipes(route_feature_df, pass_pivot_df, feature_route_id_col, pass_route_id_col,
                                     pass_old_ratio_col, pass_total_swipes_col):
    """
    匹配线路特征表与线路刷卡透视表，添加老人刷卡比率列和刷卡总次数列

        feature_route_id_col: 线路特征表中的route_id列名
        pass_route_id_col: 线路刷卡透视表中的route_id列名
        pass_old_ratio_col: 线路刷卡透视表中的老人刷卡比率列名
        pass_total_swipes_col: 线路刷卡透视表中的刷卡总次数列名
    """
    print("正在执行线路特征与刷卡数据匹配任务...")
    print(f"特征表route_id列: {feature_route_id_col}")
    print(f"刷卡表route_id列: {pass_route_id_col}")
    print(f"刷卡表老人刷卡比率列: {pass_old_ratio_col}")
    print(f"刷卡表刷卡总次数列: {pass_total_swipes_col}")

    # 读取线路特征表
    try:
        feature_df = route_feature_df.copy()
        print(f"成功读取线路特征表，共 {len(feature_df)} 行数据")
    except Exception as e:
        print(f"读取线路特征表失败: {e}")
        return False

    # 读取线路刷卡透视表
    try:
        pass_pivot_df = pass_pivot_df.copy()
        print(f"成功读取线路刷卡透视表，共 {len(pass_pivot_df)} 行数据")
    except Exception as e:
        print(f"读取线路刷卡透视表失败: {e}")
        return False

    # 检查必要列是否存在
    missing_columns = []
    if feature_route_id_col not in feature_df.columns:
        missing_columns.append(f"线路特征表缺少'{feature_route_id_col}'列")
    if pass_route_id_col not in pass_pivot_df.columns:
        missing_columns.append(f"线路刷卡透视表缺少'{pass_route_id_col}'列")
    if pass_old_ratio_col not in pass_pivot_df.columns:
        missing_columns.append(f"线路刷卡透视表缺少'{pass_old_ratio_col}'列")
    if pass_total_swipes_col not in pass_pivot_df.columns:
        missing_columns.append(f"线路刷卡透视表缺少'{pass_total_swipes_col}'列")

    if missing_columns:
        print("错误:")
        for msg in missing_columns:
            print(f" - {msg}")
        print(f"线路特征表列: {list(feature_df.columns)}")
        print(f"线路刷卡透视表列: {list(pass_pivot_df.columns)}")
        return False

    # 统一数据类型：将route_id列转换为字符串
    # 特征表route_id
    feature_route_ids = feature_df[feature_route_id_col].astype(str).str.strip()
    # 刷卡表route_id
    pass_route_ids = pass_pivot_df[pass_route_id_col].astype(str).str.strip()

    # 创建映射字典
    # 老人刷卡比率映射
    old_ratio_mapping = dict(zip(pass_route_ids, pass_pivot_df[pass_old_ratio_col]))
    # 刷卡总次数映射
    total_swipes_mapping = dict(zip(pass_route_ids, pass_pivot_df[pass_total_swipes_col]))

    # 在特征表中添加新列
    feature_df['老人刷卡比率'] = feature_route_ids.map(old_ratio_mapping).fillna(0)
    feature_df['刷卡总次数'] = feature_route_ids.map(total_swipes_mapping).fillna(0)


    # 统计匹配情况
    matched_old_ratio = (feature_df['老人刷卡比率'] != 0).sum()
    matched_total_swipes = (feature_df['刷卡总次数'] != 0).sum()


    print(f"\n匹配统计:")
    print(f" 总线路数: {len(feature_df)}")
    print(f" 老人刷卡比率匹配成功: {matched_old_ratio}")
    print(f" 刷卡总次数匹配成功: {matched_total_swipes}")

    try:
        # 显示匹配成功示例
        matched_sample = feature_df[(feature_df['老人刷卡比率'] != 0) | (feature_df['刷卡总次数'] != 0)].head()
        print(f"匹配成功线路示例 (前5条):")
        for idx, row in matched_sample.iterrows():
            print(
                f" 路线ID: {row[feature_route_id_col]}, 老人刷卡比率: {row['老人刷卡比率']}, 刷卡总次数: {row['刷卡总次数']}")
    except Exception as e:
        print(f"保存文件失败: {e}")
        return False

    return feature_df




async def main(df1, df2):
    # 配置参数
    FEATURE_ROUTE_ID_COL = "route_id"  # 线路特征表中的route_id列名
    PASS_ROUTE_ID_COL = "linecode"  # 线路刷卡透视表中的route_id列名
    PASS_OLD_RATIO_COL = "老人刷卡比率"  # 线路刷卡透视表中的老人刷卡比率列名
    PASS_TOTAL_SWIPES_COL = "刷卡总次数"  # 线路刷卡透视表中的刷卡总次数列名（请根据实际列名修改）
    print("线路特征与刷卡数据匹配工具")
    print("功能: 匹配线路特征表与刷卡透视表，添加老人刷卡比率列和刷卡总次数列")
    print(" - 匹配成功: 填入刷卡透视表的对应值")
    print(" - 匹配失败: 填入0")

    result = match_old_ratio_and_total_swipes(
        df1,
        df2,
        FEATURE_ROUTE_ID_COL,
        PASS_ROUTE_ID_COL,
        PASS_OLD_RATIO_COL,
        PASS_TOTAL_SWIPES_COL,
    )

    return result


if __name__ == "__main__":
    print('1')



