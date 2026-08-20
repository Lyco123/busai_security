import psycopg2
from typing import List, Dict, Tuple, Optional
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class POIBatchInserter:
    def __init__(self, connection_params: Dict[str, str], schema: str = 'bus_ai'):
        """
        初始化POI批量插入器
        :param connection_params: 数据库连接参数
        :param schema: 数据库模式
        """
        self.connection_params = connection_params
        self.schema = schema
        self.connection = None

    def connect(self) -> bool:
        """建立数据库连接"""
        try:
            self.connection = psycopg2.connect(**self.connection_params)
            with self.connection.cursor() as cursor:
                cursor.execute(f"SET search_path TO {self.schema}")
            logger.info("数据库连接成功")
            return True
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            return False

    def disconnect(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            logger.info("数据库连接已关闭")

    def validate_poi_data(self, poi_data: Dict) -> Optional[Tuple]:
        """
        验证单条POI数据并转换为元组
        :param poi_data: POI数据字典
        :return: 验证后的数据元组或None（如果验证失败）
        """
        try:
            # 检查必需字段是否存在
            required_fields = [
                'org_name','use_org_name','line_code','line_name','direction','address', 'adname', 'cityname', 'id',
                'keytag', 'location', 'name', 'pname', 'tel', 'type', 'typecode','lng_min','lat_min','keyword'
            ]

            for field in required_fields:
                if field not in poi_data or poi_data[field] is None:
                    logger.warning(f"数据缺失字段: {field}")
                    return None

            # 特别处理location字段
            location = poi_data['location']
            if isinstance(location, str):
                # 如果是字符串，尝试解析为坐标
                coords = location.split(',')
                if len(coords) != 2:
                    logger.warning(f"Location格式错误: {location}")
                    return None
                try:
                    float(coords[0])
                    float(coords[1])
                except ValueError:
                    logger.warning(f"Location坐标不是数字: {location}")
                    return None
            elif isinstance(location, (list, tuple)):
                if len(location) != 2:
                    logger.warning(f"Location元组长度错误: {location}")
                    return None
                try:
                    float(location[0])
                    float(location[1])
                except ValueError:
                    logger.warning(f"Location坐标不是数字: {location}")
                    return None
            else:
                logger.warning(f"Location类型错误: {type(location)}")
                return None

            # 构建数据元组
            data_tuple = (
                str(poi_data['org_name']),
                str(poi_data['use_org_name']),
                str(poi_data['line_code']),
                str(poi_data['line_name']),
                str(poi_data['direction']),
                str(poi_data['address']),
                str(poi_data['adname']),
                str(poi_data['cityname']),
                str(poi_data['id']),
                str(poi_data['keytag']),
                str(poi_data['location']),  # 保持原始格式存储
                str(poi_data['name']),
                str(poi_data['pname']),
                str(poi_data['tel']),
                str(poi_data['type']),
                str(poi_data['typecode']),
                str(poi_data['lng_min']),
                str(poi_data['lat_min']),
                str(poi_data['keyword'])
            )

            return data_tuple

        except Exception as e:
            logger.error(f"数据验证过程中出错: {e}")
            return None

    def save_poi_data(self, poi_datas: List[Dict]) -> int:
        """
        批量保存POI数据到数据库
        :param poi_datas: POI数据列表
        :return: 成功插入的记录数
        """
        if not self.connect():
            return 0

        try:
            logger.info(f"开始插入 {len(poi_datas)} 条POI数据")


            # 构建批量插入SQL
            insert_query = """
                           INSERT INTO poi_data_gym (org_name,use_org_name,line_code,line_name,direction,address, adname, cityname, id, keytag, \
                                                 location, name, pname, tel, type, typecode,lng_min,lat_min,keyword) \
                           VALUES (  %s, %s, %s, %s, %s,%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s, %s,%s) \
                           """

            # 验证并准备数据
            valid_data = []
            for i, poi_data in enumerate(poi_datas):
                validated_data = self.validate_poi_data(poi_data)
                if validated_data:
                    valid_data.append(validated_data)
                else:
                    logger.warning(f"第 {i + 1} 条数据验证失败，已跳过")

            if not valid_data:
                logger.warning("没有有效的数据可以插入")
                return 0

            # 执行批量插入
            with self.connection.cursor() as cursor:
                cursor.executemany(insert_query, valid_data)
                self.connection.commit()
                inserted_count = cursor.rowcount
                logger.info(f"成功插入 {inserted_count} 条数据")
                return inserted_count

        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"数据库操作错误: {e}")
            return 0
        except Exception as e:
            self.connection.rollback()
            logger.error(f"批量插入过程中出现未知错误: {e}")
            return 0
        finally:
            self.disconnect()

    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """
        执行SQL查询并返回结果
        :param query: SQL查询语句
        :param params: 查询参数
        :return: 查询结果列表
        """
        if not self.connect():
            return 0

        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)

            # 获取列名
            columns = [desc[0] for desc in cursor.description]

            # 获取数据
            rows = cursor.fetchall()

            # 转换为字典列表
            result = []
            for row in rows:
                result.append(dict(zip(columns, row)))

            cursor.close()
            print(f"查询成功，返回 {len(result)} 条记录")
            return result

        except Exception as e:
            print(f"查询执行失败: {e}")
            return []


def main():
    """主函数 - 演示POI数据批量插入"""
    # 数据库连接配置
    db_config = {
        'host': '127.0.0.1',
        'port': 5432,
        'database': 'zhongda_map',
        'user': 'postgres',
        'password': 'jinqi2016'
    }

    # 示例POI数据
    sample_poi_data = [
        {
            'address': '龙溪大道芳村花园中环街22号',
            'adname': '荔湾区',
            'cityname': '广州市',
            'id': 'B0FFHOL4BX',
            'keytag': '幼儿园',
            'location': '113.222852,23.077312',
            'name': '芳村花园幼儿园',
            'pname': '广东省',
            'tel': '020-81682523',
            'type': '科教文化服务;学校;幼儿园',
            'typecode': '141204'
        },
        {
            'address': '中山路123号',
            'adname': '越秀区',
            'cityname': '广州市',
            'id': 'B0FFHOL4BY',
            'keytag': '小学',
            'location': [113.291852, 23.127312],
            'name': '中山路小学',
            'pname': '广东省',
            'tel': '020-81682524',
            'type': '科教文化服务;学校;小学',
            'typecode': '141205'
        }
        # 可以添加更多数据...
    ]

    # 创建插入器并执行插入
    inserter = POIBatchInserter(db_config, schema='bus_ai')
    aaa=inserter.execute_query("select * from poi_data where id='B0FFIY1JQP'")
    inserted_count = inserter.save_poi_data(sample_poi_data)
    print(f"总共成功插入 {inserted_count} 条记录")


if __name__ == "__main__":
    main()
