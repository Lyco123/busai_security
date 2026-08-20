from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from decimal import Decimal

from utils.tools import get_shanghai_time


@dataclass
class AbsRouteQuotaScoreSub:
    """线路画像指标分数子表实体类"""

    # 主键字段
    ppartition: str  # 分区字段(yyyymmdd)
    # 关联字段
    id: str  # 分数主键

    # 关联字段
    main_id: str  # 线路画像主表主键

    # 指标信息
    quota_id: str  # 指标ID
    quota_name: str  # 指标名称
    score: Decimal  # 换算后数值
    weight_rate: Decimal  # 计算权重
    original_value: Decimal  # 风险值
    risk_data: str  # 风险数据值
    quota_level: str  # 指标等级 1-一级指标 2-二级指标 3-三级指标
    parent_id: str  # 父级指标ID
    start_time: datetime  # 开始日期
    end_time: datetime  # 结束日期

    # 审计字段
    creator: str  # 创建人
    create_time: datetime  # 创建日期
    updater: str  # 更改人
    update_time: datetime  # 更改时间
    deleted: str  # 是否删除

    def to_dict(self) -> Dict[str, Any]:
        """
        将AbsRouteQuotaScoreSub对象转换为字典格式

        Returns:
            Dict[str, Any]: 包含所有字段的字典
        """
        return asdict(self)


@dataclass
class AbsRouteSuggestedSub:
    """线路画像建议子表实体类"""

    # 主键字段
    ppartition: str  # 分区字段(yyyymmdd)
    id: str  # 主键

    # 关联字段
    main_id: str  # 线路画像主表主键

    # 建议信息
    suggested_id: str  # 建议ID
    suggested_content: str  # 建议内容
    #指标信息
    quota_id: str  # 指标ID
    quota_name: str #指标名称
    score: Decimal  #换算后数值
    weight_rate: Decimal   #计算权重
    original_value: Decimal  #风险值

    risk_data: str #风险数据值
    quota_level: str  #指标等级 1-一级指标 2-二级指标 3-三级指标

    accept_status: str #是否接受 0-未接受 1-已接受 2-已处理
    accept_time: datetime #接受时间

    dispose_status: str #是否处理 0-待处理 1-已处理
    dispose_time: datetime  #处理时间

    optimize_score: Decimal  #优化值
    optimize_time: datetime  #优化时间
    optimize_status: str #干预状态 0-维持不变 1-变好 2-变差

    # 审计字段
    creator: str  # 创建人
    create_time: datetime  # 创建日期
    updater: str  # 更改人
    update_time: datetime  # 更改时间
    deleted: str  # 是否删除
    def to_dict(self) -> Dict[str, Any]:
        """
        将AbsRouteSuggestedSub对象转换为字典格式

        Returns:
            Dict[str, Any]: 包含所有字段的字典
        """
        return asdict(self)


@dataclass
class AbsRouteProfileMain:
    """线路画像主表实体类（包含子类）"""

    # 主键字段
    ppartition: str  # 分区字段(yyyymmdd)
    id: str  # 主键

    # 基础信息
    route_id: str  # 线路ID
    route_name: str  # 线路名称
    organ_id: str  # 机构ID
    organ_name: str  # 机构名称

    # 画像信息
    calculate_date: datetime  # 画像日期
    evalutaion_type: str  # 评价类型
    score: int  # 总分
    suggested_content: str  # 建议内容

    # 审计字段
    creator: str  # 创建人
    create_time: datetime  # 创建日期
    updater: str  # 更改人
    update_time: datetime  # 更改时间
    deleted: str  # 是否删除

    def to_dict(self) -> Dict[str, Any]:
        """
        将AbsRouteProfileMain对象转换为字典格式

        Returns:
            Dict[str, Any]: 包含所有字段的字典
        """
        return asdict(self)


def main():
    # 示例用法
    print("线路画像系统实体类定义完成")
    print("- AbsRouteProfileMain: 线路画像主表实体类（包含子类）")
    print("- AbsRouteQuotaScoreSub: 线路画像指标分数子表实体类")
    print("- AbsRouteSuggestedSub: 线路画像建议子表实体类")

    # 创建示例数据
    profile = AbsRouteProfileMain(
        ppartition="20260216",
        id="profile_001",
        Route_id="DRV001",
        Route_name="张三",
        organ_id="ORG001",
        organ_name="第一车队",
        calculate_date=get_shanghai_time(),
        evalutaion_type="月度评估",
        score=85,
        suggested_content="继续保持良好驾驶习惯",
        creator="system",
        create_time=get_shanghai_time(),
        updater="system",
        update_time=get_shanghai_time(),
        deleted="0"
    )

    print(f"\n创建示例线路画像: {profile.Route_name}")
    print(f"线路ID: {profile.Route_id}")
    print(f"所属机构: {profile.organ_name}")
    print(f"评估得分: {profile.score}")


if __name__ == "__main__":
    main()
