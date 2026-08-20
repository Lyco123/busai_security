import re
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split, RandomizedSearchCV
import logging
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

async def calculate_energy_behavior_weights(df):
    """
    计算驾驶行为指标权重 (多阈值自动寻优版)
    
    参数:
    df: DataFrame，包含能耗、驾驶行为和客运量数据
    
    返回:
    weights_dict: 字典，包含所有驾驶行为指标名称 -> 权重值
    remark: 字符串，模型评估及调优结果备注（包含选用的最佳阈值）
    """
    
    print("开始计算驾驶行为指标权重并寻找最佳过滤阈值...")

    # 预处理基础格式
    df['total_mileage'] = pd.to_numeric(df['total_mileage'])
    df['total_energy_consumption'] = pd.to_numeric(df['total_energy_consumption'])
    
    # ---------------- 静态配置定义区 ----------------
    all_driving_behaviors = [
        '起步急加速', '急加速', '急减速', '急刹车', '斑马线不文明礼让',
        '斑马线超速', '违规使用手刹', '停站N档违规', '违规使用N档',
        '不规范转弯', '车辆未停稳开车门', '车辆起步不关车门', '空档滑行',
        '熄火滑行', '不文明鸣笛', '安全带行为', '不规范进站', '不规范出站',
        '急停', '门开禁启开关', '停车不挂N档', '不规范开关门', '安全启动',
        '违规使用空调', '平路不规范行为', '上坡不规范行为', '下坡不规范行为',
        '违规使用总电', '路口大油门', '进站违规制动', '区间超速', '全局超速',
        '左转弯未刹车', '右转弯未刹车'
    ]

    exclude_behaviors = ['安全带行为', '不文明鸣笛','不规范开关门','门开禁启开关','车辆未停稳开车门','车辆起步不关车门']
    mandatory_energy_behaviors = ['起步急加速', '急加速', '急减速', '急刹车', '急停']
    
    number_to_behavior = {
        1: '停站N档违规', 2: '停车不挂N档', 3: '安全带行为', 4: '熄火滑行',
        5: '空档滑行', 6: '起步急加速', 7: '急减速', 8: '急加速',
        9: '急刹车', 10: '急停', 11: '车辆未停稳开车门', 12: '车辆起步不关车门',
        13: '门开禁启开关', 14: '斑马线超速', 15: '斑马线不文明礼让',
        16: '违规使用N档', 17: '不规范开关门', 18: '违规使用手刹',
        19: '不文明鸣笛', 20: '不规范出站', 21: '不规范进站',
        22: '不规范转弯', 23: '安全启动', 24: '违规使用空调',
        25: '平路不规范行为', 26: '上坡不规范行为', 27: '下坡不规范行为',
        28: '违规使用总电', 29: '路口大油门', 30: '进站违规制动',
        33: '区间超速', 34: '全局超速', 36: '左转弯未刹车', 37: '右转弯未刹车'
    }

    relevant_behaviors = [b for b in all_driving_behaviors if b not in exclude_behaviors]

    # 动态构建 report_type_mapping：行为名称 -> 列名（只需在原表上匹配一次）
    report_type_mapping = {}
    for col in df.columns:
        match = re.match(r'report_type(\d+)_count', col)
        if match:
            num = int(match.group(1))
            if num in number_to_behavior:
                behavior = number_to_behavior[num]
                report_type_mapping[behavior] = col

    # ---------------- 寻优参数及记录器初始化 ----------------
    threshold_candidates = [(60, 20), (75, 25), (90, 30)]
    
    best_r2 = -float('inf')
    best_weights = {behavior: 0.0 for behavior in all_driving_behaviors}
    best_remark = "数据量过少或数据质量不佳，所有阈值组合均无法训练有效模型"
    
    # 定义超参数搜索空间 (放在循环外，避免重复初始化)
    param_distributions = {
        'n_estimators': [100, 200, 300, 400],
        'max_depth': [10, 15, 20, 25, None],
        'min_samples_split': [2, 5, 10],
        'min_samples_leaf': [1, 2, 4],
        'max_features': ['sqrt', 'log2', 1.0]
    }

    # ---------------- 开始遍历不同阈值组合 ----------------
    for mileage_thresh, energy_thresh in threshold_candidates:
        logger.info(f"正在测试过滤阈值: 里程 > {mileage_thresh}, 能耗 > {energy_thresh}")
        
        # 1. 初始过滤
        df_filtered = df[
            (df['total_mileage'] > mileage_thresh) & 
            (df['total_energy_consumption'] > energy_thresh)
        ].copy()
        
        # 计算每公里能耗
        df_filtered['每公里能耗'] = df_filtered['total_energy_consumption'] / df_filtered['total_mileage']
        
        # 4. 计算相关驾驶行为的原始总次数和每公里次数
        relevant_report_columns = [report_type_mapping[behavior] for behavior in relevant_behaviors 
                                  if report_type_mapping.get(behavior) in df_filtered.columns]
        
        if relevant_report_columns:
            df_filtered['驾驶行为总次数'] = df_filtered[relevant_report_columns].sum(axis=1)
        
        # 5. 计算每公里驾驶行为次数
        behavior_features = []
        for behavior in relevant_behaviors:
            col_name = report_type_mapping.get(behavior)
            if not col_name or col_name not in df_filtered.columns:
                continue
                
            per_km_feature = f'{behavior}_每公里次数'
            df_filtered[per_km_feature] = df_filtered[col_name] / df_filtered['total_mileage']
            behavior_features.append(per_km_feature)
        
        if behavior_features:
            df_filtered['每公里驾驶行为总次数'] = df_filtered[behavior_features].sum(axis=1)
        
        # 6. 应用二次过滤条件
        filter_conditions = []
        if '每公里能耗' in df_filtered.columns:
            filter_conditions.append((df_filtered['每公里能耗'] >= 0.3) & (df_filtered['每公里能耗'] <= 1.5))
        if '驾驶行为总次数' in df_filtered.columns:
            filter_conditions.append((df_filtered['驾驶行为总次数'] >= 10) & (df_filtered['驾驶行为总次数'] <= 200))
        if '每公里驾驶行为总次数' in df_filtered.columns:
            filter_conditions.append(df_filtered['每公里驾驶行为总次数'] <= 5.0)
        if 'bus_length' in df_filtered.columns:
            filter_conditions.append(df_filtered['bus_length'] >= 4000)
        if 'total_weight' in df_filtered.columns:
            filter_conditions.append(df_filtered['total_weight'].notnull())
        if 'passenger_total' in df_filtered.columns:
            filter_conditions.append(df_filtered['passenger_total'].notnull())
            filter_conditions.append(df_filtered['passenger_total'] >= 0)
            filter_conditions.append(df_filtered['passenger_total'] <= 600)
        
        for condition in filter_conditions:
            df_filtered = df_filtered[condition]
            
        # 7. 准备特征
        base_features = []
        if 'bus_age' in df_filtered.columns: base_features.append('bus_age')
        if 'bus_length' in df_filtered.columns: base_features.append('bus_length')
        if 'total_weight' in df_filtered.columns: base_features.append('total_weight')
        
        if 'passenger_total' in df_filtered.columns and 'total_mileage' in df_filtered.columns:
            df_filtered['每公里客流量'] = df_filtered['passenger_total'] / df_filtered['total_mileage']
            base_features.append('每公里客流量')
            df_filtered = df_filtered[df_filtered['每公里客流量'] >= 0]
        
        # 数据量太少则跳过当前阈值组合
        if len(df_filtered) < 10:
            logger.warning(f"阈值 [{mileage_thresh}, {energy_thresh}] 剩余数据过少 ({len(df_filtered)}条)，跳过...")
            continue
            
        # 8. 准备特征矩阵和目标变量
        all_features = base_features + behavior_features
        X = df_filtered[all_features].copy()
        y = df_filtered['每公里能耗'].copy()
        
        # 9. 计算皮尔逊相关系数
        correlations = {}
        for feature in all_features:
            try:
                corr = X[feature].corr(y)
                correlations[feature] = corr if not pd.isna(corr) else 0.0
            except:
                correlations[feature] = 0.0
                
        # 10. 训练及调优
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
        
        base_rf = RandomForestRegressor(random_state=42, n_jobs=-1)
        random_search = RandomizedSearchCV(
            estimator=base_rf,
            param_distributions=param_distributions,
            n_iter=15, 
            cv=3,
            scoring='r2', 
            random_state=42,
            n_jobs=-1,
            verbose=0
        )
        
        random_search.fit(X_train, y_train)
        rf_model = random_search.best_estimator_
        
        # 测试集预测与评估
        y_pred = rf_model.predict(X_test)
        r2 = rf_model.score(X_test, y_test)
        mae = mean_absolute_error(y_test, y_pred)
        
        logger.info(f"阈值 [{mileage_thresh}, {energy_thresh}] -> R²: {r2:.4f}, MAE: {mae:.4f}")
        
        # ================= 核心判定：是否为当前最优模型 =================
        if r2 > best_r2:
            best_r2 = r2
            
            # 计算当前最优权重
            importances = rf_model.feature_importances_
            feature_importance_dict = dict(zip(all_features, importances))
            behavior_weights = {}
            
            for behavior_feature in behavior_features:
                corr = correlations.get(behavior_feature, 0)
                importance = feature_importance_dict.get(behavior_feature, 0)
                behavior_name = behavior_feature.replace('_每公里次数', '')
                
                if behavior_name in mandatory_energy_behaviors:
                    weight = importance
                else:
                    weight = importance if corr > 0 else 0.0
                    
                behavior_weights[behavior_name] = weight
            
            # 归一化
            positive_behavior_weights = {k: v for k, v in behavior_weights.items() if v > 0}
            if positive_behavior_weights:
                total_weight = sum(positive_behavior_weights.values())
                for behavior in positive_behavior_weights.keys():
                    behavior_weights[behavior] = behavior_weights[behavior] / total_weight
            
            # 存入最优字典和备注
            best_weights = {behavior: behavior_weights.get(behavior, 0.0) for behavior in all_driving_behaviors}
            best_remark = (f"选用最佳阈值 [里程>{mileage_thresh}, 能耗>{energy_thresh}] -> "
                           f"调优后随机森林模型 R²: {r2:.4f}, MAE: {mae:.4f}")

    # 循环结束，返回表现最好的结果
    print(best_remark)
    return best_weights, best_remark