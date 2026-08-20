# @File           : initialize.py
# @IDE            : PyCharm
# @desc           : 简要说明

from enum import Enum


class Environment(str, Enum):
    dev = "dev"
    pro = "pro"


