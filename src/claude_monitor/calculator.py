"""根据 monitor.ini 定价计算每条记录的费用。"""

import logging

from .config import find_model_pricing
from .reader import TokenRecord

logger = logging.getLogger(__name__)


def calculate_costs(
    records: list[TokenRecord],
    pricing: dict[str, dict[str, object]],
    default_pricing: dict[str, object],
) -> None:
    """就地计算每条 TokenRecord 的 cost 和 currency。

    公式: (tokens / 1_000_000) * price_per_million
    """
    unknown_models: set[str] = set()

    for record in records:
        model_pricing = find_model_pricing(record.model, pricing, default_pricing)

        cost = (
            (record.input_tokens / 1_000_000) * float(model_pricing["input_price"])
            + (record.output_tokens / 1_000_000) * float(model_pricing["output_price"])
            + (record.cache_creation_tokens / 1_000_000)
            * float(model_pricing["cache_write_price"])
            + (record.cache_read_tokens / 1_000_000)
            * float(model_pricing["cache_read_price"])
        )

        record.cost = round(cost, 6)
        record.currency = str(model_pricing["currency"])

        # 记录未匹配到具体 section 的模型（使用了 default）
        model_lower = record.model.lower()
        if not any(k.lower() in model_lower for k in pricing):
            unknown_models.add(record.model)

    if unknown_models:
        logger.info("以下模型未匹配到定价 section，使用了 [default]: %s", ", ".join(sorted(unknown_models)))
