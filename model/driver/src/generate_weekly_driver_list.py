from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from model.driver.crud import read_raw_sql, save_warning_driver_week
from model.driver.src import driver_sql

# Input file entry.
# Fill this section, then run:
#   python generate_weekly_driver_list.py
#
# Option A: one CSV contains both the current score week and previous score week.
CONFIG_SCORE_FILE: Path | None = None

# Option B: current and previous score weeks are split into two CSV files.
CONFIG_CURRENT_FILE: Path | None = None
CONFIG_PREVIOUS_FILE: Path | None = None

# Current score date. Examples: "20260726" or "2026-07-26".
# Leave as None to use the latest ppartition date in the input file.
CONFIG_SCORE_DATE: str | None = None

# Leave as None to write to outputs/weekly_driver_risk_production/.
CONFIG_OUTPUT: Path | None = None

# Rule parameters. Usually keep these unchanged.
CONFIG_LIMIT = 350
CONFIG_MAX2_TOP = 200
CONFIG_ORG_TOP = 150

DEFAULT_OUTPUT_DIR = Path("outputs") / "weekly_driver_risk_production"
DEFAULT_LIMIT = 350
DEFAULT_MAX2_TOP = 200
DEFAULT_ORG_TOP = 150

REQUIRED_COLUMNS = {"driver_id", "score", "organ_id", "ppartition"}
OPTIONAL_COLUMNS = ["driver_name", "organ_name", "route_id"]


def normalize_id(series: pd.Series) -> pd.Series:
    values = (
        series.astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .str.upper()
    )
    return values.map(lambda value: (value.lstrip("0") or "0") if value.isdigit() else value)


def parse_score_dates(series: pd.Series) -> pd.Series:
    text = (
        series.astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
    )
    parsed = pd.to_datetime(text, format="%Y%m%d", errors="coerce")
    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(text.loc[missing], errors="coerce")
    return parsed.dt.normalize()


def parse_user_date(value: str) -> pd.Timestamp:
    text = str(value).strip()
    parsed = pd.to_datetime(text, format="%Y%m%d", errors="coerce")
    if pd.isna(parsed):
        parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Cannot parse --score-date: {value}")
    return pd.Timestamp(parsed).normalize()


def read_csv(path: Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return pd.read_csv(path, dtype=str, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    raise UnicodeDecodeError(
        "unknown", b"", 0, 1, f"Failed to read {path} with utf-8-sig/utf-8/gb18030"
    ) from last_error


def load_score_file(path: Path) -> pd.DataFrame:
    frame = read_csv(path)
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"{path} is missing required columns: {sorted(missing)}")

    for column in OPTIONAL_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""

    frame["driver_key"] = normalize_id(frame["driver_id"])
    frame["score_date"] = parse_score_dates(frame["ppartition"])
    frame["score"] = pd.to_numeric(frame["score"], errors="coerce").fillna(0.0)
    frame = frame[frame["driver_key"].notna() & frame["score_date"].notna()].copy()
    frame = frame.sort_values(
        ["driver_key", "score_date", "score", "driver_id"],
        ascending=[True, True, False, True],
    ).drop_duplicates(["driver_key", "score_date"], keep="first")
    return frame

async def load_score_db(start_time:str) -> pd.DataFrame:
    sql=driver_sql.get_driver_two_week_profile(start_time)
    frame = await read_raw_sql(sql)
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"{start_time} is missing required columns: {sorted(missing)}")

    for column in OPTIONAL_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""

    frame["driver_key"] = normalize_id(frame["driver_id"])
    frame["score_date"] = parse_score_dates(frame["ppartition"])
    frame["score"] = pd.to_numeric(frame["score"], errors="coerce").fillna(0.0)
    frame = frame[frame["driver_key"].notna() & frame["score_date"].notna()].copy()
    frame = frame.sort_values(
        ["driver_key", "score_date", "score", "driver_id"],
        ascending=[True, True, False, True],
    ).drop_duplicates(["driver_key", "score_date"], keep="first")
    return frame


def percentile(series: pd.Series) -> pd.Series:
    return series.rank(method="average", pct=True)


def ranked_keys(frame: pd.DataFrame, order_fields: list[str], ascending: list[bool]) -> list[str]:
    ordered = frame.sort_values(order_fields + ["driver_key"], ascending=ascending + [True])
    return ordered["driver_key"].astype(str).tolist()


def make_rank_map(keys: list[str]) -> dict[str, int]:
    return {key: rank for rank, key in enumerate(keys, start=1)}


def build_driver_list(
    all_scores: pd.DataFrame,
    score_date: pd.Timestamp | None,
    limit: int,
    max2_top: int,
    org_top: int,
) -> tuple[pd.DataFrame, dict]:
    if max2_top + org_top > limit:
        raise ValueError("--max2-top + --org-top must be <= --limit")

    valid_dates = sorted(pd.Timestamp(date) for date in all_scores["score_date"].dropna().unique())
    if not valid_dates:
        raise ValueError("No valid score dates found")
    if score_date is None:
        score_date = valid_dates[-1]
    previous_date = score_date - pd.Timedelta(days=7)

    current = all_scores[all_scores["score_date"].eq(score_date)].copy()
    previous = all_scores[all_scores["score_date"].eq(previous_date)].copy()
    if current.empty:
        raise ValueError(f"No rows found for score_date={score_date:%Y-%m-%d}")

    previous_scores = previous[["driver_key", "score"]].rename(
        columns={"score": "previous_score"}
    )
    frame = current.merge(previous_scores, on="driver_key", how="left", validate="one_to_one")
    frame["target_week_start"] = score_date + pd.Timedelta(days=1)
    frame["target_week_end"] = score_date + pd.Timedelta(days=7)
    frame["score_avg2"] = frame[["score", "previous_score"]].mean(axis=1, skipna=True)
    frame["score_max2"] = frame[["score", "previous_score"]].max(axis=1, skipna=True)
    frame["score_pct"] = percentile(frame["score"])
    frame["avg2_pct"] = percentile(frame["score_avg2"])
    frame["max2_pct"] = percentile(frame["score_max2"])
    frame["org_score_pct"] = frame.groupby("organ_id", observed=True)["score"].rank(
        method="average", pct=True
    )
    frame["original_score"] = (
        0.70 * frame["avg2_pct"].fillna(0.0)
        + 0.30 * frame["score_pct"].fillna(0.0)
        + 0.25 * frame["org_score_pct"].fillna(0.0)
    )

    max2_keys_ordered = ranked_keys(
        frame, ["max2_pct", "original_score"], [False, False]
    )
    org_keys_ordered = ranked_keys(
        frame, ["org_score_pct", "original_score"], [False, False]
    )
    original_keys_ordered = ranked_keys(frame, ["original_score"], [False])

    max2_keys = set(max2_keys_ordered[:max2_top])
    org_keys = set(org_keys_ordered[:org_top])
    final_keys = set(max2_keys | org_keys)
    for key in original_keys_ordered:
        if len(final_keys) >= limit:
            break
        final_keys.add(key)

    max2_rank = make_rank_map(max2_keys_ordered)
    org_rank = make_rank_map(org_keys_ordered)
    original_rank = make_rank_map(original_keys_ordered)
    frame["max2_channel_rank"] = frame["driver_key"].map(max2_rank)
    frame["org_channel_rank"] = frame["driver_key"].map(org_rank)
    frame["original_rank"] = frame["driver_key"].map(original_rank)

    selected = frame[frame["driver_key"].isin(final_keys)].copy()
    selected["in_max2_top200"] = selected["driver_key"].isin(max2_keys)
    selected["in_org_top150"] = selected["driver_key"].isin(org_keys)
    selected["selection_source"] = np.select(
        [
            selected["in_max2_top200"] & selected["in_org_top150"],
            selected["in_max2_top200"],
            selected["in_org_top150"],
        ],
        ["both_channels", "max2_top200", "org_top150"],
        default="original_score_fill",
    )
    source_priority = {
        "both_channels": 1,
        "max2_top200": 2,
        "org_top150": 3,
        "original_score_fill": 4,
    }
    selected["source_priority"] = selected["selection_source"].map(source_priority)
    selected = selected.sort_values(
        ["source_priority", "original_score", "driver_key"],
        ascending=[True, False, True],
    ).copy()
    selected["weekly_list_rank"] = np.arange(1, len(selected) + 1)

    output_columns = [
        "score_date",
        "target_week_start",
        "target_week_end",
        "weekly_list_rank",
        "selection_source",
        "driver_id",
        "driver_name",
        "organ_id",
        "organ_name",
        "route_id",
        "score",
        "previous_score",
        "score_avg2",
        "score_max2",
        "score_pct",
        "avg2_pct",
        "max2_pct",
        "org_score_pct",
        "original_score",
        "max2_channel_rank",
        "org_channel_rank",
        "original_rank",
    ]
    diagnostics = {
        "score_date": f"{score_date:%Y-%m-%d}",
        "target_week": f"{score_date + pd.Timedelta(days=1):%Y-%m-%d}~{score_date + pd.Timedelta(days=7):%Y-%m-%d}",
        "current_rows": int(len(current)),
        "previous_rows": int(len(previous)),
        "selected_rows": int(len(selected)),
        "max2_top": int(max2_top),
        "org_top": int(org_top),
        "overlap": int(len(max2_keys & org_keys)),
        "union_distinct": int(len(max2_keys | org_keys)),
        "original_score_fill": int(limit - len(max2_keys | org_keys)),
    }
    return selected[output_columns], diagnostics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the weekly driver risk list from score tables only."
    )
    parser.add_argument(
        "--score-file",
        type=Path,
        help="One CSV containing at least the current score week and previous score week.",
    )
    parser.add_argument(
        "--current-file",
        type=Path,
        help="CSV containing the current score week. Use this with --previous-file if files are split.",
    )
    parser.add_argument(
        "--previous-file",
        type=Path,
        help="CSV containing the previous score week. Optional when --score-file already has both weeks.",
    )
    parser.add_argument(
        "--score-date",
        help="Current score date, for example 20260726 or 2026-07-26. Defaults to the latest date found.",
    )
    parser.add_argument("--output", type=Path, help="Output CSV path.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--max2-top", type=int, default=DEFAULT_MAX2_TOP)
    parser.add_argument("--org-top", type=int, default=DEFAULT_ORG_TOP)
    return parser.parse_args()


def has_cli_args() -> bool:
    return len(sys.argv) > 1


def apply_config_defaults() -> argparse.Namespace:
    args=argparse.Namespace()
    # if has_cli_args():
    #     return args

    args.score_file = CONFIG_SCORE_FILE
    args.current_file = CONFIG_CURRENT_FILE
    args.previous_file = CONFIG_PREVIOUS_FILE
    args.score_date = CONFIG_SCORE_DATE
    args.output = CONFIG_OUTPUT
    args.limit = CONFIG_LIMIT
    args.max2_top = CONFIG_MAX2_TOP
    args.org_top = CONFIG_ORG_TOP
    return args


async def main_warning(start_time:str) -> None:
    global CONFIG_SCORE_DATE
    CONFIG_SCORE_DATE = start_time
    args = apply_config_defaults()
    # if not args.score_file and not args.current_file:
    #     raise SystemExit(
    #         "Fill CONFIG_SCORE_FILE or CONFIG_CURRENT_FILE at the top of this script, "
    #         "or run with --score-file / --current-file."
    #     )
    # if args.score_file and args.current_file:
    #     raise SystemExit("Use --score-file or --current-file, not both")

    frames = []
    # if args.score_file:
    #     frames.append(load_score_file(args.score_file))
    # else:
    #     frames.append(load_score_file(args.current_file))
    #     if args.previous_file:
    #         frames.append(load_score_file(args.previous_file))
    frames.append(await load_score_db(args.score_date))
    all_scores = pd.concat(frames, ignore_index=True)
    score_date = parse_user_date(args.score_date) if args.score_date else None
    result, diagnostics = build_driver_list(
        all_scores=all_scores,
        score_date=score_date,
        limit=args.limit,
        max2_top=args.max2_top,
        org_top=args.org_top,
    )

    output = args.output
    if output is None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output = DEFAULT_OUTPUT_DIR / f"weekly_driver_list_{diagnostics['score_date'].replace('-', '')}.csv"
    else:
        output.parent.mkdir(parents=True, exist_ok=True)

    result.to_csv(output, index=False, encoding="utf-8-sig")

    # 无需指定 axis=1，代码可读性更强
    result.drop(columns=['weekly_list_rank', 'selection_source','previous_score',
                         'score_avg2','score_max2','score_pct','avg2_pct',
                         'max2_pct','org_score_pct','max2_channel_rank','org_channel_rank'], inplace=True)

    result['score_date'] = result['score_date'].dt.strftime('%Y-%m-%d')
    result['target_week_start'] = result['target_week_start'].dt.strftime('%Y-%m-%d')
    result['target_week_end'] = result['target_week_end'].dt.strftime('%Y-%m-%d')
    result['creator']='system'
    result['updater']='system'
    await save_warning_driver_week(result.to_dict('records'))
    print("Generated weekly driver list")
    print(f"score_date: {diagnostics['score_date']}")
    print(f"target_week: {diagnostics['target_week']}")
    print(f"current_rows: {diagnostics['current_rows']}")
    print(f"previous_rows: {diagnostics['previous_rows']}")
    print(f"selected_rows: {diagnostics['selected_rows']}")
    print(f"max2_top: {diagnostics['max2_top']}")
    print(f"org_top: {diagnostics['org_top']}")
    print(f"overlap: {diagnostics['overlap']}")
    print(f"original_score_fill: {diagnostics['original_score_fill']}")
    print(f"output: {output}")



if __name__ == "__main__":
    # CONFIG_SCORE_FILE=Path(r"C:\Users\12384\Desktop\log\7.05-7.26日四周驾驶员事故风险线路排名.csv")
    asyncio.run(main_warning("2026-07-26"))
