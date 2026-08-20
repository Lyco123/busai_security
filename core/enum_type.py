# @File           : enum_types.py
# @IDE            : PyCharm
# @desc           : 增加枚举类方法(修复循环导入问题)

from enum import Enum


class SuperEnum(Enum):
    """扩展枚举类，提供常用方法"""

    @classmethod
    def to_dict(cls):
        """返回枚举的字典表示形式"""
        return {e.name: e.value for e in cls}

    @classmethod
    def keys(cls):
        """返回所有枚举键的列表"""
        return list(cls._member_names_)

    @classmethod
    def values(cls):
        """返回所有枚举值的列表"""
        return [e.value for e in cls]

    @classmethod
    def get_member_by_value(cls, value):
        """根据值获取枚举成员"""
        for member in cls:
            if member.value == value:
                return member
        return None

    @classmethod
    def has_value(cls, value):
        """检查枚举是否包含指定值"""
        return value in cls._value2member_map_

    def __str__(self):
        """返回枚举值的字符串表示"""
        return str(self.value)


# 示例使用
if __name__ == "__main__":
    # 定义一个测试枚举
    class TestEnum(SuperEnum):
        RED = 1
        GREEN = 2
        BLUE = 3

    # 测试各种方法
    print("枚举字典:", TestEnum.to_dict())
    print("枚举键:", TestEnum.keys())
    print("枚举值:", TestEnum.values())
    print("根据值获取成员:", TestEnum.get_member_by_value(2))
    print("是否包含值:", TestEnum.has_value(3))
    print("字符串表示:", str(TestEnum.RED))
