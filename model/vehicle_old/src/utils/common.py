# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
SQL_DIR = DATA_DIR / "sql_data"
CONFIG_DIR = PROJECT_ROOT / "config"
DOCS_DIR = PROJECT_ROOT / "docs"
OUT_DIR = PROJECT_ROOT / "output"
WEIGHTS_ROOT = OUT_DIR / "weights"
MODELS_ROOT = OUT_DIR / "models"
SCORES_ROOT = OUT_DIR / "scores"
LOGS_ROOT = OUT_DIR / "logs"

for directory in [OUT_DIR, WEIGHTS_ROOT, MODELS_ROOT, SCORES_ROOT, LOGS_ROOT, DOCS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")


@dataclass(frozen=True)
class BatchPaths:
    job_name: str
    batch_name: str
    weights_dir: Path
    models_dir: Path
    scores_dir: Path
    logs_dir: Path


def resolve_config_file(filename: str) -> Path:
    primary = CONFIG_DIR / filename
    if primary.exists():
        return primary

    from model.vehicle.src.utils.logger import logger

    logger.error(f"未找到配置文件: {primary}")
    raise FileNotFoundError(f"未找到配置文件: {primary}")


def clean_id(value) -> str:
    if pd.isna(value) or value == "":
        return "unknown"
    text = str(value).strip()
    return text[:-2] if text.endswith(".0") else text


def smart_date(series):
    dt = pd.to_datetime(series, format="%Y%m%d", errors="coerce")
    if dt.isna().mean() > 0.5:
        dt = pd.to_datetime(series, errors="coerce")
    if hasattr(dt, "dt"):
        try:
            dt = dt.dt.tz_localize(None)
        except (TypeError, AttributeError):
            pass
        dt = dt.dt.normalize()
    return dt


def normalize_weight_month(weight_month: str | None, create_date: str | None) -> str:
    if weight_month:
        normalized = str(weight_month).strip()
        if not MONTH_PATTERN.match(normalized):
            raise ValueError(f"weight_month 格式非法: {weight_month}，应为 YYYY-MM")
        return normalized
    if not create_date:
        raise ValueError("create_date 为空，无法推导 weight_month")
    return pd.to_datetime(create_date).strftime("%Y-%m")


def get_date_token(date_str: str) -> str:
    return pd.to_datetime(date_str).strftime("%Y%m%d")


def build_batch_name(job_name: str, start_date: str, end_date: str, create_date: str) -> str:
    return f"{job_name}_{get_date_token(start_date)}_{get_date_token(end_date)}_{get_date_token(create_date)}"


async def build_batch_paths(job_name: str, start_date: str, end_date: str, create_date: str) -> BatchPaths:
    batch_name = build_batch_name(job_name, start_date, end_date, create_date)
    weights_dir = WEIGHTS_ROOT / batch_name
    models_dir = MODELS_ROOT / batch_name
    scores_dir = SCORES_ROOT / batch_name
    logs_dir = LOGS_ROOT / batch_name

    required_dirs = [logs_dir]
    if job_name == "weight":
        required_dirs.extend([weights_dir, models_dir])
    elif job_name == "score":
        required_dirs.append(scores_dir)
    else:
        required_dirs.extend([weights_dir, models_dir, scores_dir])

    for directory in required_dirs:
        directory.mkdir(parents=True, exist_ok=True)

    return BatchPaths(
        job_name=job_name,
        batch_name=batch_name,
        weights_dir=weights_dir,
        models_dir=models_dir,
        scores_dir=scores_dir,
        logs_dir=logs_dir,
    )


def find_latest_artifact(root_dir: Path, pattern: str) -> Path | None:
    if not root_dir.exists():
        return None
    files = sorted(
        (path for path in root_dir.rglob(pattern) if path.is_file()),
        key=lambda path: path.stat().st_mtime,
    )
    return files[-1] if files else None


def read_raw_file(pattern: str, source: str = "raw", nrows: int | None = None):
    from model.vehicle.src.utils.logger import logger

    source_map = {
        "raw": RAW_DIR,
        "sql": SQL_DIR,
    }
    target_dir = source_map.get(source)
    if target_dir is None:
        raise ValueError(f"不支持的数据源类型: {source}")
    if not target_dir.exists():
        logger.error(f"数据目录不存在: {target_dir}")
        raise FileNotFoundError(f"数据目录不存在: {target_dir}")

    files = sorted(target_dir.glob(pattern), key=lambda path: path.stat().st_mtime)
    if not files:
        logger.warning(f"未找到匹配文件: {pattern} @ {target_dir}")
        return None

    target_file = files[-1]
    logger.info(f"读取{source}文件: {target_file.name}")
    try:
        return pd.read_csv(target_file, encoding="utf-8-sig", nrows=nrows, low_memory=False)
    except UnicodeDecodeError:
        return pd.read_csv(target_file, encoding="gbk", errors="ignore", nrows=nrows, low_memory=False)


# def parse_date_range_args(description: str, default_args=None, include_weight_month: bool = False):
#     parser = argparse.ArgumentParser(description=description)
#     parser.add_argument(
#         "--start-date",
#         type=str,
#         default=getattr(default_args, "start_date", None),
#         required=default_args is None,
#         help="数据开始日期，YYYY-MM-DD",
#     )
#     parser.add_argument(
#         "--end-date",
#         type=str,
#         default=getattr(default_args, "end_date", None),
#         required=default_args is None,
#         help="数据结束日期，YYYY-MM-DD",
#     )
#     parser.add_argument(
#         "--create-date",
#         type=str,
#         default=getattr(default_args, "create_date", None),
#         required=default_args is None,
#         help="创建日期，YYYY-MM-DD",
#     )
#     if include_weight_month:
#         parser.add_argument(
#             "--weight-month",
#             type=str,
#             default=getattr(default_args, "weight_month", None),
#             required=False,
#             help="权重月份，YYYY-MM；不传则默认取 create_date 所在月份",
#         )
#     return parser.parse_args()


def get_default_attr(obj, attr_name, default=None):
    """安全获取对象属性"""
    return getattr(obj, attr_name, default) if obj else default

def parse_date_range_args(description: str, default_args=None, include_weight_month: bool = False):
    parser = argparse.ArgumentParser(description=description)
    # 创建子解析器
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    # 添加 'run' 子命令
    run_parser = subparsers.add_parser("run", help="Run the data processing task")
    # 为 'run' 子命令添加参数
    run_parser.add_argument(
        "--start-date",
        type=str,
        default=get_default_attr(default_args, "start_date"),
        required=False,  # 在子命令中，通常设为非必填，或在逻辑中检查
        help="数据开始日期，YYYY-MM-DD",
    )
    run_parser.add_argument(
        "--end-date",
        type=str,
        default=get_default_attr(default_args, "end_date"),
        required=False,
        help="数据结束日期，YYYY-MM-DD",
    )
    run_parser.add_argument(
        "--create-date",
        type=str,
        default=get_default_attr(default_args, "create_date"),
        required=False,
        help="创建日期，YYYY-MM-DD",
    )
    if include_weight_month:
        run_parser.add_argument(
            "--weight-month",
            type=str,
            default=get_default_attr(default_args, "weight_month"),
            required=False,
            help="权重月份，YYYY-MM；不传则默认取 create_date 所在月份",
        )
    args = parser.parse_args()
    return args
