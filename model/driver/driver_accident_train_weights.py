import asyncio
import os

import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import (roc_auc_score,f1_score,precision_recall_curve,
                             confusion_matrix,auc)

from core.clickhouse_connect import connect_to_clickhouse
from model.driver.driver_accident_data_process import load_and_preprocess_data,encode_and_handle_outliers,process_outliers,apply_business_rules_direct
import joblib
import warnings

from model.driver import crud

warnings.filterwarnings('ignore')

# ==================== 4. 模型训练 ====================
def train_single_model(X_train,y_train,X_valid,y_valid):
    pos_weight=np.sqrt((y_train==0).sum()/(y_train==1).sum())

    params={
        'boosting_type':'gbdt',
        'objective':'binary',
        'metric':'auc',
        'num_leaves':31,
        'max_depth':6,
        'learning_rate':0.05,
        'feature_fraction':0.8,
        'bagging_fraction':0.8,
        'bagging_freq':5,
        'scale_pos_weight':pos_weight,
        'min_data_in_leaf':20,
        'verbose':-1,
        'random_state':42
    }

    weights=np.where(y_train==1,pos_weight,1.0)
    train_data=lgb.Dataset(X_train,label=y_train,weight=weights)
    valid_data=lgb.Dataset(X_valid,label=y_valid)

    model=lgb.train(
        params,
        train_data,
        num_boost_round=1000,
        valid_sets=[train_data,valid_data],
        valid_names=['train','valid'],
        callbacks=[
            lgb.early_stopping(50,verbose=False),
            lgb.log_evaluation(period=0)
        ]
    )

    return model




# ==================== 8. 模型评估（完整版） ====================
def evaluate_model_complete(y_true,y_pred,title="Model"):
    """完整的模型评估，包含所有指标"""
    y_true = np.array(y_true, dtype=int)
    y_pred = np.array(y_pred, dtype=float)
    precision,recall,ths=precision_recall_curve(y_true,y_pred)
    f1_scores=2*precision*recall/(precision+recall+1e-8)
    best_idx=f1_scores.argmax() if len(f1_scores)>0 else 0
    best_th=ths[best_idx] if len(ths)>best_idx else 0.05

    y_pred_bin=(y_pred>=best_th).astype(int)

    # 混淆矩阵
    tn,fp,fn,tp=confusion_matrix(y_true,y_pred_bin).ravel()

    print(f"\n{'='*60}")
    print(f"=== {title} ===")
    print(f"{'='*60}")
    print(f'AUC: {roc_auc_score(y_true,y_pred):.4f}')
    print(f'F1 (最佳阈值={best_th:.3f}): {f1_score(y_true,y_pred_bin):.4f}')
    print(f'TP={tp} TN={tn} FP={fp} FN={fn}')
    print(f'Precision: {tp/(tp+fp+1e-8):.4f}')
    print(f'Recall: {tp/(tp+fn+1e-8):.4f}')
    print(f'PR-AUC: {auc(recall,precision):.4f}')
    print(f"预测概率范围: [{y_pred.min():.4f}, {y_pred.max():.4f}]")
    print(f"{'='*60}")

    return {
        'best_threshold':best_th,
        'auc':roc_auc_score(y_true,y_pred),
        'f1':f1_score(y_true,y_pred_bin),
        'precision':tp/(tp+fp+1e-8),
        'recall':tp/(tp+fn+1e-8),
        'pr_auc':auc(recall,precision),
        'tp':tp,'tn':tn,'fp':fp,'fn':fn
    }


# ==================== 9. 主流程 ====================
async def accident_weights_main(_start_time:str):
    try:
        async with await connect_to_clickhouse() as client:
            print("="*90)
            print("驾驶员事故风险预测 - 单模型两层评分系统")
            print("="*90)

            datas = await crud.Driver(client).get_drivers_datas()
            if datas is None:
                raise ValueError(f"{_start_time}事故风险权重宽表为空，无法输出权重结果")
            # 进行驾驶员能耗驾驶行为权重计算（时间跨度为一个月，每条数据为每人每天每辆车的驾驶行为次数、总能耗、总里程、客流量）
            # 权重字典驾驶行为使用中文格式，而非type_1格式
            # df_energy_weights = pd.DataFrame(datas)

            # 1. 加载数据
            print("\n1. 加载数据...")
            # data,base_cols,behavior_cols,health_cols,illegal_cols,all_feature_cols=load_and_preprocess_data('4.csv')
            data, base_cols, behavior_cols, health_cols, illegal_cols, all_feature_cols = await load_and_preprocess_data(datas)
            print(f"总特征数: {len(all_feature_cols)}")

            # 2. 特征编码
            data,le_gender,le_edu,mental_encoder=encode_and_handle_outliers(data)

            # 3. 处理异常值
            print("\n2. 处理异常值...")
            data=process_outliers(data,base_cols,is_health=False)
            data=process_outliers(data,behavior_cols,is_health=False)
            data=process_outliers(data,health_cols,is_health=True)
            data=process_outliers(data,illegal_cols,is_health=False)

            # 4. 准备数据
            X=data[all_feature_cols].values
            y=data['has_accident'].values

            # 5. 数据分割
            print("\n3. 数据分割...")
            X_train,X_test,y_train,y_test=train_test_split(
                X,y,test_size=0.2,random_state=42,stratify=y)

            # 6. 训练模型
            print("\n4. 训练单一模型...")
            model=train_single_model(X_train,y_train,X_test,y_test)

            # 7. 评估模型（完整版）
            print("\n5. 模型评估...")
            pred_prob=model.predict(X_test)
            pred_prob=apply_business_rules_direct(pd.DataFrame(X_test,columns=all_feature_cols),pred_prob)

            eval_results=evaluate_model_complete(y_test,pred_prob,"单一模型")

            # 8. 特征重要性
            print("\n6. 特征重要性 Top 15:")
            importance=model.feature_importance(importance_type='split')
            feat_imp=pd.DataFrame({
                '特征':all_feature_cols,
                '重要性':importance
            }).sort_values('重要性',ascending=False)
            print(feat_imp.head(15).to_string(index=False))

            # 9. 保存模型
            model_data={
                'model':model,
                'feature_names':all_feature_cols,
                'base_cols':base_cols,
                'behavior_cols':behavior_cols,
                'health_cols':health_cols,
                'illegal_cols':illegal_cols,
                'le_gender':le_gender,
                'le_edu':le_edu,
                'best_threshold':eval_results['best_threshold']
            }
            delete_pickle_file('single_model_two_layer.pkl')
            joblib.dump(model_data,'single_model_two_layer.pkl')
            print("\n模型已保存至 single_model_two_layer.pkl")

            return model_data,X_test,y_test,all_feature_cols,base_cols,behavior_cols,health_cols,illegal_cols
    except Exception as e:
        print(f"驾驶员画像主程序执行出错: {e}")

    print("数据库连接已关闭")


# ==================== 9. 主流程 ====================
async def accident_weights_1hour_main(_start_time:str):
    try:
        async with await connect_to_clickhouse() as client:
            print("="*90)
            print("驾驶员事故风险预测 - 单模型两层评分系统")
            print("="*90)

            datas = await crud.Driver(client).get_drivers_1hour_datas()
            if datas is None:
                raise ValueError(f"{_start_time}事故风险权重宽表为空，无法输出权重结果")
            # 进行驾驶员能耗驾驶行为权重计算（时间跨度为一个月，每条数据为每人每天每辆车的驾驶行为次数、总能耗、总里程、客流量）
            # 权重字典驾驶行为使用中文格式，而非type_1格式
            # df_energy_weights = pd.DataFrame(datas)

            # 1. 加载数据
            print("\n1. 加载数据...")
            # data,base_cols,behavior_cols,health_cols,illegal_cols,all_feature_cols=load_and_preprocess_data('4.csv')
            data, base_cols, behavior_cols, health_cols, illegal_cols, all_feature_cols = await load_and_preprocess_data(datas)
            print(f"总特征数: {len(all_feature_cols)}")

            # 2. 特征编码
            data,le_gender,le_edu,mental_encoder=encode_and_handle_outliers(data)

            # 3. 处理异常值
            print("\n2. 处理异常值...")
            data=process_outliers(data,base_cols,is_health=False)
            data=process_outliers(data,behavior_cols,is_health=False)
            data=process_outliers(data,health_cols,is_health=True)
            data=process_outliers(data,illegal_cols,is_health=False)

            # 4. 准备数据
            X=data[all_feature_cols].values
            y=data['has_accident'].values

            # 5. 数据分割
            print("\n3. 数据分割...")
            X_train,X_test,y_train,y_test=train_test_split(
                X,y,test_size=0.2,random_state=42,stratify=y)

            # 6. 训练模型
            print("\n4. 训练单一模型...")
            model=train_single_model(X_train,y_train,X_test,y_test)

            # 7. 评估模型（完整版）
            print("\n5. 模型评估...")
            pred_prob=model.predict(X_test)
            pred_prob=apply_business_rules_direct(pd.DataFrame(X_test,columns=all_feature_cols),pred_prob)

            eval_results=evaluate_model_complete(y_test,pred_prob,"单一模型")

            # 8. 特征重要性
            print("\n6. 特征重要性 Top 15:")
            importance=model.feature_importance(importance_type='split')
            feat_imp=pd.DataFrame({
                '特征':all_feature_cols,
                '重要性':importance
            }).sort_values('重要性',ascending=False)
            print(feat_imp.head(15).to_string(index=False))

            # 9. 保存模型
            model_data={
                'model':model,
                'feature_names':all_feature_cols,
                'base_cols':base_cols,
                'behavior_cols':behavior_cols,
                'health_cols':health_cols,
                'illegal_cols':illegal_cols,
                'le_gender':le_gender,
                'le_edu':le_edu,
                'best_threshold':eval_results['best_threshold']
            }
            delete_pickle_file('single_model_two_layer_1hour.pkl')
            joblib.dump(model_data,'single_model_two_layer_1hour.pkl')
            print("\n模型已保存至 single_model_two_layer_1hour.pkl")

            return model_data,X_test,y_test,all_feature_cols,base_cols,behavior_cols,health_cols,illegal_cols
    except Exception as e:
        print(f"驾驶员画像主程序执行出错: {e}")

    print("数据库连接已关闭")


def delete_pickle_file(file_path):
    """
    删除指定的pickle文件

    Args:
        file_path (str): 要删除的文件路径

    Returns:
        bool: 删除成功返回True，失败返回False
    """
    try:
        # 检查文件是否存在
        if os.path.exists(file_path):
            # 检查是否为文件（而不是目录）
            if os.path.isfile(file_path):
                # 删除文件
                os.remove(file_path)
                print(f"成功删除文件: {file_path}")
                return True
            else:
                print(f"路径 '{file_path}' 存在但不是文件")
                return False
        else:
            print(f"文件 '{file_path}' 不存在")
            return False
    except PermissionError:
        print(f"权限不足，无法删除文件: {file_path}")
        return False
    except Exception as e:
        print(f"删除文件时发生错误: {e}")
        return False

if __name__=="__main__":
    # 训练模型
    model_data,X_test,y_test,all_feature_cols,base_cols,behavior_cols,health_cols,illegal_cols= asyncio.run(accident_weights_main())
