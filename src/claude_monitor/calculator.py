"""根据 monitor.ini 定价计算每条记录的费用（支持生效日期与峰谷分时）。"""

import logging

from .config import resolve_pricing
from .reader import TokenRecord

logger = logging.getLogger(__name__)


def _price(entry: dict[str, object], key: str, is_peak: bool) -> float:
    """返回该层级（峰/谷）的每百万 token 单价；高峰价缺失时回退空闲价。"""
    if is_peak:
        peak = entry.get(f"peak_{key}")
        if peak is not None:
            return float(peak)
    return float(entry[key])


def calculate_costs(
    records: list[TokenRecord],
    pricing: dict[str, dict[str, object]],
    default_pricing: list[dict[str, object]],
) -> None:
    """就地计算每条 TokenRecord 的 cost、currency 与峰谷拆分。

    公式: (tokens / 1_000_000) * price_per_million
    peak_cost + offpeak_cost 恒等于 cost。
    """
    unknown_models: set[str] = set()

    for record in records:
        entry, is_peak, used_default = resolve_pricing(
            record.model, pricing, default_pricing, record.timestamp
        )

        cost = (
            (record.input_tokens / 1_000_000) * _price(entry, "input_price", is_peak)
            + (record.output_tokens / 1_000_000) * _price(entry, "output_price", is_peak)
            + (record.cache_creation_tokens / 1_000_000) * _price(entry, "cache_write_price", is_peak)
            + (record.cache_read_tokens / 1_000_000) * _price(entry, "cache_read_price", is_peak)
        )

        record.cost = round(cost, 6)
        record.currency = str(entry["currency"])
        record.peak_cost = record.cost if is_peak else 0.0
        record.offpeak_cost = 0.0 if is_peak else record.cost

        # 记录未匹配到具体 section 的模型（使用了 default）
        if used_default and pricing:
            unknown_models.add(record.model)

    if unknown_models:
        logger.info("以下模型未匹配到定价 section，使用了 [default]: %s", ", ".join(sorted(unknown_models)))
