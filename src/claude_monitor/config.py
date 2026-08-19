"""解析 monitor.ini 定价（支持生效日期与峰谷分时计价）。"""

import configparser
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# monitor.ini 搜索路径
CONFIG_SEARCH_PATHS = [
    Path("./monitor.ini"),
    Path.home() / ".claude" / "monitor.ini",
]

# 价格键（空闲/平价）及内置缺省值
_PRICE_KEYS = ("input_price", "output_price", "cache_write_price", "cache_read_price")
_KEY_DEFAULTS = {"input_price": 3.0, "output_price": 6.0, "cache_write_price": 3.0, "cache_read_price": 0.025}

# “无生效日期”版本的排序键
_INF = datetime.min.replace(tzinfo=timezone.utc)


def load_pricing(
    config_path: Optional[Path] = None,
) -> tuple[dict[str, dict[str, object]], list[dict[str, object]]]:
    """解析 monitor.ini，返回 (模型定价字典, 默认定价列表)。

    模型定价字典：{section_name: entry}。entry 字段：
      input_price / output_price / cache_write_price / cache_read_price / currency
      base_name（去掉 @日期 的基础名，用于匹配）
      effective（aware datetime 或 None，None=无生效日期限制）
      tz（ZoneInfo 或 None，None=系统本地时区）
      peak_hours（[(start_hour, end_hour), ...]，空列表=无峰谷）
      peak_input_price ... peak_cache_read_price（float 或 None）
    默认定价列表：所有 [default] 与 [default@日期] entry；
    未找到配置文件时返回 ([], [内置默认])。
    """
    # 无显式 --config 时，按搜索顺序取第一个存在的文件（README 优先级表）；
    # 全部不存在时 read([]) 返回空列表，走内置默认
    if config_path:
        paths_to_try = [Path(config_path)]
    else:
        first = next((p for p in CONFIG_SEARCH_PATHS if p.exists()), None)
        paths_to_try = [first] if first else []

    parser = configparser.ConfigParser()
    found = parser.read([str(p) for p in paths_to_try], encoding="utf-8")
    if not found:
        logger.warning("未找到 monitor.ini，将使用内置默认定价")
        return {}, [_builtin_default()]

    pricing: dict[str, dict[str, object]] = {}
    defaults: list[dict[str, object]] = []

    for section in parser.sections():
        base, _, date_suffix = section.partition("@")
        base = base.strip()
        sec = parser[section]
        tz = _parse_tz(sec.get("tz"))
        effective = _parse_effective_date(date_suffix, tz) if date_suffix else None
        peak_hours = _parse_peak_hours(sec["peak_hours"]) if "peak_hours" in sec else []

        entry: dict[str, object] = {
            "base_name": base,
            "effective": effective,
            "tz": tz,
            "peak_hours": peak_hours,
            "currency": sec.get("currency", "CNY"),
        }
        for key in _PRICE_KEYS:
            entry[key] = sec.getfloat(key, _KEY_DEFAULTS[key])
            if peak_hours:
                peak_val = sec.getfloat(f"peak_{key}", fallback=None)
                entry[f"peak_{key}"] = peak_val
                if peak_val is None:
                    logger.warning(
                        "section [%s] 配置了 peak_hours 但缺少 %s，该项按空闲价计",
                        section, f"peak_{key}",
                    )
            else:
                entry[f"peak_{key}"] = None

        if base.lower() == "default":
            defaults.append(entry)
        else:
            pricing[section] = entry

    if not defaults:
        defaults.append(_builtin_default())

    return pricing, defaults


def _parse_tz(raw: Optional[str]) -> Optional[ZoneInfo]:
    """解析 tz 键；空或无法识别时返回 None（回退系统本地时区）。"""
    if not raw:
        return None
    try:
        return ZoneInfo(raw)
    except Exception:
        logger.warning("无法识别时区 '%s'，回退系统本地时区", raw)
        return None


def _parse_effective_date(suffix: str, tz: Optional[ZoneInfo]) -> Optional[datetime]:
    """解析 section 名 @YYYY-MM-DD 后缀为 aware 的当日 00:00；格式错误返回 None（当无日期处理）。"""
    try:
        d = date.fromisoformat(suffix)
    except ValueError:
        logger.warning("section 名中的生效日期 '%s' 无效，按无日期处理", suffix)
        return None
    tzinfo = tz or datetime.now().astimezone().tzinfo
    return datetime(d.year, d.month, d.day, tzinfo=tzinfo)


def _parse_peak_hours(raw: str) -> list[tuple[int, int]]:
    """解析 '9-12,14-18' 为 [(9,12),(14,18)]；格式错误返回 []（按平价处理）。

    区间为半开 [start:00, end:00)，单位整点。
    """
    ranges: list[tuple[int, int]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            s, e = (int(x) for x in part.split("-"))
            if not 0 <= s < e <= 24:
                raise ValueError(part)
        except ValueError:
            logger.warning("peak_hours '%s' 无法解析，该 section 按平价处理", raw)
            return []
        ranges.append((s, e))
    return ranges


def _builtin_default() -> dict[str, object]:
    """内置默认定价（当没有 monitor.ini 时使用）。"""
    entry: dict[str, object] = {
        "base_name": "default",
        "effective": None,
        "tz": None,
        "peak_hours": [],
        "currency": "CNY",
    }
    for key in _PRICE_KEYS:
        entry[key] = _KEY_DEFAULTS[key]
        entry[f"peak_{key}"] = None
    return entry


def _best_entry(
    entries: list[dict[str, object]],
    timestamp: datetime,
) -> Optional[dict[str, object]]:
    """在 entry 列表中选出“生效日期最大且 ≤ timestamp”的版本（无日期视为 -∞）。"""
    candidates = [
        e for e in entries
        if e["effective"] is None or e["effective"] <= timestamp
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda e: e["effective"] or _INF)


def _is_peak_at(entry: dict[str, object], timestamp: datetime) -> bool:
    """判断 timestamp 是否落入 entry 的 peak_hours（按 entry 的 tz 换算小时）。"""
    ranges = entry["peak_hours"]
    if not ranges:
        return False
    tz = entry["tz"] or datetime.now().astimezone().tzinfo
    hour = timestamp.astimezone(tz).hour
    return any(s <= hour < e for s, e in ranges)


def resolve_pricing(
    model_name: str,
    pricing: dict[str, dict[str, object]],
    default_pricing: list[dict[str, object]],
    timestamp: datetime,
) -> tuple[dict[str, object], bool, bool]:
    """解析给定模型在给定时刻的 (定价 entry, 是否按高峰价, 是否回退到 default)。

    规则：
    1. base_name（去 @日期 的基础名）对模型名做大小写不敏感子串匹配
    2. 版本选择：生效日期最大且 ≤ timestamp 的版本；无版本满足时间条件视为未匹配
    3. 未匹配 → [default]（同样支持带日期版本）；default 也无可用版本 → 内置默认
    """
    model_lower = model_name.lower()
    matched = [e for e in pricing.values() if e["base_name"].lower() in model_lower]
    entry = _best_entry(matched, timestamp)
    used_default = False
    if entry is None:
        entry = _best_entry(default_pricing, timestamp) or _builtin_default()
        used_default = True

    return entry, _is_peak_at(entry, timestamp), used_default
