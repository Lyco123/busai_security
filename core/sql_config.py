from datetime import datetime,timedelta


def insert_driver_behavior_month(start_date_str: str,end_date_str: str) -> str:
    # 解析结束日期
    start_date=datetime.strptime(start_date_str,'%Y-%m-%d')
    # 计算开始日期
    end_date=datetime.strptime(end_date_str,'%Y-%m-%d')
    # 格式化为YYYYMMDD格式
    start_date_str=start_date.strftime('%Y%m%d')
    end_date_str=end_date.strftime('%Y%m%d')
    sql=f"""
    insert into ai_security.ods_communication_driver_behavior_month
    (ppartition, report_type, report_sub_type, report_time,obuid, operator_code, latitude, longitude, speed, 
    direction, station_code, create_time, id )
    select
    ppartition,report_type,report_sub_type,report_time,obuid, operator_code, latitude, longitude, speed, direction, 
    station_code, create_time, id from canbus.ods_communication_driver_behavior 
    where ppartition  between '{start_date_str}' and '{end_date_str}'
    """
    return sql.strip()
#一周驾驶行为
def driver_behavior_week_query(start_date_str: str,end_date_str: str) -> str:
    # 解析结束日期
    start_date=datetime.strptime(start_date_str,'%Y-%m-%d')
    # 计算开始日期
    end_date=datetime.strptime(end_date_str,'%Y-%m-%d')
    # 格式化为YYYYMMDD格式
    start_date_str=start_date.strftime('%Y%m%d')
    end_date_str=end_date.strftime('%Y%m%d')

    # 构建SQL查询
    sql=f"""
    with cet as (select c.operator_code,c.obuid,c.ppartition,formatDateTime(c.report_time,'%%Y-%%m-%%d') as report_time, '{start_date_str}' as start_time,'{end_date_str}' as end_time,
      SUM(CASE WHEN c.report_type = 1 THEN 1 ELSE 0 END) AS report_type1_count,
      SUM(CASE WHEN c.report_type = 2 THEN 1 ELSE 0 END) AS report_type2_count,
      SUM(CASE WHEN c.report_type = 3 THEN 1 ELSE 0 END) AS report_type3_count,
      SUM(CASE WHEN c.report_type = 4 THEN 1 ELSE 0 END) AS report_type4_count,
      SUM(CASE WHEN c.report_type = 5 THEN 1 ELSE 0 END) AS report_type5_count,
      SUM(CASE WHEN c.report_type = 6 THEN 1 ELSE 0 END) AS report_type6_count,
      SUM(CASE WHEN c.report_type = 7 THEN 1 ELSE 0 END) AS report_type7_count,
      SUM(CASE WHEN c.report_type = 8 THEN 1 ELSE 0 END) AS report_type8_count,
      SUM(CASE WHEN c.report_type = 9 THEN 1 ELSE 0 END) AS report_type9_count,
      SUM(CASE WHEN c.report_type = 10 THEN 1 ELSE 0 END) AS report_type10_count,
      SUM(CASE WHEN c.report_type = 11 THEN 1 ELSE 0 END) AS report_type11_count,
      SUM(CASE WHEN c.report_type = 12 THEN 1 ELSE 0 END) AS report_type12_count,
      SUM(CASE WHEN c.report_type = 13 THEN 1 ELSE 0 END) AS report_type13_count,
      SUM(CASE WHEN c.report_type = 14 THEN 1 ELSE 0 END) AS report_type14_count,
      SUM(CASE WHEN c.report_type = 15 THEN 1 ELSE 0 END) AS report_type15_count,
      SUM(CASE WHEN c.report_type = 16 THEN 1 ELSE 0 END) AS report_type16_count,
      SUM(CASE WHEN c.report_type = 17 THEN 1 ELSE 0 END) AS report_type17_count,
      SUM(CASE WHEN c.report_type = 18 THEN 1 ELSE 0 END) AS report_type18_count,
      SUM(CASE WHEN c.report_type = 19 THEN 1 ELSE 0 END) AS report_type19_count,
      SUM(CASE WHEN c.report_type = 20 THEN 1 ELSE 0 END) AS report_type20_count,
      SUM(CASE WHEN c.report_type = 21 THEN 1 ELSE 0 END) AS report_type21_count,
      SUM(CASE WHEN c.report_type = 22 THEN 1 ELSE 0 END) AS report_type22_count,
      SUM(CASE WHEN c.report_type = 23 THEN 1 ELSE 0 END) AS report_type23_count,
      SUM(CASE WHEN c.report_type = 24 THEN 1 ELSE 0 END) AS report_type24_count,
      SUM(CASE WHEN c.report_type = 25 THEN 1 ELSE 0 END) AS report_type25_count,
      SUM(CASE WHEN c.report_type = 26 THEN 1 ELSE 0 END) AS report_type26_count,
      SUM(CASE WHEN c.report_type = 27 THEN 1 ELSE 0 END) AS report_type27_count,
      SUM(CASE WHEN c.report_type = 28 THEN 1 ELSE 0 END) AS report_type28_count,
      SUM(CASE WHEN c.report_type = 29 THEN 1 ELSE 0 END) AS report_type29_count,
      SUM(CASE WHEN c.report_type = 30 THEN 1 ELSE 0 END) AS report_type30_count,
      SUM(CASE WHEN c.report_type = 31 THEN 1 ELSE 0 END) AS report_type31_count,
      SUM(CASE WHEN c.report_type = 32 THEN 1 ELSE 0 END) AS report_type32_count,
      SUM(CASE WHEN c.report_type = 33 THEN 1 ELSE 0 END) AS report_type33_count,
      SUM(CASE WHEN c.report_type = 34 THEN 1 ELSE 0 END) AS report_type34_count,
      SUM(CASE WHEN c.report_type = 36 THEN 1 ELSE 0 END) AS report_type36_count,
      SUM(CASE WHEN c.report_type = 37 THEN 1 ELSE 0 END) AS report_type37_count
  from ai_security.ods_communication_driver_behavior_month c 
  where  ppartition between '{start_date_str}' and '{end_date_str}'
   group by c.operator_code,c.obuid,c.ppartition,formatDateTime(c.report_time,'%%Y-%%m-%%d'))
select operator_code,obuid,ppartition,report_time,start_time,end_time,
report_type1_count,report_type2_count,report_type3_count,report_type4_count,
report_type5_count,report_type6_count,
report_type7_count,report_type8_count,report_type9_count,report_type10_count,report_type11_count,report_type12_count,
report_type13_count,report_type14_count,report_type15_count,report_type16_count,report_type17_count,report_type18_count,
report_type19_count,report_type20_count,report_type21_count,report_type22_count,report_type23_count,report_type24_count,
report_type25_count,report_type26_count,report_type27_count,report_type28_count,report_type29_count,report_type30_count,
report_type31_count,report_type32_count,
report_type33_count,report_type34_count,report_type36_count,report_type37_count,
ROW_NUMBER() OVER (ORDER BY operator_code, obuid, ppartition, report_time) AS row_num 
from cet 
  """
    return sql.strip()


def driver_behavior_month_init_query(start_date_str: str, end_date_str:str) -> str:
  # 解析结束日期
  start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
  # 计算开始日期
  end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
  # 格式化为YYYYMMDD格式
  start_date_str = start_date.strftime('%Y%m%d')
  end_date_str = end_date.strftime('%Y%m%d')

  # 构建SQL查询
  sql = f"""
    select ppartition,report_type,report_sub_type,report_time,obuid,operator_code,
    latitude,longitude,speed,direction,station_code,create_time,id
    from ai_security.ods_communication_driver_behavior_month
    where  ppartition between '{start_date_str}' and '{end_date_str}'
  """
  return sql.strip()

#驾驶员，线路，驾驶行为，里程一周汇总
def driver_behavior_energy_report_sum(start_date_str: str,end_date_str: str) -> str:
    # # 解析结束日期
    # start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    # end_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    # # 格式化为YYYYMMDD格式
    # start_date_str = start_date.strftime('%Y%m%d')
    # end_date_str = end_date.strftime('%Y%m%d')

    sql=f"""
  with cet as (select c.ppartition as ppartition, b.employee_number as employee_number ,b.employee_id as employee_id,b.employee_name as employee_name ,b.qualification_no,
  max(c.report_time) as report_time,
  sum(c.report_type1_count) as report_type1_count,sum(c.report_type2_count) as report_type2_count,sum(c.report_type3_count) as report_type3_count,sum(c.report_type4_count) as report_type4_count,
  sum(c.report_type5_count) as report_type5_count,sum(c.report_type6_count) as report_type6_count,sum(c.report_type7_count) as report_type7_count,sum(c.report_type8_count) as report_type8_count,
  sum(c.report_type9_count) as report_type9_count,sum(c.report_type10_count) as report_type10_count,sum(c.report_type11_count) as report_type11_count,sum(c.report_type12_count) as report_type12_count,
  sum(c.report_type13_count) as report_type13_count,sum(c.report_type14_count) as report_type14_count,sum(c.report_type15_count) as report_type15_count,sum(c.report_type16_count) as report_type16_count,
  sum(c.report_type17_count) as report_type17_count,sum(c.report_type18_count) as report_type18_count,sum(c.report_type19_count) as report_type19_count,sum(c.report_type20_count) as report_type20_count,
  sum(c.report_type21_count) as report_type21_count,sum(c.report_type22_count) as report_type22_count,sum(c.report_type23_count) as report_type23_count,sum(c.report_type24_count) as report_type24_count,
  sum(c.report_type25_count) as report_type25_count,sum(c.report_type26_count) as report_type26_count,sum(c.report_type27_count) as report_type27_count,sum(c.report_type28_count) as report_type28_count,
  sum(c.report_type29_count) as report_type29_count,sum(c.report_type30_count) as report_type30_count,
  sum(c.report_type31_count) as report_type31_count,sum(c.report_type32_count) as report_type32_count,
  sum(c.report_type33_count) as report_type33_count,sum(c.report_type34_count) as report_type34_count, 
  sum(c.report_type36_count) as report_type36_count,sum(c.report_type37_count) as report_type37_count,
  b.route_id,b.organ_id
  from  canbus.ods_jituan_bs_employee b
  GLOBAL left outer join (select * from ai_security.abs_driver_behavior_sum where  ppartition between '{start_date_str}' and '{end_date_str}')c
  ON b.qualification_no = c.operator_code where b.organ_id<>''
  group by 
  c.ppartition as ppartition, b.employee_number as employee_number ,b.employee_id as employee_id,b.employee_name as employee_name,
  b.qualification_no,b.route_id,b.organ_id
  ),
  energy_sum as (select aa.ppartition as ppartition, cast(aa.employee_number as varchar(10)) as employee_number,cast(aa.employee_id as varchar(10)) as employee_id,aa.employee_name as employee_name,
  report_type1_count,report_type2_count,report_type3_count,report_type4_count,
  report_type5_count,report_type6_count,
  report_type7_count,report_type8_count,report_type9_count,report_type10_count,report_type11_count,report_type12_count,
  report_type13_count,report_type14_count,report_type15_count,report_type16_count,report_type17_count,report_type18_count,
  report_type19_count,report_type20_count,report_type21_count,report_type22_count,report_type23_count,report_type24_count,
  report_type25_count,report_type26_count,report_type27_count,report_type28_count,report_type29_count,report_type30_count,
  report_type31_count,report_type32_count,
  report_type33_count,report_type34_count,report_type36_count,report_type37_count,
  bb.total_mileage,route_id,organ_id  
  from cet aa GLOBAL left outer join 
  (select ppartition,employee_id,round(sum(toFloat32(total_mileage)),2) as total_mileage
  from ai_security.ads_driver_workhour where  ppartition between '{start_date_str}' and '{end_date_str}' group by ppartition,employee_id)  bb 
  on aa.employee_id = bb.employee_id  
  and aa.ppartition=bb.ppartition )
  select employee_number,employee_id,employee_name,route_id,c.organ_id as organ_id,b.organ_name as organ_name,e.danger_point as danger_point,e.station_count as station_count,
  sum(c.report_type1_count) as report_type1_count,sum(c.report_type2_count) as report_type2_count,sum(c.report_type3_count) as report_type3_count,sum(c.report_type4_count) as report_type4_count,
  sum(c.report_type5_count) as report_type5_count,sum(c.report_type6_count) as report_type6_count,sum(c.report_type7_count) as report_type7_count,sum(c.report_type8_count) as report_type8_count,
  sum(c.report_type9_count) as report_type9_count,sum(c.report_type10_count) as report_type10_count,sum(c.report_type11_count) as report_type11_count,sum(c.report_type12_count) as report_type12_count,
  sum(c.report_type13_count) as report_type13_count,sum(c.report_type14_count) as report_type14_count,sum(c.report_type15_count) as report_type15_count,sum(c.report_type16_count) as report_type16_count,
  sum(c.report_type17_count) as report_type17_count,sum(c.report_type18_count) as report_type18_count,sum(c.report_type19_count) as report_type19_count,sum(c.report_type20_count) as report_type20_count,
  sum(c.report_type21_count) as report_type21_count,sum(c.report_type22_count) as report_type22_count,sum(c.report_type23_count) as report_type23_count,sum(c.report_type24_count) as report_type24_count,
  sum(c.report_type25_count) as report_type25_count,sum(c.report_type26_count) as report_type26_count,sum(c.report_type27_count) as report_type27_count,sum(c.report_type28_count) as report_type28_count,
  sum(c.report_type29_count) as report_type29_count,sum(c.report_type30_count) as report_type30_count,
  sum(c.report_type31_count) as report_type31_count,sum(c.report_type32_count) as report_type32_count,
  sum(c.report_type33_count) as report_type33_count,sum(c.report_type34_count) as report_type34_count, 
  sum(c.report_type36_count) as report_type36_count,sum(c.report_type37_count) as report_type37_count,
  sum(c.total_mileage) as total_mileage 
   from energy_sum c GLOBAL inner join canbus.ods_jituan_bs_organ b on c.organ_id=b.organ_id 
   GLOBAL inner join ai_security.v_line_danger_point e on c.route_id=e.line_code 
   group by employee_number,employee_id,employee_name,route_id,c.organ_id,b.organ_name,e.danger_point,e.station_count 
  """
    return sql.strip()


def accident_3month_query(start_date_str: str,end_date_str: str,routid: str) -> str:
    sql = f"""
        SELECT a.longitude,a.latitude,a.detail,b.route_id,b.organ_id
         FROM
         (select longitude,latitude,detail,obuid,ppartition from canbus.ods_jituan_accident
         WHERE ppartition between '{start_date_str}' and '{end_date_str}') a
            GLOBAL inner JOIN
            (select obuid,route_id,organ_id from canbus.ods_jituan_bs_bus) b
            ON a.obuid = b.obuid
        """
    return sql.strip()

#一个月驾驶行为经纬度
def driver_behavior_month_query(start_date_str: str,end_date_str: str,routid: str) -> str:
    # # # 解析结束日期
    # end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    # start_date = datetime.strptime(start_date_, '%Y-%m-%d')
    # 构建SQL查询
    sql=f"""
     WITH numbered_rows AS (SELECT a.longitude as longitude,a.latitude as latitude,a.report_type as report_type,b.route_id as route_id,b.organ_id as organ_id,row_number() OVER() as row_num FROM 
     (select  longitude,latitude,report_type,obuid,station_code from ai_security.ods_communication_driver_behavior_month where  ppartition between '{start_date_str}' and '{end_date_str}' )a
        GLOBAL inner JOIN 	
        (select obuid,route_id,organ_id from canbus.ods_jituan_bs_bus where route_id GLOBAL in (select route_id from canbus.ods_jituan_bs_route)) b
        ON a.obuid = b.obuid 
     WHERE a.station_code!='' 
            and (a.latitude BETWEEN '22.562803' AND '23.935966')
            and (a.longitude BETWEEN '112.953161' AND '114.054546')
            and a.report_type GLOBAL IN (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 33, 34, 36, 37)
      ) SELECT longitude,latitude,report_type,route_id,organ_id FROM numbered_rows WHERE row_num % 30 = 0 """
    return sql.strip()

#一个月驾驶行为权重（驾驶员画像）
def driver_behavior_weight_month_query(start_date_str: str,end_date_str: str,routid: str) -> str:
    # # # 解析结束日期
    # end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    # start_date = datetime.strptime(start_date_, '%Y-%m-%d')
    # 构建SQL查询
    sql=f"""
        SELECT 
        quota_name3 as behavior_type_name, calculate_weight_rate3 as weight_rate, start_time, end_time ,
        CASE quota_name3
            WHEN '起步急加速' THEN 1
            WHEN '急加速' THEN 2
            WHEN '急减速' THEN 3
            WHEN '急刹车' THEN 4
            WHEN '斑马线不文明礼让' THEN 5
            WHEN '斑马线超速' THEN 6
            WHEN '违规使用手刹' THEN 7
            WHEN '停站N档违规' THEN 8
            WHEN '违规使用N档' THEN 9
            WHEN '不规范转弯' THEN 10
            WHEN '车辆未停稳开车门' THEN 11
            WHEN '车辆起步不关车门' THEN 12
            WHEN '空档滑行' THEN 13
            WHEN '熄火滑行' THEN 14
            WHEN '不文明鸣笛' THEN 15
            WHEN '安全带行为' THEN 16
            WHEN '不规范进站' THEN 17
            WHEN '不规范出站' THEN 18
            WHEN '急停' THEN 19
            WHEN '门开禁启开关' THEN 20
            WHEN '停车不挂N挡' THEN 21
            WHEN '不规范开关门' THEN 22
            WHEN '安全启动' THEN 23
            WHEN '违规使用空调' THEN 24
            WHEN '平路不规范行为' THEN 25
            WHEN '上坡不规范行为' THEN 26
            WHEN '下坡不规范行为' THEN 27
            WHEN '违规使用总电' THEN 28
            WHEN '路口大油门' THEN 29
            WHEN '进站违规制动' THEN 30
            WHEN '区间超速' THEN 33
            WHEN '全局超速' THEN 34
            WHEN '左转弯未刹车' THEN 36
            WHEN '右转弯未刹车' THEN 37
        END AS behavior_type_code
    FROM 
        ai_security.obs_quota_weight_configuration 
    WHERE 
        profile_type = '驾驶员画像' 
        AND quota_name1 = '事故风险' 
        AND quota_name2 = '不良行为' 
        AND creator = 'system'
        AND start_time  >= STR_TO_DATE('{start_date_str}', '%%Y%%m%%d')
        AND start_time <= STR_TO_DATE('{end_date_str}', '%%Y%%m%%d')
        AND quota_name3 GLOBAL IN ('起步急加速','急加速', '急减速','急刹车','斑马线不文明礼让','斑马线超速','违规使用手刹','停站N档违规',
            '违规使用N档','不规范转弯','车辆未停稳开车门','车辆起步不关车门','空档滑行','熄火滑行', '不文明鸣笛','安全带行为','不规范进站',
            '不规范出站','急停','门开禁启开关','停车不挂N挡','不规范开关门','安全启动','违规使用空调','平路不规范行为','上坡不规范行为',
            '下坡不规范行为','违规使用总电','路口大油门','进站违规制动','区间超速','全局超速','左转弯未刹车','右转弯未刹车'
        )
        order by behavior_type_code;"""
    return sql.strip()

def abs_driver_behavior_route_coordinates_query(end_date_str: str,days_back: int = 7) -> str:
    # 解析结束日期
    end_date=datetime.strptime(end_date_str,'%Y-%m-%d')

    # 计算开始日期
    start_date=end_date-timedelta(days=end_date.day-1)

    # 格式化为YYYYMMDD格式
    start_date_str=start_date.strftime('%Y%m%d')
    end_date_str=end_date.strftime('%Y%m%d')

    # 构建SQL查询
    sql=f""" 
    select  ppartition,route_id, report_type, combined_coordinates from ai_security.abs_driver_behavior_route_coordinates prewhere ppartition between '{start_date_str}' and '{end_date_str}' 
    """
    return sql.strip()


#驾驶员画像事故风险一天数据
def abs_driver_day_datas(start_date_str: str) -> str:
    sql1=f"""
        WITH all_drivers AS (
        SELECT DISTINCT 
        e.employee_name as drv_name,
        e.employee_id as drv_id,
        e.organ_id as organ_id,f.organ_name organ_name,gg.route_name 
        FROM canbus.ods_jituan_bs_employee e GLOBAL inner join canbus.ods_jituan_bs_organ f
        on e.organ_id=f.organ_id 
        GLOBAL inner join canbus.ods_jituan_bs_route gg 
        on e.route_id=gg.route_id 
        WHERE e.employee_name IS NOT NULL 
        AND e.employee_name != ''
        ),
        yesterday_window AS (
        SELECT
        drv_name,
        drv_id,
        toDateTime(toDate('{start_date_str}')) AS start_date,
        toDateTime(toDate('{start_date_str}')) + INTERVAL 1 DAY - INTERVAL 1 SECOND AS end_date
        FROM all_drivers
        ),
        yesterday_30m_bhv AS (
        SELECT
        e.employee_name AS driver_name,
        e.employee_id as driver_id,
        CASE 
        WHEN b.report_type = 6 THEN '起步加速评价'
        WHEN b.report_type = 8 THEN '加速评价'
        WHEN b.report_type = 7 THEN '减速评价'
        WHEN b.report_type = 9 THEN '急刹车'
        WHEN b.report_type = 15 THEN '路口再加速评价'
        WHEN b.report_type = 14 THEN '路口速度评价'
        WHEN b.report_type = 18 THEN '违规使用手刹'
        WHEN b.report_type = 1 THEN '停站N档评价'
        WHEN b.report_type = 16 THEN 'N档评价'
        WHEN b.report_type = 22 THEN '不规范转弯'
        WHEN b.report_type = 11 THEN '车辆未停稳开车门'
        WHEN b.report_type = 12 THEN '门未关起步'
        WHEN b.report_type = 5 THEN '空档滑行'
        WHEN b.report_type = 4 THEN '熄火滑行'
        WHEN b.report_type = 19 THEN '不文明鸣笛'
        WHEN b.report_type = 3 THEN '驾驶员未系安全带'
        WHEN b.report_type = 21 THEN '拒载'
        WHEN b.report_type = 20 THEN '飞站'
        WHEN b.report_type = 10 THEN '急停'
        WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
        WHEN b.report_type = 2 THEN '停车不挂N档'
        WHEN b.report_type = 17 THEN '开关车门评价'
        WHEN b.report_type = 23 THEN '动车前安全确认'
        WHEN b.report_type = 24 THEN '违规使用空调'
        WHEN b.report_type = 25 THEN '平路不规范'
        WHEN b.report_type = 26 THEN '上坡不规范'
        WHEN b.report_type = 27 THEN '下坡不规范'
        WHEN b.report_type = 28 THEN '违规使用总电'
        WHEN b.report_type = 29 THEN '路口大油门'
        WHEN b.report_type = 30 THEN '进站违规制动'
        WHEN b.report_type = 33 THEN '区间超速'
        WHEN b.report_type = 34 THEN '全局超速'
        WHEN b.report_type = 36 THEN '左转弯未刹车'
        WHEN b.report_type = 37 THEN '右转弯未停车'
        END AS drv_sct_bhv,
        COUNT(*) AS cnt
        FROM yesterday_window r
        GLOBAL JOIN canbus.ods_jituan_bs_employee e 
        ON r.drv_id = e.employee_id
        GLOBAL LEFT JOIN ai_security.ods_communication_driver_behavior_month b
        ON e.qualification_no = b.operator_code
        WHERE b.report_time BETWEEN r.start_date AND r.end_date
        GROUP BY e.employee_id, 
        e.employee_name,
        CASE 
        WHEN b.report_type = 6 THEN '起步加速评价'
        WHEN b.report_type = 8 THEN '加速评价'
        WHEN b.report_type = 7 THEN '减速评价'
        WHEN b.report_type = 9 THEN '急刹车'
        WHEN b.report_type = 15 THEN '路口再加速评价'
        WHEN b.report_type = 14 THEN '路口速度评价'
        WHEN b.report_type = 18 THEN '违规使用手刹'
        WHEN b.report_type = 1 THEN '停站N档评价'
        WHEN b.report_type = 16 THEN 'N档评价'
        WHEN b.report_type = 22 THEN '不规范转弯'
        WHEN b.report_type = 11 THEN '车辆未停稳开车门'
        WHEN b.report_type = 12 THEN '门未关起步'
        WHEN b.report_type = 5 THEN '空档滑行'
        WHEN b.report_type = 4 THEN '熄火滑行'
        WHEN b.report_type = 19 THEN '不文明鸣笛'
        WHEN b.report_type = 3 THEN '驾驶员未系安全带'
        WHEN b.report_type = 21 THEN '拒载'
        WHEN b.report_type = 20 THEN '飞站'
        WHEN b.report_type = 10 THEN '急停'
        WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
        WHEN b.report_type = 2 THEN '停车不挂N档'
        WHEN b.report_type = 17 THEN '开关车门评价'
        WHEN b.report_type = 23 THEN '动车前安全确认'
        WHEN b.report_type = 24 THEN '违规使用空调'
        WHEN b.report_type = 25 THEN '平路不规范'
        WHEN b.report_type = 26 THEN '上坡不规范'
        WHEN b.report_type = 27 THEN '下坡不规范'
        WHEN b.report_type = 28 THEN '违规使用总电'
        WHEN b.report_type = 29 THEN '路口大油门'
        WHEN b.report_type = 30 THEN '进站违规制动'
        WHEN b.report_type = 33 THEN '区间超速'
        WHEN b.report_type = 34 THEN '全局超速'
        WHEN b.report_type = 36 THEN '左转弯未刹车'
        WHEN b.report_type = 37 THEN '右转弯未停车'
        END
        ),
         yesterday_adas_bhv AS (
        SELECT
        r.drv_name AS driver_name,
        r.drv_id as driver_id,
        CASE 
        WHEN e.resultname = '车距过近' THEN '车距过近'
        WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
        WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
        WHEN e.resultname = '分神' THEN '分神'
        WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
        WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
        WHEN e.resultname = '打电话' THEN '打电话'
        WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
        ELSE e.resultname
        END AS drv_sct_bhv,
        COUNT(*) AS cnt
        FROM yesterday_window r
        GLOBAL JOIN ai_security.ods_jituan_mssql_192_168_181_135_eddata_eddata e
        ON r.drv_id = e.drivercode
        WHERE e.happentime BETWEEN r.start_date AND r.end_date
        AND e.resultname GLOBAL IN ('车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警','前车碰撞预警','未系安全带','打电话','手长时间离开方向盘（吸烟）')
        GROUP BY r.drv_id, r.drv_name,
        CASE 
        WHEN e.resultname = '车距过近' THEN '车距过近'
        WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
        WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
        WHEN e.resultname = '分神' THEN '分神'
        WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
        WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
        WHEN e.resultname = '打电话' THEN '打电话'
        WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
        ELSE e.resultname
        END
        ),
        yesterday_aebs_bhv AS (
        SELECT
        r.drv_name AS driver_name,
        r.drv_id as driver_id,
        CASE 
        WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
        WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
        WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
        END AS drv_sct_bhv,
        COUNT(*) AS cnt
        FROM yesterday_window r
        GLOBAL JOIN ai_security.ods_jituan_mysql_10_163_90_62_strong_tpss_alarm_warn_base_aebs e
        ON r.drv_id = e.driverCode
        WHERE toDate(e.warnTime) BETWEEN r.start_date AND r.end_date
        AND e.typename GLOBAL IN ('严重疲劳驾驶识别','握方向盘不规范','驾驶姿势不端正')
        GROUP BY r.drv_id, r.drv_name,
        CASE 
        WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
        WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
        WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
        END
        ),
        all_30m_bhv AS (
        SELECT * FROM yesterday_30m_bhv
        UNION ALL
        SELECT * FROM yesterday_adas_bhv
        UNION ALL
        SELECT * FROM yesterday_aebs_bhv
        ),
        yesterday_traffic_illegal AS (
        SELECT
        t.driver_name,
        t.employee_code as driver_id,
        CASE 
        WHEN t.illegalact LIKE '%红灯%' THEN '闯红灯'
        WHEN t.illegalact LIKE '%黄灯%' THEN '闯黄灯'
        ELSE '违反交通标志标线'
        END AS drv_sct_bhv,
        COUNT(*) AS cnt
        FROM yesterday_window r
        GLOBAL JOIN ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_traffic_illegal_handle t
        ON r.drv_id = t.employee_code
        WHERE t.illegal_date = toDate(r.start_date)
        AND t.illegal_classify_label = '违反交通指示灯号或禁令标志、标线'
        GROUP BY t.employee_code, 
        t.driver_name,
        CASE 
        WHEN t.illegalact LIKE '%红灯%' THEN '闯红灯'
        WHEN t.illegalact LIKE '%黄灯%' THEN '闯黄灯'
        ELSE '违反交通标志标线'
        END
        ),
        all_30m_bhv_with_traffic AS (
        SELECT * FROM all_30m_bhv
        UNION ALL
        SELECT * FROM yesterday_traffic_illegal
        ),
        health_daily AS (
        SELECT
        h.driver_name,
        h.driver_code as driver_id,
        toDate(h.happen_time) AS date_key,
        MAX(CASE WHEN vname = '心率' THEN vvalue END) AS heart_rate,
        MAX(CASE WHEN vname = '酒精含量' THEN vvalue END) AS alcohol,
        MAX(CASE WHEN vname = '收缩压' THEN vvalue END) AS sbp,
        MAX(CASE WHEN vname = '舒张压' THEN vvalue END) AS dbp,
        MAX(CASE WHEN vname = '脉搏' THEN vvalue END) AS pulse,
        MAX(CASE WHEN vname = '血氧' THEN vvalue END) AS spo2,
        MAX(CASE WHEN vname = '体温' THEN vvalue END) AS temp
        FROM ai_security.ods_jituan_mysql_10_181_92_38_cloud_anfu_public_huyun_warn h
        WHERE h.driver_code GLOBAL IN (SELECT drv_id FROM all_drivers)
        AND toDate(h.happen_time) = toDate('{start_date_str}') 
        AND h.vname GLOBAL IN ('心率', '酒精含量', '收缩压', '舒张压', '脉搏', '血氧', '体温')
        GROUP BY h.driver_code, h.driver_name, toDate(h.happen_time)
        ),
        health_with_rn AS (
        SELECT 
        *,
        row_number() OVER (PARTITION BY driver_id ORDER BY date_key DESC) as rn
        FROM health_daily
        ),
        health_wide AS (
        SELECT 
        driver_name,
        driver_id,
        heart_rate, alcohol, sbp, dbp, pulse, spo2, temp
        FROM health_with_rn
        WHERE rn = 1
        ),
        workhour_agg AS (
        SELECT
        employee_name AS driver_name,
        employee_id as driver_id,
        toDate(parseDateTimeBestEffort(ppartition)) AS date_key,
        SUM(toFloat64OrNull(safty_mileage)) AS daily_mileage,
        SUM(toFloat64OrNull(work_hour)) AS daily_work_hour
        FROM ai_security.ads_driver_workhour
        WHERE employee_id GLOBAL IN (SELECT drv_id FROM all_drivers)
        AND toDate(parseDateTimeBestEffort(ppartition)) = toDate('{start_date_str}') 
        GROUP BY employee_id, employee_name, toDate(parseDateTimeBestEffort(ppartition))
        ),
        workhour_daily AS (
        SELECT
        driver_name,
        driver_id,
        date_key,
        daily_mileage,
        SUM(daily_mileage) OVER (
        PARTITION BY driver_id 
        ORDER BY date_key
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS cumulative_safty_mileage,
        daily_work_hour AS work_hour
        FROM workhour_agg
        ),
        global_avg_mileage AS (
        SELECT AVG(daily_mileage) as avg_mileage_all_drivers
        FROM workhour_agg
        WHERE daily_mileage > 0
        ),
        workhour_wide AS (
        SELECT 
        w.driver_name,
        w.driver_id,
        COALESCE(NULLIF(w.daily_mileage, 0), g.avg_mileage_all_drivers) as safty_mileage,
        w.cumulative_safty_mileage,
        w.work_hour
        FROM workhour_daily w
        GLOBAL CROSS JOIN global_avg_mileage g
        ),
        mileage_mode AS (
        SELECT safty_mileage as mode_value
        FROM workhour_wide
        WHERE safty_mileage > 0
        GROUP BY safty_mileage
        ORDER BY count() DESC
        LIMIT 1
        ),
        pass_station_list AS(
        SELECT 
        drive_date,
        employee_id ,
        driver_name,
        sum(station_count) AS total_station_count,
        count(*) AS trip_count
        FROM (
        SELECT 
        toDate(t.ppartition) AS drive_date,
        t.employee_id AS employee_id, 
        t.employee_name AS driver_name, 
        t.bus_id,
        t.route_id,
        t.from_station,
        t.to_station,
        abs(s2.min_sort - s1.min_sort) + 1 AS station_count
        FROM canbus.ads_triplog_energy t
        GLOBAL LEFT JOIN (
        SELECT line_code, motorcade_name, min(sort) as min_sort
        FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
        GROUP BY line_code, motorcade_name
        ) s1 ON t.route_id = s1.line_code AND t.from_station = s1.motorcade_name
        GLOBAL LEFT JOIN (
        SELECT line_code, motorcade_name, min(sort) as min_sort
        FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
        GROUP BY line_code, motorcade_name
        ) s2 ON t.route_id = s2.line_code AND t.to_station = s2.motorcade_name
        WHERE s1.min_sort IS NOT NULL 
        AND s2.min_sort IS NOT NULL
        AND toDate(t.ppartition) = toDate('{start_date_str}')
        ) as sub
        GROUP BY 
        drive_date,
        employee_id,
        driver_name
        ),
        pass_turn_list AS(
        SELECT 
        drive_date,
        employee_id ,
        driver_name,
        sum(turn_count) AS total_turn_count
        FROM (
        SELECT
        toDate(t.ppartition) AS drive_date,
        t.employee_id AS employee_id, 
        t.employee_name AS driver_name, 
        t.route_id, 
        COUNT(b.event_type) AS turn_count
        FROM canbus.ads_triplog_energy t
        GLOBAL LEFT JOIN ai_security.ads_event_black_spot b
        ON toString(t.route_id) = splitByChar('#', b.route_ids)[1]
        AND b.event_type GLOBAL IN (2, 3)
        WHERE toDate(t.ppartition) = toDate('{start_date_str}')
        GROUP BY drive_date, employee_id, driver_name, t.route_id
        ) as sub
        GROUP BY 
        drive_date,
        employee_id,
        driver_name
        ),
        mental_list AS (
        SELECT 
        m.driver_name,
        case when m.dept_name GLOBAL in ('佛广集团','增从片区','马会巴士') then m.fleet else m.dept_name || '-' || m.fleet end AS organ_name,
        m.heart_level_label AS heart_level_label, 
        m.follow_year_month,n.drv_id,
        m.line_name  
        FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_dailyreport_driver_heart_body_healthy m 
        GLOBAL inner join all_drivers n on m.driver_name=n.drv_name and m.line_name=n.route_name
        and n.organ_name=case when m.dept_name GLOBAL in ('佛广集团','增从片区','马会巴士') then m.fleet else m.dept_name || '-' || m.fleet end 
        WHERE m.follow_year_month = formatDateTime(toDate('{start_date_str}'), '%Y-%m') 
        ),
        driver_list AS (
        SELECT drv_name AS driver_name,
        drv_id as driver_id,
        organ_id
        FROM all_drivers
        ),
        driver_accident AS (
        SELECT 
        org_code,
        org_name,
        CASE 
        WHEN POSITION('-' IN line_code) > 0 
        THEN SUBSTRING(line_code, POSITION('-' IN line_code) + 1)
        ELSE line_code END AS line_code,
        line_name,
        driver_name,
        yearly,
        accident_num 
        FROM ai_security.ads_driver_accident_yearly
        ), 
        s_result AS (
        SELECT a.*,b.employee_name,b.organ_id,b.organ_name 
        FROM driver_accident a 
        GLOBAL LEFT OUTER JOIN (
        SELECT a.*,b.organ_name 
        FROM canbus.ods_jituan_bs_employee a 
        GLOBAL INNER JOIN canbus.ods_jituan_bs_organ b 
        ON a.organ_id=b.organ_id ) b 
        ON a.driver_name=b.employee_name 
        WHERE b.organ_name LIKE CONCAT('%',a.org_name,'%') 
        ),
        accident_yearly AS (
        SELECT 
        d.driver_name,
        d.driver_id,
        a.organ_id,
        COALESCE(SUM(a.accident_num), 0) AS total_accidents
        FROM driver_list d
        GLOBAL LEFT JOIN s_result a
        ON (d.driver_name = a.driver_name) AND(d.organ_id = a.organ_id)
        AND a.yearly GLOBAL IN (2023, 2024)
        GROUP BY d.driver_name,d.driver_id,a.organ_id
        )
        SELECT
        d.driver_name,
        d.driver_id,
        d.organ_id, 
        o.organ_name, 
        e.sex AS gender,
        e.age,
        e.education_level,
        dateDiff('year', e.entry_time, now()) AS driving_years,
        w.safty_mileage,
        w.work_hour,
        y.total_accidents,
        SUM(CASE WHEN b.drv_sct_bhv = 'N档评价' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS ndang_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '上坡不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS upslope_bad_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '下坡不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS downslope_bad_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '不文明鸣笛' THEN b.cnt ELSE 0 END) AS rude_horn_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '不规范转弯' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), 1) AS bad_turn_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '停站N档评价' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS stop_ndang_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '停车不挂N档' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS no_n_on_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '全局超速' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS global_over_spd_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '减速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS decel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS accel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '动车前安全确认' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), 1) AS before_move_safe_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '区间超速' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS section_over_spd_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '右转弯未停车' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), 1) AS right_turn_no_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '左转弯未刹车' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), 1) AS left_turn_no_brake_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '平路不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS flat_bad_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '开关车门评价' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), 1) AS door_op_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '急停' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS sudden_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '急刹车' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS sudden_brake_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '拒载' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), 1) AS refuse_ride_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '熄火滑行' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS stall_coast_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '空档滑行' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS neutral_coast_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '起步加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS start_accel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '路口再加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS junction_reaccel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '路口大油门' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS junction_heavy_gas_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '路口速度评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS junction_spd_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '车辆未停稳开车门' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS door_open_before_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '进站违规制动' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS illegal_brake_on_entry_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规使用总电' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS illegal_main_power_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规使用手刹' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS illegal_hand_brake_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规使用空调' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS illegal_ac_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规关闭"开门禁启开关"' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS illegal_door_switch_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '门未关起步' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS start_with_open_door_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '飞站' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), 1) AS skip_station_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '驾驶员未系安全带' THEN b.cnt ELSE 0 END) AS no_seat_belt_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '车距过近' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS distance_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '车道保持能力下降' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS lane_keep_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '疲劳预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS fatigue_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '分神' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS distraction_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '行人避让预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS pedestrian_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '前车碰撞预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS collision_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '打电话' THEN b.cnt ELSE 0 END) AS phone_call_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '手长时间离开方向盘' THEN b.cnt ELSE 0 END) AS hands_off_wheel_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '严重疲劳驾驶识别' THEN b.cnt ELSE 0 END) AS very_fatigue_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '握方向盘不规范' THEN b.cnt ELSE 0 END) AS hold_steeringwheel_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '驾驶姿势不端正' THEN b.cnt ELSE 0 END) AS driving_posture_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '闯红灯' THEN b.cnt ELSE 0 END) AS red_light_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '闯黄灯' THEN b.cnt ELSE 0 END) AS yellow_light_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违反交通标志标线' THEN b.cnt ELSE 0 END) AS traffic_sign_violation_cnt,
        h.heart_rate, h.alcohol, h.sbp, h.dbp, h.pulse, h.spo2, h.temp,
        m2.heart_level_label as heart_level_label, e.route_id as route_id
        FROM driver_list d
        GLOBAL LEFT JOIN canbus.ods_jituan_bs_employee e 
        ON d.driver_id = e.employee_id
        GLOBAL LEFT JOIN canbus.ods_jituan_bs_organ o 
        ON d.organ_id = o.organ_id
        GLOBAL LEFT JOIN workhour_wide w 
        ON d.driver_id = w.driver_id
        GLOBAL CROSS JOIN mileage_mode m
        GLOBAL LEFT JOIN all_30m_bhv_with_traffic b 
        ON d.driver_id = b.driver_id
        GLOBAL LEFT JOIN health_wide h 
        ON d.driver_id = h.driver_id
        GLOBAL LEFT JOIN pass_station_list p 
        ON d.driver_id = p.employee_id
        GLOBAL LEFT JOIN pass_turn_list p2
        ON d.driver_id = p2.employee_id
        GLOBAL LEFT JOIN mental_list m2
        ON d.driver_id = m2.drv_id
        GLOBAL LEFT JOIN accident_yearly y
        ON d.driver_id = y.driver_id
        GROUP BY 
        d.driver_name,
        d.driver_id,
        d.organ_id, 
        o.organ_name,
        e.sex, 
        e.age, 
        e.route_id,
        e.education_level, 
        driving_years,
        w.safty_mileage,
        w.work_hour,
        h.heart_rate, h.alcohol, h.sbp, h.dbp, h.pulse, h.spo2, h.temp,
        m2.heart_level_label,
        m.mode_value,
        p.total_station_count,
        p2.total_turn_count,
        y.total_accidents  
        ORDER BY d.driver_name """
    sql=sql1
    return sql.strip()


def abs_driver_hour_datas(start_date_str: str) -> str:
    # 定义格式字符串
    format_str="%Y-%m-%d %H:%M:%S"
    # 使用 strptime 将字符串转换为日期对象
    _start_time_=datetime.strptime(start_date_str,format_str)
    _last_time_=(_start_time_-timedelta(hours=1))
    _start_date_=_start_time_.strftime('%Y%m%d')

    sql1=f"""
        WITH all_drivers AS (
        SELECT DISTINCT 
        e.employee_name as drv_name,
        e.employee_id as drv_id,
        e.organ_id as organ_id,f.organ_name organ_name,gg.route_name 
        FROM canbus.ods_jituan_bs_employee e GLOBAL inner join canbus.ods_jituan_bs_organ f
        on e.organ_id=f.organ_id 
        GLOBAL inner join canbus.ods_jituan_bs_route gg 
        on e.route_id=gg.route_id 
        WHERE e.employee_name IS NOT NULL 
        AND e.employee_name != ''
        ),
        yesterday_window AS (
        SELECT
        drv_name,
        drv_id,
        toDateTime('{_last_time_.strftime(format_str)}') AS start_date,
        toDateTime('{_start_time_.strftime(format_str)}') AS end_date
        FROM all_drivers
        ),
        yesterday_30m_bhv AS (
        SELECT
        e.employee_name AS driver_name,
        e.employee_id as driver_id,
        CASE 
        WHEN b.report_type = 6 THEN '起步加速评价'
        WHEN b.report_type = 8 THEN '加速评价'
        WHEN b.report_type = 7 THEN '减速评价'
        WHEN b.report_type = 9 THEN '急刹车'
        WHEN b.report_type = 15 THEN '路口再加速评价'
        WHEN b.report_type = 14 THEN '路口速度评价'
        WHEN b.report_type = 18 THEN '违规使用手刹'
        WHEN b.report_type = 1 THEN '停站N档评价'
        WHEN b.report_type = 16 THEN 'N档评价'
        WHEN b.report_type = 22 THEN '不规范转弯'
        WHEN b.report_type = 11 THEN '车辆未停稳开车门'
        WHEN b.report_type = 12 THEN '门未关起步'
        WHEN b.report_type = 5 THEN '空档滑行'
        WHEN b.report_type = 4 THEN '熄火滑行'
        WHEN b.report_type = 19 THEN '不文明鸣笛'
        WHEN b.report_type = 3 THEN '驾驶员未系安全带'
        WHEN b.report_type = 21 THEN '拒载'
        WHEN b.report_type = 20 THEN '飞站'
        WHEN b.report_type = 10 THEN '急停'
        WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
        WHEN b.report_type = 2 THEN '停车不挂N档'
        WHEN b.report_type = 17 THEN '开关车门评价'
        WHEN b.report_type = 23 THEN '动车前安全确认'
        WHEN b.report_type = 24 THEN '违规使用空调'
        WHEN b.report_type = 25 THEN '平路不规范'
        WHEN b.report_type = 26 THEN '上坡不规范'
        WHEN b.report_type = 27 THEN '下坡不规范'
        WHEN b.report_type = 28 THEN '违规使用总电'
        WHEN b.report_type = 29 THEN '路口大油门'
        WHEN b.report_type = 30 THEN '进站违规制动'
        WHEN b.report_type = 33 THEN '区间超速'
        WHEN b.report_type = 34 THEN '全局超速'
        WHEN b.report_type = 36 THEN '左转弯未刹车'
        WHEN b.report_type = 37 THEN '右转弯未停车'
        END AS drv_sct_bhv,
        COUNT(*) AS cnt
        FROM yesterday_window r
        GLOBAL JOIN canbus.ods_jituan_bs_employee e 
        ON r.drv_id = e.employee_id
        GLOBAL LEFT JOIN (select * from canbus.ods_communication_driver_behavior where ppartition='{_start_date_}') b
        ON e.qualification_no = b.operator_code
        WHERE b.report_time BETWEEN r.start_date AND r.end_date
        GROUP BY e.employee_id, 
        e.employee_name,
        CASE 
        WHEN b.report_type = 6 THEN '起步加速评价'
        WHEN b.report_type = 8 THEN '加速评价'
        WHEN b.report_type = 7 THEN '减速评价'
        WHEN b.report_type = 9 THEN '急刹车'
        WHEN b.report_type = 15 THEN '路口再加速评价'
        WHEN b.report_type = 14 THEN '路口速度评价'
        WHEN b.report_type = 18 THEN '违规使用手刹'
        WHEN b.report_type = 1 THEN '停站N档评价'
        WHEN b.report_type = 16 THEN 'N档评价'
        WHEN b.report_type = 22 THEN '不规范转弯'
        WHEN b.report_type = 11 THEN '车辆未停稳开车门'
        WHEN b.report_type = 12 THEN '门未关起步'
        WHEN b.report_type = 5 THEN '空档滑行'
        WHEN b.report_type = 4 THEN '熄火滑行'
        WHEN b.report_type = 19 THEN '不文明鸣笛'
        WHEN b.report_type = 3 THEN '驾驶员未系安全带'
        WHEN b.report_type = 21 THEN '拒载'
        WHEN b.report_type = 20 THEN '飞站'
        WHEN b.report_type = 10 THEN '急停'
        WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
        WHEN b.report_type = 2 THEN '停车不挂N档'
        WHEN b.report_type = 17 THEN '开关车门评价'
        WHEN b.report_type = 23 THEN '动车前安全确认'
        WHEN b.report_type = 24 THEN '违规使用空调'
        WHEN b.report_type = 25 THEN '平路不规范'
        WHEN b.report_type = 26 THEN '上坡不规范'
        WHEN b.report_type = 27 THEN '下坡不规范'
        WHEN b.report_type = 28 THEN '违规使用总电'
        WHEN b.report_type = 29 THEN '路口大油门'
        WHEN b.report_type = 30 THEN '进站违规制动'
        WHEN b.report_type = 33 THEN '区间超速'
        WHEN b.report_type = 34 THEN '全局超速'
        WHEN b.report_type = 36 THEN '左转弯未刹车'
        WHEN b.report_type = 37 THEN '右转弯未停车'
        END
        ),"""
    sql2=f"""  yesterday_adas_bhv AS (
        SELECT
        r.drv_name AS driver_name,
        r.drv_id as driver_id,
        CASE 
        WHEN e.resultname = '车距过近' THEN '车距过近'
        WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
        WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
        WHEN e.resultname = '分神' THEN '分神'
        WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
        WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
        WHEN e.resultname = '打电话' THEN '打电话'
        WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
        ELSE e.resultname
        END AS drv_sct_bhv,
        COUNT(*) AS cnt
        FROM yesterday_window r
        GLOBAL JOIN ai_security.ods_jituan_mssql_192_168_181_135_eddata_eddata e
        ON r.drv_id = e.drivercode
        WHERE e.happentime BETWEEN r.start_date AND r.end_date
        AND e.resultname GLOBAL IN ('车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警','前车碰撞预警','未系安全带','打电话','手长时间离开方向盘（吸烟）')
        GROUP BY r.drv_id, r.drv_name,
        CASE 
        WHEN e.resultname = '车距过近' THEN '车距过近'
        WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
        WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
        WHEN e.resultname = '分神' THEN '分神'
        WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
        WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
        WHEN e.resultname = '打电话' THEN '打电话'
        WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
        ELSE e.resultname
        END
        ),
        yesterday_aebs_bhv AS (
        SELECT
        r.drv_name AS driver_name,
        r.drv_id as driver_id,
        CASE 
        WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
        WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
        WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
        END AS drv_sct_bhv,
        COUNT(*) AS cnt
        FROM yesterday_window r
        GLOBAL JOIN ai_security.ods_jituan_mysql_10_163_90_62_strong_tpss_alarm_warn_base_aebs e
        ON r.drv_id = e.driverCode
        WHERE toDate(e.warnTime) BETWEEN r.start_date AND r.end_date
        AND e.typename GLOBAL IN ('严重疲劳驾驶识别','握方向盘不规范','驾驶姿势不端正')
        GROUP BY r.drv_id, r.drv_name,
        CASE 
        WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
        WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
        WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
        END
        ),
        all_30m_bhv AS (
        SELECT * FROM yesterday_30m_bhv
        UNION ALL
        SELECT * FROM yesterday_adas_bhv
        UNION ALL
        SELECT * FROM yesterday_aebs_bhv
        ),
        yesterday_traffic_illegal AS (
        SELECT
        t.driver_name,
        t.employee_code as driver_id,
        CASE 
        WHEN t.illegalact LIKE '%红灯%' THEN '闯红灯'
        WHEN t.illegalact LIKE '%黄灯%' THEN '闯黄灯'
        ELSE '违反交通标志标线'
        END AS drv_sct_bhv,
        COUNT(*) AS cnt
        FROM yesterday_window r
        GLOBAL JOIN ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_traffic_illegal_handle t
        ON r.drv_id = t.employee_code
        WHERE t.illegal_date = toDate(r.start_date)
        AND t.illegal_classify_label = '违反交通指示灯号或禁令标志、标线'
        GROUP BY t.employee_code, 
        t.driver_name,
        CASE 
        WHEN t.illegalact LIKE '%红灯%' THEN '闯红灯'
        WHEN t.illegalact LIKE '%黄灯%' THEN '闯黄灯'
        ELSE '违反交通标志标线'
        END
        ),
        all_30m_bhv_with_traffic AS (
        SELECT * FROM all_30m_bhv
        UNION ALL
        SELECT * FROM yesterday_traffic_illegal
        ),
        health_daily AS (
        SELECT
        h.driver_name,
        h.driver_code as driver_id,
        toDate(h.happen_time) AS date_key,
        MAX(CASE WHEN vname = '心率' THEN vvalue END) AS heart_rate,
        MAX(CASE WHEN vname = '酒精含量' THEN vvalue END) AS alcohol,
        MAX(CASE WHEN vname = '收缩压' THEN vvalue END) AS sbp,
        MAX(CASE WHEN vname = '舒张压' THEN vvalue END) AS dbp,
        MAX(CASE WHEN vname = '脉搏' THEN vvalue END) AS pulse,
        MAX(CASE WHEN vname = '血氧' THEN vvalue END) AS spo2,
        MAX(CASE WHEN vname = '体温' THEN vvalue END) AS temp
        FROM ai_security.ods_jituan_mysql_10_181_92_38_cloud_anfu_public_huyun_warn h
        WHERE h.driver_code GLOBAL IN (SELECT drv_id FROM all_drivers)
        AND toDate(h.happen_time) = toDate('{start_date_str}') 
        AND h.vname GLOBAL IN ('心率', '酒精含量', '收缩压', '舒张压', '脉搏', '血氧', '体温')
        GROUP BY h.driver_code, h.driver_name, toDate(h.happen_time)
        ),
        health_with_rn AS (
        SELECT 
        *,
        row_number() OVER (PARTITION BY driver_id ORDER BY date_key DESC) as rn
        FROM health_daily
        ),
        health_wide AS (
        SELECT 
        driver_name,
        driver_id,
        heart_rate, alcohol, sbp, dbp, pulse, spo2, temp
        FROM health_with_rn
        WHERE rn = 1
        ),
        workhour_agg AS (
        SELECT
        employee_name AS driver_name,
        employee_id as driver_id,
        toDate(parseDateTimeBestEffort('{_start_date_}')) AS date_key,
        safty_mileage AS daily_mileage,
        work_hour AS daily_work_hour
        FROM all_drivers b left outer join ( select employee_id,employee_name,
        SUM(cast(safty_mileage as decimal(12,2))) as safty_mileage,
        sum(cast(work_hour as decimal(12,2))) as work_hour 
        from ai_security.ads_driver_workhour where ppartition='{_start_date_}'
        group by employee_id,employee_name) a
        on b.drv_id=a.employee_id
        ),
        workhour_daily AS (
        SELECT
        driver_name,
        driver_id,
        date_key,
        daily_mileage,
        SUM(daily_mileage) OVER (
        PARTITION BY driver_id 
        ORDER BY date_key
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS cumulative_safty_mileage,
        daily_work_hour AS work_hour
        FROM workhour_agg
        ),
        global_avg_mileage AS (
        SELECT AVG(daily_mileage) as avg_mileage_all_drivers
        FROM workhour_agg
        WHERE daily_mileage > 0
        ),
        workhour_wide AS (
        SELECT 
        w.driver_name,
        w.driver_id,
        COALESCE(w.daily_mileage, g.avg_mileage_all_drivers) as safty_mileage,
        w.cumulative_safty_mileage,
        w.work_hour
        FROM workhour_daily w
        GLOBAL CROSS JOIN global_avg_mileage g
        ),
        mileage_mode AS (
        SELECT safty_mileage as mode_value
        FROM workhour_wide
        WHERE safty_mileage > 0
        GROUP BY safty_mileage
        ORDER BY count() DESC
        LIMIT 1
        ),
        pass_station_list AS(
        SELECT 
        drive_date,
        employee_id ,
        driver_name,
        sum(station_count) AS total_station_count,
        count(*) AS trip_count
        FROM (
        SELECT 
        toDate(t.ppartition) AS drive_date,
        t.employee_id AS employee_id, 
        t.employee_name AS driver_name, 
        t.bus_id,
        t.route_id,
        t.from_station,
        t.to_station,
        abs(s2.min_sort - s1.min_sort) + 1 AS station_count
        FROM canbus.ads_triplog_energy t
        GLOBAL LEFT JOIN (
        SELECT line_code, motorcade_name, min(sort) as min_sort
        FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
        GROUP BY line_code, motorcade_name
        ) s1 ON t.route_id = s1.line_code AND t.from_station = s1.motorcade_name
        GLOBAL LEFT JOIN (
        SELECT line_code, motorcade_name, min(sort) as min_sort
        FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
        GROUP BY line_code, motorcade_name
        ) s2 ON t.route_id = s2.line_code AND t.to_station = s2.motorcade_name
        WHERE s1.min_sort IS NOT NULL 
        AND s2.min_sort IS NOT NULL
        AND t.ppartition = '{_start_date_}'
        ) as sub
        GROUP BY 
        drive_date,
        employee_id,
        driver_name
        ),
        pass_turn_list AS(
        SELECT 
        drive_date,
        employee_id ,
        driver_name,
        sum(turn_count) AS total_turn_count
        FROM (
        SELECT
        toDate(t.ppartition) AS drive_date,
        t.employee_id AS employee_id, 
        t.employee_name AS driver_name, 
        t.route_id, 
        COUNT(b.event_type) AS turn_count
        FROM canbus.ads_triplog_energy t
        GLOBAL LEFT JOIN ai_security.ads_event_black_spot b
        ON toString(t.route_id) = splitByChar('#', b.route_ids)[1]
        AND b.event_type GLOBAL IN (2, 3)
        WHERE t.ppartition = '{_start_date_}'
        GROUP BY drive_date, employee_id, driver_name, t.route_id
        ) as sub
        GROUP BY 
        drive_date,
        employee_id,
        driver_name
        ),
        mental_list AS (
        SELECT 
        m.driver_name,
        case when m.dept_name GLOBAL in ('佛广集团','增从片区','马会巴士') then m.fleet else m.dept_name || '-' || m.fleet end AS organ_name,
        m.heart_level_label AS heart_level_label, 
        m.follow_year_month,n.drv_id,
        m.line_name  
        FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_dailyreport_driver_heart_body_healthy m 
        GLOBAL inner join all_drivers n on m.driver_name=n.drv_name  and m.line_name=n.route_name
        and n.organ_name=case when m.dept_name GLOBAL in ('佛广集团','增从片区','马会巴士') then m.fleet else m.dept_name || '-' || m.fleet end 
        WHERE m.follow_year_month = formatDateTime(toDate('{start_date_str}'), '%Y-%m') 
        ),
        driver_list AS (
        SELECT drv_name AS driver_name,
        drv_id as driver_id,
        organ_id
        FROM all_drivers
        ),
        driver_accident AS (
        SELECT 
        org_code,
        org_name,
        CASE 
        WHEN POSITION('-' IN line_code) > 0 
        THEN SUBSTRING(line_code, POSITION('-' IN line_code) + 1)
        ELSE line_code END AS line_code,
        line_name,
        driver_name,
        yearly,
        accident_num 
        FROM ai_security.ads_driver_accident_yearly
        ), 
        s_result AS (
        SELECT a.*,b.employee_name,b.organ_id,b.organ_name 
        FROM driver_accident a 
        GLOBAL LEFT OUTER JOIN (
        SELECT a.*,b.organ_name 
        FROM canbus.ods_jituan_bs_employee a 
        GLOBAL INNER JOIN canbus.ods_jituan_bs_organ b 
        ON a.organ_id=b.organ_id ) b 
        ON a.driver_name=b.employee_name 
        WHERE b.organ_name LIKE CONCAT('%',a.org_name,'%') 
        ),
        accident_yearly AS (
        SELECT 
        d.driver_name,
        d.driver_id,
        a.organ_id,
        COALESCE(SUM(a.accident_num), 0) AS total_accidents
        FROM driver_list d
        GLOBAL LEFT JOIN s_result a
        ON (d.driver_name = a.driver_name) AND(d.organ_id = a.organ_id)
        AND a.yearly GLOBAL IN (2023, 2024)
        GROUP BY d.driver_name,d.driver_id,a.organ_id
        )
        SELECT
        d.driver_name,
        d.driver_id,
        d.organ_id, 
        o.organ_name, 
        e.sex AS gender,
        e.age,
        e.education_level,
        dateDiff('year', e.entry_time, now()) AS driving_years,
        w.safty_mileage,
        w.work_hour,
        y.total_accidents,
        SUM(CASE WHEN b.drv_sct_bhv = 'N档评价' THEN b.cnt ELSE 0 END) AS ndang_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '上坡不规范' THEN b.cnt ELSE 0 END) AS upslope_bad_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '下坡不规范' THEN b.cnt ELSE 0 END) AS downslope_bad_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '不文明鸣笛' THEN b.cnt ELSE 0 END) AS rude_horn_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '不规范转弯' THEN b.cnt ELSE 0 END) AS bad_turn_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '停站N档评价' THEN b.cnt ELSE 0 END) AS stop_ndang_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '停车不挂N档' THEN b.cnt ELSE 0 END) AS no_n_on_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '全局超速' THEN b.cnt ELSE 0 END) AS global_over_spd_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '减速评价' THEN b.cnt ELSE 0 END) AS decel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '加速评价' THEN b.cnt ELSE 0 END) AS accel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '动车前安全确认' THEN b.cnt ELSE 0 END) AS before_move_safe_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '区间超速' THEN b.cnt ELSE 0 END) AS section_over_spd_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '右转弯未停车' THEN b.cnt ELSE 0 END) AS right_turn_no_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '左转弯未刹车' THEN b.cnt ELSE 0 END) AS left_turn_no_brake_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '平路不规范' THEN b.cnt ELSE 0 END) AS flat_bad_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '开关车门评价' THEN b.cnt ELSE 0 END) AS door_op_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '急停' THEN b.cnt ELSE 0 END) AS sudden_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '急刹车' THEN b.cnt ELSE 0 END) AS sudden_brake_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '拒载' THEN b.cnt ELSE 0 END) AS refuse_ride_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '熄火滑行' THEN b.cnt ELSE 0 END) AS stall_coast_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '空档滑行' THEN b.cnt ELSE 0 END) AS neutral_coast_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '起步加速评价' THEN b.cnt ELSE 0 END) AS start_accel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '路口再加速评价' THEN b.cnt ELSE 0 END) AS junction_reaccel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '路口大油门' THEN b.cnt ELSE 0 END) AS junction_heavy_gas_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '路口速度评价' THEN b.cnt ELSE 0 END) AS junction_spd_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '车辆未停稳开车门' THEN b.cnt ELSE 0 END) AS door_open_before_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '进站违规制动' THEN b.cnt ELSE 0 END) AS illegal_brake_on_entry_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规使用总电' THEN b.cnt ELSE 0 END) AS illegal_main_power_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规使用手刹' THEN b.cnt ELSE 0 END) AS illegal_hand_brake_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规使用空调' THEN b.cnt ELSE 0 END) AS illegal_ac_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规关闭"开门禁启开关"' THEN b.cnt ELSE 0 END) AS illegal_door_switch_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '门未关起步' THEN b.cnt ELSE 0 END) AS start_with_open_door_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '飞站' THEN b.cnt ELSE 0 END) AS skip_station_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '驾驶员未系安全带' THEN b.cnt ELSE 0 END) AS no_seat_belt_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '车距过近' THEN b.cnt ELSE 0 END) AS distance_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '车道保持能力下降' THEN b.cnt ELSE 0 END) AS lane_keep_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '疲劳预警' THEN b.cnt ELSE 0 END) AS fatigue_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '分神' THEN b.cnt ELSE 0 END) AS distraction_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '行人避让预警' THEN b.cnt ELSE 0 END) AS pedestrian_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '前车碰撞预警' THEN b.cnt ELSE 0 END) AS collision_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '打电话' THEN b.cnt ELSE 0 END) AS phone_call_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '手长时间离开方向盘' THEN b.cnt ELSE 0 END) AS hands_off_wheel_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '严重疲劳驾驶识别' THEN b.cnt ELSE 0 END) AS very_fatigue_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '握方向盘不规范' THEN b.cnt ELSE 0 END) AS hold_steeringwheel_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '驾驶姿势不端正' THEN b.cnt ELSE 0 END) AS driving_posture_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '闯红灯' THEN b.cnt ELSE 0 END) AS red_light_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '闯黄灯' THEN b.cnt ELSE 0 END) AS yellow_light_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违反交通标志标线' THEN b.cnt ELSE 0 END) AS traffic_sign_violation_cnt,
        h.heart_rate, h.alcohol, h.sbp, h.dbp, h.pulse, h.spo2, h.temp,
        m2.heart_level_label
        FROM driver_list d
        GLOBAL LEFT JOIN canbus.ods_jituan_bs_employee e 
        ON d.driver_id = e.employee_id
        GLOBAL LEFT JOIN canbus.ods_jituan_bs_organ o 
        ON d.organ_id = o.organ_id
        GLOBAL LEFT JOIN workhour_wide w 
        ON d.driver_id = w.driver_id
        GLOBAL CROSS JOIN mileage_mode m
        GLOBAL LEFT JOIN all_30m_bhv_with_traffic b 
        ON d.driver_id = b.driver_id
        GLOBAL LEFT JOIN health_wide h 
        ON d.driver_id = h.driver_id
        GLOBAL LEFT JOIN pass_station_list p 
        ON d.driver_id = p.employee_id
        GLOBAL LEFT JOIN pass_turn_list p2
        ON d.driver_id = p2.employee_id
        GLOBAL LEFT JOIN mental_list m2
        ON d.driver_id = m2.drv_id
        GLOBAL LEFT JOIN accident_yearly y
        ON d.driver_id = y.driver_id
        GROUP BY 
        d.driver_name,
        d.driver_id,
        d.organ_id, 
        o.organ_name,
        e.sex, 
        e.age, 
        e.education_level, 
        driving_years,
        w.safty_mileage,
        w.work_hour,
        h.heart_rate, h.alcohol, h.sbp, h.dbp, h.pulse, h.spo2, h.temp,
        m2.heart_level_label,
        m.mode_value,
        p.total_station_count,
        p2.total_turn_count,
        y.total_accidents
        ORDER BY d.driver_name """
    sql=sql1+sql2
    return sql.strip()


def ods_communication_driver_bus_behavior_route_week_sum(start_date_str: str,end_date_str: str) -> str:
    sql=f"""
        WITH cet AS
            (SELECT c.ppartition AS ppartition, b.employee_number AS employee_number, b.employee_id AS employee_id,
          b.employee_name AS employee_name, b.qualification_no, c.report_time AS report_time, sum(c.report_type1_count) AS report_type1_count,
         sum(c.report_type2_count) AS report_type2_count, sum(c.report_type3_count) AS report_type3_count,
         sum(c.report_type4_count) AS report_type4_count, sum(c.report_type5_count) AS report_type5_count,
         sum(c.report_type6_count) AS report_type6_count, sum(c.report_type7_count) AS report_type7_count,
         sum(c.report_type8_count) AS report_type8_count, sum(c.report_type9_count) AS report_type9_count,
         sum(c.report_type10_count) AS report_type10_count, sum(c.report_type11_count) AS report_type11_count,
         sum(c.report_type12_count) AS report_type12_count, sum(c.report_type13_count) AS report_type13_count,
         sum(c.report_type14_count) AS report_type14_count, sum(c.report_type15_count) AS report_type15_count,
         sum(c.report_type16_count) AS report_type16_count, sum(c.report_type17_count) AS report_type17_count,
         sum(c.report_type18_count) AS report_type18_count, sum(c.report_type19_count) AS report_type19_count,
         sum(c.report_type20_count) AS report_type20_count, sum(c.report_type21_count) AS report_type21_count,
         sum(c.report_type22_count) AS report_type22_count, sum(c.report_type23_count) AS report_type23_count,
         sum(c.report_type24_count) AS report_type24_count, sum(c.report_type25_count) AS report_type25_count,
         sum(c.report_type26_count) AS report_type26_count, sum(c.report_type27_count) AS report_type27_count,
         sum(c.report_type28_count) AS report_type28_count, sum(c.report_type29_count) AS report_type29_count,
         sum(c.report_type30_count) AS report_type30_count, sum(c.report_type31_count) AS report_type31_count,
         sum(c.report_type32_count) AS report_type32_count, sum(c.report_type33_count) AS report_type33_count,
         sum(c.report_type34_count) AS report_type34_count, sum(c.report_type36_count) AS report_type36_count,
         sum(c.report_type37_count) AS report_type37_count, b.route_id, b.organ_id 
         FROM canbus.ods_jituan_bs_employee AS b 
         GLOBAL INNER JOIN (select * from ai_security.abs_driver_behavior_sum where ppartition between '{start_date_str}' and '{end_date_str}') 
         AS c ON b.qualification_no = c.operator_code GROUP BY ppartition, employee_number, employee_id, employee_name,
         b.qualification_no, report_time, b.route_id, b.organ_id
        )
        SELECT route_id, sum(c.report_type1_count) AS report_type1_count, sum(c.report_type2_count) AS report_type2_count,
         sum(c.report_type3_count) AS report_type3_count, sum(c.report_type4_count) AS report_type4_count,
         sum(c.report_type5_count) AS report_type5_count, sum(c.report_type6_count) AS report_type6_count,
         sum(c.report_type7_count) AS report_type7_count, sum(c.report_type8_count) AS report_type8_count,
         sum(c.report_type9_count) AS report_type9_count, sum(c.report_type10_count) AS report_type10_count,
         sum(c.report_type11_count) AS report_type11_count, sum(c.report_type12_count) AS report_type12_count,
         sum(c.report_type13_count) AS report_type13_count, sum(c.report_type14_count) AS report_type14_count,
         sum(c.report_type15_count) AS report_type15_count, sum(c.report_type16_count) AS report_type16_count,
         sum(c.report_type17_count) AS report_type17_count, sum(c.report_type18_count) AS report_type18_count,
         sum(c.report_type19_count) AS report_type19_count, sum(c.report_type20_count) AS report_type20_count,
         sum(c.report_type21_count) AS report_type21_count, sum(c.report_type22_count) AS report_type22_count,
         sum(c.report_type23_count) AS report_type23_count, sum(c.report_type24_count) AS report_type24_count,
         sum(c.report_type25_count) AS report_type25_count, sum(c.report_type26_count) AS report_type26_count,
         sum(c.report_type27_count) AS report_type27_count, sum(c.report_type28_count) AS report_type28_count,
         sum(c.report_type29_count) AS report_type29_count, sum(c.report_type30_count) AS report_type30_count,
         sum(c.report_type31_count) AS report_type31_count, sum(c.report_type32_count) AS report_type32_count,
         sum(c.report_type33_count) AS report_type33_count, sum(c.report_type34_count) AS report_type34_count,
         sum(c.report_type36_count) AS report_type36_count, sum(c.report_type37_count) AS report_type37_count
         FROM cet AS c GROUP BY route_id;
        """
    return sql.strip()


def abs_all_30m_bhv_with_traffic(start_date_str: str,end_date_str: str) -> str:
    sql1="""
        WITH communication_drivers AS (
          SELECT DISTINCT 
              e.employee_name as drv_name,
              b.operator_code
          FROM ai_security.ods_communication_driver_behavior_month b 
            GLOBAL JOIN canbus.ods_jituan_bs_employee e 
              ON b.operator_code = e.qualification_no
          WHERE e.employee_name IS NOT NULL 
            AND e.employee_name != ''
      ),
      accident_info AS (
          SELECT
              driver_name,
              accident_date
          FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_accident_forecast_handle
          WHERE accident_liability GLOBAL IN ('048002','048003','048004','048005') and YEAR(accident_date)='2025'
      ),
      no_accident_drivers AS (
          SELECT drv_name
          FROM communication_drivers
          WHERE drv_name GLOBAL NOT IN (SELECT driver_name FROM accident_info)
      ),
      rand_window AS (
           select ppartition, drv_name,start_rand, end_rand from ai_security.abs_rand_window
      ),
      accident_30m_bhv AS (
          SELECT
              a.driver_name,
              b.drv_sct_bhv,
              COUNT(*) AS cnt
          FROM accident_info a
          GLOBAL JOIN ai_security.ods_jituan_oracle_10_181_92_175_sc_sync_v_comm_drv_sct_bhv_all b
            ON a.driver_name = b.drv_name
          WHERE b.rcrd_time BETWEEN toDate(a.accident_date)
                            AND toDate(a.accident_date) + INTERVAL 1 DAY - INTERVAL 1 SECOND
          GROUP BY a.driver_name, b.drv_sct_bhv
      ),
       rand_30m_bhv AS (
          SELECT 
              e.employee_name AS driver_name,
              CASE 
                WHEN b.report_type = 6 THEN '起步加速评价'
                WHEN b.report_type = 8 THEN '加速评价'
                WHEN b.report_type = 7 THEN '减速评价'
                WHEN b.report_type = 9 THEN '急刹车'
                WHEN b.report_type = 15 THEN '路口再加速评价'
                WHEN b.report_type = 14 THEN '路口速度评价'
                WHEN b.report_type = 18 THEN '违规使用手刹'
                WHEN b.report_type = 1 THEN '停站N档评价'
                WHEN b.report_type = 16 THEN 'N档评价'
                WHEN b.report_type = 22 THEN '不规范转弯'
                WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                WHEN b.report_type = 12 THEN '门未关起步'
                WHEN b.report_type = 5 THEN '空档滑行'
                WHEN b.report_type = 4 THEN '熄火滑行'
                WHEN b.report_type = 19 THEN '不文明鸣笛'
                WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                WHEN b.report_type = 21 THEN '拒载'
                WHEN b.report_type = 20 THEN '飞站'
                WHEN b.report_type = 10 THEN '急停'
                WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                WHEN b.report_type = 2 THEN '停车不挂N档'
                WHEN b.report_type = 17 THEN '开关车门评价'
                WHEN b.report_type = 23 THEN '动车前安全确认'
                WHEN b.report_type = 24 THEN '违规使用空调'
                WHEN b.report_type = 25 THEN '平路不规范'
                WHEN b.report_type = 26 THEN '上坡不规范'
                WHEN b.report_type = 27 THEN '下坡不规范'
                WHEN b.report_type = 28 THEN '违规使用总电'
                WHEN b.report_type = 29 THEN '路口大油门'
                WHEN b.report_type = 30 THEN '进站违规制动'
                WHEN b.report_type = 33 THEN '区间超速'
                WHEN b.report_type = 34 THEN '全局超速'
                WHEN b.report_type = 36 THEN '左转弯未刹车'
                WHEN b.report_type = 37 THEN '右转弯未停车'
                END AS drv_sct_bhv,
              COUNT(*) AS cnt
          FROM rand_window r
          GLOBAL JOIN canbus.ods_jituan_bs_employee e 
              ON r.drv_name = e.employee_name
          GLOBAL JOIN ai_security.ods_communication_driver_behavior_month b
            ON e.qualification_no = b.operator_code
          WHERE b.report_time BETWEEN r.start_rand AND r.end_rand
          GROUP BY e.employee_name, 
              CASE 
                WHEN b.report_type = 6 THEN '起步加速评价'
                WHEN b.report_type = 8 THEN '加速评价'
                WHEN b.report_type = 7 THEN '减速评价'
                WHEN b.report_type = 9 THEN '急刹车'
                WHEN b.report_type = 15 THEN '路口再加速评价'
                WHEN b.report_type = 14 THEN '路口速度评价'
                WHEN b.report_type = 18 THEN '违规使用手刹'
                WHEN b.report_type = 1 THEN '停站N档评价'
                WHEN b.report_type = 16 THEN 'N档评价'
                WHEN b.report_type = 22 THEN '不规范转弯'
                WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                WHEN b.report_type = 12 THEN '门未关起步'
                WHEN b.report_type = 5 THEN '空档滑行'
                WHEN b.report_type = 4 THEN '熄火滑行'
                WHEN b.report_type = 19 THEN '不文明鸣笛'
                WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                WHEN b.report_type = 21 THEN '拒载'
                WHEN b.report_type = 20 THEN '飞站'
                WHEN b.report_type = 10 THEN '急停'
                WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                WHEN b.report_type = 2 THEN '停车不挂N档'
                WHEN b.report_type = 17 THEN '开关车门评价'
                WHEN b.report_type = 23 THEN '动车前安全确认'
                WHEN b.report_type = 24 THEN '违规使用空调'
                WHEN b.report_type = 25 THEN '平路不规范'
                WHEN b.report_type = 26 THEN '上坡不规范'
                WHEN b.report_type = 27 THEN '下坡不规范'
                WHEN b.report_type = 28 THEN '违规使用总电'
                WHEN b.report_type = 29 THEN '路口大油门'
                WHEN b.report_type = 30 THEN '进站违规制动'
                WHEN b.report_type = 33 THEN '区间超速'
                WHEN b.report_type = 34 THEN '全局超速'
                WHEN b.report_type = 36 THEN '左转弯未刹车'
                WHEN b.report_type = 37 THEN '右转弯未停车'
                END
      ),
      accident_adas_bhv AS (
          SELECT
              a.driver_name,
              CASE 
                  WHEN e.resultname = '车距过近' THEN '车距过近'
                  WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                  WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                  WHEN e.resultname = '分神' THEN '分神'
                  WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                  WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                  WHEN e.resultname = '打电话' THEN '打电话'
                  WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                  ELSE e.resultname
              END AS drv_sct_bhv,
              COUNT(*) AS cnt
          FROM accident_info a
          GLOBAL JOIN ai_security.ods_jituan_mssql_192_168_181_135_eddata_eddata e
            ON a.driver_name = e.drivername
          WHERE e.happentime BETWEEN toDate(a.accident_date)
                             AND toDate(a.accident_date) + INTERVAL 1 DAY - INTERVAL 1 SECOND
            AND e.resultname GLOBAL IN ('车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警','前车碰撞预警','未系安全带','打电话','手长时间离开方向盘（吸烟）')
          GROUP BY a.driver_name, 
              CASE 
                  WHEN e.resultname = '车距过近' THEN '车距过近'
                  WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                  WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                  WHEN e.resultname = '分神' THEN '分神'
                  WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                  WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                  WHEN e.resultname = '打电话' THEN '打电话'
                  WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                  ELSE e.resultname
              END
      ),"""
    sql2=f""" rand_adas_bhv AS (
    SELECT
        r.drv_name AS driver_name,
        CASE 
            WHEN e.resultname = '车距过近' THEN '车距过近'
            WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
            WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
            WHEN e.resultname = '分神' THEN '分神'
            WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
            WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
            WHEN e.resultname = '打电话' THEN '打电话'
            WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
            ELSE e.resultname
        END AS drv_sct_bhv,
        COUNT(*) AS cnt
    FROM rand_window r
    GLOBAL JOIN ai_security.ods_jituan_mssql_192_168_181_135_eddata_eddata e
      ON r.drv_name = e.drivername
    WHERE e.happentime BETWEEN r.start_rand AND r.end_rand
      AND e.resultname GLOBAL IN ('车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警','前车碰撞预警','未系安全带','打电话','手长时间离开方向盘（吸烟）')
    GROUP BY r.drv_name, 
        CASE 
            WHEN e.resultname = '车距过近' THEN '车距过近'
            WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
            WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
            WHEN e.resultname = '分神' THEN '分神'
            WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
            WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
            WHEN e.resultname = '打电话' THEN '打电话'
            WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
            ELSE e.resultname
        END
),
        rand_aebs_bhv AS (
            SELECT
                r.drv_name AS driver_name,
                CASE 
                    WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                    WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                    WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM ai_security.abs_rand_window r
            GLOBAL JOIN ai_security.ods_jituan_mysql_10_163_90_62_strong_tpss_alarm_warn_base_aebs e
            ON r.drv_name = e.driverName
            WHERE toDate(e.warnTime) BETWEEN r.start_rand AND r.end_rand
            AND e.typename GLOBAL IN ('严重疲劳驾驶识别','握方向盘不规范','驾驶姿势不端正')
            GROUP BY r.drv_name, 
            CASE 
                WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
            END
        ),
        accident_aebs_bhv AS (
        SELECT
            a.driver_name,
            CASE 
                WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
            END AS drv_sct_bhv,
            COUNT(*) AS cnt
        FROM accident_info a
        GLOBAL JOIN ai_security.ods_jituan_mysql_10_163_90_62_strong_tpss_alarm_warn_base_aebs e
        ON a.driver_name = e.driverName
        WHERE toDate(e.warnTime) BETWEEN toDate(a.accident_date)
        AND toDate(a.accident_date) + INTERVAL 1 DAY - INTERVAL 1 SECOND
        AND e.typename GLOBAL IN ('严重疲劳驾驶识别','握方向盘不规范','驾驶姿势不端正')
        GROUP BY a.driver_name, 
        CASE 
            WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
            WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
            WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
        END
    ),
      all_30m_bhv AS (
        SELECT * FROM accident_30m_bhv
        UNION ALL
        SELECT * FROM rand_30m_bhv
        UNION ALL
        SELECT * FROM accident_adas_bhv
        UNION ALL
        SELECT * FROM rand_adas_bhv
        UNION ALL
        SELECT * FROM accident_aebs_bhv
        UNION ALL
        SELECT * FROM rand_aebs_bhv
      ),
      accident_traffic_illegal AS (
          SELECT
              t.driver_name,
              CASE 
                  WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                  WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                  ELSE '违反交通标志标线'
              END AS drv_sct_bhv,
              COUNT(*) AS cnt
          FROM accident_info a
          GLOBAL JOIN ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_traffic_illegal_handle t
            ON a.driver_name = t.driver_name
          WHERE t.illegal_date = toDate(a.accident_date)  
            AND t.illegal_classify_label = '违反交通指示灯号或禁令标志、标线'
          GROUP BY t.driver_name, 
              CASE 
                  WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                  WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                  ELSE '违反交通标志标线'
              END
      ),
      rand_traffic_illegal AS (
          SELECT
              t.driver_name,
              CASE 
                  WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                  WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                  ELSE '违反交通标志标线'
              END AS drv_sct_bhv,
              COUNT(*) AS cnt
          FROM rand_window r
          GLOBAL JOIN ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_traffic_illegal_handle t
            ON r.drv_name = t.driver_name
          WHERE t.illegal_date = toDate(r.start_rand)  
            AND t.illegal_classify_label = '违反交通指示灯号或禁令标志、标线'
          GROUP BY t.driver_name, 
              CASE 
                  WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                  WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                  ELSE '违反交通标志标线'
              END
      ),

      all_30m_bhv_with_traffic AS (
          SELECT * FROM all_30m_bhv
          UNION ALL
          SELECT * FROM accident_traffic_illegal
          UNION ALL
          SELECT * FROM rand_traffic_illegal
      ) 
      select  formatDateTime(now(), '%%Y%%m%%d') AS ppartition,
              COALESCE(driver_name,'') as driver_name,
              COALESCE(drv_sct_bhv,'') as drv_sct_bhv,
              COALESCE(cnt,0) AS cnt  from all_30m_bhv_with_traffic """
    sql=sql1+sql2
    return sql.strip()


def abs_health_wide(start_date_str: str,end_date_str: str) -> str:
    sql=f"""
        WITH communication_drivers AS (
            SELECT DISTINCT 
                e.employee_name as drv_name,
                b.operator_code
            FROM ai_security.ods_communication_driver_behavior_month b
            GLOBAL JOIN canbus.ods_jituan_bs_employee e 
                ON b.operator_code = e.qualification_no
            WHERE e.employee_name IS NOT NULL 
              AND e.employee_name != ''
        ),
        accident_info AS (
            SELECT
                driver_name,
                accident_date
            FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_accident_forecast_handle
            WHERE accident_liability GLOBAL IN ('048002','048003','048004','048005') and YEAR(accident_date) = '2025'
        ),
        no_accident_drivers AS (
            SELECT drv_name
            FROM communication_drivers
            WHERE drv_name GLOBAL NOT IN (SELECT driver_name FROM accident_info)
        ),
        rand_window AS (
            select ppartition, drv_name,start_rand, end_rand from ai_security.abs_rand_window
        ),
        health_daily AS (
            SELECT
                h.driver_name,
                toDate(h.happen_time) AS date_key,
                cast(ROUND(MAX(CASE WHEN vname = '心率' THEN toFloat64OrNull(vvalue) ELSE 0.0 END), 2) as decimal(12,2)) AS heart_rate,
                cast(ROUND(MAX(CASE WHEN vname = '酒精含量' THEN toFloat64OrNull(vvalue) ELSE 0.0 END), 2) as decimal(12,2))  AS alcohol,
                cast(ROUND(MAX(CASE WHEN vname = '收缩压' THEN toFloat64OrNull(vvalue) ELSE 0.0 END), 2) as decimal(12,2))  AS sbp,
                cast(ROUND(MAX(CASE WHEN vname = '舒张压' THEN toFloat64OrNull(vvalue) ELSE 0.0 END), 2) as decimal(12,2))  AS dbp,
                cast(ROUND(MAX(CASE WHEN vname = '脉搏' THEN toFloat64OrNull(vvalue) ELSE 0.0 END), 2) as decimal(12,2))  AS pulse,
                cast(ROUND(MAX(CASE WHEN vname = '血氧' THEN toFloat64OrNull(vvalue) ELSE 0.0 END), 2) as decimal(12,2))  AS spo2,
                cast(ROUND(MAX(CASE WHEN vname = '体温' THEN toFloat64OrNull(vvalue) ELSE 0.0 END), 2) as decimal(12,2))  AS temp
            FROM ai_security.ods_jituan_mysql_10_181_92_38_cloud_anfu_public_huyun_warn h
            WHERE (h.driver_name, toDate(h.happen_time)) GLOBAL IN (
                SELECT driver_name, toDate(accident_date) FROM accident_info
                UNION ALL
                SELECT drv_name, toDate(start_rand) FROM rand_window
            )
            AND h.vname GLOBAL IN ('心率', '酒精含量', '收缩压', '舒张压', '脉搏', '血氧', '体温')
            GROUP BY h.driver_name, toDate(h.happen_time)
        ),
        health_with_rn AS (
            SELECT 
                *,
                row_number() OVER (PARTITION BY driver_name ORDER BY date_key DESC) as rn
            FROM health_daily
        ),
        health_wide AS (
            SELECT 
                formatDateTime(now(), '%%Y%%m%%d') AS ppartition,
                driver_name,
                cast(COALESCE(heart_rate, '0') as decimal(12,2)) AS heart_rate,
                cast(COALESCE(alcohol, '0') AS decimal(12,2)) AS alcohol,
                cast(COALESCE(sbp, '0') AS decimal(12,2)) AS sbp,
                cast(COALESCE(dbp, '0') AS decimal(12,2)) AS dbp,
                cast(COALESCE(pulse, '0') AS decimal(12,2)) AS pulse,
                cast(COALESCE(spo2, '0') AS decimal(12,2)) AS spo2,
                cast(COALESCE(temp, '0') AS decimal(12,2)) AS temp 
            FROM health_with_rn
            WHERE rn = 1
        )
        select * from health_wide
        """
    return sql.strip()


def abs_workhour_wide(start_date_str: str,end_date_str: str) -> str:
    sql=f"""
    WITH communication_drivers AS (
        SELECT DISTINCT 
            e.employee_name as drv_name,
            b.operator_code
        FROM ai_security.ods_communication_driver_behavior_month b
        GLOBAL JOIN canbus.ods_jituan_bs_employee e 
            ON b.operator_code = e.qualification_no
        WHERE e.employee_name IS NOT NULL 
          AND e.employee_name != ''
    ),
    accident_info AS (
        SELECT
            driver_name,
            accident_date
        FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_accident_forecast_handle
        WHERE accident_liability GLOBAL IN ('048002','048003','048004','048005')  and YEAR(accident_date) = '2025'
    ),
    no_accident_drivers AS (
        SELECT drv_name
        FROM communication_drivers
        WHERE drv_name GLOBAL NOT IN (SELECT driver_name FROM accident_info)
    ),
    rand_window AS (
       select ppartition, drv_name,start_rand, end_rand from ai_security.abs_rand_window
    ),
    workhour_agg AS (
        SELECT
            employee_name AS driver_name,
            toDate(parseDateTimeBestEffort(ppartition)) AS date_key,
            SUM(toFloat64OrNull(safty_mileage)) AS daily_mileage,
            SUM(toFloat64OrNull(work_hour)) AS daily_work_hour
        FROM ai_security.ads_driver_workhour
        WHERE (employee_name, toDate(parseDateTimeBestEffort(ppartition))) GLOBAL IN (
            SELECT driver_name, toDate(accident_date) FROM accident_info
            UNION ALL
            SELECT drv_name, toDate(start_rand) FROM rand_window
        )
        GROUP BY employee_name, toDate(parseDateTimeBestEffort(ppartition))
    ),
    workhour_daily AS (
        SELECT
            driver_name,
            date_key,
            daily_mileage,
            SUM(daily_mileage) OVER (
                PARTITION BY driver_name 
                ORDER BY date_key
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS cumulative_safty_mileage,
            daily_work_hour AS work_hour
        FROM workhour_agg
    ),
    global_avg_mileage AS (
        SELECT AVG(daily_mileage) as avg_mileage_all_drivers
        FROM workhour_agg
        WHERE daily_mileage > 0
    ),
    workhour_wide AS (
        SELECT 
            w.driver_name,
            COALESCE(NULLIF(w.daily_mileage, 0), g.avg_mileage_all_drivers) as safty_mileage,
            w.cumulative_safty_mileage,
            w.work_hour
        FROM workhour_daily w
        GLOBAL CROSS JOIN global_avg_mileage g
    )
    SELECT formatDateTime(now(), '%%Y%%m%%d') AS ppartition,driver_name,safty_mileage,cumulative_safty_mileage,work_hour FROM workhour_wide
    """
    return sql.strip()


def abs_rand_window(start_date_str: str,end_date_str: str) -> str:
    sql=f"""
        WITH communication_drivers AS (
        SELECT DISTINCT 
        e.employee_name as drv_name,
        b.operator_code
        FROM ai_security.ods_communication_driver_behavior_month b 
        GLOBAL JOIN canbus.ods_jituan_bs_employee e 
        ON b.operator_code = e.qualification_no
        WHERE e.employee_name IS NOT NULL 
        AND e.employee_name != ''
        ),

        accident_info AS (
        SELECT
        driver_name,
        accident_date
        FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_accident_forecast_handle
        WHERE accident_liability GLOBAL IN ('048002','048003','048004','048005')  and YEAR(accident_date) = '2025'
        ),

        no_accident_drivers AS (
        SELECT drv_name
        FROM communication_drivers
        WHERE drv_name GLOBAL NOT IN (SELECT driver_name FROM accident_info)
        ),
        rand_window AS (
        SELECT
        drv_name,
        toDateTime(rand_date) AS start_rand,
        start_rand + INTERVAL 1 DAY - INTERVAL 1 SECOND AS end_rand,
        toDateTime(rand_date) AS start_rand2,
        start_rand + INTERVAL 1 HOUR - INTERVAL 1 SECOND AS end_rand2
        FROM (
        SELECT
        drv_name,
        toDate(min_date) + toIntervalDay(rand() %% greatest(1, toUInt32(max_date - min_date))) AS rand_date
        FROM (
        SELECT
        e.employee_name AS drv_name,
        toDate('{start_date_str}') AS min_date, 
        toDate('{end_date_str}') AS max_date 
        FROM ai_security.ods_communication_driver_behavior_month b
        GLOBAL JOIN canbus.ods_jituan_bs_employee e 
        ON b.operator_code = e.qualification_no
        WHERE e.employee_name GLOBAL IN (SELECT drv_name FROM no_accident_drivers) and b.ppartition between '{start_date_str}' and '{end_date_str}'
        GROUP BY e.employee_name
        HAVING max_date - min_date >= 1
        ) t
        ) t2
        )
        SELECT formatDateTime(now(), '%%Y%%m%%d') AS ppartition, drv_name,start_rand, end_rand, start_rand2, end_rand2 FROM rand_window
        """
    return sql.strip()


def ads_air_conditioner_sum(start_date_str: str,end_date_str: str) -> str:
    sql=f"""
        SELECT 
            ppartition,
            obuid,
            SUM(open_time) AS total_open_time,
            SUM(close_time) AS total_close_time,
            COUNT(*) AS record_count
        FROM `ai_security`.`ads_air_conditioner_use`
        where ppartition BETWEEN '{start_date_str}' and '{end_date_str}' 
        GROUP BY 
            ppartition, 
            obuid;
        """
    return sql.strip()


def v_ods_communication_driver_bus_behavior_energy_report_ads_driver_workhouse_week(start_date_str: str,
                                                                                    end_date_str: str) -> str:
    sql=f"""
    WITH cet AS
    (
        SELECT
            b.employee_number AS employee_number,
            b.employee_id AS employee_id,
            b.employee_name AS employee_name,
            b.qualification_no,
            b.route_id as route_id,
            c.obuid AS obuid,
            d.bus_length AS bus_length,
            d.total_weight AS total_weight,
            d.bus_age AS bus_age,
            d.bus_code AS bus_code,
            d.number_plate AS number_plate,
            c.report_time AS report_time,
            c.ppartition AS ppartition,
            c.report_type1_count AS report_type1_count,
            c.report_type2_count AS report_type2_count,
            c.report_type3_count AS report_type3_count,
            c.report_type4_count AS report_type4_count,
            c.report_type5_count AS report_type5_count,
            c.report_type6_count AS report_type6_count,
            c.report_type7_count AS report_type7_count,
            c.report_type8_count AS report_type8_count,
            c.report_type9_count AS report_type9_count,
            c.report_type10_count AS report_type10_count,
            c.report_type11_count AS report_type11_count,
            c.report_type12_count AS report_type12_count,
            c.report_type13_count AS report_type13_count,
            c.report_type14_count AS report_type14_count,
            c.report_type15_count AS report_type15_count,
            c.report_type16_count AS report_type16_count,
            c.report_type17_count AS report_type17_count,
            c.report_type18_count AS report_type18_count,
            c.report_type19_count AS report_type19_count,
            c.report_type20_count AS report_type20_count,
            c.report_type21_count AS report_type21_count,
            c.report_type22_count AS report_type22_count,
            c.report_type23_count AS report_type23_count,
            c.report_type24_count AS report_type24_count,
            c.report_type25_count AS report_type25_count,
            c.report_type26_count AS report_type26_count,
            c.report_type27_count AS report_type27_count,
            c.report_type28_count AS report_type28_count,
            c.report_type29_count AS report_type29_count,
            c.report_type30_count AS report_type30_count,
            c.report_type31_count AS report_type31_count,
            c.report_type32_count AS report_type32_count,
            c.report_type33_count AS report_type33_count,
            c.report_type34_count AS report_type34_count,
            c.report_type36_count AS report_type36_count,
            c.report_type37_count AS report_type37_count
        FROM canbus.ods_jituan_bs_employee AS b
        GLOBAL INNER JOIN (select obuid,report_time,ppartition,operator_code,COLUMNS('^report_type.*_count$') from ai_security.abs_driver_behavior_sum where ppartition between '{start_date_str}' and '{end_date_str}') AS c ON b.qualification_no = c.operator_code
        GLOBAL INNER JOIN canbus.ods_jituan_bs_bus AS d ON c.obuid = d.obuid
    ),
    passenger_data AS (
    SELECT 
        g_worker_code,
        driver_name,
        passenger_total,
        toYYYYMMDD(toDate(operate_date)) AS operate_date_int
    FROM ai_security.ads_driver_passengerflux_daily
    WHERE toDate(operate_date) between toDate('{start_date_str}') and toDate('{end_date_str}')
)
SELECT
    aa.ppartition AS ppartition,
    CAST(aa.employee_number,
 'varchar(10)') AS employee_number,
    CAST(aa.employee_id,
 'varchar(10)') AS employee_id,
    aa.employee_name AS employee_name,
    aa.route_id AS route_id,
    aa.obuid AS obuid,
    aa.bus_code AS bus_code,
    aa.number_plate AS number_plate,
    aa.bus_length AS bus_length,
    aa.total_weight AS total_weight,
    aa.bus_age AS bus_age,
    aa.report_time AS report_time,
    report_type1_count,
    report_type2_count,
    report_type3_count,
    report_type4_count,
    report_type5_count,
    report_type6_count,
    report_type7_count,
    report_type8_count,
    report_type9_count,
    report_type10_count,
    report_type11_count,
    report_type12_count,
    report_type13_count,
    report_type14_count,
    report_type15_count,
    report_type16_count,
    report_type17_count,
    report_type18_count,
    report_type19_count,
    report_type20_count,
    report_type21_count,
    report_type22_count,
    report_type23_count,
    report_type24_count,
    report_type25_count,
    report_type26_count,
    report_type27_count,
    report_type28_count,
    report_type29_count,
    report_type30_count,
    report_type31_count,
    report_type32_count,
    report_type33_count,
    report_type34_count,
    report_type36_count,
    report_type37_count,
    bb.bus_type AS bus_type,
    bb.total_energy_consumption AS total_energy_consumption,
    bb.run_energy_consumption AS run_energy_consumption,
    bb.run_mileage AS run_mileage,
    bb.record_date AS record_date,
    bb.recharge_energy AS recharge_energy,
    bb.route_name AS route_name,
    bb.organ_id AS organ_id,
    bb.organ_name AS organ_name,
    cc.work_hour AS work_hour,
    cc.safty_mileage AS safty_mileage,
    cc.trip_mileage AS trip_mileage,
    cc.total_mileage AS total_mileage,
    route_id,passenger_total 
FROM cet AS aa
GLOBAL INNER JOIN (select ppartition,employee_id,bus_type,total_energy_consumption,run_energy_consumption,run_mileage,record_date,recharge_energy,route_name,organ_id,organ_name from ai_security.ads_driver_energy_report where ppartition between '{start_date_str}' and '{end_date_str}' )  AS bb ON (aa.employee_id = bb.employee_id) AND (aa.ppartition = bb.ppartition)
GLOBAL INNER JOIN (select ppartition,route_name,employee_id,work_hour,safty_mileage,trip_mileage,total_mileage,route_id from ai_security.ads_driver_workhour where ppartition between '{start_date_str}' and '{end_date_str}') AS cc ON (aa.employee_id = cc.employee_id) AND (bb.route_name = cc.route_name) AND (aa.ppartition = cc.ppartition)
GLOBAL INNER JOIN (
SELECT g_worker_code as employee_id, driver_name,sum(passenger_total) AS passenger_total, cast(operate_date_int as varchar(8)) AS ppartition
FROM passenger_data GROUP BY g_worker_code,driver_name,operate_date_int ORDER BY ppartition, g_worker_code) dd on aa.employee_id=dd.employee_id and aa.ppartition=dd.ppartition
    """
    return sql.strip()


def v_drivers_weights_data() -> str:
    sql=f"""
        WITH communication_drivers AS (
        SELECT DISTINCT 
        e.employee_name as drv_name,
        b.operator_code
        FROM ai_security.ods_communication_driver_behavior_month b
        GLOBAL JOIN canbus.ods_jituan_bs_employee e 
        ON b.operator_code = e.qualification_no
        WHERE e.employee_name IS NOT NULL 
        AND e.employee_name != ''
        ),
        accident_info AS (
        SELECT
        driver_name,
        accident_date
        FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_accident_forecast_handle
        WHERE accident_liability IN ('048002','048003','048004','048005')  and YEAR(accident_date) = '2025'
        ),
        no_accident_drivers AS (
        SELECT drv_name
        FROM communication_drivers
        WHERE drv_name NOT IN (SELECT driver_name FROM accident_info)
        ),
        driver_list AS (
        SELECT driver_name, 1 AS has_accident FROM accident_info
        UNION ALL
        SELECT drv_name, 0 FROM no_accident_drivers
        ),
        -- 2023-2024年事故统计
        accident_yearly AS (
        SELECT 
        d.driver_name,
        COALESCE(SUM(a.accident_num), 0) AS total_accidents_2023_2024
        FROM driver_list d
        GLOBAL LEFT JOIN ai_security.ads_driver_accident_yearly a
        ON d.driver_name = a.driver_name
        AND a.yearly IN (2023, 2024)
        GROUP BY d.driver_name
        ),
        -- 计算 safty_mileage 的众数（排除 0 和 NULL）
        mileage_mode AS (
        SELECT safty_mileage as mode_value
        FROM ai_security.abs_workhour_wide
        WHERE safty_mileage > 0
        GROUP BY safty_mileage
        ORDER BY count() DESC
        LIMIT 1
        ),
        pass_station_list AS(
        SELECT 
        drive_date,
        employee_id ,
        driver_name,
        sum(station_count) AS total_station_count,
        count(*) AS trip_count
        FROM (
        SELECT 
        toDate(t.ppartition) AS drive_date,
        t.employee_id AS employee_id, 
        t.employee_name AS driver_name, 
        t.bus_id,
        t.route_id,
        t.from_station,
        t.to_station,
        abs(s2.min_sort - s1.min_sort) + 1 AS station_count
        FROM canbus.ads_triplog_energy t
        GLOBAL LEFT JOIN (
        -- 站点去重：同线路同站名取最小站序
        SELECT line_code, motorcade_name, min(sort) as min_sort
        FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
        GROUP BY line_code, motorcade_name
        ) s1 ON t.route_id = s1.line_code AND t.from_station = s1.motorcade_name
        GLOBAL LEFT JOIN (
        SELECT line_code, motorcade_name, min(sort) as min_sort
        FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
        GROUP BY line_code, motorcade_name
        ) s2 ON t.route_id = s2.line_code AND t.to_station = s2.motorcade_name
        WHERE s1.min_sort IS NOT NULL 
        AND s2.min_sort IS NOT NULL
        AND (t.employee_name, toDate(t.ppartition)) GLOBAL IN (
        SELECT driver_name, toDate(accident_date) FROM accident_info
        UNION ALL
        SELECT drv_name, toDate(start_rand) FROM ai_security.abs_rand_window)
        ) as sub
        GROUP BY 
        drive_date,
        employee_id,
        driver_name
        ),
        pass_turn_list AS(
        SELECT 
        drive_date,
        employee_id ,
        driver_name,
        sum(turn_count) AS total_turn_count
        FROM (
        SELECT
        toDate(t.ppartition) AS drive_date,
        t.employee_id AS employee_id, 
        t.employee_name AS driver_name, 
        t.route_id, 
        COUNT(b.event_type) AS turn_count
        FROM canbus.ads_triplog_energy t
        GLOBAL LEFT JOIN ai_security.ads_event_black_spot b
        ON toString(t.route_id) = splitByChar('#', b.route_ids)[1]
        AND b.event_type GLOBAL IN (2, 3)
        WHERE (t.employee_name, toDate(t.ppartition))  GLOBAL IN (
        SELECT driver_name, toDate(accident_date) FROM accident_info
        UNION ALL
        SELECT drv_name, toDate(start_rand) FROM ai_security.abs_rand_window)
        GROUP BY drive_date, employee_id, driver_name, t.route_id
        ) as sub
        GROUP BY 
        drive_date,
        employee_id,
        driver_name
        ),
        mental_list AS (
        SELECT 
        m.driver_name,
        any(m.heart_level_label) AS heart_level_label, 
        m.follow_year_month 
        FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_dailyreport_driver_heart_body_healthy m
        WHERE m.follow_year_month GLOBAL IN (
        -- 子查询：提取所有事故和随机窗口的月份
        SELECT formatDateTime(toDate(accident_date), '%%Y-%%m') 
        FROM accident_info
        UNION ALL
        SELECT formatDateTime(toDate(start_rand), '%%Y-%%m') 
        FROM ai_security.abs_rand_window
        )
        AND m.driver_name GLOBAL IN (
        -- 子查询：提取所有相关司机名
        SELECT driver_name FROM accident_info
        UNION ALL
        SELECT drv_name FROM ai_security.abs_rand_window
        )
        GROUP BY m.driver_name, m.follow_year_month
        ),
        all_bhv AS (
        SELECT driver_name, drv_sct_bhv, cnt 
        FROM ai_security.abs_all_30m_bhv_with_traffic
        )
        SELECT
        d.driver_name,
        -- 员工基础信息（7列）
        e.sex AS gender,
        e.age,
        e.education_level,
        dateDiff('year', e.entry_time, now()) AS driving_years,
        w.safty_mileage,
        --w.cumulative_safty_mileage,
        w.work_hour,
        ay.total_accidents_2023_2024,
        -- 原37列基础行为
        SUM(CASE WHEN b.drv_sct_bhv = 'N档评价' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS ndang_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '上坡不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS upslope_bad_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '下坡不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS downslope_bad_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '不文明鸣笛' THEN b.cnt ELSE 0 END) AS rude_horn_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '不规范转弯' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), 1) AS bad_turn_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '停站N档评价' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS stop_ndang_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '停车不挂N档' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS no_n_on_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '全局超速' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS global_over_spd_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '减速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS decel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS accel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '动车前安全确认' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), 1) AS before_move_safe_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '区间超速' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS section_over_spd_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '右转弯未停车' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), 1) AS right_turn_no_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '左转弯未刹车' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), 1) AS left_turn_no_brake_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '平路不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS flat_bad_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '开关车门评价' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), 1) AS door_op_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '急停' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS sudden_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '急刹车' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS sudden_brake_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '拒载' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), 1) AS refuse_ride_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '熄火滑行' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS stall_coast_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '空档滑行' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS neutral_coast_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '起步加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS start_accel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '路口再加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS junction_reaccel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '路口大油门' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS junction_heavy_gas_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '路口速度评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS junction_spd_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '车辆未停稳开车门' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS door_open_before_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '进站违规制动' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS illegal_brake_on_entry_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规使用总电' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS illegal_main_power_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规使用手刹' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS illegal_hand_brake_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规使用空调' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS illegal_ac_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规关闭"开门禁启开关"' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS illegal_door_switch_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '门未关起步' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS start_with_open_door_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '飞站' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), 1) AS skip_station_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '驾驶员未系安全带' THEN b.cnt ELSE 0 END) AS no_seat_belt_cnt,
        -- 9列ADAS行为
        SUM(CASE WHEN b.drv_sct_bhv = '车距过近' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS distance_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '车道保持能力下降' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS lane_keep_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '疲劳预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS fatigue_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '分神' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS distraction_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '行人避让预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS pedestrian_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '前车碰撞预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), m.mode_value) AS collision_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '打电话' THEN b.cnt ELSE 0 END) AS phone_call_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '手长时间离开方向盘' THEN b.cnt ELSE 0 END) AS hands_off_wheel_cnt,
        -- 3列失能行为
        SUM(CASE WHEN b.drv_sct_bhv = '严重疲劳驾驶识别' THEN b.cnt ELSE 0 END) AS very_fatigue_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '握方向盘不规范' THEN b.cnt ELSE 0 END) AS hold_steeringwheel_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '驾驶姿势不端正' THEN b.cnt ELSE 0 END) AS driving_posture_warning_cnt,
        -- 3列交通违法
        SUM(CASE WHEN b.drv_sct_bhv = '闯红灯' THEN b.cnt ELSE 0 END) AS red_light_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '闯黄灯' THEN b.cnt ELSE 0 END) AS yellow_light_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违反交通标志标线' THEN b.cnt ELSE 0 END) AS traffic_sign_violation_cnt,
        -- 7列健康指标
        h.heart_rate, h.alcohol, h.sbp, h.dbp, h.pulse, h.spo2, h.temp,
        -- 1列心理指标
        m2.heart_level_label,
        -- 事故标记
        d.has_accident
        FROM driver_list d
        GLOBAL LEFT JOIN canbus.ods_jituan_bs_employee e 
        ON d.driver_name = e.employee_name
        GLOBAL LEFT JOIN ai_security.abs_workhour_wide w 
        ON d.driver_name = w.driver_name
        GLOBAL CROSS JOIN mileage_mode m
        GLOBAL LEFT JOIN all_bhv b 
        ON d.driver_name = b.driver_name
        GLOBAL LEFT JOIN ai_security.abs_health_wide h 
        ON d.driver_name = h.driver_name
        GLOBAL LEFT JOIN pass_station_list p 
        ON d.driver_name = p.driver_name
        GLOBAL LEFT JOIN pass_turn_list p2
        ON d.driver_name = p2.employee_id
        GLOBAL LEFT JOIN mental_list m2
        ON d.driver_name = m2.driver_name
        GLOBAL LEFT JOIN accident_yearly ay 
        ON d.driver_name = ay.driver_name 
        group by 
        d.driver_name, 
        d.has_accident,
        e.sex, 
        e.age, 
        e.education_level, 
        driving_years,
        --w.cumulative_safty_mileage,
        w.safty_mileage,
        w.work_hour,
        h.heart_rate, h.alcohol, h.sbp, h.dbp, h.pulse, h.spo2, h.temp,
        m2.heart_level_label,
        m.mode_value,
        p.total_station_count,
        p2.total_turn_count,
        ay.total_accidents_2023_2024
        ORDER BY d.driver_name;
    """
    return sql.strip()


def get_risk_value() -> str:
    sql=f"""select
        dict_id, item_text, item_value
        from ai_security.sys_dict_item sdi
        where
        dict_id GLOBAL in (
            select id from ai_security.sys_dict sd where sd.dict_code = 'risk_level'
        )"""
    return sql.strip()




def abs_all_1HOUR_bhv_with_traffic(start_date_str:str,end_date_str: str) -> str:
    sql1="""
        WITH communication_drivers AS (
          SELECT DISTINCT 
              e.employee_name as drv_name,
              b.operator_code
          FROM ai_security.ods_communication_driver_behavior_month b
          GLOBAL JOIN canbus.ods_jituan_bs_employee e 
              ON b.operator_code = e.qualification_no
          WHERE e.employee_name IS NOT NULL 
            AND e.employee_name != ''
      ),
      accident_info AS (
          SELECT
              driver_name,
              accident_date
          FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_accident_forecast_handle
          WHERE accident_liability GLOBAL IN ('048002','048003','048004','048005')  and YEAR(accident_date) = '2025'
      ),
      no_accident_drivers AS (
          SELECT drv_name
          FROM communication_drivers
          WHERE drv_name GLOBAL NOT IN (SELECT driver_name FROM accident_info)
      ),
      rand_window AS (
           select ppartition, drv_name,start_rand, end_rand, start_rand2, end_rand2 from abs_rand_window
      ),
      accident_30m_bhv AS (
          SELECT
              a.driver_name,
              b.drv_sct_bhv,
              COUNT(*) AS cnt
          FROM accident_info a
          GLOBAL JOIN ai_security.ods_jituan_oracle_10_181_92_175_sc_sync_v_comm_drv_sct_bhv_all b
            ON a.driver_name = b.drv_name
          WHERE b.rcrd_time BETWEEN toDate(a.accident_date)
                            AND toDate(a.accident_date) + INTERVAL 1 HOUR - INTERVAL 1 SECOND
          GROUP BY a.driver_name, b.drv_sct_bhv
      ),
       rand_30m_bhv AS (
          SELECT 
              e.employee_name AS driver_name,
              CASE 
                WHEN b.report_type = 6 THEN '起步加速评价'
                WHEN b.report_type = 8 THEN '加速评价'
                WHEN b.report_type = 7 THEN '减速评价'
                WHEN b.report_type = 9 THEN '急刹车'
                WHEN b.report_type = 15 THEN '路口再加速评价'
                WHEN b.report_type = 14 THEN '路口速度评价'
                WHEN b.report_type = 18 THEN '违规使用手刹'
                WHEN b.report_type = 1 THEN '停站N档评价'
                WHEN b.report_type = 16 THEN 'N档评价'
                WHEN b.report_type = 22 THEN '不规范转弯'
                WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                WHEN b.report_type = 12 THEN '门未关起步'
                WHEN b.report_type = 5 THEN '空档滑行'
                WHEN b.report_type = 4 THEN '熄火滑行'
                WHEN b.report_type = 19 THEN '不文明鸣笛'
                WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                WHEN b.report_type = 21 THEN '拒载'
                WHEN b.report_type = 20 THEN '飞站'
                WHEN b.report_type = 10 THEN '急停'
                WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                WHEN b.report_type = 2 THEN '停车不挂N档'
                WHEN b.report_type = 17 THEN '开关车门评价'
                WHEN b.report_type = 23 THEN '动车前安全确认'
                WHEN b.report_type = 24 THEN '违规使用空调'
                WHEN b.report_type = 25 THEN '平路不规范'
                WHEN b.report_type = 26 THEN '上坡不规范'
                WHEN b.report_type = 27 THEN '下坡不规范'
                WHEN b.report_type = 28 THEN '违规使用总电'
                WHEN b.report_type = 29 THEN '路口大油门'
                WHEN b.report_type = 30 THEN '进站违规制动'
                WHEN b.report_type = 33 THEN '区间超速'
                WHEN b.report_type = 34 THEN '全局超速'
                WHEN b.report_type = 36 THEN '左转弯未刹车'
                WHEN b.report_type = 37 THEN '右转弯未停车'
                END AS drv_sct_bhv,
              COUNT(*) AS cnt
          FROM rand_window r
          GLOBAL JOIN canbus.ods_jituan_bs_employee e 
              ON r.drv_name = e.employee_name
          GLOBAL JOIN ai_security.ods_communication_driver_behavior_month b
            ON e.qualification_no = b.operator_code
          WHERE b.report_time BETWEEN r.start_rand2 AND r.end_rand2
          GROUP BY e.employee_name, 
              CASE 
                WHEN b.report_type = 6 THEN '起步加速评价'
                WHEN b.report_type = 8 THEN '加速评价'
                WHEN b.report_type = 7 THEN '减速评价'
                WHEN b.report_type = 9 THEN '急刹车'
                WHEN b.report_type = 15 THEN '路口再加速评价'
                WHEN b.report_type = 14 THEN '路口速度评价'
                WHEN b.report_type = 18 THEN '违规使用手刹'
                WHEN b.report_type = 1 THEN '停站N档评价'
                WHEN b.report_type = 16 THEN 'N档评价'
                WHEN b.report_type = 22 THEN '不规范转弯'
                WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                WHEN b.report_type = 12 THEN '门未关起步'
                WHEN b.report_type = 5 THEN '空档滑行'
                WHEN b.report_type = 4 THEN '熄火滑行'
                WHEN b.report_type = 19 THEN '不文明鸣笛'
                WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                WHEN b.report_type = 21 THEN '拒载'
                WHEN b.report_type = 20 THEN '飞站'
                WHEN b.report_type = 10 THEN '急停'
                WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                WHEN b.report_type = 2 THEN '停车不挂N档'
                WHEN b.report_type = 17 THEN '开关车门评价'
                WHEN b.report_type = 23 THEN '动车前安全确认'
                WHEN b.report_type = 24 THEN '违规使用空调'
                WHEN b.report_type = 25 THEN '平路不规范'
                WHEN b.report_type = 26 THEN '上坡不规范'
                WHEN b.report_type = 27 THEN '下坡不规范'
                WHEN b.report_type = 28 THEN '违规使用总电'
                WHEN b.report_type = 29 THEN '路口大油门'
                WHEN b.report_type = 30 THEN '进站违规制动'
                WHEN b.report_type = 33 THEN '区间超速'
                WHEN b.report_type = 34 THEN '全局超速'
                WHEN b.report_type = 36 THEN '左转弯未刹车'
                WHEN b.report_type = 37 THEN '右转弯未停车'
                END
      ),
      accident_adas_bhv AS (
          SELECT
              a.driver_name,
              CASE 
                  WHEN e.resultname = '车距过近' THEN '车距过近'
                  WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                  WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                  WHEN e.resultname = '分神' THEN '分神'
                  WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                  WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                  WHEN e.resultname = '打电话' THEN '打电话'
                  WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                  ELSE e.resultname
              END AS drv_sct_bhv,
              COUNT(*) AS cnt
          FROM accident_info a
          GLOBAL JOIN ai_security.ods_jituan_mssql_192_168_181_135_eddata_eddata e
            ON a.driver_name = e.drivername
          WHERE e.happentime BETWEEN toDate(a.accident_date)
                             AND toDate(a.accident_date) + INTERVAL 1 HOUR - INTERVAL 1 SECOND
            AND e.resultname GLOBAL IN ('车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警','前车碰撞预警','未系安全带','打电话','手长时间离开方向盘（吸烟）')
          GROUP BY a.driver_name, 
              CASE 
                  WHEN e.resultname = '车距过近' THEN '车距过近'
                  WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                  WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                  WHEN e.resultname = '分神' THEN '分神'
                  WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                  WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                  WHEN e.resultname = '打电话' THEN '打电话'
                  WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                  ELSE e.resultname
              END
      ),"""

    sql2=f"""rand_adas_bhv AS (
        SELECT
            r.drv_name AS driver_name,
            CASE 
                WHEN e.resultname = '车距过近' THEN '车距过近'
                WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                WHEN e.resultname = '分神' THEN '分神'
                WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                WHEN e.resultname = '打电话' THEN '打电话'
                WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                ELSE e.resultname
            END AS drv_sct_bhv,
            COUNT(*) AS cnt
        FROM rand_window r
        GLOBAL JOIN ai_security.ods_jituan_mssql_192_168_181_135_eddata_eddata e
          ON r.drv_name = e.drivername
        WHERE e.happentime BETWEEN r.start_rand AND r.end_rand
          AND e.resultname GLOBAL IN ('车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警','前车碰撞预警','未系安全带','打电话','手长时间离开方向盘（吸烟）')
        GROUP BY r.drv_name, 
            CASE 
                WHEN e.resultname = '车距过近' THEN '车距过近'
                WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                WHEN e.resultname = '分神' THEN '分神'
                WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                WHEN e.resultname = '打电话' THEN '打电话'
                WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                ELSE e.resultname
            END
    ),
     rand_aebs_bhv AS (
                SELECT
                    r.drv_name AS driver_name,
                    CASE 
                        WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                        WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                        WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
                    END AS drv_sct_bhv,
                    COUNT(*) AS cnt
                FROM ai_security.abs_rand_window r
                GLOBAL JOIN ai_security.ods_jituan_mysql_10_163_90_62_strong_tpss_alarm_warn_base_aebs e
                ON r.drv_name = e.driverName
                WHERE toDate(e.warnTime) BETWEEN r.start_rand2 AND r.end_rand2
                AND e.typename GLOBAL IN ('严重疲劳驾驶识别','握方向盘不规范','驾驶姿势不端正')
                GROUP BY r.drv_name, 
                CASE 
                    WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                    WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                    WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
                END
            ),
              accident_aebs_bhv AS (
            SELECT
                a.driver_name,
                CASE 
                    WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                    WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                    WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM accident_info a
            GLOBAL JOIN ai_security.ods_jituan_mysql_10_163_90_62_strong_tpss_alarm_warn_base_aebs e
            ON a.driver_name = e.driverName
            WHERE toDate(e.warnTime) BETWEEN toDate(a.accident_date)
            AND toDate(a.accident_date) + INTERVAL 1 HOUR - INTERVAL 1 SECOND
            AND e.typename GLOBAL IN ('严重疲劳驾驶识别','握方向盘不规范','驾驶姿势不端正')
            GROUP BY a.driver_name, 
            CASE 
                WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
            END
        ),
          all_30m_bhv AS (
                SELECT * FROM accident_30m_bhv
                UNION ALL
                SELECT * FROM rand_30m_bhv
                UNION ALL
                SELECT * FROM accident_adas_bhv
                UNION ALL
                SELECT * FROM rand_adas_bhv
                UNION ALL
                SELECT * FROM accident_aebs_bhv
                UNION ALL
                SELECT * FROM rand_aebs_bhv
          ),
          accident_traffic_illegal AS (
              SELECT
                  t.driver_name,
                  CASE 
                      WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                      WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                      ELSE '违反交通标志标线'
                  END AS drv_sct_bhv,
                  COUNT(*) AS cnt
              FROM accident_info a
              GLOBAL JOIN ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_traffic_illegal_handle t
                ON a.driver_name = t.driver_name
              WHERE t.illegal_date = toDate(a.accident_date)  
                AND t.illegal_classify_label = '违反交通指示灯号或禁令标志、标线'
              GROUP BY t.driver_name, 
                  CASE 
                      WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                      WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                      ELSE '违反交通标志标线'
                  END
          ),
          rand_traffic_illegal AS (
              SELECT
                  t.driver_name,
                  CASE 
                      WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                      WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                      ELSE '违反交通标志标线'
                  END AS drv_sct_bhv,
                  COUNT(*) AS cnt
              FROM rand_window r
              GLOBAL JOIN ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_traffic_illegal_handle t
                ON r.drv_name = t.driver_name
              WHERE t.illegal_date = toDate(r.start_rand)  
                AND t.illegal_classify_label = '违反交通指示灯号或禁令标志、标线'
              GROUP BY t.driver_name, 
                  CASE 
                      WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                      WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                      ELSE '违反交通标志标线'
                  END
          ),
    
          all_30m_bhv_with_traffic AS (
              SELECT * FROM all_30m_bhv
              UNION ALL
              SELECT * FROM accident_traffic_illegal
              UNION ALL
              SELECT * FROM rand_traffic_illegal
          ) 
          select  formatDateTime(now(), '%%Y%%m%%d') AS ppartition,
                  COALESCE(driver_name,'') as driver_name,
                  COALESCE(drv_sct_bhv,'') as drv_sct_bhv,
                  COALESCE(cnt,0) AS cnt  from all_30m_bhv_with_traffic """
    sql=sql1+sql2
    return sql.strip()

def v_drivers_weights_1hour_data()->str:
    sql = f"""
        WITH communication_drivers AS (
        SELECT DISTINCT 
        e.employee_name as drv_name,
        b.operator_code
        FROM ai_security.ods_communication_driver_behavior_month b
        GLOBAL JOIN canbus.ods_jituan_bs_employee e 
        ON b.operator_code = e.qualification_no
        WHERE e.employee_name IS NOT NULL 
        AND e.employee_name != ''
        ),
        accident_info AS (
        SELECT
        driver_name,
        accident_date
        FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_accident_forecast_handle
        WHERE accident_liability GLOBAL IN ('048002','048003','048004','048005')  and YEAR(accident_date) = '2025'
        ),
        no_accident_drivers AS (
        SELECT drv_name
        FROM communication_drivers
        WHERE drv_name GLOBAL NOT IN (SELECT driver_name FROM accident_info)
        ),
        driver_list AS (
        SELECT driver_name, 1 AS has_accident FROM accident_info
        UNION ALL
        SELECT drv_name, 0 FROM no_accident_drivers
        ),
        -- 2023-2024年事故统计
        accident_yearly AS (
        SELECT 
        d.driver_name,
        COALESCE(SUM(a.accident_num), 0) AS total_accidents_2023_2024
        FROM driver_list d
        GLOBAL LEFT JOIN ai_security.ads_driver_accident_yearly a
        ON d.driver_name = a.driver_name
        AND a.yearly GLOBAL IN (2023, 2024)
        GROUP BY d.driver_name
        ),
        -- 计算 safty_mileage 的众数（排除 0 和 NULL）
        mileage_mode AS (
        SELECT safty_mileage as mode_value
        FROM ai_security.abs_workhour_wide
        WHERE safty_mileage > 0
        GROUP BY safty_mileage
        ORDER BY count() DESC
        LIMIT 1
        ),
        pass_station_list AS(
        SELECT 
        drive_date,
        employee_id ,
        driver_name,
        sum(station_count) AS total_station_count,
        count(*) AS trip_count
        FROM (
        SELECT 
        toDate(t.ppartition) AS drive_date,
        t.employee_id AS employee_id, 
        t.employee_name AS driver_name, 
        t.bus_id,
        t.route_id,
        t.from_station,
        t.to_station,
        abs(s2.min_sort - s1.min_sort) + 1 AS station_count
        FROM canbus.ads_triplog_energy t
        GLOBAL LEFT JOIN (
        -- 站点去重：同线路同站名取最小站序
        SELECT line_code, motorcade_name, min(sort) as min_sort
        FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
        GROUP BY line_code, motorcade_name
        ) s1 ON t.route_id = s1.line_code AND t.from_station = s1.motorcade_name
        GLOBAL LEFT JOIN (
        SELECT line_code, motorcade_name, min(sort) as min_sort
        FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
        GROUP BY line_code, motorcade_name
        ) s2 ON t.route_id = s2.line_code AND t.to_station = s2.motorcade_name
        WHERE s1.min_sort IS NOT NULL 
        AND s2.min_sort IS NOT NULL
        AND (t.employee_name, toDate(t.ppartition)) GLOBAL IN (
        SELECT driver_name, toDate(accident_date) FROM accident_info
        UNION ALL
        SELECT drv_name, toDate(start_rand) FROM ai_security.abs_rand_window)
        ) as sub
        GROUP BY 
        drive_date,
        employee_id,
        driver_name
        ),
        pass_turn_list AS(
        SELECT 
        drive_date,
        employee_id ,
        driver_name,
        sum(turn_count) AS total_turn_count
        FROM (
        SELECT
        toDate(t.ppartition) AS drive_date,
        t.employee_id AS employee_id, 
        t.employee_name AS driver_name, 
        t.route_id, 
        COUNT(b.event_type) AS turn_count
        FROM canbus.ads_triplog_energy t
        GLOBAL LEFT JOIN ai_security.ads_event_black_spot b
        ON toString(t.route_id) = splitByChar('#', b.route_ids)[1]
        AND b.event_type GLOBAL IN (2, 3)
        WHERE (t.employee_name, toDate(t.ppartition)) GLOBAL  IN (
        SELECT driver_name, toDate(accident_date) FROM accident_info
        UNION ALL
        SELECT drv_name, toDate(start_rand) FROM ai_security.abs_rand_window)
        GROUP BY drive_date, employee_id, driver_name, t.route_id
        ) as sub
        GROUP BY 
        drive_date,
        employee_id,
        driver_name
        ),
        mental_list AS (
        SELECT 
        m.driver_name,
        any(m.heart_level_label) AS heart_level_label, 
        m.follow_year_month 
        FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_dailyreport_driver_heart_body_healthy m
        WHERE m.follow_year_month GLOBAL IN (
        -- 子查询：提取所有事故和随机窗口的月份
        SELECT formatDateTime(toDate(accident_date), '%%Y-%%m') 
        FROM accident_info
        UNION ALL
        SELECT formatDateTime(toDate(start_rand), '%%Y-%%m') 
        FROM ai_security.abs_rand_window
        )
        AND m.driver_name GLOBAL IN (
        -- 子查询：提取所有相关司机名
        SELECT driver_name FROM accident_info
        UNION ALL
        SELECT drv_name FROM ai_security.abs_rand_window
        )
        GROUP BY m.driver_name, m.follow_year_month
        ),
        all_bhv AS (
        SELECT driver_name, drv_sct_bhv, cnt 
        FROM ai_security.abs_all_1HOUR_bhv_with_traffic
        )
        SELECT
        d.driver_name,
        -- 员工基础信息（7列）
        e.sex AS gender,
        e.age,
        e.education_level,
        dateDiff('year', e.entry_time, now()) AS driving_years,
        w.safty_mileage,
        --w.cumulative_safty_mileage,
        w.work_hour,
        ay.total_accidents_2023_2024,
        -- 原37列基础行为
        SUM(CASE WHEN b.drv_sct_bhv = 'N档评价' THEN b.cnt ELSE 0 END) AS ndang_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '上坡不规范' THEN b.cnt ELSE 0 END) AS upslope_bad_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '下坡不规范' THEN b.cnt ELSE 0 END) AS downslope_bad_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '不文明鸣笛' THEN b.cnt ELSE 0 END) AS rude_horn_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '不规范转弯' THEN b.cnt ELSE 0 END) AS bad_turn_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '停站N档评价' THEN b.cnt ELSE 0 END) AS stop_ndang_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '停车不挂N档' THEN b.cnt ELSE 0 END) AS no_n_on_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '全局超速' THEN b.cnt ELSE 0 END) AS global_over_spd_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '减速评价' THEN b.cnt ELSE 0 END) AS decel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '加速评价' THEN b.cnt ELSE 0 END) AS accel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '动车前安全确认' THEN b.cnt ELSE 0 END) AS before_move_safe_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '区间超速' THEN b.cnt ELSE 0 END) AS section_over_spd_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '右转弯未停车' THEN b.cnt ELSE 0 END) AS right_turn_no_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '左转弯未刹车' THEN b.cnt ELSE 0 END) AS left_turn_no_brake_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '平路不规范' THEN b.cnt ELSE 0 END) AS flat_bad_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '开关车门评价' THEN b.cnt ELSE 0 END) AS door_op_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '急停' THEN b.cnt ELSE 0 END) AS sudden_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '急刹车' THEN b.cnt ELSE 0 END) AS sudden_brake_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '拒载' THEN b.cnt ELSE 0 END) AS refuse_ride_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '熄火滑行' THEN b.cnt ELSE 0 END) AS stall_coast_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '空档滑行' THEN b.cnt ELSE 0 END) AS neutral_coast_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '起步加速评价' THEN b.cnt ELSE 0 END) AS start_accel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '路口再加速评价' THEN b.cnt ELSE 0 END) AS junction_reaccel_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '路口大油门' THEN b.cnt ELSE 0 END) AS junction_heavy_gas_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '路口速度评价' THEN b.cnt ELSE 0 END) AS junction_spd_eval_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '车辆未停稳开车门' THEN b.cnt ELSE 0 END) AS door_open_before_stop_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '进站违规制动' THEN b.cnt ELSE 0 END) AS illegal_brake_on_entry_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规使用总电' THEN b.cnt ELSE 0 END) AS illegal_main_power_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规使用手刹' THEN b.cnt ELSE 0 END) AS illegal_hand_brake_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规使用空调' THEN b.cnt ELSE 0 END) AS illegal_ac_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违规关闭"开门禁启开关"' THEN b.cnt ELSE 0 END) AS illegal_door_switch_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '门未关起步' THEN b.cnt ELSE 0 END) AS start_with_open_door_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '飞站' THEN b.cnt ELSE 0 END) AS skip_station_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '驾驶员未系安全带' THEN b.cnt ELSE 0 END) AS no_seat_belt_cnt,
        -- 9列ADAS行为
        SUM(CASE WHEN b.drv_sct_bhv = '车距过近' THEN b.cnt ELSE 0 END) AS distance_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '车道保持能力下降' THEN b.cnt ELSE 0 END) AS lane_keep_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '疲劳预警' THEN b.cnt ELSE 0 END) AS fatigue_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '分神' THEN b.cnt ELSE 0 END) AS distraction_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '行人避让预警' THEN b.cnt ELSE 0 END) AS pedestrian_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '前车碰撞预警' THEN b.cnt ELSE 0 END) AS collision_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '打电话' THEN b.cnt ELSE 0 END) AS phone_call_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '手长时间离开方向盘' THEN b.cnt ELSE 0 END) AS hands_off_wheel_cnt,
        -- 3列失能行为
        SUM(CASE WHEN b.drv_sct_bhv = '严重疲劳驾驶识别' THEN b.cnt ELSE 0 END) AS very_fatigue_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '握方向盘不规范' THEN b.cnt ELSE 0 END) AS hold_steeringwheel_warning_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '驾驶姿势不端正' THEN b.cnt ELSE 0 END) AS driving_posture_warning_cnt,
        -- 3列交通违法
        SUM(CASE WHEN b.drv_sct_bhv = '闯红灯' THEN b.cnt ELSE 0 END) AS red_light_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '闯黄灯' THEN b.cnt ELSE 0 END) AS yellow_light_cnt,
        SUM(CASE WHEN b.drv_sct_bhv = '违反交通标志标线' THEN b.cnt ELSE 0 END) AS traffic_sign_violation_cnt,
        -- 7列健康指标
        h.heart_rate, h.alcohol, h.sbp, h.dbp, h.pulse, h.spo2, h.temp,
        -- 1列心理指标
        m2.heart_level_label,
        -- 事故标记
        d.has_accident
        FROM driver_list d
        GLOBAL LEFT JOIN canbus.ods_jituan_bs_employee e 
        ON d.driver_name = e.employee_name
        GLOBAL LEFT JOIN ai_security.abs_workhour_wide w 
        ON d.driver_name = w.driver_name
        GLOBAL CROSS JOIN mileage_mode m
        GLOBAL LEFT JOIN all_bhv b 
        ON d.driver_name = b.driver_name
        GLOBAL LEFT JOIN ai_security.abs_health_wide h 
        ON d.driver_name = h.driver_name
        GLOBAL LEFT JOIN pass_station_list p 
        ON d.driver_name = p.driver_name
        GLOBAL LEFT JOIN pass_turn_list p2
        ON d.driver_name = p2.employee_id
        GLOBAL LEFT JOIN mental_list m2
        ON d.driver_name = m2.driver_name
        GLOBAL LEFT JOIN accident_yearly ay 
        ON d.driver_name = ay.driver_name 
        group by 
        d.driver_name, 
        d.has_accident,
        e.sex, 
        e.age, 
        e.education_level, 
        driving_years,
        --w.cumulative_safty_mileage,
        w.safty_mileage,
        w.work_hour,
        h.heart_rate, h.alcohol, h.sbp, h.dbp, h.pulse, h.spo2, h.temp,
        m2.heart_level_label,
        m.mode_value,
        p.total_station_count,
        p2.total_turn_count,
        ay.total_accidents_2023_2024
        ORDER BY d.driver_name;
    """
    return sql.strip()

def station_huading_sql(ym_str:str)->str:
    # ym = datetime.strptime(start_date, "%Y-%m-%d")
    # ym_str=ym.strftime("%Y-%m")
    sql= f"""
        WITH cet AS (
    SELECT 
        bus_station_id,
        bus_station_name, 
        organ_id,
        organ_name, 
        MAX(CASE WHEN quota_id = '站场画像-三防安全-划定区域-三防应急设施、设备' THEN risk_data END) AS `三防应急设施、设备_1`,
        MAX(CASE WHEN quota_id = '站场画像-三防安全-划定区域-三防应急设施、设备' THEN CASE WHEN risk_level='安全型' THEN '2' WHEN risk_level='关注型' THEN '1' ELSE '0' END END) AS `三防应急设施、设备`,
        MAX(CASE WHEN quota_id = '站场画像-三防安全-划定区域-临水临崖' THEN risk_data END) AS `临水临崖_1`,
        MAX(CASE WHEN quota_id = '站场画像-三防安全-划定区域-临水临崖' THEN CASE WHEN risk_level='安全型' THEN '2' WHEN risk_level='关注型' THEN '1' ELSE '0' END END) AS `临水临崖`,
        MAX(CASE WHEN quota_id = '站场画像-三防安全-划定区域-场地设施、建筑、树木' THEN risk_data END) AS `场地设施、建筑、树木_1`,
        MAX(CASE WHEN quota_id = '站场画像-三防安全-划定区域-场地设施、建筑、树木' THEN CASE WHEN risk_level='安全型' THEN '2' WHEN risk_level='关注型' THEN '1' ELSE '0' END END) AS `场地设施、建筑、树木`,
        MAX(CASE WHEN quota_id = '站场画像-三防安全-划定区域-场站地势' THEN risk_data END) AS `场站地势_1`,
        MAX(CASE WHEN quota_id = '站场画像-三防安全-划定区域-场站地势' THEN CASE WHEN risk_level='安全型' THEN '2' WHEN risk_level='关注型' THEN '1' ELSE '0' END END) AS `场站地势`,
        MAX(CASE WHEN quota_id = '站场画像-三防安全-划定区域-监控设备' THEN risk_data END) AS `监控设备_1`,
        MAX(CASE WHEN quota_id = '站场画像-三防安全-划定区域-监控设备' THEN CASE WHEN risk_level='安全型' THEN '2' WHEN risk_level='关注型' THEN '1' ELSE '0' END END) AS `监控设备`,
        MAX(CASE WHEN quota_id = '站场画像-交通安全-划定区域-人流量、车流量' THEN risk_data END) AS `人流量、车流量_1`,
        MAX(CASE WHEN quota_id = '站场画像-交通安全-划定区域-人流量、车流量' THEN CASE WHEN risk_level='安全型' THEN '2' WHEN risk_level='关注型' THEN '1' ELSE '0' END END) AS `人流量、车流量`,
        MAX(CASE WHEN quota_id = '站场画像-交通安全-划定区域-人车分流' THEN risk_data END) AS `人车分流_1`,
        MAX(CASE WHEN quota_id = '站场画像-交通安全-划定区域-人车分流' THEN CASE WHEN risk_level='安全型' THEN '2' WHEN risk_level='关注型' THEN '1' ELSE '0' END END) AS `人车分流`,
        MAX(CASE WHEN quota_id = '站场画像-交通安全-划定区域-公交线路、车数' THEN risk_data END) AS `公交线路、车数_1`,
        MAX(CASE WHEN quota_id = '站场画像-交通安全-划定区域-公交线路、车数' THEN CASE WHEN risk_level='安全型' THEN '2' WHEN risk_level='关注型' THEN '1' ELSE '0' END END) AS `公交线路、车数`,
        MAX(CASE WHEN quota_id = '站场画像-交通安全-划定区域-出入口' THEN risk_data END) AS `出入口_1`,
        MAX(CASE WHEN quota_id = '站场画像-交通安全-划定区域-出入口' THEN CASE WHEN risk_level='安全型' THEN '2' WHEN risk_level='关注型' THEN '1' ELSE '0' END END) AS `出入口`,
        MAX(CASE WHEN quota_id = '站场画像-交通安全-划定区域-夜间灯光' THEN risk_data END) AS `夜间灯光_1`,
        MAX(CASE WHEN quota_id = '站场画像-交通安全-划定区域-夜间灯光' THEN CASE WHEN risk_level='安全型' THEN '2' WHEN risk_level='关注型' THEN '1' ELSE '0' END END) AS `夜间灯光`,
        MAX(CASE WHEN quota_id = '站场画像-交通安全-划定区域-安保' THEN risk_data END) AS `安保_1`,
        MAX(CASE WHEN quota_id = '站场画像-交通安全-划定区域-安保' THEN CASE WHEN risk_level='安全型' THEN '2' WHEN risk_level='关注型' THEN '1' ELSE '0' END END) AS `安保`,
        MAX(CASE WHEN quota_id = '站场画像-交通安全-划定区域-站场警示标志' THEN risk_data END) AS `站场警示标志_1`,
        MAX(CASE WHEN quota_id = '站场画像-交通安全-划定区域-站场警示标志' THEN CASE WHEN risk_level='安全型' THEN '2' WHEN risk_level='关注型' THEN '1' ELSE '0' END END) AS `站场警示标志`,
        MAX(CASE WHEN quota_id = '站场画像-交通安全-划定区域-视觉盲区' THEN risk_data END) AS `视觉盲区_1`,
        MAX(CASE WHEN quota_id = '站场画像-交通安全-划定区域-视觉盲区' THEN CASE WHEN risk_level='安全型' THEN '2' WHEN risk_level='关注型' THEN '1' ELSE '0' END END) AS `视觉盲区`,
        MAX(CASE WHEN quota_id = '站场画像-消防安全-划定区域-充电场车数' THEN risk_data END) AS `充电场车数_1`,
        MAX(CASE WHEN quota_id = '站场画像-消防安全-划定区域-充电场车数' THEN CASE WHEN risk_level='安全型' THEN '2' WHEN risk_level='关注型' THEN '1' ELSE '0' END END) AS `充电场车数`,
        MAX(CASE WHEN quota_id = '站场画像-消防安全-划定区域-消防水源' THEN risk_data END) AS `消防水源_1`,
        MAX(CASE WHEN quota_id = '站场画像-消防安全-划定区域-消防水源' THEN CASE WHEN risk_level='安全型' THEN '2' WHEN risk_level='关注型' THEN '1' ELSE '0' END END) AS `消防水源`,
        MAX(CASE WHEN quota_id = '站场画像-消防安全-划定区域-消防设备' THEN risk_data END) AS `消防设备_1`,
        MAX(CASE WHEN quota_id = '站场画像-消防安全-划定区域-消防设备' THEN CASE WHEN risk_level='安全型' THEN '2' WHEN risk_level='关注型' THEN '1' ELSE '0' END END) AS `消防设备`,
        MAX(CASE WHEN quota_id = '站场画像-消防安全-划定区域-风险隐患' THEN risk_data END) AS `风险隐患_1`,
        MAX(CASE WHEN quota_id = '站场画像-消防安全-划定区域-风险隐患' THEN CASE WHEN risk_level='安全型' THEN '2' WHEN risk_level='关注型' THEN '1' ELSE '0' END END) AS `风险隐患`
    FROM ai_security.ods_custom_bus_station_profile
    WHERE quota_id LIKE '%划定区域%' 
      AND run_date = '{ym_str}' 
    GROUP BY bus_station_id, bus_station_name, organ_id, organ_name
)
SELECT 
    aa.id AS station_code,
    aa.station_name,
    aa.terminal_name,
    bb.organ_id,
    bb.organ_name,
    aa.station_type,       -- 修正1: 从 aa 表获取，去掉多余逗号
    aa.run_area,           -- 修正2: 从 aa 表获取
    '划定区域' AS station_properties, 
    aa.route_num,
    aa.service_bus_number,
    bb.`三防应急设施、设备`,
    bb.`临水临崖`,
    bb.`场地设施、建筑、树木`,
    bb.`场站地势`,
    bb.`监控设备`,
    bb.`人流量、车流量`,
    bb.`人车分流`,
    bb.`公交线路、车数`,
    bb.`出入口`,
    bb.`夜间灯光`,
    bb.`安保`,
    bb.`站场警示标志`,
    bb.`视觉盲区`,
    bb.`充电场车数`,
    bb.`消防水源`,
    bb.`消防设备`,
    bb.`风险隐患`
FROM ai_security.ods_jituan_bs_bus_park aa 
INNER JOIN cet bb ON aa.id = bb.bus_station_id where aa.station_properties='划定区域';
        """
    return sql.strip()

def station_roadside_sql(ym_str:str)->str:
    # ym=datetime.strptime(start_date, "%Y-%m-%d")
    # ym_str=ym.strftime("%Y-%m")
    sql=f"""
        with cet as (select  bus_station_id,bus_station_name,organ_id,organ_name, 
            MAX(CASE WHEN quota_id = '站场画像-三防安全-路边区域-三防应急设施、设备' THEN risk_data END ) AS `三防应急设施、设备_1`,
            MAX(CASE WHEN quota_id = '站场画像-三防安全-路边区域-三防应急设施、设备' THEN case when risk_level='安全型' then '2' when risk_level='关注型' then '1' else '0' end END) AS `三防应急设施、设备`,
            MAX(CASE WHEN quota_id = '站场画像-三防安全-路边区域-临水临崖' THEN risk_data END) AS `临水临崖_1`,
            MAX(CASE WHEN quota_id = '站场画像-三防安全-路边区域-临水临崖' THEN case when risk_level='安全型' then '2' when risk_level='关注型' then '1' else '0' end END) AS `临水临崖`,
            MAX(CASE WHEN quota_id = '站场画像-三防安全-路边区域-场地设施、建筑、树木' THEN risk_data END) AS `场地设施、建筑、树木_1`,
            MAX(CASE WHEN quota_id = '站场画像-三防安全-路边区域-场地设施、建筑、树木' THEN case when risk_level='安全型' then '2' when risk_level='关注型' then '1' else '0' end END) AS `场地设施、建筑、树木`,
            MAX(CASE WHEN quota_id = '站场画像-三防安全-路边区域-场站地势' THEN risk_data END) AS `场站地势_1`,
            MAX(CASE WHEN quota_id = '站场画像-三防安全-路边区域-场站地势' THEN case when risk_level='安全型' then '2' when risk_level='关注型' then '1' else '0' end END) AS `场站地势`,
            MAX(CASE WHEN quota_id = '站场画像-三防安全-路边区域-监控设备' THEN risk_data END) AS `监控设备_1`,
            MAX(CASE WHEN quota_id = '站场画像-三防安全-路边区域-监控设备' THEN case when risk_level='安全型' then '2' when risk_level='关注型' then '1' else '0' end END) AS `监控设备`,
            MAX(CASE WHEN quota_id = '站场画像-交通安全-路边区域-人流量、车流量' THEN risk_data END) AS `人流量、车流量_1`,
            MAX(CASE WHEN quota_id = '站场画像-交通安全-路边区域-人流量、车流量' THEN case when risk_level='安全型' then '2' when risk_level='关注型' then '1' else '0' end END) AS `人流量、车流量`,
            MAX(CASE WHEN quota_id = '站场画像-交通安全-路边区域-公交线路、车数' THEN risk_data END) AS `公交线路、车数_1`,
            MAX(CASE WHEN quota_id = '站场画像-交通安全-路边区域-公交线路、车数' THEN case when risk_level='安全型' then '2' when risk_level='关注型' then '1' else '0' end END) AS `公交线路、车数`,
            MAX(CASE WHEN quota_id = '站场画像-交通安全-路边区域-夜间灯光' THEN risk_data END) AS `夜间灯光_1`,
            MAX(CASE WHEN quota_id = '站场画像-交通安全-路边区域-夜间灯光' THEN case when risk_level='安全型' then '2' when risk_level='关注型' then '1' else '0' end END) AS `夜间灯光`,
            MAX(CASE WHEN quota_id = '站场画像-交通安全-路边区域-视觉盲区' THEN risk_data END) AS `视觉盲区_1`,
            MAX(CASE WHEN quota_id = '站场画像-交通安全-路边区域-视觉盲区' THEN case when risk_level='安全型' then '2' when risk_level='关注型' then '1' else '0' end END) AS `视觉盲区`,
            MAX(CASE WHEN quota_id = '站场画像-消防安全-路边区域-充电场车数' THEN risk_data END) AS `充电场车数_1`,
            MAX(CASE WHEN quota_id = '站场画像-消防安全-路边区域-充电场车数' THEN case when risk_level='安全型' then '2' when risk_level='关注型' then '1' else '0' end END) AS `充电场充电车数`,
            MAX(CASE WHEN quota_id = '站场画像-消防安全-路边区域-消防水源' THEN risk_data END) AS `消防水源_1`,
            MAX(CASE WHEN quota_id = '站场画像-消防安全-路边区域-消防水源' THEN case when risk_level='安全型' then '2' when risk_level='关注型' then '1' else '0' end END) AS `消防水源`,
            MAX(CASE WHEN quota_id = '站场画像-消防安全-路边区域-消防设备' THEN risk_data END) AS `消防设备_1`,
            MAX(CASE WHEN quota_id = '站场画像-消防安全-路边区域-消防设备' THEN case when risk_level='安全型' then '2' when risk_level='关注型' then '1' else '0' end END) AS `消防设备`,
            MAX(CASE WHEN quota_id = '站场画像-消防安全-路边区域-风险隐患' THEN risk_data END) AS `风险隐患_1`,
            MAX(CASE WHEN quota_id = '站场画像-消防安全-路边区域-风险隐患' THEN case when risk_level='安全型' then '2' when risk_level='关注型' then '1' else '0' end END) AS `风险隐患`
         from ai_security.ods_custom_bus_station_profile WHERE  quota_id like '%路边区域%' and run_date='{ym_str}'     
         GROUP BY bus_station_id,bus_station_name,organ_id,organ_name) 
         select id as station_code,station_name,terminal_name,bb.organ_id,bb.organ_name,station_type,
         run_area,'路边区域' as station_properties, route_num,service_bus_number,`充电场充电车数`, `消防水源`, `消防设备`, `风险隐患`, `人流量、车流量`, `公交线路、车数`, `夜间灯光`, `视觉盲区`, `三防应急设施、设备`, `临水临崖`, `场地设施、建筑、树木`, `场站地势`, `监控设备` 
        from ai_security.ods_jituan_bs_bus_park aa inner join cet bb on aa.id = bb.bus_station_id 
        where aa.station_properties='路边区域'
    """
    return sql.strip()

def station_roadside_dict()->dict:
    dict={
        '划定区域': {
            '人车分流':{'2':'好','1':'中','0':'差'},
            '人流量、车流量': {'2':'小','1':'一般','0':'大'},
            '站场警示标志': {'2':'齐全','1':'有缺漏','0':'无部署'},
            '安保': {'2':'>2人','1':'1～2人','0':'0人'},
            '出入口': {'2':'无转弯','1':'≥90°转弯','0':'<90°转弯'},
            '公交线路、车数': {'2':'少','1':'一般','0':'多'},
            '夜间灯光': {'2':'良好','1':'一般','0':'差'},
            '视觉盲区':  {'2':'0处','1':'1~3处','0':'>3处'},
            '场站地势': {'2':'较高','1':'较低','0':'低洼'},
            '临水临崖': {'2':'较远','1':'较近','0':'非常近'},
            '场地设施、建筑、树木': {'2':'风险小','1':'风险较小','0':'风险较大'},
            '三防应急设施、设备': {'2':'齐全','1':'有缺漏','0':'无设备'},
            '监控设备': {'2':'全覆盖','1':'部分覆盖','0':'无监控'},
            '充电场充电车数': {'2':'<50台','1':'50~100台','0':'>100台'},
            '风险隐患': {'2':'0处','1':'1~2处','0':'>2处'},
            '消防水源': {'2':'充足','1':'较充足','0':'无水源'},
            '消防设备': {'2':'充足','1':'较充足','0':'不足'},
        },
        '路边区域': {
            '人车分流': {'2': '好', '1': '中', '0': '差'},
            '人流量、车流量': {'2': '小', '1': '一般', '0': '大'},
            '站场警示标志': {'2': '齐全', '1': '有缺漏', '0': '无部署'},
            '安保': {'2': '>2人', '1': '1～2人', '0': '0人'},
            '出入口': {'2': '无转弯', '1': '≥90°转弯', '0': '<90°转弯'},
            '公交线路、车数': {'2': '少', '1': '一般', '0': '多'},
            '夜间灯光': {'2': '良好', '1': '一般', '0': '差'},
            '视觉盲区': {'2': '0处', '1': '1~5处', '0': '>5处'},
            '场站地势': {'2': '较高', '1': '较低', '0': '低洼'},
            '临水临崖': {'2': '较远', '1': '较近', '0': '非常近'},
            '场地设施、建筑、树木': {'2': '风险小', '1': '风险较小', '0': '风险较大'},
            '三防应急设施、设备': {'2': '齐全', '1': '有缺漏', '0': '无设备'},
            '监控设备': {'2': '全覆盖', '1': '部分覆盖', '0': '无监控'},
            '充电场充电车数': {'2': '<50台', '1': '50~100台', '0': '>100台'},
            '风险隐患': {'2': '0处', '1': '1~2处', '0': '>2处'},
            '消防水源': {'2':'充足','1':'较充足','0':'无水源'},
            '消防设备': {'2': '充足', '1': '较充足', '0': '不足'},
        }
    }
    return dict

# /* ============================================================
#    0. 统一参数表
#    ============================================================ */
def tmp_vrp_00_params_sql(start_date,end_date)->str:
    sql=f""" SELECT toDate('{start_date}') AS source_start_date, 
             toDate('{end_date}') AS source_end_date"""
    return sql

# /* ============================================================
#    01. 能耗主样本表
#    粒度：stat_date + bus_id + route_id
#    下载：data/tmp_vrp_01_energy_route_day.csv
#    ============================================================ */

def tmp_vrp_01_energy_route_day_sql()->str:
    sql=f"""
        SELECT
            toDate(parseDateTimeBestEffort(toString(ppartition))) AS stat_date,
            any(toString(ppartition)) AS raw_ppartition,
            any(toString(obuid)) AS obuid,
            toString(bus_id) AS bus_id,
            any(toString(bus_code)) AS bus_code,
            any(replaceRegexpAll(trimBoth(toString(number_plate)), '\\s+', '')) AS number_plate,
            any(toString(organ_id)) AS organ_id,
            any(toString(organ_name)) AS organ_name,
            toString(route_id) AS route_id,
            any(toString(route_name)) AS route_name,
            anyIf(
                trimBoth(toString(bus_type)),
                trimBoth(toString(bus_type)) != ''
            ) AS static_bus_type,
            sum(toFloat64OrZero(toString(run_mileage))) AS src_run_mileage,
            sum(toFloat64OrZero(toString(energy))) AS src_energy,
            avg(toFloat64OrNull(toString(mileage_energy))) AS src_mileage_energy,
            avg(toFloat64OrNull(toString(mileage_energy2))) AS src_mileage_energy2,
            sum(toFloat64OrZero(toString(total_second))) AS src_total_second
        FROM canbus.ads_bus_energy_day_stat
        WHERE toDate(parseDateTimeBestEffort(toString(ppartition)))
          BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
              AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)
          AND bus_id IS NOT NULL 
          AND toString(bus_id) != ''
          AND route_id IS NOT NULL
          AND toString(route_id) != ''
            GROUP BY stat_date, bus_id, route_id;
        """
    return sql

# /* ============================================================
#    02. 车辆静态表
#    粒度：bus_id
#    下载：data/tmp_vrp_02_static_bus.csv
#    ============================================================ */
def tmp_vrp_02_static_bus_sql()->str:
    sql=f"""
        SELECT
            toString(bus_id) AS bus_id,
            any(toString(bus_brand)) AS static_bus_brand,
            any(toFloat64OrNull(replaceAll(toString(total_weight), ',', ''))) AS static_total_weight,
            any(
                if(
                    toFloat64OrNull(replaceAll(toString(bus_length), ',', '')) > 100,
                    toFloat64OrNull(replaceAll(toString(bus_length), ',', '')) / 1000.0,
                    toFloat64OrNull(replaceAll(toString(bus_length), ',', ''))
                )
            ) AS static_bus_length,
            any(toFloat64OrNull(replaceAll(toString(battery_capacity), ',', ''))) AS static_battery_capacity,
            any(toFloat64OrNull(toString(bus_age))) AS static_bus_age
        FROM canbus.ods_jituan_bs_bus
        WHERE bus_id IS NOT NULL
          AND toString(bus_id) != ''
        GROUP BY
            bus_id;
        """
    return sql

# /* ============================================================
#    03. 故障表
#    粒度：stat_date + bus_id
#    下载：data/tmp_vrp_03_fault_day.csv
#    ============================================================ */
def tmp_vrp_03_fault_day_sql()->str:
    sql=f"""
        SELECT
            toDate(parseDateTimeBestEffort(toString(ppartition))) AS stat_date,
            toString(bus_id) AS bus_id,
            count() AS fault_total_count,
            count() AS fault_total_count_raw,
            countIf(toString(fault_type_name) LIKE '%%ABS%%') AS fault_abs_dashboard_count,
            countIf(toString(fault_type_name) LIKE '%%动力电池%%') AS fault_power_battery_count,
            countIf(toString(fault_type_name) LIKE '%%空调%%') AS fault_aircond_mode_count,
            countIf(toString(fault_type_name) LIKE '%%电压差%%') AS fault_cell_voltage_diff_count,
            countIf(toString(fault_type_name) LIKE '%%左电机%%') AS fault_left_motor_count,
            countIf(toString(fault_type_name) LIKE '%%右电机%%') AS fault_right_motor_count,
            countIf(toString(fault_type_name) LIKE '%%整车控制器%%') AS fault_battery_vcu_count,
            countIf(toString(fault_type_name) LIKE '%%轮胎温度%%') AS fault_tire_temp_count,
            countIf(toString(fault_type_name) LIKE '%%轮胎压力%%') AS fault_tire_pressure_count,
            countIf(toString(fault_type_name) LIKE '%%润滑%%') AS fault_lubrication_count,
            countIf(toString(fault_type_name) LIKE '%%打气泵%%') AS fault_controller_air_pump_count,
            countIf(toString(fault_type_name) LIKE '%%助力转向泵%%') AS fault_controller_steering_pump_count,
            countIf(toString(fault_type_name) LIKE '%%DCDC%%') AS fault_controller_dcdc_count,
            countIf(toString(fault_type_name) LIKE '%%绝缘%%') AS fault_insulation_count
        FROM canbus.ads_fault_analysis
        WHERE toDate(parseDateTimeBestEffort(toString(ppartition)))
              BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
                  AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)
          AND bus_id IS NOT NULL
          AND toString(bus_id) != ''
        GROUP BY
            stat_date,
            bus_id;
        """
    return sql
# /* ============================================================
#    04. CAN表
#    粒度：stat_date + number_plate
#    下载：data/tmp_vrp_04_can_day.csv
#    Python 后续用 stat_date + number_plate 映射 bus_id。
#    ============================================================ */
def tmp_vrp_04_can_day_sql()->str:
    sql=f"""
        SELECT
            toDate(parseDateTimeBestEffort(toString(ppartition))) AS stat_date,
            replaceRegexpAll(trimBoth(toString(number_plate)), '\\s+', '') AS number_plate,
            max(toFloat64OrNull(toString(D30_max))) AS can_D30_max,
            min(toFloat64OrNull(toString(D31_min))) AS can_D31_min,
            max(toFloat64OrNull(toString(D34_max))) AS can_D34_max,
            min(toFloat64OrNull(toString(D35_min))) AS can_D35_min,
            max(toFloat64OrNull(toString(D29_max))) AS can_D29_max,
            min(toFloat64OrNull(toString(D29_min))) AS can_D29_min,
            any(toFloat64OrNull(toString(standard_voltage))) AS can_standard_voltage,
            any(toFloat64OrNull(toString(standard_current))) AS can_standard_current
        FROM canbus.ads_can_day_bus_agg
        WHERE toDate(parseDateTimeBestEffort(toString(ppartition)))
              BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
                  AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)
          AND number_plate IS NOT NULL
          AND toString(number_plate) != ''
        GROUP BY
            stat_date,
            number_plate;
        """
    return sql

# /* ============================================================
#    05. 驾驶行为表
#    粒度：stat_date + obuid
#    下载：data/tmp_vrp_05_behavior_day.csv
#    Python 后续用 stat_date + obuid 映射 bus_id。
#    ============================================================ */
def tmp_vrp_05_behavior_day_sql()->str:
    sql=f"""
        SELECT
            toDate(parseDateTimeBestEffort(toString(ppartition))) AS stat_date,
            toString(obuid) AS obuid,
            uniqExact(toString(operator_code)) AS operator_code_count,
            uniqExact(toString(obuid)) AS behavior_obuid_count,
            count() AS raw_behavior_row_count,
            sum(toFloat64OrZero(toString(report_type1_count))) AS report_type1_count,
            sum(toFloat64OrZero(toString(report_type2_count))) AS report_type2_count,
            sum(toFloat64OrZero(toString(report_type3_count))) AS report_type3_count,
            sum(toFloat64OrZero(toString(report_type4_count))) AS report_type4_count,
            sum(toFloat64OrZero(toString(report_type5_count))) AS report_type5_count,
            sum(toFloat64OrZero(toString(report_type6_count))) AS report_type6_count,
            sum(toFloat64OrZero(toString(report_type7_count))) AS report_type7_count,
            sum(toFloat64OrZero(toString(report_type8_count))) AS report_type8_count,
            sum(toFloat64OrZero(toString(report_type9_count))) AS report_type9_count,
            sum(toFloat64OrZero(toString(report_type10_count))) AS report_type10_count,
            sum(toFloat64OrZero(toString(report_type11_count))) AS report_type11_count,
            sum(toFloat64OrZero(toString(report_type12_count))) AS report_type12_count,
            sum(toFloat64OrZero(toString(report_type13_count))) AS report_type13_count,
            sum(toFloat64OrZero(toString(report_type14_count))) AS report_type14_count,
            sum(toFloat64OrZero(toString(report_type15_count))) AS report_type15_count,
            sum(toFloat64OrZero(toString(report_type16_count))) AS report_type16_count,
            sum(toFloat64OrZero(toString(report_type17_count))) AS report_type17_count,
            sum(toFloat64OrZero(toString(report_type18_count))) AS report_type18_count,
            sum(toFloat64OrZero(toString(report_type19_count))) AS report_type19_count,
            sum(toFloat64OrZero(toString(report_type20_count))) AS report_type20_count,
            sum(toFloat64OrZero(toString(report_type21_count))) AS report_type21_count,
            sum(toFloat64OrZero(toString(report_type22_count))) AS report_type22_count,
            sum(toFloat64OrZero(toString(report_type23_count))) AS report_type23_count,
            sum(toFloat64OrZero(toString(report_type24_count))) AS report_type24_count,
            sum(toFloat64OrZero(toString(report_type25_count))) AS report_type25_count,
            sum(toFloat64OrZero(toString(report_type26_count))) AS report_type26_count,
            sum(toFloat64OrZero(toString(report_type27_count))) AS report_type27_count,
            sum(toFloat64OrZero(toString(report_type28_count))) AS report_type28_count,
            sum(toFloat64OrZero(toString(report_type29_count))) AS report_type29_count,
            sum(toFloat64OrZero(toString(report_type30_count))) AS report_type30_count,
            sum(toFloat64OrZero(toString(report_type33_count))) AS report_type33_count,
            sum(toFloat64OrZero(toString(report_type34_count))) AS report_type34_count,
            sum(toFloat64OrZero(toString(report_type36_count))) AS report_type36_count,
            sum(toFloat64OrZero(toString(report_type37_count))) AS report_type37_count
        FROM ai_security.abs_driver_behavior_sum
        WHERE toDate(parseDateTimeBestEffort(toString(ppartition)))
              BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
                  AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)
          AND obuid IS NOT NULL
          AND toString(obuid) != ''
        GROUP BY
            stat_date,
            obuid;
        """
    return sql

# /* ============================================================
#    06. 充电表
#    粒度：stat_date + bus_id
#    下载：data/tmp_vrp_06_charge_day.csv
#    ============================================================ */
def tmp_vrp_06_charge_day_sql()->str:
    sql=f"""
        SELECT
            toDate(parseDateTimeBestEffort(toString(ppartition))) AS stat_date,
            toString(bus_id) AS bus_id,
            sum(toFloat64OrZero(toString(day_charge_count))) AS day_charge_count,
            sum(toFloat64OrZero(toString(night_charge_count))) AS night_charge_count,
            sum(toFloat64OrZero(toString(day_charge_soc))) AS day_charge_soc,
            sum(toFloat64OrZero(toString(night_charge_soc))) AS night_charge_soc,
            sum(toFloat64OrZero(toString(use_soc))) AS use_soc,
            sum(toFloat64OrZero(toString(run_mileage))) AS charge_run_mileage
        FROM canbus.ads_day_energy_analysis
        WHERE toDate(parseDateTimeBestEffort(toString(ppartition)))
              BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
                  AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)
          AND bus_id IS NOT NULL
          AND toString(bus_id) != ''
        GROUP BY
            stat_date,
            bus_id;
    """
    return sql

# /* ============================================================
#    07. 空调表
#    粒度：stat_date + bus_id
#    下载：data/tmp_vrp_07_aircond_day.csv
#    ============================================================ */
def tmp_vrp_07_aircond_day_sql()->str:
    sql=f"""
        SELECT
        toDate(parseDateTimeBestEffort(toString(ppartition))) AS stat_date,
        toString(bus_id) AS bus_id,
        sum(toFloat64OrZero(toString(open_time))) AS aircond_open_time_minutes,
        count() AS aircond_record_count
    FROM canbus.ads_air_conditioner_use
    WHERE toDate(parseDateTimeBestEffort(toString(ppartition)))
          BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
              AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)
      AND bus_id IS NOT NULL
      AND toString(bus_id) != ''
    GROUP BY
        stat_date,
        bus_id;
    """
    return sql

# /* ============================================================
#    08. 车辆线路班次表
#    粒度：stat_date + bus_id + route_id
#    下载：data/tmp_vrp_08_route_trip_day.csv
#    ============================================================ */
def tmp_vrp_08_route_trip_day_sql()->str:
    sql=f"""
        SELECT
        toDate(parseDateTimeBestEffort(toString(ppartition))) AS stat_date,
        toString(bus_id) AS bus_id,
        toString(route_id) AS route_id,
        count() AS route_trip_count
    FROM canbus.ads_triplog_energy
    WHERE toDate(parseDateTimeBestEffort(toString(ppartition)))
          BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
              AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)
      AND bus_id IS NOT NULL
      AND toString(bus_id) != ''
      AND route_id IS NOT NULL
      AND toString(route_id) != ''
    GROUP BY
        stat_date,
        bus_id,
        route_id;
    """
    return sql

# /* ============================================================
#    09. 线路站点静态表
#    粒度：route_id
#    下载：data/tmp_vrp_09_route_station_static.csv
#    ============================================================ */
def tmp_vrp_09_route_station_static_sql()->str:
    sql=f"""
       SELECT
    toString(route_id) AS route_id,
    countDistinct(
        replaceRegexpAll(trimBoth(toString(route_station_name)), '\\s+', '')
    ) AS route_station_count
    FROM canbus.ods_jituan_bs_route_sta
    WHERE route_id IS NOT NULL
      AND toString(route_id) != ''
      AND route_station_name IS NOT NULL
      AND toString(route_station_name) != ''
    GROUP BY
        route_id;
    """
    return sql

# /* ============================================================
#    10. 线路黑点/转弯静态表
#    粒度：route_id
#    下载：data/tmp_vrp_10_route_black_static.csv
#    ============================================================ */
def tmp_vrp_10_route_black_static_sql()->str:
    sql=f"""
        SELECT
            route_id,
            avg(direction_black_count) AS route_black_count,
            sum(direction_turn_count) AS route_turn_count
        FROM
        (
            SELECT
                splitByChar('#', toString(route_ids))[1] AS route_id,
                toString(route_ids) AS route_ids_key,
                count() AS direction_black_count,
                countIf(toString(event_type) IN ('2', '3')) AS direction_turn_count
            FROM canbus.ads_event_black_spot
            WHERE route_ids IS NOT NULL
              AND toString(route_ids) != ''
            GROUP BY
                route_id,
                route_ids_key
        ) t
        GROUP BY
            route_id;
    """
    return sql

# /* ============================================================
#    11. 客流表
#    粒度：stat_date + number_plate
#    下载：data/tmp_vrp_11_passenger_day.csv
#    Python 后续用 stat_date + number_plate 映射 bus_id。
#    ============================================================ */
def tmp_vrp_11_passenger_day_sql()->str:
    sql=f"""
        SELECT
            toDate(parseDateTimeBestEffort(toString(operate_date))) AS stat_date,
            replaceRegexpAll(trimBoth(toString(car_license)), '\\s+', '') AS number_plate,
            sum(toFloat64OrZero(toString(passenger_total))) AS passenger_total
        FROM ai_security.ads_driver_passengerflux_daily
        WHERE operate_date IS NOT NULL
          AND car_license IS NOT NULL
          AND toString(car_license) != ''
          AND toDate(parseDateTimeBestEffort(toString(operate_date)))
              BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
                  AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)
        GROUP BY
            stat_date,
            number_plate;
        """
    return sql

# /* ============================================================
#    12. 维修表
#    粒度：stat_date + number_plate
#    下载：data/tmp_vrp_12_repair_day.csv
#    Python 后续用 stat_date + number_plate 映射 bus_id。
#    ============================================================ */
def tmp_vrp_12_repair_day_sql()->str:
    # sql=f"""
    #     SELECT
    #     toDate(f_indatetime) AS stat_date,
    #     replaceRegexpAll(trimBoth(toString(f_buslisence)), '\\s+', '') AS number_plate,
    #     uniqExact(toString(f_projectno)) AS repair_order_count
    # FROM ai_security.ods_jituan_mssql_10_91_172_11_gzbus_repair_v_busteam_project
    # WHERE f_indatetime IS NOT NULL
    #   AND f_buslisence IS NOT NULL
    #   AND toString(f_buslisence) != ''
    #   AND toDate(f_indatetime)
    #       BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
    #           AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)
    # GROUP BY
    #     stat_date,
    #     number_plate;
    #     """
    sql="""
            SELECT
            toDate(coalesce(in_time, order_time)) AS stat_date,
            replaceRegexpAll(trimBoth(toString(plate_number)), '\\s+', '') AS number_plate,
        
            uniqExact(
                if(
                    main_repair_order_no IS NOT NULL
                    AND trimBoth(toString(main_repair_order_no)) != '',
                    toString(main_repair_order_no),
                    toString(repair_order_no)
                )
            ) AS repair_order_count
        
        FROM ai_security.ods_jituan_mssql_192_168_181_169_dataupload_v_bus_repair
        
        WHERE coalesce(in_time, order_time) IS NOT NULL
          AND plate_number IS NOT NULL
          AND trimBoth(toString(plate_number)) != ''
          AND repair_order_no IS NOT NULL
          AND trimBoth(toString(repair_order_no)) != ''
        
          -- 排除作废 / 删除维修单，避免把无效单计入车辆维修风险
          AND ifNull(cancel_status, '') != '作废'
          AND ifNull(delete_flag, '') != '删除'
        
          AND toDate(coalesce(in_time, order_time))
              BETWEEN (SELECT source_start_date FROM ai_security.tmp_vrp_00_params)
                  AND (SELECT source_end_date FROM ai_security.tmp_vrp_00_params)
        
        GROUP BY
            stat_date,
            number_plate;

    """
    return sql


   #  /* ============================================================
   # 车辆画像风险模型：tmp_vrp_00_feature_source raw 宽表生成脚本（修复列别名版）
   # 修复点：
   # - ClickHouse 在 CTAS 中使用 base.stat_date 这类带表别名表达式时，
   #   可能把输出列名保存成 `base.stat_date`，导致后续检查语句 min(stat_date) 报 Unknown identifier。
   # - 本版对 SELECT 中所有输出字段都显式 AS 别名，保证 tmp_vrp_00_feature_source 中字段名为 stat_date、bus_id 等干净列名。
   #
   # 输入依赖：
   # ai_security.tmp_vrp_01_energy_route_day
   # ai_security.tmp_vrp_02_static_bus
   # ai_security.tmp_vrp_03_fault_day
   # ai_security.tmp_vrp_04_can_day
   # ai_security.tmp_vrp_05_behavior_day
   # ai_security.tmp_vrp_06_charge_day
   # ai_security.tmp_vrp_07_aircond_day
   # ai_security.tmp_vrp_08_route_trip_day
   # ai_security.tmp_vrp_09_route_station_static
   # ai_security.tmp_vrp_10_route_black_static
   # ai_security.tmp_vrp_11_passenger_day
   # ai_security.tmp_vrp_12_repair_day
   #
   # 输出：
   # ai_security.tmp_vrp_00_feature_source
   #
   # 说明：
   # 1. tmp_vrp_00_feature_source 只是 raw wide 下载表，不是模型特征表。
   # 2. 本脚本只做简单 LEFT JOIN 和 route 环境 raw 汇总。
   # 3. 不做中文字段、不做标签、不做 LOO、不做 rolling、不做缺失填充、不做归一化。
   # 4. Python 后续继续负责全部模型逻辑。
   # ============================================================ */
def tmp_vrp_00_feature_source_sql()->str:
    sql=f"""
        WITH
            route_env_day AS
            (
                SELECT
                    t.stat_date AS stat_date,
                    t.bus_id AS bus_id,
        
                    sum(ifNull(s.route_station_count, 0) * t.route_trip_count) AS denom_station_count,
                    sum(ifNull(b.route_turn_count, 0) * t.route_trip_count) AS denom_turn_count,
                    avg(ifNull(b.route_black_count, 0)) AS route_black_count,
                    sum(t.route_trip_count) AS route_trip_count,
                    uniqExact(t.route_id) AS route_cnt,
        
                    countIf(s.route_station_count IS NULL) AS station_missing_route_cnt,
                    countIf(b.route_black_count IS NULL) AS black_missing_route_cnt
        
                FROM ai_security.tmp_vrp_08_route_trip_day t
                LEFT JOIN ai_security.tmp_vrp_09_route_station_static s
                    ON t.route_id = s.route_id
                LEFT JOIN ai_security.tmp_vrp_10_route_black_static b
                    ON t.route_id = b.route_id
                GROUP BY
                    t.stat_date,
                    t.bus_id
            )
        
        SELECT
            base.stat_date AS stat_date,
            base.raw_ppartition AS raw_ppartition,
            base.obuid AS obuid,
            base.bus_id AS bus_id,
            base.bus_code AS bus_code,
            base.number_plate AS number_plate,
            base.organ_id AS organ_id,
            base.organ_name AS organ_name,
            base.route_id AS route_id,
            base.route_name AS route_name,
        
            base.src_run_mileage AS src_run_mileage,
            base.src_energy AS src_energy,
            base.src_mileage_energy AS src_mileage_energy,
            base.src_mileage_energy2 AS src_mileage_energy2,
            base.src_total_second AS src_total_second,
        
            static_bus.static_bus_brand AS static_bus_brand,
            static_bus.static_total_weight AS static_total_weight,
            static_bus.static_bus_length AS static_bus_length,
            static_bus.static_battery_capacity AS static_battery_capacity,
        --    static_bus.static_bus_type AS static_bus_type,
            base.static_bus_type AS static_bus_type,
            static_bus.static_bus_age AS static_bus_age,
        
            can.can_D30_max AS can_D30_max,
            can.can_D31_min AS can_D31_min,
            can.can_D34_max AS can_D34_max,
            can.can_D35_min AS can_D35_min,
            can.can_D29_max AS can_D29_max,
            can.can_D29_min AS can_D29_min,
            can.can_standard_voltage AS can_standard_voltage,
            can.can_standard_current AS can_standard_current,
        
            fault.fault_total_count AS fault_total_count,
            fault.fault_total_count_raw AS fault_total_count_raw,
            fault.fault_abs_dashboard_count AS fault_abs_dashboard_count,
            fault.fault_power_battery_count AS fault_power_battery_count,
            fault.fault_aircond_mode_count AS fault_aircond_mode_count,
            fault.fault_cell_voltage_diff_count AS fault_cell_voltage_diff_count,
            fault.fault_left_motor_count AS fault_left_motor_count,
            fault.fault_right_motor_count AS fault_right_motor_count,
            fault.fault_battery_vcu_count AS fault_battery_vcu_count,
            fault.fault_tire_temp_count AS fault_tire_temp_count,
            fault.fault_tire_pressure_count AS fault_tire_pressure_count,
            fault.fault_lubrication_count AS fault_lubrication_count,
            fault.fault_controller_air_pump_count AS fault_controller_air_pump_count,
            fault.fault_controller_steering_pump_count AS fault_controller_steering_pump_count,
            fault.fault_controller_dcdc_count AS fault_controller_dcdc_count,
            fault.fault_insulation_count AS fault_insulation_count,
        
            air.aircond_open_time_minutes AS aircond_open_time_minutes,
            air.aircond_record_count AS aircond_record_count,
        
            charge.day_charge_count AS day_charge_count,
            charge.night_charge_count AS night_charge_count,
            charge.day_charge_soc AS day_charge_soc,
            charge.night_charge_soc AS night_charge_soc,
            charge.use_soc AS use_soc,
            charge.charge_run_mileage AS charge_run_mileage,
        
            env.denom_station_count AS denom_station_count,
            env.denom_turn_count AS denom_turn_count,
            env.route_black_count AS route_black_count,
            env.route_trip_count AS route_trip_count,
            env.route_cnt AS route_cnt,
            env.station_missing_route_cnt AS station_missing_route_cnt,
            env.black_missing_route_cnt AS black_missing_route_cnt,
        
            passenger.passenger_total AS passenger_total,
        
            behavior.operator_code_count AS operator_code_count,
            behavior.behavior_obuid_count AS behavior_obuid_count,
            behavior.raw_behavior_row_count AS raw_behavior_row_count,
            behavior.report_type1_count AS report_type1_count,
            behavior.report_type2_count AS report_type2_count,
            behavior.report_type3_count AS report_type3_count,
            behavior.report_type4_count AS report_type4_count,
            behavior.report_type5_count AS report_type5_count,
            behavior.report_type6_count AS report_type6_count,
            behavior.report_type7_count AS report_type7_count,
            behavior.report_type8_count AS report_type8_count,
            behavior.report_type9_count AS report_type9_count,
            behavior.report_type10_count AS report_type10_count,
            behavior.report_type11_count AS report_type11_count,
            behavior.report_type12_count AS report_type12_count,
            behavior.report_type13_count AS report_type13_count,
            behavior.report_type14_count AS report_type14_count,
            behavior.report_type15_count AS report_type15_count,
            behavior.report_type16_count AS report_type16_count,
            behavior.report_type17_count AS report_type17_count,
            behavior.report_type18_count AS report_type18_count,
            behavior.report_type19_count AS report_type19_count,
            behavior.report_type20_count AS report_type20_count,
            behavior.report_type21_count AS report_type21_count,
            behavior.report_type22_count AS report_type22_count,
            behavior.report_type23_count AS report_type23_count,
            behavior.report_type24_count AS report_type24_count,
            behavior.report_type25_count AS report_type25_count,
            behavior.report_type26_count AS report_type26_count,
            behavior.report_type27_count AS report_type27_count,
            behavior.report_type28_count AS report_type28_count,
            behavior.report_type29_count AS report_type29_count,
            behavior.report_type30_count AS report_type30_count,
            behavior.report_type33_count AS report_type33_count,
            behavior.report_type34_count AS report_type34_count,
            behavior.report_type36_count AS report_type36_count,
            behavior.report_type37_count AS report_type37_count,
        
            repair.repair_order_count AS repair_order_count
        
        FROM ai_security.tmp_vrp_01_energy_route_day base
        LEFT JOIN ai_security.tmp_vrp_02_static_bus static_bus
            ON base.bus_id = static_bus.bus_id
        LEFT JOIN ai_security.tmp_vrp_03_fault_day fault
            ON base.stat_date = fault.stat_date
           AND base.bus_id = fault.bus_id
        LEFT JOIN ai_security.tmp_vrp_04_can_day can
            ON base.stat_date = can.stat_date
           AND base.number_plate = can.number_plate
        LEFT JOIN ai_security.tmp_vrp_05_behavior_day behavior
            ON base.stat_date = behavior.stat_date
           AND base.obuid = behavior.obuid
        LEFT JOIN ai_security.tmp_vrp_06_charge_day charge
            ON base.stat_date = charge.stat_date
           AND base.bus_id = charge.bus_id
        LEFT JOIN ai_security.tmp_vrp_07_aircond_day air
            ON base.stat_date = air.stat_date
           AND base.bus_id = air.bus_id
        LEFT JOIN route_env_day env
            ON base.stat_date = env.stat_date
           AND base.bus_id = env.bus_id
        LEFT JOIN ai_security.tmp_vrp_11_passenger_day passenger
            ON base.stat_date = passenger.stat_date
           AND base.number_plate = passenger.number_plate
        LEFT JOIN ai_security.tmp_vrp_12_repair_day repair
            ON base.stat_date = repair.stat_date
           AND base.number_plate = repair.number_plate
        SETTINGS join_use_nulls = 1;
        """
    return sql

def vr_weight_lable_dict()->dict:
    dict={'能耗风险_车辆设备_百公里充电SOC':'能耗风险-车辆设备-充电SOC',
            '能耗风险_车辆设备_百公里充电次数':'能耗风险-车辆设备-充电次数',
            '能耗风险_车辆设备_百公里空气压缩机开关次数':'能耗风险-车辆设备-空气压缩机开启次数',
            '能耗风险_车辆设备_百公里空气压缩机开启时长':'能耗风险-车辆设备-空气压缩机开启时长',
            '故障风险_车辆设备_近30日百公里充电SOC':'故障风险-车辆设备-充电SOC',
            '故障风险_车辆设备_近30日百公里充电次数':'故障风险-车辆设备-充电次数',
            '故障风险_车辆设备_近30日百公里空气压缩机开关次数':'故障风险-车辆设备-空气压缩机开启次数',
            '故障风险_车辆设备_近30日百公里空气压缩机开启时长':'故障风险-车辆设备-空气压缩机开启时长',
            '故障风险_车辆设备_近30日电池最大电流差均值':'故障风险-车辆设备-电池最大电流差',
            '故障风险_车辆设备_近30日电池最大电压差均值':'故障风险-车辆设备-电池最大电压差',
            '故障风险_车辆设备_近30日电池最大电压均值':'故障风险-车辆设备-电池最大电压',
            '故障风险_车辆设备_近30日电池最高电流均值':'故障风险-车辆设备-电池最高电流',
            '故障风险_车辆设备_近30日电池最高温度均值':'故障风险-车辆设备-电池最高温度',
            '故障风险_车辆设备_近30日电池最高温度最大值':'故障风险-车辆设备-电池最高温度最大值',
            '故障风险_车辆设备_近30日空调开启时长占比':'故障风险-车辆设备-空调开启时长占比',
            '故障风险_车辆维修_近30日动力电池相关故障次数':'故障风险-车辆维修-动力电池相关故障',
            '故障风险_车辆维修_近30日高危故障次数':'故障风险-车辆维修-高危相关故障',
            '故障风险_车辆维修_近30日控制器相关故障次数':'故障风险-车辆维修-控制器相关故障',
            '故障风险_车辆维修_近30日轮胎相关故障次数':'故障风险-车辆维修-轮胎相关故障',
            '故障风险_车辆维修_近30日三电系统故障次数':'故障风险-车辆维修-三电系统故障',
            '故障风险_车辆维修_近30日维修故障类型数':'故障风险-车辆维修-维修故障种类',
            '故障风险_车辆维修_近30日维修故障总次数':'故障风险-车辆维修-维修故障数量',
            '故障风险_车辆运营_近30日平均速度':'故障风险-车辆运营-平均速度',
            '故障风险_车辆运营_近30日拥堵指数':'故障风险-车辆运营-拥堵指数',
            '故障风险_车辆运营_近30日运营里程累计':'故障风险-车辆运营-运营里程',
            '故障风险_车辆运营_近30日运营时长累计':'故障风险-车辆运营-运营时长',
            '能耗风险_驾驶不良行为_超速类_千公里次数':'能耗风险-驾驶不良行为-超速类行为',
            '能耗风险_驾驶不良行为_档位手刹类_公里次数':'能耗风险-驾驶不良行为-档位手刹类行为',
            '能耗风险_驾驶不良行为_滑行类_千公里次数':'能耗风险-驾驶不良行为-滑行类行为',
            '能耗风险_驾驶不良行为_急加减速类_千公里次数':'能耗风险-驾驶不良行为-急加减速类行为',
            '能耗风险_驾驶不良行为_坡道路况不规范类_千公里次数':'能耗风险-驾驶不良行为-坡道路况不规范类行为',
            '能耗风险_驾驶不良行为_起步路口进站类_千公里次数':'能耗风险-驾驶不良行为-起步路口进站类行为',
            '能耗风险_驾驶不良行为_设备使用违规类_千公里次数':'能耗风险-驾驶不良行为-设备使用违规类行为',
            '能耗风险_驾驶不良行为_违规类型数':'能耗风险-驾驶不良行为-违规行为种类',
            '能耗风险_驾驶不良行为_站点作业类_百站违规率':'能耗风险-驾驶不良行为-站点作业类行为',
            '能耗风险_驾驶不良行为_转弯作业类_百转弯点违规率': '能耗风险-驾驶不良行为-转弯作业类行为',
            '故障风险_行驶路况_近30日线路黑点密度':'故障风险-行驶路况-线路黑点密度',
            '故障风险_行驶路况_近30日线路客流量密度':'故障风险-行驶路况-线路客流量密度',
            '故障风险_行驶路况_近30日线路站点密度':'故障风险-行驶路况-线路站点密度',
            '故障风险_行驶路况_近30日转弯密度':'故障风险-行驶路况-转弯密度',
            }
    return dict


f"""
能耗风险-车辆属性_车龄
能耗风险-车辆属性_车长
能耗风险-车辆属性_车辆品牌
能耗风险-车辆属性_车辆自重
能耗风险-车辆运营_运营时长
能耗风险-车辆运营_平均速度
能耗风险-车辆运营_拥堵指数
能耗风险-行驶路况_线路黑点密度
能耗风险-行驶路况_线路客流量密度
能耗风险-行驶路况_线路站点密度
能耗风险-行驶路况_转弯密度
能耗风险-车辆设备_空调开启时长占比
能耗风险-车辆设备_百公里空气压缩机开启时长
能耗风险-车辆设备_百公里空气压缩机开关次数
能耗风险-车辆设备_百公里充电次数
能耗风险-车辆设备_百公里充电SOC
能耗风险-驾驶不良行为_急加减速类_千公里次数
能耗风险-驾驶不良行为_超速类_千公里次数
能耗风险-驾驶不良行为_滑行类_千公里次数
能耗风险-驾驶不良行为_坡道路况不规范类_千公里次数
能耗风险-驾驶不良行为_设备使用违规类_千公里次数
能耗风险-驾驶不良行为_起步路口进站类_千公里次数
能耗风险-驾驶不良行为_站点作业类_百站违规率
能耗风险-驾驶不良行为_转弯作业类_百转弯点违规率
能耗风险-驾驶不良行为_档位手刹类_公里次数
能耗风险-驾驶不良行为_违规类型数
故障风险-车辆属性_车龄
故障风险-车辆属性_车长
故障风险-车辆属性_车辆品牌
故障风险-车辆属性_车辆自重
故障风险-车辆运营_近30日运营里程累计
故障风险-车辆运营_近30日运营时长累计
故障风险-车辆运营_近30日平均速度
故障风险-车辆运营_近30日拥堵指数
故障风险-行驶路况_近30日线路黑点密度
故障风险-行驶路况_近30日线路客流量密度
故障风险-行驶路况_近30日线路站点密度
故障风险-行驶路况_近30日转弯密度
故障风险-车辆设备_近30日空调开启时长占比
故障风险-车辆设备_近30日百公里空气压缩机开启时长
故障风险-车辆设备_近30日百公里空气压缩机开关次数
故障风险-车辆设备_近30日百公里充电次数
故障风险-车辆设备_近30日百公里充电SOC
故障风险-车辆设备_近30日电池最大电压差均值
故障风险-车辆设备_近30日电池最大电压均值
故障风险-车辆设备_近30日电池最高温度均值
故障风险-车辆设备_近30日电池最高温度最大值
故障风险-车辆设备_近30日电池最大电流差均值
故障风险-车辆设备_近30日电池最高电流均值
故障风险-车辆维修_近30日动力电池相关故障次数
故障风险-车辆维修_近30日维修故障类型数
故障风险-车辆维修_近30日维修故障总次数
故障风险-车辆维修_近30日三电系统故障次数
故障风险-车辆维修_近30日轮胎相关故障次数
故障风险-车辆维修_近30日控制器相关故障次数
故障风险-车辆维修_近30日高危故障次数

"""

def tmp_driver_wide_data_sql(start_date:str):
    sql=f"""
            /**************************** 1. 基础片段：取所有驾驶员（昨天数据）****************************/
        WITH all_drivers AS (
            SELECT DISTINCT 
                ojbe.employee_id AS drv_id ,
                ojbe.employee_name AS drv_name ,
                ojbe.organ_id as organ_id,
                f.organ_name as organ_name,
                gg.route_name 
                FROM canbus.ods_jituan_bs_employee ojbe  
                GLOBAL inner join canbus.ods_jituan_bs_organ f
                on ojbe.organ_id=f.organ_id 
                GLOBAL inner join canbus.ods_jituan_bs_route gg 
                on ojbe.route_id=gg.route_id
        ),
        
        -- 昨天的日期窗口
        yesterday_window AS (
            SELECT
                drv_name,
                drv_id,
                toDate('2026-07-20') AS start_date,
                toDate('2026-07-20') + INTERVAL 7 DAY - INTERVAL 1 SECOND AS end_date
            FROM all_drivers
        )
        ,
        
        /**************************** 2. 基础行为片段（原表） ****************************/
        yesterday_30m_bhv AS (
            SELECT
                e.employee_name AS driver_name,
                e.employee_id as driver_id,
                CASE 
                    WHEN b.report_type = 6 THEN '起步加速评价'
                    WHEN b.report_type = 8 THEN '加速评价'
                    WHEN b.report_type = 7 THEN '减速评价'
                    WHEN b.report_type = 9 THEN '急刹车'
                    WHEN b.report_type = 15 THEN '路口再加速评价'
                    WHEN b.report_type = 14 THEN '路口速度评价'
                    WHEN b.report_type = 18 THEN '违规使用手刹'
                    WHEN b.report_type = 1 THEN '停站N档评价'
                    WHEN b.report_type = 16 THEN 'N档评价'
                    WHEN b.report_type = 22 THEN '不规范转弯'
                    WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                    WHEN b.report_type = 12 THEN '门未关起步'
                    WHEN b.report_type = 5 THEN '空档滑行'
                    WHEN b.report_type = 4 THEN '熄火滑行'
                    WHEN b.report_type = 19 THEN '不文明鸣笛'
                    WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                    WHEN b.report_type = 21 THEN '拒载'
                    WHEN b.report_type = 20 THEN '飞站'
                    WHEN b.report_type = 10 THEN '急停'
                    WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                    WHEN b.report_type = 2 THEN '停车不挂N档'
                    WHEN b.report_type = 17 THEN '开关车门评价'
                    WHEN b.report_type = 23 THEN '动车前安全确认'
                    WHEN b.report_type = 24 THEN '违规使用空调'
                    WHEN b.report_type = 25 THEN '平路不规范'
                    WHEN b.report_type = 26 THEN '上坡不规范'
                    WHEN b.report_type = 27 THEN '下坡不规范'
                    WHEN b.report_type = 28 THEN '违规使用总电'
                    WHEN b.report_type = 29 THEN '路口大油门'
                    WHEN b.report_type = 30 THEN '进站违规制动'
                    WHEN b.report_type = 33 THEN '区间超速'
                    WHEN b.report_type = 34 THEN '全局超速'
                    WHEN b.report_type = 36 THEN '左转弯未刹车'
                    WHEN b.report_type = 37 THEN '右转弯未停车'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM yesterday_window r
            GLOBAL JOIN ai_security.ods_jituan_bs_employee e 
                ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
            GLOBAL LEFT JOIN ai_security.ods_communication_driver_behavior_month b
              ON e.qualification_no = b.operator_code
            WHERE b.report_time BETWEEN r.start_date AND r.end_date
            GROUP BY e.employee_id, 
                     e.employee_name,
                CASE 
                    WHEN b.report_type = 6 THEN '起步加速评价'
                    WHEN b.report_type = 8 THEN '加速评价'
                    WHEN b.report_type = 7 THEN '减速评价'
                    WHEN b.report_type = 9 THEN '急刹车'
                    WHEN b.report_type = 15 THEN '路口再加速评价'
                    WHEN b.report_type = 14 THEN '路口速度评价'
                    WHEN b.report_type = 18 THEN '违规使用手刹'
                    WHEN b.report_type = 1 THEN '停站N档评价'
                    WHEN b.report_type = 16 THEN 'N档评价'
                    WHEN b.report_type = 22 THEN '不规范转弯'
                    WHEN b.report_type = 11 THEN '车辆未停稳开车门'
                    WHEN b.report_type = 12 THEN '门未关起步'
                    WHEN b.report_type = 5 THEN '空档滑行'
                    WHEN b.report_type = 4 THEN '熄火滑行'
                    WHEN b.report_type = 19 THEN '不文明鸣笛'
                    WHEN b.report_type = 3 THEN '驾驶员未系安全带'
                    WHEN b.report_type = 21 THEN '拒载'
                    WHEN b.report_type = 20 THEN '飞站'
                    WHEN b.report_type = 10 THEN '急停'
                    WHEN b.report_type = 13 THEN '违规关闭"开门禁启开关"'
                    WHEN b.report_type = 2 THEN '停车不挂N档'
                    WHEN b.report_type = 17 THEN '开关车门评价'
                    WHEN b.report_type = 23 THEN '动车前安全确认'
                    WHEN b.report_type = 24 THEN '违规使用空调'
                    WHEN b.report_type = 25 THEN '平路不规范'
                    WHEN b.report_type = 26 THEN '上坡不规范'
                    WHEN b.report_type = 27 THEN '下坡不规范'
                    WHEN b.report_type = 28 THEN '违规使用总电'
                    WHEN b.report_type = 29 THEN '路口大油门'
                    WHEN b.report_type = 30 THEN '进站违规制动'
                    WHEN b.report_type = 33 THEN '区间超速'
                    WHEN b.report_type = 34 THEN '全局超速'
                    WHEN b.report_type = 36 THEN '左转弯未刹车'
                    WHEN b.report_type = 37 THEN '右转弯未停车'
                END
        ),
        
        /**************************** 2.1 ADAS行为片段 ****************************/
        yesterday_adas_bhv AS (
            SELECT
                r.drv_name AS driver_name,
                r.drv_id as driver_id,
                CASE 
                    WHEN e.resultname = '车距过近' THEN '车距过近'
                    WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                    WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                    WHEN e.resultname = '分神' THEN '分神'
                    WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                    WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                    WHEN e.resultname = '打电话' THEN '打电话'
                    WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                    ELSE e.resultname
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM yesterday_window r
            GLOBAL JOIN ai_security.ods_jituan_mssql_192_168_181_135_eddata_eddata e
              ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(e.drivercode, position(e.drivercode, '-') + 1)
            WHERE e.happentime BETWEEN r.start_date AND r.end_date
              AND e.resultname IN ('车距过近','车道保持能力下降','疲劳预警','分神','行人避让预警','前车碰撞预警','未系安全带','打电话','手长时间离开方向盘（吸烟）')
            GROUP BY r.drv_id, r.drv_name,
                CASE 
                    WHEN e.resultname = '车距过近' THEN '车距过近'
                    WHEN e.resultname = '车道保持能力下降' THEN '车道保持能力下降'
                    WHEN e.resultname = '疲劳预警' THEN '疲劳预警'
                    WHEN e.resultname = '分神' THEN '分神'
                    WHEN e.resultname = '行人避让预警' THEN '行人避让预警'
                    WHEN e.resultname = '前车碰撞预警' THEN '前车碰撞预警'
                    WHEN e.resultname = '打电话' THEN '打电话'
                    WHEN e.resultname = '手长时间离开方向盘（吸烟）' THEN '手长时间离开方向盘'
                    ELSE e.resultname
                END
        ),
        
        /**************************** 2.2 aebs行为片段 ****************************/
        yesterday_aebs_bhv AS (
            SELECT
                r.drv_name AS driver_name,
                r.drv_id as driver_id,
                CASE 
                    WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                    WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                    WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM yesterday_window r
            GLOBAL JOIN ai_security.ods_jituan_mysql_10_163_90_62_strong_tpss_alarm_warn_base_aebs e
              ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(e.driverCode, position(e.driverCode, '-') + 1)
            WHERE toDate(e.warnTime) BETWEEN r.start_date AND r.end_date
              AND e.typename IN ('严重疲劳驾驶识别','握方向盘不规范','驾驶姿势不端正')
            GROUP BY r.drv_id, r.drv_name,
                CASE 
                    WHEN e.typename = '严重疲劳驾驶识别' THEN '严重疲劳驾驶识别'
                    WHEN e.typename = '握方向盘不规范' THEN '握方向盘不规范'
                    WHEN e.typename = '驾驶姿势不端正' THEN '驾驶姿势不端正'
                END
        ),
        
        all_30m_bhv AS (
            SELECT * FROM yesterday_30m_bhv
            UNION ALL
            SELECT * FROM yesterday_adas_bhv
            UNION ALL
            SELECT * FROM yesterday_aebs_bhv
        ),
        
        /**************************** 2.2 交通违法片段 ****************************/
        yesterday_traffic_illegal AS (
            SELECT
                t.driver_name,
                t.employee_code as driver_id,
                CASE 
                    WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                    WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                    ELSE '违反交通标志标线'
                END AS drv_sct_bhv,
                COUNT(*) AS cnt
            FROM yesterday_window r
            GLOBAL JOIN ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_safetymanagement_manage_traffic_illegal_handle t
              ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(t.employee_code, position(t.employee_code, '-') + 1)
            WHERE t.illegal_date = toDate(r.start_date)
              AND t.illegal_classify_label = '违反交通指示灯号或禁令标志、标线'
            GROUP BY t.employee_code, 
                     t.driver_name,
                CASE 
                    WHEN t.illegalact LIKE '%%红灯%%' THEN '闯红灯'
                    WHEN t.illegalact LIKE '%%黄灯%%' THEN '闯黄灯'
                    ELSE '违反交通标志标线'
                END
        ),
        
        all_30m_bhv_with_traffic AS (
            SELECT * FROM all_30m_bhv
            UNION ALL
            SELECT * FROM yesterday_traffic_illegal
        ),
        
        /************************ 3. 健康指标（昨天）************************/
        
        health_daily AS (
            SELECT
                h.driver_code AS driver_id,
                toDate(h.happen_time) AS date_key,
                argMax(CASE WHEN vname = '心率' THEN toFloat64OrNull(vvalue) END, happen_time) AS heart_rate_avg,
                argMax(CASE WHEN vname = '酒精含量' THEN toFloat64OrNull(vvalue) END, happen_time) AS alcohol_avg,
                argMax(CASE WHEN vname = '收缩压' THEN toFloat64OrNull(vvalue) END, happen_time) AS sbp_avg,
                argMax(CASE WHEN vname = '舒张压' THEN toFloat64OrNull(vvalue) END, happen_time) AS dbp_avg,
                argMax(CASE WHEN vname = '脉搏' THEN toFloat64OrNull(vvalue) END, happen_time) AS pulse_avg,
                argMax(CASE WHEN vname = '血氧' THEN toFloat64OrNull(vvalue) END, happen_time) AS spo2_avg,
                argMax(CASE WHEN vname = '体温' THEN toFloat64OrNull(vvalue) END, happen_time) AS temp_avg
            FROM ai_security.ods_jituan_mysql_10_181_92_38_cloud_anfu_public_huyun_warn h
            GLOBAL INNER JOIN all_drivers r
                ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(h.driver_code, position(h.driver_code, '-') + 1)
           -- WHERE toDate(h.happen_time) = toDate('2026-07-28')  -- 取昨天
                where  toDate(h.happen_time) between toDate('2026-07-20') and toDate('2026-07-26')
                AND h.vname IN ('心率', '酒精含量', '收缩压', '舒张压', '脉搏', '血氧', '体温')
            GROUP BY h.driver_code, toDate(h.happen_time)
        ),
        
        
        /************************ 3.1 工时与里程指标（昨天）************************/
        workhour_daily AS (
            SELECT
                h.employee_id AS driver_id,
                h.employee_name AS driver_name,
                toDate(h.ppartition) ,
                SUM(toFloat64OrNull(h.safty_mileage)) AS safty_mileage,
                SUM(toFloat64OrNull(h.work_hour)) AS daily_work_hour
            FROM canbus.ads_driver_workhour h
            GLOBAL INNER JOIN all_drivers r
                ON substring(r.drv_id, position(r.drv_id, '-') + 1) = substring(h.employee_id, position(h.employee_id, '-') + 1)
            -- WHERE toDate(parseDateTimeBestEffort(h.ppartition)) = toDate('2026-07-28')
               WHERE toDate(parseDateTimeBestEffort(h.ppartition)) between  toDate('2026-07-20') and  toDate('2026-07-26')
            GROUP BY h.employee_id, h.employee_name, toDate(h.ppartition)
        ),
            
        
        pass_station_list AS(
            SELECT 
            drive_date,
            employee_id ,
            driver_name,
            toFloat64(sum(station_count)) AS total_station_count,
            count(*) AS trip_count
            FROM (
                SELECT 
                    toDate(t.ppartition) AS drive_date,
                    t.employee_id AS employee_id,         
                    t.employee_name AS driver_name, 
                    t.bus_id,
                    t.route_id,
                    t.from_station,
                    t.to_station,
                    abs(s2.min_sort - s1.min_sort) + 1 AS station_count
                FROM ai_security.ads_triplog_energy t
                GLOBAL LEFT JOIN (
                    -- 站点去重：同线路同站名取最小站序
                    SELECT line_code, motorcade_name, min(sort) as min_sort
                    FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
                    GROUP BY line_code, motorcade_name
                ) s1 ON t.route_id = s1.line_code AND t.from_station = s1.motorcade_name
                GLOBAL LEFT JOIN (
                    SELECT line_code, motorcade_name, min(sort) as min_sort
                    FROM ai_security.ods_jituan_mssql_10_181_92_95_basic_archives_line_site
                    GROUP BY line_code, motorcade_name
                ) s2 ON t.route_id = s2.line_code AND t.to_station = s2.motorcade_name
                WHERE s1.min_sort IS NOT NULL 
                  AND s2.min_sort IS NOT NULL
                  and toDate(t.ppartition) between toDate('2026-07-20') and toDate('2026-07-26') 
                  -- AND toDate(t.ppartition) = toDate('2026-07-28')
            ) as sub
            GROUP BY 
                drive_date,
                employee_id,
                driver_name
        ),
        
        pass_turn_list AS(
            SELECT 
                drive_date,
                employee_id ,
                driver_name,
                toFloat64(sum(turn_count)) AS total_turn_count
            FROM (
                
                SELECT
                    toDate(t.ppartition) AS drive_date,
                    t.employee_id AS employee_id,         
                    t.employee_name AS driver_name, 
                    t.route_id,       
                    COUNT(b.event_type) AS turn_count
                FROM ai_security.ads_triplog_energy t
                GLOBAL LEFT JOIN ai_security.ads_event_black_spot b
                ON toString(t.route_id) = splitByChar('#', b.route_ids)[1]
                    AND b.event_type IN (2, 3)
               -- WHERE toDate(t.ppartition) = toDate('2026-07-28')
                where  toDate(t.ppartition) between  toDate('2026-07-20')  and toDate('2026-07-26') 
                GROUP BY drive_date, employee_id, driver_name, t.route_id
            ) as sub
            GROUP BY 
                drive_date,
                employee_id,
                driver_name
        ),
        
        mental_list AS (
                SELECT 
                m.driver_name,
                case when m.dept_name GLOBAL in ('佛广集团','增从片区','马会巴士') then m.fleet else m.dept_name || '-' || m.fleet end AS organ_name,
                m.heart_level_label AS heart_level_label, 
                m.follow_year_month,n.drv_id,  
                m.line_name 
                FROM ai_security.ods_jituan_mysql_10_181_92_38_sc_cloud_dailyreport_driver_heart_body_healthy m 
                GLOBAL inner join all_drivers n on m.driver_name=n.drv_name  
                and n.organ_name=case when m.dept_name GLOBAL in ('佛广集团','增从片区','马会巴士') then m.fleet else m.dept_name || '-' || m.fleet end 
                WHERE m.follow_year_month = formatDateTime(toDate('2026-07-26'), '%%Y-%%m') 
                ),
        
        
        /**************************** 4. 宽表输出 ****************************/
        driver_list AS (
            SELECT drv_name AS driver_name,
            drv_id as driver_id,
            organ_id
        FROM all_drivers
        ),
        
        ---历史事故---
        driver_accident AS (
            SELECT 
                org_code,
                org_name,
                CASE 
                    WHEN POSITION('-' IN line_code) > 0 
                    THEN SUBSTRING(line_code, POSITION('-' IN line_code) + 1)
                    ELSE line_code END AS line_code,
                line_name,
                driver_name,
                yearly,
                accident_num 
            FROM  ai_security.ads_driver_accident_yearly
        ), 
         
         
        s_result AS (
            SELECT a.*,b.employee_name,b.organ_id,b.organ_name  
            FROM driver_accident a 
            GLOBAL LEFT OUTER JOIN (
                SELECT a.*,b.organ_name  
                FROM ai_security.ods_jituan_bs_employee a 
                GLOBAL INNER JOIN  ai_security.ods_jituan_bs_organ b 
                ON a.organ_id=b.organ_id ) b 
            ON a.driver_name=b.employee_name 
            WHERE b.organ_name LIKE CONCAT('%%',a.org_name,'%%') 
        ),
        
        
        -- 历史事故统计
        accident_yearly AS (
            SELECT 
                d.driver_name,
                d.driver_id,
                a.organ_id,
                a.line_code,
                COALESCE(SUM(a.accident_num), 0) AS total_accidents
            FROM driver_list d
            GLOBAL LEFT JOIN s_result a
                ON (d.driver_name = a.driver_name) AND(d.organ_id = a.organ_id)
                AND a.yearly IN (2023, 2024)
            GROUP BY d.driver_name,d.driver_id,a.organ_id,a.line_code
        ),
        
        avg_mileage AS (
            SELECT AVG(safty_mileage) AS avg_val
            FROM workhour_daily
            WHERE safty_mileage > 0   -- 排除0和NULL
        ),
        
        avg_pass_station AS (
            SELECT AVG(total_station_count) AS avg_val
            FROM pass_station_list
            WHERE total_station_count > 0   -- 排除0和NULL
        ),
        
        avg_pass_turn AS (
            SELECT AVG(total_turn_count) AS avg_val
            FROM pass_turn_list
            WHERE total_turn_count > 0   -- 排除0和NULL
        )
        
        SELECT
            d.driver_name,
            d.driver_id,
            d.organ_id, 
            o.organ_name, 
            
            -- 员工基础信息（4列）
            e.sex AS gender,
            e.age,
            e.education_level,
            dateDiff('year', e.entry_time, now()) AS driving_years,
            e.route_id,
            
            -- 工时与里程指标（3列）
            w.safty_mileage,
            --w.cumulative_safty_mileage,
            w.daily_work_hour,
            w.daily_work_hour as work_hour,
            y.total_accidents,
            
            -- 原37列基础行为
            SUM(CASE WHEN b.drv_sct_bhv = 'N档评价' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS ndang_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '上坡不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS upslope_bad_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '下坡不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS downslope_bad_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '不文明鸣笛' THEN b.cnt ELSE 0 END) AS rude_horn_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '不规范转弯' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), apt.avg_val) AS bad_turn_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '停站N档评价' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS stop_ndang_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '停车不挂N档' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS no_n_on_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '全局超速' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS global_over_spd_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '减速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS decel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS accel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '动车前安全确认' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS before_move_safe_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '区间超速' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS section_over_spd_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '右转弯未停车' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), apt.avg_val) AS right_turn_no_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '左转弯未刹车' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p2.total_turn_count, 0), apt.avg_val) AS left_turn_no_brake_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '平路不规范' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS flat_bad_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '开关车门评价' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS door_op_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '急停' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS sudden_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '急刹车' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS sudden_brake_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '拒载' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS refuse_ride_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '熄火滑行' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS stall_coast_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '空档滑行' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS neutral_coast_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '起步加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS start_accel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '路口再加速评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0),am.avg_val) AS junction_reaccel_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '路口大油门' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS junction_heavy_gas_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '路口速度评价' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS junction_spd_eval_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '车辆未停稳开车门' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS door_open_before_stop_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '进站违规制动' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS illegal_brake_on_entry_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规使用总电' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS illegal_main_power_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规使用手刹' THEN b.cnt ELSE 0 END)/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS illegal_hand_brake_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规使用空调' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS illegal_ac_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违规关闭"开门禁启开关"' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS illegal_door_switch_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '门未关起步' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS start_with_open_door_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '飞站' THEN b.cnt ELSE 0 END)*100/COALESCE(NULLIF(p.total_station_count, 0), aps.avg_val) AS skip_station_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '驾驶员未系安全带' THEN b.cnt ELSE 0 END) AS no_seat_belt_cnt,
            
            -- 9列ADAS行为
            SUM(CASE WHEN b.drv_sct_bhv = '车距过近' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS distance_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '车道保持能力下降' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS lane_keep_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '疲劳预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS fatigue_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '分神' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS distraction_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '行人避让预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS pedestrian_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '前车碰撞预警' THEN b.cnt ELSE 0 END)*1000/COALESCE(NULLIF(w.safty_mileage, 0), am.avg_val) AS collision_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '打电话' THEN b.cnt ELSE 0 END) AS phone_call_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '手长时间离开方向盘' THEN b.cnt ELSE 0 END) AS hands_off_wheel_cnt,
            
            -- 3列失能行为
            SUM(CASE WHEN b.drv_sct_bhv = '严重疲劳驾驶识别' THEN b.cnt ELSE 0 END) AS very_fatigue_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '握方向盘不规范' THEN b.cnt ELSE 0 END) AS hold_steeringwheel_warning_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '驾驶姿势不端正' THEN b.cnt ELSE 0 END) AS driving_posture_warning_cnt,
            
            -- 3列交通违法
            SUM(CASE WHEN b.drv_sct_bhv = '闯红灯' THEN b.cnt ELSE 0 END) AS red_light_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '闯黄灯' THEN b.cnt ELSE 0 END) AS yellow_light_cnt,
            SUM(CASE WHEN b.drv_sct_bhv = '违反交通标志标线' THEN b.cnt ELSE 0 END) AS traffic_sign_violation_cnt,
            
            -- 7列健康指标
            h.heart_rate_avg, h.alcohol_avg, h.sbp_avg, h.dbp_avg, h.pulse_avg, h.spo2_avg, h.temp_avg,
            
            -- 1列心理指标
            m2.heart_level_label
            
        FROM driver_list d
        GLOBAL LEFT JOIN ai_security.ods_jituan_bs_employee e 
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(e.employee_id, position(e.employee_id, '-') + 1)
        GLOBAL LEFT JOIN ai_security.ods_jituan_bs_organ o 
            ON d.organ_id = o.organ_id
        GLOBAL LEFT JOIN workhour_daily w 
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(w.driver_id, position(w.driver_id, '-') + 1)
        --GLOBAL CROSS JOIN mileage_mode m
        GLOBAL LEFT JOIN all_30m_bhv_with_traffic b 
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(b.driver_id, position(b.driver_id, '-') + 1)
        GLOBAL LEFT JOIN health_daily h 
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(h.driver_id, position(h.driver_id, '-') + 1)
        GLOBAL LEFT JOIN pass_station_list p 
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(p.employee_id, position(p.employee_id, '-') + 1)
        GLOBAL LEFT JOIN pass_turn_list p2
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(p2.employee_id, position(p2.employee_id, '-') + 1)
        GLOBAL LEFT JOIN mental_list m2
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(m2.drv_id, position(m2.drv_id, '-') + 1)
        GLOBAL LEFT JOIN (select driver_id,driver_name,sum(total_accidents) as total_accidents from accident_yearly group by driver_id,driver_name) y
            ON substring(d.driver_id, position(d.driver_id, '-') + 1) = substring(y.driver_id, position(y.driver_id, '-') + 1)
        GLOBAL CROSS JOIN avg_mileage am
        GLOBAL CROSS JOIN avg_pass_station aps
        GLOBAL CROSS JOIN avg_pass_turn apt
        
        GROUP BY 
            d.driver_name,
            d.driver_id,
            d.organ_id, 
            o.organ_name,
            e.sex, 
            e.age, 
            e.education_level, 
            e.route_id,
            driving_years,
            --w.cumulative_safty_mileage,
            w.safty_mileage,
            w.daily_work_hour,
            h.heart_rate_avg, h.alcohol_avg, h.sbp_avg, h.dbp_avg, h.pulse_avg, h.spo2_avg, h.temp_avg,
            m2.heart_level_label,
            --m.mode_value,
            p.total_station_count,
            p2.total_turn_count,
            y.total_accidents,
            am.avg_val,
            apt.avg_val,
            aps.avg_val
            
        ORDER BY d.driver_name;

    """
    return sql
          
          

