import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

def preprocess_data(df, config):
    """
    数据预处理：检查数据质量，处理异常值
    """
    # 检查数据形状
    print(f"原始数据形状: {df.shape}")
    # 检查目标变量分布
    target_col = config['target_column']
    feature_cols = config['feature_columns']

    # 检查特征列
    print(f"\n特征列统计:")
    for col in feature_cols:
        print(
            f"  {col}: 均值={df[col].mean():.3f}, 标准差={df[col].std():.3f}, 零值比例={len(df[df[col] == 0]) / len(df):.2%}")
    # 检查是否有足够的非零数据
    non_zero_targets = df[df[target_col] > 0]
    print(f"\n非零目标值数量: {len(non_zero_targets)} ({len(non_zero_targets) / len(df):.2%})")

    if len(non_zero_targets) < 10:
        print("警告: 非零目标值数量过少，可能导致模型训练困难")
    # 处理缺失值和异常值
    df_processed = df.copy()

    # 填充缺失值
    for col in feature_cols:
        if df_processed[col].isnull().any():
            median_val = df_processed[col].median()
            df_processed[col] = df_processed[col].fillna(median_val)
            print(f"填充 {col} 列的缺失值，使用中位数: {median_val}")
    # 目标变量的缺失值也填充
    if df_processed[target_col].isnull().any():
        median_val = df_processed[target_col].median()
        df_processed[target_col] = df_processed[target_col].fillna(median_val)
        print(f"填充目标变量的缺失值，使用中位数: {median_val}")
    # 处理极值（使用IQR方法）
    Q1 = df_processed[target_col].quantile(0.25)
    Q3 = df_processed[target_col].quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    # 将异常值限制在合理范围内
    outliers_count = len(
        df_processed[(df_processed[target_col] < lower_bound) | (df_processed[target_col] > upper_bound)])
    print(f"检测到 {outliers_count} 个目标变量异常值")

    df_processed[target_col] = np.clip(df_processed[target_col], lower_bound, upper_bound)
    return df_processed


def optimize_lightgbm_model(X_train, y_train, X_test, y_test, param_grid,
                            num_boost_round=1000, early_stopping_rounds=50):
    """
    通过网格搜索优化LightGBM模型参数
    """
    # 创建LightGBM数据集
    train_data = lgb.Dataset(X_train, label=y_train)
    val_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

    # 基础参数优化
    print("优化基础参数...")
    best_score = float('inf')
    best_params = {}

    # 检查是否有足够的验证数据
    if len(X_test) < 10:
        print("验证集数据过少，调整early_stopping_rounds")
        early_stopping_rounds = max(5, len(X_test) // 2)

    # 优化num_leaves和max_depth
    for num_leaves in param_grid['num_leaves']:
        for max_depth in param_grid['max_depth']:
            current_params = {
                'objective': 'regression',
                'metric': 'mae',
                'num_leaves': num_leaves,
                'max_depth': max_depth,
                'feature_fraction': 0.8,
                'bagging_fraction': 0.8,
                'min_data_in_leaf': 5,
                'learning_rate': 0.1,
                'random_state': 42,
                'verbose': -1,  # 关闭详细输出
                'min_gain_to_split': 0.001,  # 设置最小分割增益
                'feature_pre_filter': False
            }

            try:
                model = lgb.train(
                    current_params,
                    train_data,
                    num_boost_round=num_boost_round,
                    valid_sets=[val_data],
                    valid_names=['valid'],
                    callbacks=[
                        lgb.early_stopping(stopping_rounds=early_stopping_rounds),

                    ]
                )

                y_pred = model.predict(X_test, num_iteration=model.best_iteration or num_boost_round)
                score = mean_absolute_error(y_test, y_pred)

                if score < best_score:
                    best_score = score
                    best_params.update({
                        'num_leaves': num_leaves,
                        'max_depth': max_depth
                    })

            except Exception as e:
                print(f"参数组合 {current_params} 训练失败: {e}")
                continue

    # 优化学习率
    print("优化学习率...")
    for learning_rate in param_grid['learning_rate']:
        current_params = {
            'objective': 'regression',
            'metric': 'mae',
            'num_leaves': best_params.get('num_leaves', 20),
            'max_depth': best_params.get('max_depth', 5),
            'learning_rate': learning_rate,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'min_data_in_leaf': 5,
            'random_state': 42,
            'verbose': -1,
            'min_gain_to_split': 0.001,
            'feature_pre_filter': False
        }

        try:
            model = lgb.train(
                current_params,
                train_data,
                num_boost_round=num_boost_round,
                valid_sets=[val_data],
                valid_names=['valid'],
                callbacks=[
                    lgb.early_stopping(stopping_rounds=early_stopping_rounds),

                ]
            )

            y_pred = model.predict(X_test, num_iteration=model.best_iteration or num_boost_round)
            score = mean_absolute_error(y_test, y_pred)

            if score < best_score:
                best_score = score
                best_params['learning_rate'] = learning_rate

        except Exception as e:
            print(f"参数组合 {current_params} 训练失败: {e}")
            continue

    # 优化最小叶子节点样本数
    print("优化最小叶子节点样本数...")
    for min_data_in_leaf in param_grid['min_data_in_leaf']:
        current_params = {
            'objective': 'regression',
            'metric': 'mae',
            'num_leaves': best_params.get('num_leaves', 20),
            'max_depth': best_params.get('max_depth', 5),
            'learning_rate': best_params.get('learning_rate', 0.1),
            'min_data_in_leaf': min_data_in_leaf,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'random_state': 42,
            'verbose': -1,
            'min_gain_to_split': 0.001,
            'feature_pre_filter': False
        }

        try:
            model = lgb.train(
                current_params,
                train_data,
                num_boost_round=num_boost_round,
                valid_sets=[val_data],
                valid_names=['valid'],
                callbacks=[
                    lgb.early_stopping(stopping_rounds=early_stopping_rounds),

                ]
            )

            y_pred = model.predict(X_test, num_iteration=model.best_iteration or num_boost_round)
            score = mean_absolute_error(y_test, y_pred)

            if score < best_score:
                best_score = score
                best_params['min_data_in_leaf'] = min_data_in_leaf

        except Exception as e:
            print(f"参数组合 {current_params} 训练失败: {e}")
            continue

    # 优化特征分数
    print("优化特征分数...")
    for feature_fraction in param_grid['feature_fraction']:
        current_params = {
            'objective': 'regression',
            'metric': 'mae',
            'num_leaves': best_params.get('num_leaves', 20),
            'max_depth': best_params.get('max_depth', 5),
            'learning_rate': best_params.get('learning_rate', 0.1),
            'min_data_in_leaf': best_params.get('min_data_in_leaf', 10),
            'feature_fraction': feature_fraction,
            'bagging_fraction': 0.8,
            'random_state': 42,
            'verbose': -1,
            'min_gain_to_split': 0.001,
            'feature_pre_filter': False
        }

        try:
            model = lgb.train(
                current_params,
                train_data,
                num_boost_round=num_boost_round,
                valid_sets=[val_data],
                valid_names=['valid'],
                callbacks=[
                    lgb.early_stopping(stopping_rounds=early_stopping_rounds),

                ]
            )

            y_pred = model.predict(X_test, num_iteration=model.best_iteration or num_boost_round)
            score = mean_absolute_error(y_test, y_pred)

            if score < best_score:
                best_score = score
                best_params['feature_fraction'] = feature_fraction

        except Exception as e:
            print(f"参数组合 {current_params} 训练失败: {e}")
            continue

    # 优化袋装分数
    print("优化袋装分数...")
    for bagging_fraction in param_grid['bagging_fraction']:
        current_params = {
            'objective': 'regression',
            'metric': 'mae',
            'num_leaves': best_params.get('num_leaves', 20),
            'max_depth': best_params.get('max_depth', 5),
            'learning_rate': best_params.get('learning_rate', 0.1),
            'min_data_in_leaf': best_params.get('min_data_in_leaf', 10),
            'feature_fraction': best_params.get('feature_fraction', 0.8),
            'bagging_fraction': bagging_fraction,
            'random_state': 42,
            'verbose': -1,
            'min_gain_to_split': 0.001,
            'feature_pre_filter': False
        }

        try:
            model = lgb.train(
                current_params,
                train_data,
                num_boost_round=num_boost_round,
                valid_sets=[val_data],
                valid_names=['valid'],
                callbacks=[
                    lgb.early_stopping(stopping_rounds=early_stopping_rounds),

                ]
            )

            y_pred = model.predict(X_test, num_iteration=model.best_iteration or num_boost_round)
            score = mean_absolute_error(y_test, y_pred)

            if score < best_score:
                best_score = score
                best_params['bagging_fraction'] = bagging_fraction

        except Exception as e:
            print(f"参数组合 {current_params} 训练失败: {e}")
            continue

    # 优化L1正则化
    print("优化L1正则化...")
    for lambda_l1 in param_grid['lambda_l1']:
        current_params = {
            'objective': 'regression',
            'metric': 'mae',
            'num_leaves': best_params.get('num_leaves', 20),
            'max_depth': best_params.get('max_depth', 5),
            'learning_rate': best_params.get('learning_rate', 0.1),
            'min_data_in_leaf': best_params.get('min_data_in_leaf', 10),
            'feature_fraction': best_params.get('feature_fraction', 0.8),
            'bagging_fraction': best_params.get('bagging_fraction', 0.8),
            'lambda_l1': lambda_l1,
            'lambda_l2': 0.1,
            'random_state': 42,
            'verbose': -1,
            'min_gain_to_split': 0.001,
            'feature_pre_filter': False
        }

        try:
            model = lgb.train(
                current_params,
                train_data,
                num_boost_round=num_boost_round,
                valid_sets=[val_data],
                valid_names=['valid'],
                callbacks=[
                    lgb.early_stopping(stopping_rounds=early_stopping_rounds),

                ]
            )

            y_pred = model.predict(X_test, num_iteration=model.best_iteration or num_boost_round)
            score = mean_absolute_error(y_test, y_pred)

            if score < best_score:
                best_score = score
                best_params['lambda_l1'] = lambda_l1

        except Exception as e:
            print(f"参数组合 {current_params} 训练失败: {e}")
            continue


    # 优化L2正则化
    print("优化L2正则化...")
    for lambda_l2 in param_grid['lambda_l2']:
        current_params = {
            'objective': 'regression',
            'metric': 'mae',
            'num_leaves': best_params.get('num_leaves', 20),
            'max_depth': best_params.get('max_depth', 5),
            'learning_rate': best_params.get('learning_rate', 0.1),
            'min_data_in_leaf': best_params.get('min_data_in_leaf', 10),
            'feature_fraction': best_params.get('feature_fraction', 0.8),
            'bagging_fraction': best_params.get('bagging_fraction', 0.8),
            'lambda_l1': best_params.get('lambda_l1', 0.1),
            'lambda_l2': lambda_l2,
            'random_state': 42,
            'verbose': -1,
            'min_gain_to_split': 0.001,
            'feature_pre_filter': False
        }

        try:
            model = lgb.train(
                current_params,
                train_data,
                num_boost_round=num_boost_round,
                valid_sets=[val_data],
                valid_names=['valid'],
                callbacks=[
                    lgb.early_stopping(stopping_rounds=early_stopping_rounds),

                ]
            )

            y_pred = model.predict(X_test, num_iteration=model.best_iteration or num_boost_round)
            score = mean_absolute_error(y_test, y_pred)

            if score < best_score:
                best_score = score
                best_params['lambda_l2'] = lambda_l2

        except Exception as e:
            print(f"参数组合 {current_params} 训练失败: {e}")
            continue

    # 使用最佳参数训练最终模型
    final_params = {
        'objective': 'regression',
        'metric': 'mae',
        'num_leaves': best_params.get('num_leaves', 20),
        'max_depth': best_params.get('max_depth', 5),
        'learning_rate': best_params.get('learning_rate', 0.1),
        'min_data_in_leaf': best_params.get('min_data_in_leaf', 10),
        'feature_fraction': best_params.get('feature_fraction', 0.8),
        'bagging_fraction': best_params.get('bagging_fraction', 0.8),
        'lambda_l1': best_params.get('lambda_l1', 0.1),
        'lambda_l2': best_params.get('lambda_l2', 0.1),
        'random_state': 42,
        'verbose': -1,
        'min_gain_to_split': 0.001,  # 这个参数很重要，设置最小分割增益
        'feature_pre_filter': False
    }

    print(f"使用最佳参数训练最终模型: {final_params}")
    final_model = lgb.train(
        final_params,
        train_data,
        num_boost_round=num_boost_round,
        valid_sets=[val_data],
        valid_names=['valid'],
        callbacks=[
            lgb.early_stopping(stopping_rounds=early_stopping_rounds),

        ]
    )
    return final_model, best_params


def lightgbm_regression_analysis_optimized(route_feature_df, config):
    """
    优化后的LightGBM回归分析
    """
    # 读取数据
    df = route_feature_df.copy()
    # 数据预处理
    df = preprocess_data(df, config)

    # 选择特征和目标
    X = df[config['feature_columns']].copy()
    y = df[config['target_column']].copy()

    # 检查是否有足够的数据
    if len(X) < 20:
        raise ValueError(f"数据量过少 ({len(X)} 行)，无法进行有效建模")

    if len(X[X.sum(axis=1) == 0]) > len(X) * 0.8:
        print("警告: 大部分特征为零，可能影响模型性能")

    # 划分数据集
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=config['test_size'], random_state=config['random_state'],
        stratify=None  # 由于是回归问题，不需要分层抽样
    )

    print(f"\n训练集大小: {X_train.shape[0]}")
    print(f"测试集大小: {X_test.shape[0]}")

    # 检查划分后是否有足够的数据
    if len(X_train) < 10 or len(X_test) < 5:
        raise ValueError("训练集或测试集数据过少")

    # 标准化特征（LightGBM不需要标准化，但保留接口）
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # 参数优化
    model, best_params = optimize_lightgbm_model(
        X_train_scaled, y_train, X_test_scaled, y_test,
        config['param_grid'], config['num_boost_round'], config['early_stopping_rounds']
    )

    # 预测
    y_train_pred = model.predict(X_train_scaled, num_iteration=model.best_iteration or config['num_boost_round'])
    y_test_pred = model.predict(X_test_scaled, num_iteration=model.best_iteration or config['num_boost_round'])

    # 计算评估指标
    train_mae = mean_absolute_error(y_train, y_train_pred)
    test_mae = mean_absolute_error(y_test, y_test_pred)
    train_rmse = np.sqrt(mean_squared_error(y_train, y_train_pred))
    test_rmse = np.sqrt(mean_squared_error(y_test, y_test_pred))
    train_r2 = r2_score(y_train, y_train_pred)
    test_r2 = r2_score(y_test, y_test_pred)

    # 模型诊断
    print(f"\n优化后模型评估结果 (事故数预测):")
    print(f"训练集 - MAE: {train_mae:.3f}, RMSE: {train_rmse:.3f}, R²: {train_r2:.3f}")
    print(f"测试集 - MAE: {test_mae:.3f}, RMSE: {test_rmse:.3f}, R²: {test_r2:.3f}")

    # 特征重要性
    feature_importance = pd.DataFrame({
        'Feature': config['feature_columns'],
        'Importance': model.feature_importance()
    }).sort_values('Importance', ascending=False)

    # 计算每个特征重要性占总和的权重
    total_importance = feature_importance['Importance'].sum()
    feature_importance['Weight'] = ((feature_importance['Importance'] / total_importance)).round(4)
    # 将 feature_importance['Weight'] 转换为字典
    line_weight_dict = dict(zip(feature_importance['Feature'], feature_importance['Weight']))

    print(f"\n特征重要性（重要性排序）:")
    print(line_weight_dict)

    # 保存结果
    results = {
        'model': model,
        'X_train': X_train,
        'X_test': X_test,
        'y_train': y_train,
        'y_test': y_test,
        'y_train_pred': y_train_pred,
        'y_test_pred': y_test_pred,
        'feature_importance': feature_importance,
        'train_mae': train_mae,
        'test_mae': test_mae,
        'train_rmse': train_rmse,
        'test_rmse': test_rmse,
        'train_r2': train_r2,
        'test_r2': test_r2,
        'best_params': best_params
    }

    return results, line_weight_dict

async def main(df):
    # 配置参数模块
    CONFIG = {
        'target_column': '事故数',
        'feature_columns': [
            '急转弯点数量', '斑马线数量', '左转弯数量', '右转弯数量', '上坡路段数量', '下坡路段数量', '事故黑点', '总修正里程', '区域限速点数量',
            '行为黑点', '老人刷卡比率', '临水临崖数量', '学校数量', '商场数量', '体育馆数量', '医院数量', '刷卡总次数'
        ],
        'test_size': 0.2,
        'random_state': 42,
        'param_grid': {
            'num_leaves': [10, 15, 20, 25, 31, 40, 50, 63, 80, 100, 127],
            'learning_rate': [0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.1, 0.12, 0.15, 0.2, 0.25],
            'feature_fraction': [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0],
            'bagging_fraction': [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0],
            'max_depth': [3, 5, 7, 9, 11, 13, 15, -1],
            'min_data_in_leaf': [3, 5, 7, 10, 15, 20, 30, 50, 100],
            'lambda_l1': [0.0, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0],
            'lambda_l2': [0.0, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]
        },
        'cv_folds': 5,
        'early_stopping_rounds': 200,
        'num_boost_round': 4000
    }
    config = CONFIG

    try:
        results, line_weight_dict = lightgbm_regression_analysis_optimized(df, config)
        # 关键结果摘要
        print("\n关键结果摘要:")
        print(f"测试集 MAE: {results['test_mae']:.3f}")
        print(f"测试集 RMSE: {results['test_rmse']:.3f}")
        print(f"测试集 R²: {results['test_r2']:.3f}")
        return line_weight_dict, results

    except FileNotFoundError as e:
        print(f"文件错误: {str(e)}")
    except KeyError as e:
        print(f"列错误: {str(e)}")



# if __name__ == "__main__":
#     main()
