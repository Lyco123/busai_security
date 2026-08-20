from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict

@dataclass
class ObsQuotaWeightConfiguration:
    """指标权重配置实体类"""

    # 主键
    id: str

    # 画像类别 1-司机画像 2-车辆画像 2-线路画像 3-站场画像 4-单位画像
    profile_type: str

    # 一级指标
    quota_id1: Optional[str] = None
    quota_name1: Optional[str] = None
    calculate_weight_rate1: Optional[Decimal] = None
    weight_rate1: Optional[Decimal] = None
    quoa_desc1: Optional[str] = None
    quoa_unit1: Optional[str] = None

    # 二级指标
    quota_id2: Optional[str] = None
    quota_name2: Optional[str] = None
    calculate_weight_rate2: Optional[Decimal] = None
    weight_rate2: Optional[Decimal] = None
    quoa_desc2: Optional[str] = None
    quoa_unit2: Optional[str] = None

    # 三级指标
    quota_id3: Optional[str] = None
    quota_name3: Optional[str] = None
    calculate_weight_rate3: Optional[Decimal] = None
    weight_rate3: Optional[Decimal] = None
    quoa_desc3: Optional[str] = None
    quoa_unit3: Optional[str] = None

    # 四级指标
    quota_id4: Optional[str] = None
    quota_name4: Optional[str] = None
    calculate_weight_rate4: Optional[Decimal] = None
    weight_rate4: Optional[Decimal] = None
    quoa_desc4: Optional[str] = None
    quoa_unit4: Optional[str] = None

    # 有效日期
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # 创建信息
    creator: Optional[str] = None
    create_time: Optional[datetime] = None

    # 更新信息
    updater: Optional[str] = None
    update_time: Optional[datetime] = None

    # 是否删除
    deleted: str = "0"

    def to_dict(self) -> Dict[str, Any]:
        """
        将AbsDriverSuggestedSub对象转换为字典格式

        Returns:
            Dict[str, Any]: 包含所有字段的字典
        """
        return asdict(self)