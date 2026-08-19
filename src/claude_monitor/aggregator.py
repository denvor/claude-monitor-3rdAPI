"""按 摘要/日/月 聚合 token 使用数据，每个模型独立成行。"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from .reader import TokenRecord


@dataclass
class AggregatedRow:
    """一行聚合结果 — 每个模型独立一行。"""
    period: str
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_create_tokens: int = 0
    cache_read_tokens: int = 0
    total_cost: float = 0.0
    peak_cost: float = 0.0
    offpeak_cost: float = 0.0
    request_count: int = 0
    currency: str = "CNY"

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cache_hit_rate(self) -> float:
        """缓存命中率: cache_read / (cache_read + cache_create + input) * 100。"""
        denominator = self.cache_read_tokens + self.cache_create_tokens + self.input_tokens
        if denominator == 0:
            return 0.0
        return self.cache_read_tokens / denominator * 100


def aggregate(
    records: list[TokenRecord],
    mode: str,
) -> list[AggregatedRow]:
    """按指定模式聚合记录，每个模型独立成行。"""
    if mode == "summary":
        return _aggregate_summary(records)
    if mode == "daily":
        return _aggregate_daily(records)
    if mode == "monthly":
        return _aggregate_monthly(records)
    raise ValueError(f"不支持的聚合模式: {mode}")


def _aggregate_summary(records: list[TokenRecord]) -> list[AggregatedRow]:
    return _group_by_period_and_model(records, key_func=lambda r: "Total")


def _aggregate_daily(records: list[TokenRecord]) -> list[AggregatedRow]:
    return _group_by_period_and_model(records, key_func=lambda r: r.timestamp.date().isoformat())


def _aggregate_monthly(records: list[TokenRecord]) -> list[AggregatedRow]:
    return _group_by_period_and_model(records, key_func=lambda r: r.timestamp.strftime("%Y-%m"))


def _group_by_period_and_model(
    records: list[TokenRecord],
    key_func,
) -> list[AggregatedRow]:
    """按 (period, model) 分组聚合。"""
    groups: dict[tuple[str, str], AggregatedRow] = defaultdict(
        lambda: AggregatedRow(period="", model="")
    )

    for r in records:
        period = key_func(r)
        model = r.model or "unknown"
        key = (period, model)
        row = groups[key]
        row.period = period
        row.model = model
        _add_record(row, r)

    return sorted(groups.values(), key=lambda r: (r.period, r.model))


def _add_record(row: AggregatedRow, record: TokenRecord) -> None:
    """将一条记录累加到聚合行。"""
    row.input_tokens += record.input_tokens
    row.output_tokens += record.output_tokens
    row.cache_create_tokens += record.cache_creation_tokens
    row.cache_read_tokens += record.cache_read_tokens
    row.total_cost += record.cost
    row.peak_cost += record.peak_cost
    row.offpeak_cost += record.offpeak_cost
    row.request_count += 1
    if record.currency:
        row.currency = record.currency
