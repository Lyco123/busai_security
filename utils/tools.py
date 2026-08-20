# @File           : tools.py
# @IDE            : PyCharm
# @desc           : 工具类
import asyncio
import calendar
import json
import random
import re
import string
from datetime import datetime, timedelta
from typing import List, Union
import importlib

import numpy as np
import pytz
from dateutil.relativedelta import relativedelta

from core.logger import logger


def test_password(password: str) -> Union[str, bool]:
    """
    检测密码强度
    """
    if len(password) < 8 or len(password) > 16:
        return '长度需为8-16个字符,请重新输入。'
    else:
        for i in password:
            if 0x4e00 <= ord(i) <= 0x9fa5 or ord(i) == 0x20:  # Ox4e00等十六进制数分别为中文字符和空格的Unicode编码
                return '不能使用空格、中文，请重新输入。'
        else:
            key = 0
            key += 1 if bool(re.search(r'\d', password)) else 0
            key += 1 if bool(re.search(r'[A-Za-z]', password)) else 0
            key += 1 if bool(re.search(r"\W", password)) else 0
            if key >= 2:
                return True
            else:
                return '至少含数字/字母/字符2种组合，请重新输入。'


def list_dict_find(options: List[dict], key: str, value: any) -> Union[dict, None]:
    """
    字典列表查找
    """
    return next((item for item in options if item.get(key) == value), None)


def get_shanghai_time():
    """
    获取当前 Asia/Shanghai (CST, +0800) 时区的时间
    """
    # 定义上海时区
    shanghai_tz = pytz.timezone('Asia/Shanghai')

    # 获取当前上海时间
    now_shanghai =datetime.now(shanghai_tz)

    return now_shanghai

def get_time_interval(start_time: str, end_time: str, interval: int, time_format: str = "%H:%M:%S") -> List:
    """
    获取时间间隔
    :param end_time: 结束时间
    :param start_time: 开始时间
    :param interval: 间隔时间（分）
    :param time_format: 字符串格式化，默认：%H:%M:%S
    """
    if start_time.count(":") == 1:
        start_time = f"{start_time}:00"
    if end_time.count(":") == 1:
        end_time = f"{end_time}:00"
    start_time = datetime.datetime.strptime(start_time, "%H:%M:%S")
    end_time = datetime.datetime.strptime(end_time, "%H:%M:%S")
    time_range = []
    while end_time > start_time:
        time_range.append(start_time.strftime(time_format))
        start_time = start_time + datetime.timedelta(minutes=interval)
    return time_range


def generate_string(length: int = 8) -> str:
    """
    生成随机字符串
    :param length: 字符串长度
    """
    return ''.join(random.sample(string.ascii_letters + string.digits, length))


def import_modules(modules: list, desc: str, **kwargs):
    for module in modules:
        if not module:
            continue
        try:
            # 动态导入模块
            module_pag = importlib.import_module(module[0:module.rindex(".")])
            getattr(module_pag, module[module.rindex(".") + 1:])(**kwargs)
        except ModuleNotFoundError:
            logger.error(f"AttributeError：导入{desc}失败，未找到该模块：{module}")
        except AttributeError:
            logger.error(f"ModuleNotFoundError：导入{desc}失败，未找到该模块下的方法：{module}")


async def import_modules_async(modules: list, desc: str, **kwargs):
    for module in modules:
        if not module:
            continue
        try:
            # 动态导入模块
            # module_pag = importlib.import_module(module[0:module.rindex(".")])
            # await getattr(module_pag, module[module.rindex(".") + 1:])(**kwargs)
            # 分离模块路径和方法名
            module_path, method_name = module.rsplit(".", 1)
            # 动态导入模块
            module_pag = importlib.import_module(module_path)
            # 获取方法对象
            method = getattr(module_pag, method_name)
            # 检查是否为协程
            if asyncio.iscoroutinefunction(method):
                await method(**kwargs)
            else:
                method(**kwargs)

        except ModuleNotFoundError:
            logger.error(f"AttributeError：导入{desc}失败，未找到该模块：{module}")
        except AttributeError:
            logger.error(f"ModuleNotFoundError：导入{desc}失败，未找到该模块下的方法：{module}")


def get_last_month_day(start_date):
    """
    计算上月同期日期
    """
    # 先减去一个月
    if start_date.month == 1:
        # 如果是1月，则上月是去年12月
        last_month = start_date.replace(year=start_date.year - 1, month=12)
    else:
        # last_month = start_date.replace(month=start_date.month - 1)
        # 正确做法：自动处理月末边界
        last_month = start_date - relativedelta(months=1)

    # 尝试保持相同的日期，如果该月没有该日期，则使用月末日期
    try:
        last_month_same_day = last_month.replace(day=start_date.day)
    except ValueError:
        # 如果日期不存在（如2月29日），则使用该月最后一天
        import calendar
        last_day = calendar.monthrange(last_month.year, last_month.month)[1]
        last_month_same_day = last_month.replace(day=last_day)

    return last_month_same_day

def get_next_month_day(start_date):
    """
    计算上月同期日期
    """
    # 先减去一个月
    if start_date.month == 12:
        # 如果是12月，则下月是今天12月
        next_month = start_date.replace(year=start_date.year + 1, month=1)
    else:
        next_month = start_date.replace(month=start_date.month + 1)

    # 尝试保持相同的日期，如果该月没有该日期，则使用月末日期
    try:
        next_month_same_day = next_month.replace(day=start_date.day)
    except ValueError:
        # 如果日期不存在（如2月29日），则使用该月最后一天
        import calendar
        next_day = calendar.monthrange(next_month.year, next_month.month)[1]
        next_month_same_day = next_month.replace(day=next_day)

    return next_month_same_day

def get_last_half_year_day(start_date):
    """
    计算半年前同期日期
    """
    # 先减去六个月
    # 使用 relativedelta 可以自动处理年份跨越（如1月减6个月变为去年7月）
    last_half_year = start_date - relativedelta(months=6)

    # 尝试保持相同的日期，如果该月没有该日期，则使用月末日期
    try:
        # 例如：start_date 是 8月31日，last_half_year 是 2月。
        # replace(day=31) 在2月会抛出 ValueError
        last_half_year_same_day = last_half_year.replace(day=start_date.day)
    except ValueError:
        # 如果日期不存在（如2月29日、30日、31日等），则使用该月最后一天
        last_day = calendar.monthrange(last_half_year.year, last_half_year.month)[1]
        last_half_year_same_day = last_half_year.replace(day=last_day)

    return last_half_year_same_day

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)
if __name__ == '__main__':
    start_date_ = datetime.strptime('2025-12-01', '%Y-%m-%d')
    start_date = get_next_month_day(start_date_)
    end_date = get_next_month_day(start_date)
    end_date_ = end_date - timedelta(days=1)
    print(start_date_, end_date_)