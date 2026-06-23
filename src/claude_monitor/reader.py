"""扫描 JSONL 文件，提取 token 使用记录。"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def local_now() -> datetime:
    """返回本地当前时间（带时区）。"""
    return datetime.now().astimezone()


def to_local(utc_dt: datetime) -> datetime:
    """将 UTC 时间转为本地时间。"""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone()


@dataclass
class TokenRecord:
    """单条 token 使用记录。timestamp 为本地时间。"""
    timestamp: datetime
    model: str
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    cost: float = 0.0
    currency: str = "CNY"


def find_jsonl_files(data_path: Path) -> list[Path]:
    """递归查找所有 .jsonl 文件。"""
    if not data_path.exists():
        logger.warning("数据目录不存在: %s", data_path)
        return []
    return list(data_path.rglob("*.jsonl"))


def read_records(
    data_path: Optional[str] = None,
    days_back: int = 1,
    today_only: bool = True,
) -> list[TokenRecord]:
    """读取并解析 JSONL 文件，返回 token 记录列表。

    Args:
        data_path: Claude 数据目录，默认 ~/.claude/projects
        days_back: 分析最近N天，0 表示全部
        today_only: 仅返回当天（本地零点至今）的数据，优先级高于 days_back
    """
    data_path = Path(data_path if data_path else "~/.claude/projects").expanduser()
    jsonl_files = find_jsonl_files(data_path)
    if not jsonl_files:
        logger.warning("未找到 JSONL 文件: %s", data_path)
        return []

    cutoff = None
    if today_only:
        now = local_now()
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif days_back > 0:
        cutoff = local_now() - timedelta(days=days_back)

    records: list[TokenRecord] = []
    seen_uuids: set[str] = set()

    for file_path in jsonl_files:
        _process_file(file_path, cutoff, seen_uuids, records)

    records.sort(key=lambda r: r.timestamp)
    logger.info("从 %d 个文件读取 %d 条记录", len(jsonl_files), len(records))
    return records


def _process_file(
    file_path: Path,
    cutoff: Optional[datetime],
    seen_uuids: set[str],
    records: list[TokenRecord],
) -> None:
    """处理单个 JSONL 文件。"""
    try:
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = _parse_line(line, cutoff, seen_uuids)
                if record:
                    records.append(record)
    except Exception as e:
        logger.warning("读取文件失败 %s: %s", file_path.name, e)


def _parse_line(
    line: str,
    cutoff: Optional[datetime],
    seen_uuids: set[str],
) -> Optional[TokenRecord]:
    """解析单行 JSONL，返回 TokenRecord 或 None。"""
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None

    # 仅处理 assistant 类型且有 usage 的条目
    if data.get("type") != "assistant":
        return None

    message = data.get("message")
    if not isinstance(message, dict):
        return None

    model = message.get("model", "")
    # 跳过 synthetic（无实际 token 消耗）
    if not model or model == "<synthetic>":
        return None

    usage = message.get("usage")
    if not isinstance(usage, dict):
        return None

    input_tokens = usage.get("input_tokens", 0) or 0
    output_tokens = usage.get("output_tokens", 0) or 0
    cache_create = usage.get("cache_creation_input_tokens", 0) or 0
    cache_read = usage.get("cache_read_input_tokens", 0) or 0

    # 跳过零 token 条目
    if input_tokens == 0 and output_tokens == 0:
        return None

    # 去重
    uuid = data.get("uuid", "")
    if uuid and uuid in seen_uuids:
        return None
    if uuid:
        seen_uuids.add(uuid)

    # 解析时间戳
    ts_str = data.get("timestamp", "")
    if not ts_str:
        return None
    try:
        ts_str = ts_str.replace("Z", "+00:00")
        timestamp = to_local(datetime.fromisoformat(ts_str))
    except ValueError:
        return None

    # 时间过滤
    if cutoff and timestamp < cutoff:
        return None

    return TokenRecord(
        timestamp=timestamp,
        model=model,
        input_tokens=int(input_tokens),
        output_tokens=int(output_tokens),
        cache_creation_tokens=int(cache_create),
        cache_read_tokens=int(cache_read),
    )
