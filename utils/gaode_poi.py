import re
from typing import List, Dict

import requests
import json
import os
import math
from concurrent.futures import ThreadPoolExecutor
import csv
from collections import OrderedDict

from application.settings import DB_CONFIG
from utils import postgres_query
from utils.poi_batch_insert_fix import POIBatchInserter

# 全局变量
KEYS = ["a79c211b5e620b25bc359bdf0431bfa9",
        "18fd03c573d8881d9adf323d437b681a",
        "8a1008cb384566cc62da729a08f45bd0",
        "f0f26dd79771297659d8efb17279bb59",
        "ea6c6dc6dbb566f21bf469ee11ec79ad",
        "075a56d726f76f8d1121f9465f428ca",
        "29aab94118487375baeca85b027a36b5",
        "197e15f7a48e8e9d54935335ed0b6a16",
        "0fe9674ec14dd7449427652adbd319eb",
        "800eed488f181a693df7da2881479cf3",
        "60a67fff2ff0dbc6792d56ea5ed79fb1",
        "24b1f1b244cfe781840254a04ea5095e",
        "c877aaf63ff33fc20e83738a676b87bc",
        "6dbf3330f7a760234fa6f7576051923f",
        "7c8679499e97faa5f5a5fc9f421bbd7d",
        "82a1c8d6141a716ebee2ffba500389ad",
        "016c368d018f93ed4cb08c000e0d8ab9",
        "7ab44f08f006db5b08d1f86b2f900b66"]  # 这里放置多个API Key
# KEYS = ["18fd03c573d8881d9adf323d437b681a"]  # 这里放置多个API Key
SAVE_DIR = r"E:\data\gaode\data"  # 数据保存目录
GRID_SIZE = 0.01 # 网格大小为0.005度
KEYWORD = "体育馆"  # 查询关键字
NUM_THREADS = 4  # 线程数量，可以根据需求调整

def file_exists(polygon, keyword, page):
    """检查文件是否已经存在"""
    lng_min, lat_min = polygon[0][0], polygon[2][1]
    filename = f"{SAVE_DIR}/poi_{lng_min}_{lat_min}_{keyword}_page{page}.geojson"
    return os.path.exists(filename)

def save_poi_data(polygon, keyword, page, data,line):
    """保存POI数据到GeoJSON文件"""
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)
    lng_min, lat_min = polygon[0][0], polygon[2][1]
    filename = f"{SAVE_DIR}/poi_{lng_min}_{lat_min}_{keyword}_page{page}.geojson"
    filename_csv = f"{SAVE_DIR}/poi_{lng_min}_{lat_min}_{keyword}_page{page}.csv"
    list_pois=data.get("pois", [])
    poi_datas=[]
    for poi in list_pois:
        poi_data=parse_poi_data(filename_csv,poi)
        poi_datas.append(poi_data.values())

    column_names=['filename','address','adname','cityname','id','keytag','location','name','pname','tel','type','typecode']

    save_poi_data_db(list_pois,line,lng_min,lat_min,keyword);
    # # 写入CSV文件
    # with open(filename_csv, 'w', newline='', encoding='utf-8') as csvfile:
    #     writer = csv.writer(csvfile)
    #     # 写入表头
    #     writer.writerow(column_names)
    #     # 写入数据行
    #     writer.writerows(poi_datas)
    #
    # with open(filename, "w", encoding="utf-8") as f:
    #     json.dump(data, f, ensure_ascii=False, indent=4)
    # return True


def save_poi_data_db(poi_datas: List[Dict],line,lng_min,lat_min,keyword):
    # 创建插入器并执行插入
    inserter = POIBatchInserter(DB_CONFIG, schema='bus_ai')
    sample_poi_data=[]
    for poi in poi_datas:
        aaa = inserter.execute_query("select * from poi_data_gym where id= '"+poi['id']+"'")
        if aaa==[] or aaa==0:
            poi['org_name']=line['org_name']
            poi['use_org_name']=line['use_org_name']
            poi['line_code']=line['line_code']
            poi['line_name']=line['line_name']
            poi['direction']=line['direction']
            poi['lng_min']=str(lng_min)
            poi['lat_min']=str(lat_min)
            poi['keyword']=keyword
            sample_poi_data.append(poi)
    inserted_count = inserter.save_poi_data(sample_poi_data)
    print(f"总共成功插入 {inserted_count} 条记录")

def parse_poi_data(filepath, data):
    """
    解析POI数据并生成有序字典
    :param filepath: 文件路径
    :param data: POI数据字典
    :return: 有序字典
    """

    poi_info = OrderedDict([
        ('filepath', filepath),
        ('address', data.get('address')),
        ('adname', data.get('adname')),
        ('cityname', data.get('cityname')),
        ('id', data.get('id')),
        ('keytag', data.get('keytag')),
        ('location', data.get('location')),
        ('name', data.get('name')),
        ('pname', data.get('pname')),
        ('tel', data.get('tel')),
        ('type', data.get('type')),
        ('typecode', data.get('typecode'))
    ])
    return poi_info

def fetch_poi_data(polygon, key, keyword,line):
    """获取POI数据，支持分页"""
    lng_min, lat_min = polygon[0][0], polygon[2][1]
    page = 1
    inserter = POIBatchInserter(DB_CONFIG, schema='bus_ai')
    aaa = inserter.execute_query(
        "select * from poi_data_gym where lng_min= '" + str(lng_min) + "' and lat_min='" + str(lat_min) + "'")
    # aaa = inserter.execute_query(
    #     "select * from poi_data where line_code= '" +line.get('line_code') + "' and line_name='" + line.get('line_name') + "'")
    if aaa != [] and aaa != 0:
        # if file_exists(polygon, keyword, page):
        print(f"文件已存在，跳过：网格: {polygon}，页数: {page}")
        return True
    while True:
        polygon_str = f"{lng_min},{lat_min}|{polygon[1][0]},{polygon[1][1]}"
        api_url = f"https://restapi.amap.com/v3/place/polygon?polygon={polygon_str}&keywords={keyword}&key={key}&page={page}"

        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()

            infocode = data.get("infocode")
            if infocode == "10000" and data.get("pois"):
                save_poi_data(polygon, keyword, page, data,line)
                print(f"下载成功！网格: {polygon_str}，页数: {page}")
                page += 1
                if len(data.get("pois")) < 20:  # 当POI数据少于20时，说明已经是最后一页
                    break
            elif infocode in ["10001", "10003", "10004","10044","10009"]:
                print(f"Key :{key} 出现问题，infocode: {infocode}，信息: {data.get('info')}切换到下一个Key进行重试...")
                return False  # 返回False以便切换Key进行重试
            else:
                print(f"请求失败或无数据，infocode: {infocode}，信息: {data.get('info')}")
                break
        except Exception as e:
            print(f"请求异常，跳过此Key：{str(e)}")
            break
    return True  # 下载成功或完成所有页数时返回True


def convert_coordinates(input_str):
    # 使用正则表达式替换字符
    cleaned_str = re.sub(r'\{', '[', input_str)
    cleaned_str = re.sub(r'\}', ']', cleaned_str)
    cleaned_str = re.sub(r'\s*,\s*', ',', cleaned_str)
    cleaned_str = re.sub(r'\s+', '', cleaned_str)

    # 转换为Python列表
    result = eval(cleaned_str)
    return result

def generate_grids(polygon_coords):
    """生成网格"""
    min_lng = min([coord[0] for coord in polygon_coords])
    max_lng = max([coord[0] for coord in polygon_coords])
    min_lat = min([coord[1] for coord in polygon_coords])
    max_lat = max([coord[1] for coord in polygon_coords])

    grids = []
    lng_steps = math.ceil((max_lng - min_lng) / GRID_SIZE)
    lat_steps = math.ceil((max_lat - min_lat) / GRID_SIZE)

    for i in range(lng_steps):
        for j in range(lat_steps):
            grid_min_lng = min_lng + i * GRID_SIZE
            grid_max_lng = min(grid_min_lng + GRID_SIZE, max_lng)
            grid_min_lat = min_lat + j * GRID_SIZE
            grid_max_lat = min(grid_min_lat + GRID_SIZE, max_lat)
            grid_polygon = [[grid_min_lng, grid_max_lat], [grid_max_lng, grid_max_lat], [grid_max_lng, grid_min_lat], [grid_min_lng, grid_min_lat]]
            grids.append(grid_polygon)
    return grids

def download_poi_for_grid(polygon, key, keyword,line):
    """下载单个网格的POI数据"""
    print(f"Key :{key}")
    success = fetch_poi_data(polygon, key, keyword,line)
    if not success:
        return False  # 返回False以便线程外层处理Key切换
    return True

def main():
    # 创建查询对象
    db_query = postgres_query.PostgreSQLQuery()

    # 连接数据库（可指定默认模式）
    if not db_query.connect(schema='bus_ai'):
        return

    try:
        # 示例查询1: 使用默认模式查询
        print("\n=== 使用默认模式查询用户 ===")

        lines = db_query.execute_query("SELECT lr.* FROM line_range lr WHERE lr.bz_gym IS NULL AND lr.direction = '上行' "
                                       "AND NOT EXISTS (SELECT 1 FROM poi_data_gym pd WHERE pd.line_code = lr.line_code "
                                       " AND pd.line_name = lr.line_name) AND EXISTS (select 1  from v_route_202601081234 rt where rt.route_id=lr.line_code) order by line_code desc ")
        for line in lines:
            polygon_coords=line.get('points',[])
            print(f"查询线路{line.get('line_code')}-{line.get('line_name')}")
            grids = generate_grids(polygon_coords)
            key_idx = 0
            for idx, grid in enumerate(grids):
                print(idx)
                # while key_idx < len(KEYS):
                key = KEYS[key_idx]
                future=download_poi_for_grid(grid, key, KEYWORD,line)
                if future==False:
                    key_idx += 1
                    if key_idx == len(KEYS)-1:
                        print(f"所有Key均不可用，跳过此网格: {grid}")
                        return
                    print(f"key_idx: {key_idx}")
                    key = KEYS[key_idx]
                    future = download_poi_for_grid(grid, key, KEYWORD, line)

            n=db_query.execute_update_sql("update line_range set bz_gym=1 where line_code='" + line['line_code'] + "'")
            print(f"总共成功插入 {n} 条记录")
    except Exception as e:
        print(f"操作过程中出现错误: {e}")
    finally:
        # 关闭连接
        db_query.disconnect()
if __name__ == "__main__":
    main()