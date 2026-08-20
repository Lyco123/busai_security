import asyncio
import uuid
from datetime import datetime

import numpy as np
import pandas as pd

from core.clickhouse_connect import connect_to_clickhouse
from model.driver import crud
from model.driver.schemas.driver_profile import AbsDriverProfileMain, AbsDriverQuotaScoreSub


# ==================== 5. 核心：两层分数计算系统 ====================
def calculate_two_layer_scores(X,X_input,feature_names):

    n_samples=X_input.shape[0]
    final_scores={}
    if len(feature_names)==3:
        weights=[0.33,0.33,0.33]
    else:
        weights=[0.2,0.2,0.1,0.1,0.1,0.1,0.1,0.1]

    raw_scores={}
    for col in feature_names:
        raw_scores[col]=np.random.uniform(0,100,n_samples)
        raw_scores[col]=np.clip(raw_scores[col],0,100)

    for i, col in enumerate(feature_names):
        final_scores[col]=raw_scores[col]*weights[i]

    total_score=np.zeros(n_samples)
    for col in feature_names:
        total_score+=final_scores[col]
    total_score=np.clip(total_score,0,100)


    return {
        'driver_name':X.iloc[:,0], # 司机名称
        'driver_id':X.iloc[:,1],  # 司机ID
        'organ_id':X.iloc[:,2],  # 机构ID
        'organ_name':X.iloc[:,3],  # 机构名称
        'final_scores':final_scores,  # 总分细分
        'raw_scores':raw_scores,  # 原始分
        'feat_weights':weights,  #  特征权重
        'total_score':total_score,  # 总分
    }


async def driver_other_cores():
    try:
        async with await connect_to_clickhouse() as client:
            date_range = pd.date_range(start="2025-12-01", end="2025-12-28")
            for date in date_range:
                start_date_ = date.to_pydatetime()
                start_date = start_date_.strftime('%Y-%m-%d')  # 转为字符串
                results1,results2=await prediction()
                start_date_str = start_date_.strftime('%Y%m%d')
                ppartition = start_date_str  # datetime.now().strftime('%Y%m%d')
                driver_profile_main_datas = await crud.Driver(client).get_abs_driver_profile_main(ppartition)
                driver_ids = []
                if driver_profile_main_datas:
                    for d in driver_profile_main_datas:
                        driver_ids.append(d['driver_id'])
                main_datas = []
                quota_scores = []
                profile_main = None
                info=results1['driver_name'].tolist()
                for i in range(len(results1['total_score'])):
                    # if info[i][1]!='63000398':
                    #     continue
                    if info[i] in driver_ids:
                        x = driver_ids.index(info[i])
                        main_id = driver_profile_main_datas[x]['id']
                        profile_main = None
                    quota_score_1 = AbsDriverQuotaScoreSub(
                        ppartition=start_date_str,#datetime.now().strftime("%Y%m%d"),
                        id=str(uuid.uuid4()),
                        main_id=main_id,
                        quota_id="驾驶员画像-服务态度",
                        quota_name="服务态度",
                        score=round(results1['total_score'][i], 2),
                        weight_rate=0.25,
                        original_value=round(results1['total_score'][i], 2)*0.25,
                        risk_data="",
                        quota_level="1",
                        parent_id="驾驶员画像",
                        creator="system",
                        create_time=datetime.now(),
                        updater="system",
                        update_time=datetime.now(),
                        deleted="0",
                        start_time=start_date_,
                        end_time=start_date_,
                    )
                    quota_scores.append(quota_score_1.to_dict())
                    for j, feat in enumerate(results1['final_scores']):
                        quota_score_3 = AbsDriverQuotaScoreSub(
                        ppartition=start_date_str,#datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id="驾驶员画像-服务态度-"+ feat,
                            quota_name=feat,
                            score=round(results1['raw_scores'][feat][j], 2),
                            weight_rate=round(results1['feat_weights'][j], 2),
                            original_value=round(results1['final_scores'][feat][j], 2),
                            risk_data="",
                            quota_level="2",
                            parent_id="驾驶员画像-服务态度" ,
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=start_date_,
                        )
                        quota_scores.append(quota_score_3.to_dict())
                    if profile_main is not None:
                        main_datas.append(profile_main.to_dict())

                    # 保存驾驶员事故风险数据

                info = results2['driver_name'].tolist()
                for i in range(len(results2['total_score'])):
                    # if info[i][1]!='63000398':
                    #     continue
                    if info[i] in driver_ids:
                        x = driver_ids.index(info[i])
                        main_id = driver_profile_main_datas[x]['id']
                        profile_main = None
                    quota_score_1 = AbsDriverQuotaScoreSub(
                        ppartition=start_date_str,#datetime.now().strftime("%Y%m%d"),
                        id=str(uuid.uuid4()),
                        main_id=main_id,
                        quota_id="驾驶员画像-安全评价",
                        quota_name="安全评价",
                        score=round(results2['total_score'][i], 2),
                        weight_rate=0.25,
                        original_value=round(results2['total_score'][i], 2)*0.25,
                        risk_data="",
                        quota_level="1",
                        parent_id="驾驶员画像",
                        creator="system",
                        create_time=datetime.now(),
                        updater="system",
                        update_time=datetime.now(),
                        deleted="0",
                        start_time=start_date_,
                        end_time=start_date_,
                    )
                    quota_scores.append(quota_score_1.to_dict())
                    for j, feat in enumerate(results2['final_scores']):
                        quota_score_3 = AbsDriverQuotaScoreSub(
                        ppartition=start_date_str,#datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id="驾驶员画像-安全评价-"+ feat,
                            quota_name=feat,
                            score=round(results2['raw_scores'][feat][j], 2),
                            weight_rate=round(results2['feat_weights'][j], 2),
                            original_value=round(results2['final_scores'][feat][j], 2),
                            risk_data="",
                            quota_level="2",
                            parent_id="驾驶员画像-安全评价" ,
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=start_date_,
                        )
                        quota_scores.append(quota_score_3.to_dict())
                    if profile_main is not None:
                        main_datas.append(profile_main.to_dict())

                await crud.Driver(client).save(main_datas, quota_scores)




    except Exception as e:
        print(f"驾驶员画像事故风险分数主程序执行出错: {e}")
    print("数据库连接已关闭")
# ==================== 10. 演示预测 ====================

async def prediction():
    try:
        async with await connect_to_clickhouse() as client:
            """演示两层分数预测"""
            print("\n"+"="*90)
            print("评分系统")
            print("="*90)

            # 重新加载数据
            # data=pd.read_csv('alldriver.csv')
            datas = await crud.Driver(client).get_drivers()
            data = pd.DataFrame(datas)

            complaints_cols=[]
            quota3 = await crud.Driver(client).get_driver_quota3('服务态度')
            for s in quota3:
                complaints_cols.append(s['quota_name'])

            complaints_cols=['车辆技术','安全管理','服务质量']

            safe_cols=[]
            quota3 = await crud.Driver(client).get_driver_quota3('安全评价')
            for s in quota3:
                safe_cols.append(s['quota_name'])
            safe_cols=['安全启动','违规使用N档','全局超速','斑马线超速','斑马线不文明礼让','区间超速','右转弯未刹车','左转弯未刹车']

            X=data.iloc[:,:4]
            X1=data.iloc[:, :3].values
            X2=data.iloc[:,3:11].values


            # 预测
            results1=calculate_two_layer_scores(
                X,X1,complaints_cols
            )

            results2=calculate_two_layer_scores(
                X,X2,safe_cols
            )
            return results1,results2
    except Exception as e:
        print(f"驾驶员画像事故风险分数主程序执行出错: {e}")
    print("数据库连接已关闭")


async def update_organ_main():
    """<UNK>"""
    try:
        async with await connect_to_clickhouse() as client:
            ppartition = "20251201"
            driver_profile_main_datas = await crud.Driver(client).get_abs_driver_profile_main(ppartition)
            driver_ids = []
            if driver_profile_main_datas:
                for d in driver_profile_main_datas:
                    driver_ids.append(d['driver_id'])
            organ_ids =  await crud.Driver(client).get_abs_driver_profile_main_organ()
            for _organ_id in organ_ids:
                if _organ_id['driver_id'] in driver_ids:
                    x = driver_ids.index(_organ_id['driver_id'])
                    organ_id = driver_profile_main_datas[x]['organ_id']
                    organ_name = driver_profile_main_datas[x]['organ_name']
                    _id = _organ_id['id']
                    if organ_id !="":
                        sql=f"""ALTER TABLE ai_security.abs_driver_profile_main UPDATE organ_id='{organ_id}',organ_name='{organ_name}' where id='{_id}'"""
                        await crud.Driver(client).execute_query(sql)


    except Exception as e:
        print(f"驾驶员能耗风险计算分数执行出错: {e}")
if __name__=="__main__":
    # 分数预测
    asyncio.run(update_organ_main())