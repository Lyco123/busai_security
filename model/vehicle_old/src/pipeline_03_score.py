# -*- coding: utf-8 -*-
"""
Script 03: Feature-level Risk Scoring & Attribution (Daily Export Version)
功能：
1. 读取特征宽表和模型权重表。
2. 对特征进行全局 Min-Max 归一化，并计算 特征风险小分。
3. 【新增】输出表1：feature_attribution (特征级归因长表)
4. 【新增】输出表2：vehicle_scoring (车辆级评分宽表，含评级)
5. 按“统计日期”每天分片输出 CSV 文件。
"""
import uuid

import pandas as pd
import sys
from datetime import datetime, timedelta

from fontTools.misc.plistlib import end_date

from core.clickhouse_connect import connect_to_clickhouse
from model.vehicle.src import crud
from model.vehicle.src.schemas.vehicle_profile import AbsBusProfileMain, AbsBusQuotaScoreSub
# --- 导入通用环境与日志 ---
from model.vehicle.src.utils.common import CONFIG_DIR, read_raw_file, smart_date, clean_id
from model.vehicle.src.utils.logger import logger
from utils.compute import Compute


class FeatureScorer:
    def __init__(self, start_date, end_date, output_base, run_date):
        """
        初始化特征评分器
        """
        self.start_date = start_date
        self.end_date = end_date
        self.run_date = run_date or datetime.now().strftime('%Y-%m-%d')
    
        # 使用传入的批次目录
        self.model_res_dir = output_base / "model_results"
        self.output_dir = output_base / "scoring_results"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 权重文件路径
        self.energy_weight_path = self.model_res_dir / "result_energy_weights.csv"
        self.fault_weight_path = self.model_res_dir / "result_fault_weights.csv"
        
        self.wide_table_path = FEATURES_DIR / "feature_wide_table.csv"
        self.df_wide = pd.DataFrame()

    def load_wide_table(self):
        if not self.wide_table_path.exists():
            raise FileNotFoundError(f"宽表未找到: {self.wide_table_path}")
        
        df = pd.read_csv(self.wide_table_path)
        original_len = len(df)
        
        # 1. 规范化日期格式并筛选日期范围
        if '信息_统计日期' in df.columns and self.start_date and self.end_date:
            df['信息_统计日期'] = pd.to_datetime(df['信息_统计日期'])
            mask = (df['信息_统计日期'] >= self.start_date) & (df['信息_统计日期'] <= self.end_date)
            df = df[mask].copy()
            # 筛选完后转回字符串格式 (YYYY-MM-DD)
            df['信息_统计日期'] = df['信息_统计日期'].dt.strftime('%Y-%m-%d')
            
            logger.info(f"📅 日期筛选 ({self.start_date} ~ {self.end_date}): {original_len} -> {len(df)} 行")
            
        if df.empty:
            raise ValueError("⚠️ 筛选后宽表数据为空，请检查日期配置！")

        df['信息_车辆ID'] = df['信息_车辆ID'].astype(str)
        self.df_wide = df

    def infer_unit(self, feature_name: str) -> str:
        """根据特征名称推断物理单位"""
        if any(k in feature_name for k in ['里程']): return 'km'
        if any(k in feature_name for k in ['时长', '时间']): return 's'
        if any(k in feature_name for k in ['次数']): return '次'
        if any(k in feature_name for k in ['点数']): return '个'
        if any(k in feature_name for k in ['能耗', '耗电']): return 'kWh/100km'
        if any(k in feature_name for k in ['压差', '电压']): return 'V'
        if any(k in feature_name for k in ['温差', '温度']): return '摄氏度'
        if any(k in feature_name for k in ['电池容量', '日充电量']): return 'kWh'
        if any(k in feature_name for k in ['车长']): return 'm'
        if any(k in feature_name for k in ['车辆自重', '重量']): return 'kg'
        if any(k in feature_name for k in ['平均速度']): return 'km/h'
        if any(k in feature_name for k in ['年龄', '车龄']): return '年'
        return '-'

    async def process_model_task(self, model_name: str, weight_path) -> pd.DataFrame:
        """处理单一模型（能耗/故障）的特征归因计算"""
        # if not weight_path.exists():
        #     logger.warning(f"未找到 {model_name} 权重文件: {weight_path.name}，跳过该模型。")
        #     return pd.DataFrame()

        #从数据库中取权重
        db_weight= await get_weights(model_name,self.start_date)
        if not db_weight:
            logger.warning(f"未找到 {model_name} 权重文件: {weight_path.name}，跳过该模型。")
            return pd.DataFrame()
        df_weight= pd.DataFrame(db_weight)
        df_weight['weight'] = df_weight['weight'].astype(float)
        # 1. 读取并归一化权重 (总和为1)
        # df_weight = pd.read_csv(weight_path)
        df_weight['weight'] = df_weight['weight'] / df_weight['weight'].sum()
        
        features = df_weight['feature'].tolist()
        features = [f for f in features if f in self.df_wide.columns]
        weight_dict = dict(zip(df_weight['feature'], df_weight['weight']))
        
        # 2. 提取子集并生成缺失值标记
        base_cols = ['信息_车辆ID', '信息_统计日期']
        df_sub = self.df_wide[base_cols + features].copy()
        
        df_missing = df_sub.copy()
        for f in features:
            df_missing[f] = df_missing[f].isna().astype(int)  # 1表示缺失，0表示正常
            
        df_sub[features] = df_sub[features].fillna(0)

        # 3. 计算 Min-Max 归一化值 (加入 1%~99% 分位数截断，防极端异常值)
        df_norm = df_sub.copy()
        for f in features:
            col_min = df_sub[f].quantile(0.01)  # 使用 1% 分位数代替绝对最小值
            col_max = df_sub[f].quantile(0.99)  # 使用 99% 分位数代替绝对最大值
            
            if col_max > col_min:
                df_norm[f] = (df_sub[f] - col_min) / (col_max - col_min)
                # 将超出范围的异常值强制拉回 0~1 之间
                df_norm[f] = df_norm[f].clip(0, 1)
            else:
                df_norm[f] = 0.0

        # 4. 逆透视 (Melt): 宽表 -> 长表
        logger.info(f"🔄 正在展开 {model_name} 特征矩阵...")
        melt_orig = df_sub.melt(id_vars=base_cols, value_vars=features, var_name='原始特征名', value_name='特征原值')
        melt_miss = df_missing.melt(id_vars=base_cols, value_vars=features, var_name='原始特征名', value_name='是否为缺失值填充')
        melt_norm = df_norm.melt(id_vars=base_cols, value_vars=features, var_name='原始特征名', value_name='特征归一化的值')

        # 5. 合并并计算得分
        res = melt_orig.merge(melt_miss, on=base_cols + ['原始特征名']) \
                       .merge(melt_norm, on=base_cols + ['原始特征名'])

        res['特征全局权重'] = res['原始特征名'].map(weight_dict)
        res['特征风险小分'] = res['特征归一化的值'] * res['特征全局权重']
        
        # 6. 整理业务输出列
        res['所属模型'] = model_name
        res['特征名称'] = res['原始特征名']
        res['数据单位'] = res['原始特征名'].apply(self.infer_unit)
        res['创建日期'] = self.run_date
        
        res.rename(columns={'信息_车辆ID': 'obuid', '信息_统计日期': '统计日期'}, inplace=True)

        final_cols = [
            'obuid', '统计日期', '所属模型', '特征名称', 
            '特征原值', '特征归一化的值', '特征全局权重', 
            '特征风险小分', '数据单位', '是否为缺失值填充', '创建日期'
        ]
        
        return res[final_cols]

    def build_vehicle_scoring(self, df_attribution: pd.DataFrame,w_energy:float =0.6,w_fault:float = 0.4) -> pd.DataFrame:
        """
        通过汇总特征小分，计算车辆级的最终风险分与评级
        """
        logger.info("🧮 正在计算车辆级总体风险分与评级...")
        
        # 1. 按 (日期, 车辆, 模型) 对特征小分求和
        agg_scores = df_attribution.groupby(['统计日期', 'obuid', '所属模型'])['特征风险小分'].sum().reset_index()
        
        # 2. 透视表：将 能耗模型 和 故障模型 展开为两列
        pivot_scores = agg_scores.pivot(index=['统计日期', 'obuid'], columns='所属模型', values='特征风险小分').fillna(0).reset_index()
        
        # 容错：防止某个模型缺失
        if '能耗模型' not in pivot_scores.columns: pivot_scores['能耗模型'] = 0.0
        if '故障模型' not in pivot_scores.columns: pivot_scores['故障模型'] = 0.0
            
        # 3. 映射到百分制 (0-100分)
        pivot_scores['能耗风险分'] = (pivot_scores['能耗模型'] * 100).round(2)
        pivot_scores['故障风险分'] = (pivot_scores['故障模型'] * 100).round(2)
        
        # 4. 计算总风险分 (默认取能耗与故障的平均风险)
        pivot_scores['总风险分'] = (w_energy * pivot_scores['能耗风险分'] + w_fault * pivot_scores['故障风险分']).round(2)
        
        # 5. 生成评级 (Rating Logic)
        def get_risk_rating(score):
            if score >= 75: return '高风险'
            elif score >= 50: return '中等风险'
            elif score >= 25: return '低风险'
            else: return '安全'
            
        pivot_scores['评级'] = pivot_scores['总风险分'].apply(get_risk_rating)
        pivot_scores['创建日期'] = self.run_date
        
        return pivot_scores[['统计日期', 'obuid', '能耗风险分', '故障风险分', '总风险分', '评级', '创建日期']]

    async def run(self):
        self.load_wide_table()

        # 1. 生成长表 (feature_attribution)
        df_energy_attr = await self.process_model_task('能耗风险', self.energy_weight_path)
        df_fault_attr  = await self.process_model_task('故障风险', self.fault_weight_path)


        
        df_attribution = pd.concat([df_energy_attr, df_fault_attr], ignore_index=True)
        if df_attribution.empty:
            logger.error("❌ 没有生成任何归因数据。")
            return

        # 优化浮点数精度以减小文件体积
        float_cols = ['特征原值', '特征归一化的值', '特征全局权重', '特征风险小分']
        df_attribution[float_cols] = df_attribution[float_cols].round(6)
        df_attribution.sort_values(['统计日期', 'obuid', '所属模型', '特征名称'], inplace=True)

        # 2. 生成宽表 (vehicle_scoring)
        df_scoring = self.build_vehicle_scoring(df_attribution)

        # 3. 按日分片输出 (双表同频导出)
        logger.info(f"📦 准备按日分片导出结果数据...")
        unique_dates = df_attribution['统计日期'].unique()
        
        for date_str in sorted(unique_dates):
            # 导出表1: Feature Attribution
            day_attr = df_attribution[df_attribution['统计日期'] == date_str]
            attr_path = self.output_dir / f"feature_attribution_{date_str}.csv"
            day_attr.to_csv(attr_path, index=False, encoding='utf-8-sig')
            
            # 导出表2: Vehicle Scoring
            day_score = df_scoring[df_scoring['统计日期'] == date_str]
            score_path = self.output_dir / f"vehicle_scoring_{date_str}.csv"
            day_score.to_csv(score_path, index=False, encoding='utf-8-sig')

            # 车辆评分入库
            day_score_dicts=day_score.to_dict("records")
            day_attr_dists=day_attr.to_dict("records")

            await save_scores_old(day_score_dicts,day_attr_dists,date_str,self.start_date)
            
            logger.info(f"💾 已保存 {date_str} 数据分片: 归因明细 {len(day_attr)}行, 车辆评分 {len(day_score)}行")
            
        logger.info(f"🎉 评分模块执行完毕！共生成 {len(unique_dates) * 2} 个文件。")

async def get_weights(model_name,start_time:str):
    try:
        async with await connect_to_clickhouse() as client:
            quota3_datas = await crud.Vehicle(client).get_vehicle_quota3(model_name,start_time)
            return quota3_datas
    except Exception as e:
        logger.error("车辆画像主程序执行出错", exc_info=True)
        print(f"车辆画像主程序执行出错: {e}")
        return None
    print("数据库连接已关闭")

async def save_scores_old(result,start_time,end_time,start_date):
        # 使用异步上下文管理器方式
        try:
            async with await connect_to_clickhouse() as client:

                quota1_datas = await crud.Vehicle(client).get_vehicle_quota1(None,start_date)
                quota2_datas = await crud.Vehicle(client).get_vehicle_quota2(None,start_date)
                quota3_datas = await crud.Vehicle(client).get_vehicle_quota3(None,start_date)
                # 解析开始日期
                start_date_ = datetime.strptime(start_time, '%Y-%m-%d')
                end_date_ = datetime.strptime(end_time, '%Y-%m-%d')
                end_date_str = end_date_.strftime('%Y%m%d')
                main_datas = []
                quota_scores = []
                profile_main = None
                feature_names=[]
                # for day_attr_dict in day_attr_dists:
                #     if day_attr_dict['特征名称'].count('_') == 2:
                #         feature=Compute.process_vehicle_string(day_attr_dict['特征名称'],0)
                #     else:
                #         feature=day_attr_dict['特征名称']
                #     feature_names.append(day_attr_dict['obuid']+"_"+day_attr_dict['所属模型'].replace("模型","风险")+"_"+feature)
                for score in result['final_contrib_df']:
                    main_id = str(uuid.uuid4())
                    profile_main = AbsBusProfileMain(
                        ppartition=end_date_str,
                        id=main_id,
                        bus_id =score['obuid'],
                        bus_name="",
                        organ_id="",
                        organ_name="",
                        calculate_date=end_date_,  # datetime.combine(datetime.now().date(), datetime.min.time()),
                        evalutaion_type="",
                        score=round(score['总风险分']),
                        suggested_content="",
                        creator="system",
                        create_time=datetime.now(),
                        updater="system",
                        update_time=datetime.now(),
                        deleted="0"
                    )
                    for m in quota1_datas:
                        weight_rate1 = float(m['weight_rate1'] / 100)
                        if weight_rate1 == 0:
                            _score = 0
                        else:
                            _score = round(score[m['quota_name']] / weight_rate1, 2)
                        quota_score_1 = AbsBusQuotaScoreSub(
                            ppartition=end_date_str,  # datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id=m['quota_id'],
                            quota_name=m['quota_name'],
                            score=_score,
                            weight_rate=weight_rate1,
                            # original_value=round(route_score[score_name],2)*weight_rate1,
                            original_value=round(score[m['quota_name']+"分"],2),
                            risk_data="",
                            quota_level="1",
                            parent_id="车辆画像",
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=end_date_,
                        )
                        quota_scores.append(quota_score_1.to_dict())
                    for m in quota2_datas:
                        weight_rate2 = float(m['weight_rate2'] / 100)
                        weight_rate1 = float(m['weight_rate1'] / 100)
                        if weight_rate1 * weight_rate2 == 0:
                            _score = 0
                        else:
                            _score =0
                        quota_score_1 = AbsBusQuotaScoreSub(
                            ppartition=end_date_str,  # datetime.now().strftime("%Y%m%d"),
                            id=str(uuid.uuid4()),
                            main_id=main_id,
                            quota_id=m['quota_id'],
                            quota_name=m['quota_name'],
                            score=_score,
                            weight_rate=weight_rate1 * weight_rate2,
                            # original_value=round(route_score[score_name],2)*weight_rate1*weight_rate2,
                            original_value=0,
                            risk_data="",
                            quota_level="2",
                            parent_id=m['parent_id'],
                            creator="system",
                            create_time=datetime.now(),
                            updater="system",
                            update_time=datetime.now(),
                            deleted="0",
                            start_time=start_date_,
                            end_time=end_date_,
                        )
                        quota_scores.append(quota_score_1.to_dict())
                    filter_company_quota1_scores = [d for d in day_attr_dists if d.get("obuid") == score['obuid']]
                    for x in filter_company_quota1_scores:
                    # for x in quota3_datas:
                    #     weight_rate3 = float(x['weight_rate3'] / 100)
                    #     weight_rate2 = float(x['weight_rate2'] / 100)
                    #     weight_rate1 = float(x['weight_rate1'] / 100)
                    #     if score['obuid']+"_"+x['quota_name'] in feature_names:
                    #         n=feature_names.index(score['obuid']+"_"+x['quota_name'])
                        if x['特征名称'].count('_') == 2:
                            feature=Compute.process_vehicle_string(day_attr_dict['特征名称'],0)
                        else:
                            feature=x['特征名称']

                            feature_name=Compute.process_vehicle_string(feature,1)
                            parent_name=Compute.process_vehicle_string(feature,0)
                            quota_score_3 = AbsBusQuotaScoreSub(
                                ppartition=end_date_str,  # datetime.now().strftime("%Y%m%d"),
                                id=str(uuid.uuid4()),
                                main_id=main_id,
                                quota_id='车辆画像'+'_'+x['所属模型']+'_'+feature,
                                quota_name=feature_name,
                                # score=_score,
                                score=round(x["特征归一化的值"], 2),
                                weight_rate=round(x["特征全局权重"], 2),
                                # original_value=round(route_score[score_name3], 2)*weight_rate1*weight_rate2*weight_rate3,
                                original_value=round(x["特征风险小分"], 2),
                                risk_data=str(x["特征原值"]),
                                quota_level="3",
                                parent_id='车辆画像'+'_'+x['所属模型']+'_'+parent_name,
                                creator="system",
                                create_time=datetime.now(),
                                updater="system",
                                update_time=datetime.now(),
                                deleted="0",
                                start_time=start_date_,
                                end_time=end_date_,
                            )
                            quota_scores.append(quota_score_3.to_dict())
                    if profile_main is not None:
                        main_datas.append(profile_main.to_dict())
                await crud.Vehicle(client).save(main_datas, quota_scores)

        except Exception as e:
            logger.error("车辆画像主程序执行出错", exc_info=True)
            print(f"车辆画像主程序执行出错: {e}")
        print("数据库连接已关闭")

if __name__ == "__main__":
    from model.vehicle.src.utils.common import get_pipeline_args, OUT_DIR
    args = get_pipeline_args("模块3：特征归因与评分")
    
    output_base = OUT_DIR / f"run_{args.run_date}"
    output_base.mkdir(parents=True, exist_ok=True)
    FeatureScorer(args.start_date, args.end_date, output_base, args.run_date).run()