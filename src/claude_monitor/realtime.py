"""实时模式 — Rich Live 轮询刷新 token 用量显示。"""

import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.table import Table

from .aggregator import aggregate
from .calculator import calculate_costs
from .config import load_pricing
from .display import _table_currency, format_cost, format_hit_rate, format_number
from .reader import read_records


def run_realtime(
    data_path: Optional[str] = None,
    config_path: Optional[Path] = None,
    refresh_rate: int = 10,
    days_back: int = 1,
    today_only: bool = True,
) -> None:
    """启动实时监视模式。"""
    pricing, default_pricing = load_pricing(config_path)
    console = Console(force_terminal=True, legacy_windows=False)

    last_refresh = 0.0
    current_data: Optional[Table] = None

    def load_data() -> Table:
        records = read_records(data_path=data_path, days_back=days_back, today_only=today_only)
        if records:
            calculate_costs(records, pricing, default_pricing)
            rows = aggregate(records, "summary")
            if rows:
                return _build_table(rows)
        return _empty_table()

    try:
        with Live(console=console, refresh_per_second=2, screen=True) as live:
            while True:
                now = time.time()

                if now - last_refresh >= refresh_rate:
                    current_data = load_data()
                    last_refresh = now

                elapsed = int(now - last_refresh)
                live.update(_render(current_data, refresh_rate, elapsed))

                time.sleep(0.5)
    except KeyboardInterrupt:
        pass


def _build_table(rows) -> Table:
    currency = _table_currency(rows)

    table = Table(expand=False)
    table.add_column("Model", style="cyan")
    table.add_column("Input", justify="right")
    table.add_column("Output", justify="right")
    table.add_column("Cache Write", justify="right")
    table.add_column("Cache Read", justify="right")
    table.add_column("Requests", justify="right")
    table.add_column("Cache Hit Rate", justify="right")
    table.add_column(f"Cost ({currency})", justify="right", style="green")
    table.add_column("Peak", justify="right")
    table.add_column("Off-peak", justify="right")

    total_input = total_output = total_cw = total_cr = total_requests = total_cost = 0
    total_peak = total_offpeak = 0

    for row in rows:
        table.add_row(
            row.model,
            format_number(row.input_tokens),
            format_number(row.output_tokens),
            format_number(row.cache_create_tokens),
            format_number(row.cache_read_tokens),
            str(row.request_count),
            format_hit_rate(row.cache_hit_rate, row.cache_read_tokens + row.cache_create_tokens + row.input_tokens),
            format_cost(row.total_cost),
            format_cost(row.peak_cost),
            format_cost(row.offpeak_cost),
        )
        total_input += row.input_tokens
        total_output += row.output_tokens
        total_cw += row.cache_create_tokens
        total_cr += row.cache_read_tokens
        total_requests += row.request_count
        total_cost += row.total_cost
        total_peak += row.peak_cost
        total_offpeak += row.offpeak_cost

    table.add_section()
    total_cache_input = total_cr + total_cw + total_input
    total_hit_rate = (total_cr / total_cache_input * 100) if total_cache_input else 0.0
    table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{format_number(total_input)}[/bold]",
        f"[bold]{format_number(total_output)}[/bold]",
        f"[bold]{format_number(total_cw)}[/bold]",
        f"[bold]{format_number(total_cr)}[/bold]",
        f"[bold]{total_requests}[/bold]",
        format_hit_rate(total_hit_rate, total_cache_input),
        f"[bold green]{format_cost(total_cost)}[/bold green]",
        f"[bold green]{format_cost(total_peak)}[/bold green]",
        f"[bold green]{format_cost(total_offpeak)}[/bold green]",
    )

    return table


def _empty_table() -> Table:
    table = Table()
    table.add_column("Status")
    table.add_row("[yellow]Waiting for data...[/yellow]")
    return table


def _render(table: Optional[Table], refresh_rate: int, elapsed: int) -> object:
    from rich.text import Text

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    remaining = max(refresh_rate - elapsed, 0)
    header = Text(f"Claude Monitor — {now_str}  refresh:{refresh_rate}s  next:{remaining}s", style="bold")

    if table is None:
        table = Table()
        table.add_column("Status")
        table.add_row("Loading...")

    from rich.console import Group
    return Group(header, table)
