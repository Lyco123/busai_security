# -*- coding: utf-8 -*-
"""通用小工具：日志、车辆ID清洗、日期格式。"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import pandas as pd


class AppLogger:
    """控制台 + 当前批次日志文件。"""

    def __init__(self):
        self.logger = logging.getLogger("Vehicle")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self.file_handler: TimedRotatingFileHandler | None = None
        self.formatter = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")

        if not self.logger.handlers:
            console = logging.StreamHandler(sys.stdout)
            console.setFormatter(self.formatter)
            self.logger.addHandler(console)

    def configure(self, log_dir: str | Path, job_name: str, create_date: str) -> None:
        """切换日志文件；每次 Weight/Score 运行单独一个日志。"""
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        if self.file_handler is not None:
            self.logger.removeHandler(self.file_handler)
            self.file_handler.close()

        log_file = log_dir / f"{job_name}_{create_date}.log"
        self.file_handler = TimedRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=30, encoding="utf-8")
        self.file_handler.setFormatter(self.formatter)
        self.logger.addHandler(self.file_handler)
        self.logger.info(f"日志文件: {log_file}")

    def info(self, message: str) -> None:
        self.logger.info(message)

    def warning(self, message: str) -> None:
        self.logger.warning(message)

    def error(self, message: str) -> None:
        self.logger.error(message)

    def exception(self, message: str) -> None:
        self.logger.exception(message)


logger = AppLogger()


def clean_id(value) -> str:
    """统一车辆ID/车牌等主键格式，去掉空值和尾部 .0。"""
    if pd.isna(value) or value == "":
        return ""
    text = str(value).strip()
    return text[:-2] if text.endswith(".0") else text


def get_date_token(date_str: str) -> str:
    """YYYY-MM-DD -> YYYYMMDD，用于批次目录名。"""
    return pd.to_datetime(date_str).strftime("%Y%m%d")


def get_month(date_str: str) -> str:
    """YYYY-MM-DD -> YYYY-MM，用于权重文件后缀。"""
    return pd.to_datetime(date_str).strftime("%Y-%m")


def get_latest_score_date(df: pd.DataFrame, date_col: str = "信息_统计日期") -> str:
    """获取评分数据中最新统计日期，作为结果表日期。"""
    if df.empty or date_col not in df.columns:
        raise ValueError("评分宽表为空或缺少统计日期列")
    latest = pd.to_datetime(df[date_col], errors="coerce").max()
    if pd.isna(latest):
        raise ValueError("评分宽表中无法解析最新统计日期")
    return latest.strftime("%Y-%m-%d")
