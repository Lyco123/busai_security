import datetime
import time

import pandas as pd
from clickhouse_driver import Client
import utils
from application.settings import DB_CONFIG
from core.clickhouse_manage import ClickHouseManage
from utils import postgres_query
import utils.candata_convert
import csv
import numpy as np

def to_cancsv(can_datas):
    # 创建查询对象
    db_query = postgres_query.PostgreSQLQuery()

    # 连接数据库（可指定默认模式）
    if not db_query.connect(schema=DB_CONFIG['schema']):
        return

    try:
        # 示例查询1: 使用默认模式查询
        print("\n=== 使用默认模式查询用户 ===")

        lines = db_query.execute_query("select * from baseinfo_can")
    except Exception as e:
        print(f"操作过程中出现错误: {e}")


    datas=can_datas.get('canList')
    data_cans=[]
    valid_data=[]
    j=0
    for data in datas:
       data_can={}
       j = j + 1
       for i, line in enumerate(lines):
           data_tuple = (
               str(line['moudle']),
               str(line['id']),
               str(line['data_name']),
               str(data.get(line['id'],'')),
               str(can_datas.get('obuid')),
               str(timestamp_to_datetime(can_datas.get('reportTime')*1000)),
               str(timestamp_to_datetime(data['timespan'])),
               str(j),
               datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
           )
           valid_data.append(data_tuple)

    try:
        # 示例查询1: 使用默认模式查询
        print("\n=== 使用默认模式查询用户 ===")
        insert_query = "INSERT INTO can_infos (moudle, id, data_name, value, obuid, report_time, data_time,idx,insert_time) VALUES (%s, %s, %s, %s, %s, %s, %s,%s,%s)"
        lines = db_query.execute_update_batch(insert_query,valid_data)
    except Exception as e:
        print(f"操作过程中出现错误: {e}")
    finally:
        # 关闭连接
        db_query.disconnect()

async def to_cancsv_ck(db: Client, can_datas,obuid,reporttime,ppartition):
    # 创建管理实例
    manager = ClickHouseManage(db, "obs_baseinfo_can")

    try:
        lines = await manager.get_datas(1,0)
    except Exception as e:
        print(f"操作过程中出现错误: {e}")

    datas=can_datas.get('canList')
    data_cans=[]
    valid_data=[]
    j=0
    for data in datas:
       j = j + 1
       for i, line in enumerate(lines):
           data_can={}
           data_can['ppartition'] = ppartition #datetime.datetime.now().strftime("%Y%m%d")
           data_can['moudle'] = line['moudle']
           data_can['id']=line['id']
           data_can['data_name']=line['data_name']
           try:
                data_can['value']=float(data.get(line['id'],0))
           except Exception as e:
               data_can['value']=0
           data_can['obuid']=obuid #can_datas.get('obuid')
           data_can['report_time']=reporttime #timestamp_to_datetime(can_datas.get('reportTime')*1000)
           data_can['data_time']=timestamp_to_datetime(data['timespan'])
           data_can['idx']=str(j)
           data_can['insert_time']=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
           data_cans.append(data_can)

    # list_dict_to_csv(data_cans,"can_datas_1.csv")
    try:
        print("解压开始时间2：" + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        df= await utils.candata_convert.data_convert(data_cans)
        datas=df.to_dict('records')
        print("解压结束时间2：" + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        print(f"操作过程中出现错误: {e}")
    # try:
    #     batch_insert(db,df,"abs_can_stats_result",1)
    # except Exception as e:
    #     print(f"操作过程中出现错误: {e}")
    # 删除不需要的字段
    cols=[]
    cols.append('ppartition')
    cols.append('data_time')
    cols.append('obuid')
    cols.append('report_time')
    cols.append('insert_time')
    cols.append('data_start_time')
    cols.append('data_end_time')
    cols.append('data_duration_minutes')
    for col in lines:
        cols.append(col['id'])

    filtered_datas=filter_dict_fields(datas,cols)
    if len(filtered_datas)>0:
        try:
            columns = list(filtered_datas[0].keys())
            for data in filtered_datas:
                for col in columns:
                    value = data.get(col, None)
                    # 判断字段是否为 int 或 float 类型
                    if isinstance(value, (int, float)):
                        data[col]=str(value)
            manager = ClickHouseManage(db, "abs_can_stats_result")
            cans = await manager.batch_insert("abs_can_stats_result",filtered_datas, batch_size=len(filtered_datas))
        except Exception as e:
            print(f"操作过程中出现错误: {e}")


def batch_insert(client, df, table_name, batch_size=10000):
    # 确保 batch_size 是正整数，避免 range() 参数错误
    if batch_size <= 0:
        raise ValueError("batch_size 必须大于 0")

    # 处理时间列，避免 'str' object has no attribute 'tzinfo' 错误
    df_copy = df.copy()
    for col in df_copy.columns:
        if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
            # 将datetime64转换为字符串，避免时区相关问题
            df_copy[col] = df_copy[col].dt.strftime('%Y-%m-%d %H:%M:%S')

    for i in range(0, len(df_copy), batch_size):
        batch = df_copy.iloc[i:i + batch_size]
        client.execute(
            f"INSERT INTO {table_name} VALUES",
            batch.to_dict('records')
        )
        print(f"已写入 {min(i + batch_size, len(df_copy))} 条")



def timestamp_to_datetime(timestamp):
    # 将毫秒级时间戳转换为秒级
    timestamp_seconds = timestamp / 1000.0
    # 转换为datetime对象
    dt = date_to_string(datetime.datetime.fromtimestamp(timestamp_seconds))
    return dt

def date_to_string(date_obj, format_str="%Y-%m-%d %H:%M:%S"):
    """将日期对象转换为字符串"""
    return date_obj.strftime(format_str)


def filter_dict_fields(datas, cols):
    """
    过滤字典列表中字段名不以lines中元素开头的字段

    Args:
        datas (list): 字典列表
        cols (list): 行标识列表

    Returns:
        list: 过滤后的字典列表
    """
    valid_fields = set()
    for line in cols:
        valid_fields.add(line)

    # 过滤每个字典的字段
    filtered_datas = []
    for data in datas:
        if data['obuid']==None:
            continue
        filtered_dict = {}
        for key, value in data.items():
            if  key in valid_fields:
                if value!=None :
                    filtered_dict[key] = value
        filtered_datas.append(filtered_dict)

    return filtered_datas


def list_dict_to_csv(data, filename):
    """
    将包含字典的列表转换为CSV文件
    data: 字典列表，每个字典代表一行数据
    filename: 输出的CSV文件名
    """
    if not data:
        return

    # 获取所有可能的字段名
    fieldnames = set()
    for item in data:
        fieldnames.update(item.keys())

    # 转换为列表并排序，确保字段顺序一致
    fieldnames = sorted(list(fieldnames))

    try:

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
    except Exception as e:
        print(f"导数出现错误: {e}")

def main():
    return True
if __name__ == "__main__":
    main()