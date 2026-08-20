from pydantic import BaseModel

from core.data_types import DatetimeStr

#实例类
class can(BaseModel):
    obuid : str
    can:str
    start_time: DatetimeStr | None = None
    end_time: DatetimeStr | None = None
