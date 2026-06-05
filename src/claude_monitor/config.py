"""读取 monitor.ini 自定义 token 价格配置。"""

import configparser
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# monitor.ini 搜索路径
CONFIG_SEARCH_PATHS = [
    Path("./monitor.ini"),
    Path.home() / ".claude" / "monitor.ini",
]


def load_pricing(
    config_path: Optional[Path] = None,
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    """解析 monitor.ini，返回 (模型定价字典, 默认定价)。

    模型定价字典：{section_name: {input_price, output_price, cache_write_price, cache_read_price, currency}}
    默认定价：来自 [default] section
    """
    # 确定配置文件路径
    if config_path:
        paths_to_try = [Path(config_path)]
    else:
        paths_to_try = CONFIG_SEARCH_PATHS

    parser = configparser.ConfigParser()
    found = parser.read([str(p) for p in paths_to_try], encoding="utf-8")
    if not found:
        logger.warning("未找到 monitor.ini，将使用内置默认定价")
        return {}, _builtin_default()

    pricing: dict[str, dict[str, object]] = {}
    default: dict[str, object] = {}

    for section in parser.sections():
        sec = parser[section]
        entry = {
            "input_price": sec.getfloat("input_price", 3.0),
            "output_price": sec.getfloat("output_price", 6.0),
            "cache_write_price": sec.getfloat("cache_write_price", 3.0),
            "cache_read_price": sec.getfloat("cache_read_price", 0.025),
            "currency": sec.get("currency", "CNY"),
        }
        if section.lower() == "default":
            default = entry
        else:
            pricing[section] = entry

    if not default:
        default = _builtin_default()

    return pricing, default


def _builtin_default() -> dict[str, object]:
    """内置默认定价（当没有 monitor.ini 时使用）。"""
    return {
        "input_price": 3.0,
        "output_price": 6.0,
        "cache_write_price": 3.0,
        "cache_read_price": 0.025,
        "currency": "CNY",
    }


def find_model_pricing(
    model_name: str,
    pricing: dict[str, dict[str, object]],
    default_pricing: dict[str, object],
) -> dict[str, object]:
    """根据模型名匹配定价，大小写不敏感子串匹配，未匹配返回 default。"""
    model_lower = model_name.lower()
    for section_name, section_pricing in pricing.items():
        if section_name.lower() in model_lower:
            return section_pricing
    return default_pricing
