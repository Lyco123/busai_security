# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

import pandas as pd


def parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def get_output_month(create_date: str) -> str:
    return parse_date(create_date).strftime("%Y-%m")


def get_latest_score_date(df: pd.DataFrame, date_col: str = "信息_统计日期") -> str:
    if df.empty or date_col not in df.columns:
        raise ValueError("评分宽表为空或缺少统计日期列")
    latest = pd.to_datetime(df[date_col], errors="coerce").max()
    if pd.isna(latest):
        raise ValueError("评分宽表中无法解析最新统计日期")
    return latest.strftime("%Y-%m-%d")
