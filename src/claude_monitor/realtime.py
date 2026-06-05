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
from .display import format_cost, format_number
from .reader import read_records

CURRENCY_SYMBOLS = {"CNY": "CNY", "USD": "$", "EUR": "EUR"}


def run_realtime(
    data_path: Optional[str] = None,
    config_path: Optional[Path] = None,
    refresh_rate: int = 10,
) -> None:
    """启动实时监视模式。"""
    pricing, default_pricing = load_pricing(config_path)
    console = Console(force_terminal=True, legacy_windows=False)

    last_refresh = 0.0
    current_data: Optional[Table] = None

    def load_data() -> Table:
        records = read_records(data_path=data_path, days_back=1)
        if records:
            calculate_costs(records, pricing, default_pricing)
            rows = aggregate(records, "summary")
            if rows:
                return _build_table(rows, refresh_rate)
        return _empty_table(refresh_rate)

    try:
        with Live(console=console, refresh_per_second=2, screen=True) as live:
            while True:
                now = time.time()

                if now - last_refresh >= refresh_rate:
                    current_data = load_data()
                    last_refresh = now

                live.update(_render(current_data, refresh_rate, int(now - last_refresh)))

                time.sleep(0.5)
    except KeyboardInterrupt:
        pass


def _build_table(rows, refresh_rate: int) -> Table:
    currency = CURRENCY_SYMBOLS.get(rows[0].currency, rows[0].currency)

    table = Table(expand=False)
    table.add_column("Model", style="cyan")
    table.add_column("Input", justify="right")
    table.add_column("Output", justify="right")
    table.add_column("Cache Write", justify="right")
    table.add_column("Cache Read", justify="right")
    table.add_column("Requests", justify="right")
    table.add_column(f"Cost ({currency})", justify="right", style="green")

    total_input = total_output = total_cw = total_cr = total_requests = total_cost = 0

    for row in rows:
        table.add_row(
            row.model,
            format_number(row.input_tokens),
            format_number(row.output_tokens),
            format_number(row.cache_create_tokens),
            format_number(row.cache_read_tokens),
            str(row.request_count),
            format_cost(row.total_cost),
        )
        total_input += row.input_tokens
        total_output += row.output_tokens
        total_cw += row.cache_create_tokens
        total_cr += row.cache_read_tokens
        total_requests += row.request_count
        total_cost += row.total_cost

    table.add_section()
    table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{format_number(total_input)}[/bold]",
        f"[bold]{format_number(total_output)}[/bold]",
        f"[bold]{format_number(total_cw)}[/bold]",
        f"[bold]{format_number(total_cr)}[/bold]",
        f"[bold]{total_requests}[/bold]",
        f"[bold green]{format_cost(total_cost)}[/bold green]",
    )

    return table


def _empty_table(refresh_rate: int) -> Table:
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
