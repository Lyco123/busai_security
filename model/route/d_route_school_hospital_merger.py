# 线路POI数量匹配（学校/商场/体育馆/医院）
import pandas as pd

def merge_route_poi_counts(route_features_df, poi_counts_df):
    """
    合并线路特征表与POI统计表（含4种POI类型）
    参数:
        route_features_df: 线路特征表路径（含route_id等特征）
        poi_counts_df: POI统计表路径（含lcode, 学校数量, 商场数量, 体育馆数量, 医院数量）
    """

    # 1. 读取数据
    try:
        route_df = route_features_df.copy()
        print("成功读取线路特征表: {} 行 x {} 列".format(len(route_df), len(route_df.columns)))
    except Exception as e:
        print("错误: 读取线路特征表失败 - {}".format(str(e)))
        return None

    try:
        poi_df = poi_counts_df.copy()
        print("成功读取POI统计表: {} 行 x {} 列".format(len(poi_df), len(poi_df.columns)))
        print("POI表列名: {}".format(list(poi_df.columns)))
    except Exception as e:
        print("错误: 读取POI统计表失败 - {}".format(str(e)))
        return None

    # 2. 验证POI表必要列
    required_poi_cols = ['lcode', '学校数量', '商场数量', '体育馆数量', '医院数量']
    missing_cols = [col for col in required_poi_cols if col not in poi_df.columns]
    if missing_cols:
        print("错误: POI统计表缺失必要列: {}".format(missing_cols))
        print("请确保POI统计表包含列: {}".format(required_poi_cols))
        return None

    # 3. 数据类型标准化
    route_df['route_id'] = route_df['route_id'].astype(str).str.strip()
    poi_df['lcode'] = poi_df['lcode'].astype(str).str.strip()

    # 4. 准备POI数据（仅保留必要列）
    poi_selected = poi_df[required_poi_cols].copy()
    poi_selected = poi_selected.rename(columns={'lcode': 'route_id'})

    # 5. 合并数据（左连接：保留所有线路）
    result = pd.merge(
        route_df,
        poi_selected,
        on='route_id',
        how='left'
    )

    # 6. 处理缺失值：未匹配线路的POI数量设为0
    poi_cols = ['学校数量', '商场数量', '体育馆数量', '医院数量']
    for col in poi_cols:
        if col in result.columns:
            result[col] = result[col].fillna(0).astype(int)
        else:
            result[col] = 0


    # 8. 输出统计摘要
    print("\n合并结果统计:")
    print("  总线路数: {:,}".format(len(result)))
    print("  有学校线路: {:,} ({:.1%})".format(
        len(result[result['学校数量'] > 0]),
        result['学校数量'].gt(0).mean()))
    print("  有商场线路: {:,} ({:.1%})".format(
        len(result[result['商场数量'] > 0]),
        result['商场数量'].gt(0).mean()))
    print("  有体育馆线路: {:,} ({:.1%})".format(
        len(result[result['体育馆数量'] > 0]),
        result['体育馆数量'].gt(0).mean()))
    print("  有医院线路: {:,} ({:.1%})".format(
        len(result[result['医院数量'] > 0]),
        result['医院数量'].gt(0).mean()))

    # 9. 显示示例
    print("\n前5行示例（含POI列）:")
    display_cols = ['route_id'] + poi_cols
    if all(col in result.columns for col in display_cols):
        print(result[display_cols].head().to_string(index=False))

    return result


# ==================== 主程序 ====================
async def main(df1, df2):

    # 执行合并
    result_df = merge_route_poi_counts(df1, df2)
    return result_df


if __name__ == "__main__":
    print('1')


