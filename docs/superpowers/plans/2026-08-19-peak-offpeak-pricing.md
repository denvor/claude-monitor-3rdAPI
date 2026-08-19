# 峰谷分时计价支持 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `monitor.ini` 支持价格生效日期（`@YYYY-MM-DD` section 后缀）与峰谷分时计价（`peak_hours` + `peak_*` 价格键），使 DeepSeek 2026-08-17 起的新峰谷价格能被逐条记录正确计价，并在表格/CSV 中展示 Peak/Off-peak 成本拆分。

**Architecture:** 方案 A——就地扩展现有 6 个模块，不新增文件。`config.py` 负责解析扩展键并提供 `resolve_pricing(model, pricing, default, timestamp) -> (entry, is_peak, used_default)`；`calculator.py` 逐条按记录时间落价并拆分 `peak_cost`/`offpeak_cost`；聚合与展示层顺流而下。时区用标准库 `zoneinfo`，零新依赖。

**Tech Stack:** Python ≥ 3.9，rich（唯一第三方依赖），标准库 configparser/zoneinfo/dataclasses。

**Spec:** `docs/superpowers/specs/2026-08-19-peak-offpeak-pricing-design.md`

**项目约定（执行者必读）:**
- 项目无测试基建（无 pytest），验证一律用内联 heredoc 断言脚本 + 真实数据冒烟，不新增测试框架
- 所有验证命令在仓库根目录 `/home/denvor/work/claude-monitor-3rdAPI` 执行，统一加 `PYTHONPATH=src` 确保跑的是工作区代码
- 代码注释用中文
- 每个任务结束必须 commit；只 `git add` 本任务涉及的文件
- **`monitor.ini` 工作区带有用户未提交的 Qwen section（价格为 0），Task 5 提交 monitor.ini 时会一并带入——提交前必须向用户确认**

---

### Task 1: 计价核心 — config 解析 + resolve_pricing + calculator 拆分 + TokenRecord 字段

**Files:**
- Modify: `src/claude_monitor/config.py`（整体重写）
- Modify: `src/claude_monitor/reader.py:25-35`（TokenRecord 加两字段）
- Modify: `src/claude_monitor/calculator.py`（整体重写）

- [ ] **Step 1: TokenRecord 增加峰谷拆分字段**

`src/claude_monitor/reader.py` 中 `TokenRecord` dataclass，把

```python
    cost: float = 0.0
    currency: str = "CNY"
```

改为

```python
    cost: float = 0.0
    peak_cost: float = 0.0
    offpeak_cost: float = 0.0
    currency: str = "CNY"
```

（`peak_cost + offpeak_cost` 恒等于 `cost`，由 calculator 保证。）

- [ ] **Step 2: 整体重写 `src/claude_monitor/config.py`**

完整新内容：

```python
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
    if config_path:
        paths_to_try = [Path(config_path)]
    else:
        paths_to_try = CONFIG_SEARCH_PATHS

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
```

注意：原 `find_model_pricing` 被 `resolve_pricing` 取代，直接删除（本任务同步改掉唯一调用方 calculator.py，仓库保持可运行）。`cli.py` / `realtime.py` 中 `pricing, default_pricing = load_pricing(...)` 的解包形式不变，无需改动。

- [ ] **Step 3: 整体重写 `src/claude_monitor/calculator.py`**

完整新内容：

```python
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
```

- [ ] **Step 4: 运行边界验证脚本**

```bash
cd /home/denvor/work/claude-monitor-3rdAPI && PYTHONPATH=src python3 - <<'EOF'
import os, tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from claude_monitor.config import load_pricing
from claude_monitor.calculator import calculate_costs
from claude_monitor.reader import TokenRecord

ini = """
[default]
input_price=3.00
output_price=6.00
cache_write_price=3.00
cache_read_price=0.025
currency=CNY

[deepseek-v4-pro]
input_price=3.00
output_price=6.00
cache_write_price=3.00
cache_read_price=0.025
currency=CNY

[deepseek-v4-pro@2026-08-17]
peak_hours=9-12,14-18
tz=Asia/Shanghai
input_price=4.50
output_price=13.50
cache_write_price=4.50
cache_read_price=0.15
peak_input_price=9.00
peak_output_price=27.00
peak_cache_write_price=9.00
peak_cache_read_price=0.30
currency=CNY
"""
fd, path = tempfile.mkstemp(suffix=".ini")
with os.fdopen(fd, "w") as f:
    f.write(ini)
pricing, default_pricing = load_pricing(Path(path))
os.unlink(path)

BJT = ZoneInfo("Asia/Shanghai")

def rec(ts, inp=1_000_000, out=0, cw=0, cr=0, model="deepseek-v4-pro"):
    return TokenRecord(timestamp=ts, model=model, input_tokens=inp,
                       output_tokens=out, cache_creation_tokens=cw, cache_read_tokens=cr)

cases = [
    # (说明, 时间, 参数, 期望 cost)
    ("生效日前一晚 23:59 → 旧价",          datetime(2026, 8, 16, 23, 59, tzinfo=BJT), {}, 3.0),
    ("生效日当天 00:00 → 新价闲时",        datetime(2026, 8, 17, 0, 0, tzinfo=BJT),   {}, 4.5),
    ("高峰 10:00 → 9.0",                   datetime(2026, 8, 17, 10, 0, tzinfo=BJT),  {}, 9.0),
    ("边界 12:00:00 → 闲时（半开区间）",    datetime(2026, 8, 17, 12, 0, tzinfo=BJT),  {}, 4.5),
    ("午间 13:00 → 闲时",                  datetime(2026, 8, 17, 13, 0, tzinfo=BJT),  {}, 4.5),
    ("边界 18:00:00 → 闲时",               datetime(2026, 8, 17, 18, 0, tzinfo=BJT),  {}, 4.5),
    ("高峰缓存命中 10:00 → 0.30",          datetime(2026, 8, 17, 10, 0, tzinfo=BJT),  {"cr": 1_000_000, "inp": 0}, 0.30),
    ("闲时缓存命中 23:00 → 0.15",          datetime(2026, 8, 17, 23, 0, tzinfo=BJT),  {"cr": 1_000_000, "inp": 0}, 0.15),
    ("未匹配模型 → default 平价",          datetime(2026, 8, 17, 10, 0, tzinfo=BJT),  {}, None),
]

records = []
for name, ts, kw, expect in cases:
    model = "mystery-model" if expect is None else "deepseek-v4-pro"
    records.append(rec(ts, model=model, **kw))

calculate_costs(records, pricing, default_pricing)

for (name, _, _, expect), r in zip(cases, records):
    e = 3.0 if expect is None else expect
    assert abs(r.cost - e) < 1e-9, f"{name}: 期望 {e}，实际 {r.cost}"
    assert abs(r.cost - (r.peak_cost + r.offpeak_cost)) < 1e-9, f"{name}: 峰谷拆分之和 ≠ cost"

# 峰谷拆分方向
assert records[2].peak_cost == 9.0 and records[2].offpeak_cost == 0.0      # 高峰
assert records[1].peak_cost == 0.0 and records[1].offpeak_cost == 4.5      # 闲时
assert records[0].peak_cost == 0.0 and records[0].offpeak_cost == 3.0      # 旧价段计入 Off-peak 列
print("OK: Task 1 边界验证全部通过")
EOF
```

预期：输出 `OK: Task 1 边界验证全部通过`。

- [ ] **Step 5: 真实数据冒烟**

```bash
cd /home/denvor/work/claude-monitor-3rdAPI && PYTHONPATH=src python3 -m claude_monitor --view summary
```

预期：正常渲染表格或打印 `No token usage data found`，无 traceback。

- [ ] **Step 6: Commit**

```bash
cd /home/denvor/work/claude-monitor-3rdAPI
git add src/claude_monitor/config.py src/claude_monitor/reader.py src/claude_monitor/calculator.py
git commit -m "feat: monitor.ini 支持 @生效日期 与 peak_hours 峰谷分时计价核心"
```

---

### Task 2: aggregator 峰谷字段累加

**Files:**
- Modify: `src/claude_monitor/aggregator.py:10-21, 83-92`

- [ ] **Step 1: `AggregatedRow` 增加两字段**

`AggregatedRow` dataclass 中把

```python
    total_cost: float = 0.0
    request_count: int = 0
```

改为

```python
    total_cost: float = 0.0
    peak_cost: float = 0.0
    offpeak_cost: float = 0.0
    request_count: int = 0
```

- [ ] **Step 2: `_add_record` 累加两字段**

`_add_record` 中 `row.total_cost += record.cost` 之后加两行：

```python
    row.peak_cost += record.peak_cost
    row.offpeak_cost += record.offpeak_cost
```

- [ ] **Step 3: 验证聚合累加**

```bash
cd /home/denvor/work/claude-monitor-3rdAPI && PYTHONPATH=src python3 - <<'EOF'
import os, tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from claude_monitor.config import load_pricing
from claude_monitor.calculator import calculate_costs
from claude_monitor.reader import TokenRecord
from claude_monitor.aggregator import aggregate

ini = """
[default]
input_price=3.00
output_price=6.00
cache_write_price=3.00
cache_read_price=0.025
currency=CNY

[deepseek-v4-pro@2026-08-17]
peak_hours=9-12,14-18
tz=Asia/Shanghai
input_price=4.50
output_price=13.50
cache_write_price=4.50
cache_read_price=0.15
peak_input_price=9.00
peak_output_price=27.00
peak_cache_write_price=9.00
peak_cache_read_price=0.30
currency=CNY
"""
fd, path = tempfile.mkstemp(suffix=".ini")
with os.fdopen(fd, "w") as f:
    f.write(ini)
pricing, default_pricing = load_pricing(Path(path))
os.unlink(path)

BJT = ZoneInfo("Asia/Shanghai")
def rec(ts, inp=1_000_000):
    return TokenRecord(timestamp=ts, model="deepseek-v4-pro", input_tokens=inp,
                       output_tokens=0, cache_creation_tokens=0, cache_read_tokens=0)

# 8/16 23:59 旧价段 + 8/17 10:00 高峰 + 8/17 23:00 闲时
records = [
    rec(datetime(2026, 8, 16, 23, 59, tzinfo=BJT)),  # 旧价 3.0（无旧 section → default 3.0）
    rec(datetime(2026, 8, 17, 10, 0, tzinfo=BJT)),   # 高峰 9.0
    rec(datetime(2026, 8, 17, 23, 0, tzinfo=BJT)),   # 闲时 4.5
]
calculate_costs(records, pricing, default_pricing)

rows = aggregate(records, "summary")
assert len(rows) == 1, f"summary 应 1 行，实际 {len(rows)}"
row = rows[0]
assert row.total_cost == 16.5, row.total_cost
assert row.peak_cost == 9.0, row.peak_cost
assert row.offpeak_cost == 7.5, row.offpeak_cost
assert row.request_count == 3

daily = aggregate(records, "daily")
assert len(daily) == 2, f"daily 应 2 行，实际 {len(daily)}"
d17 = [r for r in daily if r.period == "2026-08-17"][0]
assert d17.peak_cost == 9.0 and d17.offpeak_cost == 4.5
print("OK: Task 2 聚合验证全部通过")
EOF
```

预期：输出 `OK: Task 2 聚合验证全部通过`。

- [ ] **Step 4: Commit**

```bash
cd /home/denvor/work/claude-monitor-3rdAPI
git add src/claude_monitor/aggregator.py
git commit -m "feat: AggregatedRow 增加 peak_cost/offpeak_cost 累加"
```

---

### Task 3: display 表格与 CSV 增加 Peak/Off-peak 列

**Files:**
- Modify: `src/claude_monitor/display.py:50-133`

- [ ] **Step 1: `display_table` 加两列与数据**

在 `table.add_column(f"Cost ({currency})", justify="right", style="green")` 之后加：

```python
    table.add_column("Peak", justify="right")
    table.add_column("Off-peak", justify="right")
```

数据行 `format_cost(row.total_cost),` 之后加：

```python
            format_cost(row.peak_cost),
            format_cost(row.offpeak_cost),
```

Total 行 `[bold green]{format_cost(totals.total_cost)}[/bold green],` 之后加：

```python
            f"[bold green]{format_cost(totals.peak_cost)}[/bold green]",
            f"[bold green]{format_cost(totals.offpeak_cost)}[/bold green]",
```

- [ ] **Step 2: `display_csv` 加两列**

表头 writerow 改为：

```python
    writer.writerow([
        period_header, "Model", "InputTokens", "OutputTokens",
        "CacheWrite", "CacheRead", "Requests", "CacheHitRate", currency,
        "PeakCost", "OffpeakCost",
    ])
```

数据行 `format_cost(row.total_cost),` 之后加：

```python
            format_cost(row.peak_cost),
            format_cost(row.offpeak_cost),
```

- [ ] **Step 3: `_sum_row` 累加两字段**

函数末尾加：

```python
    target.peak_cost += source.peak_cost
    target.offpeak_cost += source.offpeak_cost
```

- [ ] **Step 4: 验证表格与 CSV 输出**

```bash
cd /home/denvor/work/claude-monitor-3rdAPI && PYTHONPATH=src python3 - <<'EOF'
import contextlib, io
from rich.console import Console

from claude_monitor.aggregator import AggregatedRow
from claude_monitor.display import display_csv, display_table

row = AggregatedRow(period="2026-08-17", model="deepseek-v4-pro",
                    input_tokens=100, output_tokens=200,
                    cache_create_tokens=0, cache_read_tokens=50,
                    total_cost=10.0, peak_cost=6.0, offpeak_cost=4.0,
                    request_count=3)

# CSV
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    display_csv([row], "daily")
csv_out = buf.getvalue()
assert "PeakCost" in csv_out and "OffpeakCost" in csv_out, csv_out
assert "6.00" in csv_out and "4.00" in csv_out, csv_out

# 表格
console = Console(record=True, force_terminal=True, width=200)
display_table([row], "daily", console=console)
text = console.export_text()
assert "Peak" in text and "Off-peak" in text, text
assert "6.00" in text and "4.00" in text, text

# Total 行（两行数据时出现）
row2 = AggregatedRow(period="2026-08-18", model="deepseek-v4-pro",
                     input_tokens=10, output_tokens=20,
                     total_cost=1.0, peak_cost=0.5, offpeak_cost=0.5)
console2 = Console(record=True, force_terminal=True, width=200)
display_table([row, row2], "daily", console=console2)
text2 = console2.export_text()
assert "6.50" in text2 and "4.50" in text2, text2
print("OK: Task 3 展示层验证全部通过")
EOF
```

预期：输出 `OK: Task 3 展示层验证全部通过`。

- [ ] **Step 5: 真实数据冒烟（表格 + CSV）**

```bash
cd /home/denvor/work/claude-monitor-3rdAPI && PYTHONPATH=src python3 -m claude_monitor --view daily --days-back 0 && PYTHONPATH=src python3 -m claude_monitor --view daily --days-back 0 --csv
```

预期：表格出现 Peak / Off-peak 列；CSV 表头含 `PeakCost,OffpeakCost`，无 traceback。

- [ ] **Step 6: Commit**

```bash
cd /home/denvor/work/claude-monitor-3rdAPI
git add src/claude_monitor/display.py
git commit -m "feat: 表格与 CSV 增加 Peak/Off-peak 成本拆分列"
```

---

### Task 4: realtime 实时表格增加 Peak/Off-peak 列

**Files:**
- Modify: `src/claude_monitor/realtime.py:59-106`

- [ ] **Step 1: `_build_table` 加两列与累加**

`table.add_column(f"Cost ({currency})", justify="right", style="green")` 之后加：

```python
    table.add_column("Peak", justify="right")
    table.add_column("Off-peak", justify="right")
```

`total_input = total_output = total_cw = total_cr = total_requests = total_cost = 0` 改为：

```python
    total_input = total_output = total_cw = total_cr = total_requests = total_cost = 0
    total_peak = total_offpeak = 0
```

循环内 `total_cost += row.total_cost` 之后加：

```python
        total_peak += row.peak_cost
        total_offpeak += row.offpeak_cost
```

Total 行 `[bold green]{format_cost(total_cost)}[/bold green],` 之后加：

```python
        f"[bold green]{format_cost(total_peak)}[/bold green]",
        f"[bold green]{format_cost(total_offpeak)}[/bold green]",
```

- [ ] **Step 2: 验证实时表格构建**

```bash
cd /home/denvor/work/claude-monitor-3rdAPI && PYTHONPATH=src python3 - <<'EOF'
from rich.console import Console

from claude_monitor.aggregator import AggregatedRow
from claude_monitor.realtime import _build_table

row = AggregatedRow(period="Total", model="deepseek-v4-pro",
                    input_tokens=100, output_tokens=200,
                    total_cost=10.0, peak_cost=6.0, offpeak_cost=4.0,
                    request_count=3)

table = _build_table([row])
headers = [str(c.header) for c in table.columns]
assert headers[-3:] == ["Cost (CNY)", "Peak", "Off-peak"], headers
assert len(table.rows) == 2, f"应 1 数据行 + 1 Total 行，实际 {len(table.rows)}"

console = Console(record=True, force_terminal=True, width=200)
console.print(table)
text = console.export_text()
assert "6.00" in text and "4.00" in text, text
print("OK: Task 4 实时表格验证全部通过")
EOF
```

预期：输出 `OK: Task 4 实时表格验证全部通过`。

- [ ] **Step 3: Commit**

```bash
cd /home/denvor/work/claude-monitor-3rdAPI
git add src/claude_monitor/realtime.py
git commit -m "feat: 实时表格增加 Peak/Off-peak 成本拆分列"
```

---

### Task 5: 仓库 monitor.ini 更新 DeepSeek 官方新价

**Files:**
- Modify: `monitor.ini`（在两个 DeepSeek section 后各插入一个 `@2026-08-17` section；不动 Qwen section）

- [ ] **Step 1: `[deepseek-v4-pro]` section 末尾（`currency=CNY` 之后、`[deepseek-v4-flash]` 之前）插入**

```ini

[deepseek-v4-pro@2026-08-17]
# --- DeepSeek V4 Pro 峰谷定价（2026-08-17 起，北京时间判定）---
# 高峰时段：每日 9:00-12:00、14:00-18:00（其余为空闲时段）
peak_hours=9-12,14-18
tz=Asia/Shanghai

# 空闲时段价格
input_price=4.50
output_price=13.50
cache_write_price=4.50
cache_read_price=0.15

# 高峰时段价格
peak_input_price=9.00
peak_output_price=27.00
peak_cache_write_price=9.00
peak_cache_read_price=0.30

currency=CNY
```

- [ ] **Step 2: `[deepseek-v4-flash]` section 末尾（`currency=CNY` 之后、`[Qwen3.6-35B-A3B-UD-IQ4_NL_XL.gguf]` 之前）插入**

```ini

[deepseek-v4-flash@2026-08-17]
# --- DeepSeek V4 Flash 峰谷定价（2026-08-17 起，北京时间判定）---
peak_hours=9-12,14-18
tz=Asia/Shanghai

# 空闲时段价格
input_price=1.50
output_price=4.50
cache_write_price=1.50
cache_read_price=0.05

# 高峰时段价格
peak_input_price=3.00
peak_output_price=9.00
peak_cache_write_price=3.00
peak_cache_read_price=0.10

currency=CNY
```

- [ ] **Step 3: 验证仓库配置解析**

```bash
cd /home/denvor/work/claude-monitor-3rdAPI && PYTHONPATH=src python3 - <<'EOF'
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from claude_monitor.config import load_pricing, resolve_pricing

pricing, default_pricing = load_pricing(Path("monitor.ini"))  # 显式路径，避免与 ~/.claude/monitor.ini 合并
BJT = ZoneInfo("Asia/Shanghai")

# 8/17 10:00 高峰 → 应用 @2026-08-17 版本，peak 输出价 27.0
entry, is_peak, used_default = resolve_pricing(
    "deepseek-v4-pro", pricing, default_pricing,
    datetime(2026, 8, 17, 10, 0, tzinfo=BJT))
assert used_default is False, "应匹配命名 section"
assert entry["base_name"] == "deepseek-v4-pro"
assert is_peak is True
assert entry["peak_output_price"] == 27.0

# 8/16 任意时刻 → 旧版（无 @日期）
entry2, is_peak2, _ = resolve_pricing(
    "deepseek-v4-pro", pricing, default_pricing,
    datetime(2026, 8, 16, 10, 0, tzinfo=BJT))
assert is_peak2 is False and entry2["output_price"] == 6.0

# flash 高峰输出 9.0
entry3, is_peak3, _ = resolve_pricing(
    "deepseek-v4-flash", pricing, default_pricing,
    datetime(2026, 8, 18, 15, 0, tzinfo=BJT))
assert is_peak3 is True and entry3["peak_output_price"] == 9.0

# Qwen 本地模型（用户未提交 section）不受影响
entry4, is_peak4, _ = resolve_pricing(
    "Qwen3.6-35B-A3B-UD-IQ4_NL_XL.gguf", pricing, default_pricing,
    datetime(2026, 8, 18, 15, 0, tzinfo=BJT))
assert is_peak4 is False and entry4["output_price"] == 0
print("OK: Task 5 仓库配置验证全部通过")
EOF
```

预期：输出 `OK: Task 5 仓库配置验证全部通过`。

- [ ] **Step 4: 真实数据冒烟（检查 8/17 前后费用跳变）**

```bash
cd /home/denvor/work/claude-monitor-3rdAPI && PYTHONPATH=src python3 -m claude_monitor --view daily --days-back 0
```

预期：8/17 及之后的日期行出现 Peak 列非零值（如有高峰时段用量），无 traceback。

- [ ] **Step 5: Commit（⚠️ 先向用户确认）**

工作区的 `monitor.ini` 还带有用户未提交的 Qwen section（价格为 0），`git add monitor.ini` 会一并提交。**执行前先向用户展示 `git diff monitor.ini` 并确认**，然后：

```bash
cd /home/denvor/work/claude-monitor-3rdAPI
git add monitor.ini
git commit -m "config: DeepSeek v4-pro/v4-flash 增加 @2026-08-17 官方峰谷价格"
```

---

### Task 6: 版本号 + 双语 README + 双语 CHANGELOG

**Files:**
- Modify: `pyproject.toml:7`
- Modify: `src/claude_monitor/__init__.py:3`
- Modify: `README.md`（Configuration Format 章节）
- Modify: `README_zh.md`（配置格式章节）
- Modify: `CHANGELOG.md`（文件顶部 `# Changelog` 之后）
- Modify: `CHANGELOG_zh.md`（文件顶部 `# Changelog` 之后）

- [ ] **Step 1: 版本号 1.0.0 → 1.1.0**

`pyproject.toml` 中 `version = "1.0.0"` 改为 `version = "1.1.0"`；
`src/claude_monitor/__init__.py` 中 `__version__ = "1.0.0"` 改为 `__version__ = "1.1.0"`。

- [ ] **Step 2: README.md 在「Configuration Format」ini 示例与说明列表之后、「## How It Works」之前插入**

```markdown
### Effective Dates & Peak/Off-Peak Pricing

Sections support two optional extensions (works with any provider; omit them to keep flat pricing):

- **`@YYYY-MM-DD` suffix** in the section name — pricing takes effect from 00:00 (in the section's `tz`) on that date. The version with the latest effective date not after the record time is used; records older than all dated versions fall back to the undated version, then `[default]`.
- **`peak_hours`** — comma-separated peak hour ranges `start-end` (half-open `[start:00, end:00)`), evaluated in the section's timezone.
- **`tz`** — IANA timezone used for peak detection and the effective date (default: system local time).
- **`peak_input_price` / `peak_output_price` / `peak_cache_write_price` / `peak_cache_read_price`** — prices applied during peak hours.

Example (DeepSeek peak/off-peak pricing, effective 2026-08-17, peak = Beijing time 9:00–12:00 & 14:00–18:00):

```ini
[deepseek-v4-pro@2026-08-17]
peak_hours=9-12,14-18
tz=Asia/Shanghai
input_price=4.50
output_price=13.50
cache_write_price=4.50
cache_read_price=0.15
peak_input_price=9.00
peak_output_price=27.00
peak_cache_write_price=9.00
peak_cache_read_price=0.30
currency=CNY
```

Tables and CSV also show `Peak` / `Off-peak` cost-split columns (cost billed at peak vs off-peak rates; models without peak config always show 0 in Peak).
```

- [ ] **Step 3: README_zh.md 在「配置格式」ini 示例与说明列表之后、「## 工作原理」之前插入（与 Step 2 对应的中文版）**

```markdown
### 生效日期与峰谷分时计价

section 支持两个可选扩展（任意供应商可用；不配置则维持平价）：

- **section 名 `@YYYY-MM-DD` 后缀** — 定价自该日期 00:00（section 的 `tz` 时区）起生效。同一模型取“生效日期最大且不超过记录时间”的版本；记录早于所有带日期版本时回退无日期版本，再回退 `[default]`。
- **`peak_hours`** — 逗号分隔的高峰整点区间 `start-end`（半开区间 `[start:00, end:00)`），按 section 时区判定。
- **`tz`** — 高峰判定与生效日期所用 IANA 时区（缺省为系统本地时区）。
- **`peak_input_price` / `peak_output_price` / `peak_cache_write_price` / `peak_cache_read_price`** — 高峰时段价格。

示例（DeepSeek 峰谷定价，2026-08-17 生效；高峰 = 北京时间 9:00–12:00 与 14:00–18:00）：

```ini
[deepseek-v4-pro@2026-08-17]
peak_hours=9-12,14-18
tz=Asia/Shanghai
input_price=4.50
output_price=13.50
cache_write_price=4.50
cache_read_price=0.15
peak_input_price=9.00
peak_output_price=27.00
peak_cache_write_price=9.00
peak_cache_read_price=0.30
currency=CNY
```

表格与 CSV 同时展示 `Peak` / `Off-peak` 成本拆分列（按峰/谷费率计的成本；无峰谷配置的模型 Peak 恒为 0）。
```

- [ ] **Step 4: CHANGELOG.md 在 `# Changelog` 之后插入**

```markdown
## 2026-08-19

### Peak/off-peak pricing support (v1.1.0)
- `config.py` — Section names support `@YYYY-MM-DD` effective-date suffix; sections support `peak_hours`, `tz` and `peak_*` price keys; new `resolve_pricing()` resolves (entry, is_peak, used_default) per model and record time; removed `find_model_pricing()`
- `reader.py` — `TokenRecord` gains `peak_cost`/`offpeak_cost` fields
- `calculator.py` — Per-record pricing resolved by timestamp (effective date + peak/off-peak tier); cost split into peak/off-peak
- `aggregator.py` — `AggregatedRow` gains `peak_cost`/`offpeak_cost` accumulation
- `display.py`, `realtime.py` — Tables and CSV gain `Peak`/`Off-peak` (CSV: `PeakCost`/`OffpeakCost`) columns
- `monitor.ini` — DeepSeek v4-pro/v4-flash gain `@2026-08-17` sections with official peak/off-peak prices; old sections kept for pre-2026-08-17 data
- Version 1.0.0 → 1.1.0
```

- [ ] **Step 5: CHANGELOG_zh.md 在 `# Changelog` 之后插入**

```markdown
## 2026-08-19

### 峰谷分时计价支持（v1.1.0）
- `config.py` — section 名支持 `@YYYY-MM-DD` 生效日期后缀；section 支持 `peak_hours`、`tz` 与 `peak_*` 价格键；新增 `resolve_pricing()` 按模型与记录时间解析 (entry, is_peak, used_default)；移除 `find_model_pricing()`
- `reader.py` — `TokenRecord` 增加 `peak_cost`/`offpeak_cost` 字段
- `calculator.py` — 按记录时间（生效日期 + 峰谷层级）逐条计价，成本拆分为峰/谷
- `aggregator.py` — `AggregatedRow` 增加 `peak_cost`/`offpeak_cost` 累加
- `display.py`、`realtime.py` — 表格与 CSV 增加 `Peak`/`Off-peak`（CSV: `PeakCost`/`OffpeakCost`）列
- `monitor.ini` — DeepSeek v4-pro/v4-flash 增加 `@2026-08-17` 官方峰谷价格 section；旧 section 保留用于 2026-08-17 之前的数据
- 版本 1.0.0 → 1.1.0
```

- [ ] **Step 6: 验证**

```bash
cd /home/denvor/work/claude-monitor-3rdAPI
PYTHONPATH=src python3 -m claude_monitor --version
grep -c "peak" README.md README_zh.md
grep -c "peak_cost" CHANGELOG.md CHANGELOG_zh.md
```

预期：`claude-monitor 1.1.0`；四个文件 grep 计数均 ≥ 1。

- [ ] **Step 7: Commit**

```bash
cd /home/denvor/work/claude-monitor-3rdAPI
git add pyproject.toml src/claude_monitor/__init__.py README.md README_zh.md CHANGELOG.md CHANGELOG_zh.md
git commit -m "docs: 峰谷计价文档（双语 README/CHANGELOG），版本升至 1.1.0"
```

---

## Self-Review 记录

- **Spec 覆盖**：配置格式（Task 1 + Task 5）、解析规则 1-5（Task 1 的 resolve_pricing + 边界脚本）、token 语义映射（Task 1 calculator 的 cache_write/cache_read 用价）、6 文件改动（Task 1-4）、错误处理宽容策略（Task 1 的 _parse_* 警告回退）、展示语义（Task 3/4 + README）、配套更新（Task 5/6）、验证方式（每任务 heredoc + 冒烟）— 全覆盖
- **占位符**：无 TBD/TODO，所有代码步骤含完整代码
- **类型一致性**：`resolve_pricing -> (entry, is_peak, used_default)` 三值解包在 calculator/Task 5 脚本中一致；`load_pricing -> (dict, list)` 两值解包在 cli/realtime/脚本中一致；`AggregatedRow`/`TokenRecord` 新字段名 `peak_cost`/`offpeak_cost` 全计划统一
