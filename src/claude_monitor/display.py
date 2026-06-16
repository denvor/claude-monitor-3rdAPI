"""Rich 表格和 CSV 输出。"""

import csv
import io
from typing import Optional

from rich.console import Console
from rich.table import Table

from .aggregator import AggregatedRow

CURRENCY_SYMBOLS = {"CNY": "CNY", "USD": "$", "EUR": "EUR"}


def format_number(n: int) -> str:
    return f"{n:,}"


def format_cost(c: float) -> str:
    if c < 0.01:
        return f"{c:.4f}"
    if c < 1:
        return f"{c:.3f}"
    return f"{c:.2f}"


def _create_console() -> Console:
    return Console(force_terminal=True, legacy_windows=False)


def _table_currency(rows: list[AggregatedRow]) -> str:
    """返回表格表头货币标签，多币种时标记为 mixed。"""
    currencies = {r.currency for r in rows}
    if len(currencies) == 1:
        c = currencies.pop()
        return CURRENCY_SYMBOLS.get(c, c)
    return "mixed"


PERIOD_HEADERS = {"summary": "Period", "daily": "Date", "monthly": "Month"}


def display_table(
    rows: list[AggregatedRow],
    mode: str,
    console: Optional[Console] = None,
) -> None:
    if console is None:
        console = _create_console()

    if not rows:
        console.print("[yellow]No usage data found[/yellow]")
        return

    currency = _table_currency(rows)
    period_header = PERIOD_HEADERS.get(mode, "Period")

    table = Table(title=f"Claude Code Token Usage ({mode})")
    table.add_column(period_header, style="cyan")
    table.add_column("Model", style="dim")
    table.add_column("Input Tokens", justify="right")
    table.add_column("Output Tokens", justify="right")
    table.add_column("Cache Write", justify="right")
    table.add_column("Cache Read", justify="right")
    table.add_column("Requests", justify="right")
    table.add_column(f"Cost ({currency})", justify="right", style="green")

    totals = AggregatedRow(period="Total", model="")
    for row in rows:
        table.add_row(
            row.period,
            row.model,
            format_number(row.input_tokens),
            format_number(row.output_tokens),
            format_number(row.cache_create_tokens),
            format_number(row.cache_read_tokens),
            str(row.request_count),
            format_cost(row.total_cost),
        )
        _sum_row(totals, row)

    if len(rows) > 1:
        table.add_section()
        table.add_row(
            "[bold]Total[/bold]",
            "",
            f"[bold]{format_number(totals.input_tokens)}[/bold]",
            f"[bold]{format_number(totals.output_tokens)}[/bold]",
            f"[bold]{format_number(totals.cache_create_tokens)}[/bold]",
            f"[bold]{format_number(totals.cache_read_tokens)}[/bold]",
            f"[bold]{totals.request_count}[/bold]",
            f"[bold green]{format_cost(totals.total_cost)}[/bold green]",
        )

    console.print(table)


def display_csv(rows: list[AggregatedRow], mode: str) -> None:
    output = io.StringIO()
    writer = csv.writer(output)

    period_header = PERIOD_HEADERS.get(mode, "Period")
    currency = f"Cost({_table_currency(rows)})" if rows else "Cost"

    writer.writerow([
        period_header, "Model", "InputTokens", "OutputTokens",
        "CacheWrite", "CacheRead", "Requests", currency,
    ])

    for row in rows:
        writer.writerow([
            row.period,
            row.model,
            row.input_tokens,
            row.output_tokens,
            row.cache_create_tokens,
            row.cache_read_tokens,
            row.request_count,
            format_cost(row.total_cost),
        ])

    print(output.getvalue(), end="")


def _sum_row(target: AggregatedRow, source: AggregatedRow) -> None:
    target.input_tokens += source.input_tokens
    target.output_tokens += source.output_tokens
    target.cache_create_tokens += source.cache_create_tokens
    target.cache_read_tokens += source.cache_read_tokens
    target.total_cost += source.total_cost
    target.request_count += source.request_count
