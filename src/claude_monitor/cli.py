import argparse
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .aggregator import aggregate
from .calculator import calculate_costs
from .config import load_pricing
from .display import display_csv, display_table
from .reader import read_records
from .realtime import run_realtime


DEFAULT_DAYS_BACK = {"realtime": 1, "summary": 1, "daily": 0, "monthly": 0}


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="claude-monitor",
        description="Claude Code token usage monitor with custom pricing",
    )
    parser.add_argument(
        "--view",
        choices=["realtime", "summary", "daily", "monthly"],
        default="realtime",
        help="display mode [default: realtime]",
    )
    parser.add_argument(
        "--data-path",
        default=None,
        help="path to Claude data directory [default: ~/.claude/projects]",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="path to monitor.ini [default: ./monitor.ini or ~/.claude/monitor.ini]",
    )
    parser.add_argument(
        "--refresh-rate",
        type=int,
        default=10,
        help="data refresh interval in seconds [default: 10]",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=None,
        help="look back N days (0=all time; summary/realtime default: 1, daily/monthly default: 0)",
    )
    parser.add_argument(
        "--today",
        action="store_true",
        help="only show today's data (from 00:00 local time), overrides --days-back",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="output CSV instead of table",
    )
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="show version",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    if args.version:
        print(f"claude-monitor {__version__}")
        return 0

    config_path = Path(args.config) if args.config else None
    days_back = args.days_back if args.days_back is not None else DEFAULT_DAYS_BACK.get(args.view, 0)
    today_only = args.today

    # 实时模式 — 持续轮询刷新
    if args.view == "realtime":
        run_realtime(
            data_path=args.data_path,
            config_path=config_path,
            refresh_rate=args.refresh_rate,
            days_back=days_back,
            today_only=today_only,
        )
        return 0

    # 静态模式 — 一次性输出
    pricing, default_pricing = load_pricing(config_path)
    records = read_records(data_path=args.data_path, days_back=days_back, today_only=today_only)

    if not records:
        print("No token usage data found")
        return 0

    calculate_costs(records, pricing, default_pricing)
    rows = aggregate(records, args.view)

    if not rows:
        print("No matching usage data")
        return 0

    if args.csv:
        display_csv(rows, args.view)
    else:
        display_table(rows, args.view)

    return 0


if __name__ == "__main__":
    sys.exit(main())
