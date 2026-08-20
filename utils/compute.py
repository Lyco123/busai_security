#!/usr/bin/python
# -*- coding: utf-8 -*-
# @version        : 1.0
# @Creaet Time    : 2022/5/12 17:09 
# @File           : compute.py
# @IDE            : PyCharm
# @desc           : 精准计算
from decimal import Decimal
from typing import Union


class Compute:

    @staticmethod
    def add(precision: int, *args: Union[float, Decimal]) -> float:
        """
        相加
        :param precision: 精度
        """
        result = 0
        for i in args:
            if i is None:
                i = 0
            result += Decimal(str(i))
        if precision == -1:
            return float(result)
        return round(float(result), precision)

    @staticmethod
    def subtract(precision: int, *args: Union[float, Decimal]) -> float:
        """
        相减
        :param precision: 精度
        """
        if args[0] is None:
            start = 0
        else:
            start = args[0]
        result = Decimal(str(start))
        for i in args[1:]:
            if i is None:
                i = 0
            result -= Decimal(str(i))
        if precision == -1:
            return float(result)
        return round(float(result), precision)

    @staticmethod
    def divide(precision: int, *args: Union[float, Decimal]) -> float:
        """
        除法
        :param precision: 精度
        """
        result = Decimal(str(args[0]))
        for i in args[1:]:
            result = result / Decimal(str(i))
        if precision == -1:
            return float(result)
        return round(float(result), precision)

    @staticmethod
    def multiply(precision: int, *args: Union[float, Decimal]) -> float:
        """
        乘法
        :param precision: 精度
        """
        result = Decimal(str(1))
        for i in args:
            if i is None:
                i = 1
            result = result * Decimal(str(i))
        if precision == -1:
            return float(result)
        return round(float(result), precision)

    @staticmethod
    def scientific_to_percentage(scientific_num):
        """
        将科学计数法数字转换为百分制显示
        """
        # 先转换为普通浮点数
        decimal_num = float(scientific_num)

        # 转换为百分制（乘以100）
        percentage = decimal_num * 100

        # 保留6位小数
        return round(percentage, 6)

    @staticmethod
    def percentage_to_number(number):
        """
        将科学计数法数字转换为百分制显示
        """
        # 先转换为普通浮点数
        decimal_num = float(number)

        # 转换为百分制（乘以100）
        number = decimal_num / 100

        # 保留6位小数
        return round(number, 6)

    @staticmethod
    def safe_float_conversion(value):
        """
        安全的浮点数转换函数，处理None值
        """
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def process_vehicle_string(input_string,type):
        # 统计下划线个数
        underline_count = input_string.count('_')

        # 如果下划线个数等于2
        if underline_count == 2:
            # 找到第一个和第二个下划线的位置
            first_underscore = input_string.find('_')
            second_underscore = input_string.find('_', first_underscore + 1)

            # 提取第二个下划线前的字符串
            if type==0:
                result = input_string[:second_underscore]
            else:
                result = input_string[second_underscore + 1:]
            return result
        else:
            first_underscore = input_string.find('_')
            if type == 0:
                result = input_string[:first_underscore]
            else:
                result = input_string[first_underscore + 1:]
            return result