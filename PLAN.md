# Claude Monitor 实现计划

## 概述

基于 `Claude-Code-Usage-Monitor` 参考应用重写的精简版 claude-monitor。
核心区别：使用 `monitor.ini` 自定义 token 价格，而非硬编码价格表。

## 项目结构

```
D:\work\claude-monitor\
├── monitor.ini              # 自定义价格配置
├── plan.md                  # 本文件
├── README.md                # 使用说明
├── pyproject.toml           # 包元数据 + CLI 入口点
├── requirements.txt         # 依赖声明
├── CLAUDE.md                # 项目行为指南
├── .venv/                   # Python 虚拟环境
└── src/
    └── claude_monitor/
        ├── __init__.py      # 包版本
        ├── __main__.py      # python -m claude_monitor 入口
        ├── cli.py           # argparse + 编排调度
        ├── config.py        # 读取 monitor.ini，模型→定价匹配
        ├── reader.py        # 扫描 JSONL，提取 token 记录
        ├── calculator.py    # 根据 pricing 计算费用
        ├── aggregator.py    # 按 摘要/日/月 聚合，每模型独立成行
        ├── display.py       # Rich 表格 / CSV 输出
        └── realtime.py      # Rich Live 实时轮询刷新
```

共 9 个源文件。

## monitor.ini 格式

```ini
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

[deepseek-v4-flash]
input_price=1.00
output_price=2.00
cache_write_price=1.00
cache_read_price=0.02
currency=CNY
```

**匹配规则**：model 名称对 section 名做大小写不敏感子串匹配，未匹配则回退到 `[default]`。价格为每百万 token。

**搜索路径**：`--config 参数` > `./monitor.ini` > `~/.claude/monitor.ini`。都找不到则使用内置 CNY 默认定价。

## CLI 接口

```
claude-monitor [选项]

--view          realtime / summary / daily / monthly [默认: realtime]
--data-path     Claude 数据目录 [默认: ~/.claude/projects]
--config        monitor.ini 路径
--refresh-rate  数据刷新间隔秒数 [默认: 10，仅 realtime]
--theme         light / dark / classic / auto [默认: auto]
--timezone      时区 [默认: auto]
--csv           输出 CSV 而非表格
--version, -v   显示版本号
--clear         清除保存的配置
```

示例：
```
claude-monitor                              # 实时模式
claude-monitor --view summary               # 今日摘要
claude-monitor --view daily                 # 按日统计（全部数据）
claude-monitor --view monthly --csv         # 按月统计 + CSV 输出
claude-monitor --refresh-rate 5             # 5秒刷新
claude-monitor --config ./my-prices.ini     # 自定义定价文件
```

## 数据流

```
monitor.ini                    ~/.claude/projects/**/*.jsonl
     |                                    |
     v                                    v
 config.py ───pricing字典───▶ calculator.py ◀── TokenRecord列表 ── reader.py
                                    |                              |
                              计算每条费用                    1. rglob *.jsonl
                                    |                        2. 逐行读取JSON
                                    |                        3. 仅保留 type=assistant
                                    |                        4. 提取 model, usage, timestamp
                                    |                        5. 跳过 <synthetic>
                                    |
                                    v
                            aggregator.py ◀── 含价格的记录列表
                                    |
                                    |  按 (period, model) 分组
                                    v
                    ┌───────────────┴───────────────┐
                    v                               v
              display.py                      realtime.py
              Rich Table / CSV                Rich Live 轮询刷新
```

核心数据类：
```python
@dataclass
class TokenRecord:
    timestamp: datetime   # 本地时间
    model: str
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    cost: float           # calculator.py 填充
    currency: str         # config.py 匹配后填充

@dataclass
class AggregatedRow:
    period: str           # "Total" / "2026-06-04" / "2026-06"
    model: str
    input_tokens: int
    output_tokens: int
    cache_create_tokens: int
    cache_read_tokens: int
    total_cost: float
    request_count: int
    currency: str
```

## JSONL 数据格式

```json
{
  "type": "assistant",
  "timestamp": "2026-06-04T08:59:39.965Z",
  "uuid": "4d5dbffc-a87a-402c-b758-fc6b70555d72",
  "message": {
    "model": "deepseek-v4-pro",
    "usage": {
      "input_tokens": 36271,
      "output_tokens": 82,
      "cache_creation_input_tokens": 0,
      "cache_read_input_tokens": 0
    }
  }
}
```

- 仅处理 `type == "assistant"` 且含 `message.usage` 的条目
- 跳过 `model == "<synthetic>"` 和零 token 条目
- 通过 `uuid` 去重，`timestamp` 由 UTC 转本地时区

## 各模块职责

### config.py
- `configparser` 解析 `monitor.ini`
- `load_pricing(config_path)` → `(pricing_dict, default_pricing)`
- `find_model_pricing(model_name, pricing, default)` → 子串匹配，回退 default
- 搜索路径：`-c 参数` > `./monitor.ini` > `~/.claude/monitor.ini`

### reader.py
- `find_jsonl_files(data_path)` → `list[Path]` 递归查找 `*.jsonl`
- `read_records(data_path, days_back)` → `list[TokenRecord]`
- 时间戳从 UTC 转为本地时区，cutoff 用本地时间计算

### calculator.py
- `calculate_costs(records, pricing_dict, default_pricing)` → 就地设置 cost/currency
- 公式：`(tokens / 1_000_000) * price_per_million`
- 未匹配定价的模型记录 warning 日志

### aggregator.py
- `aggregate(records, mode)` → `list[AggregatedRow]`
- 按 `(period, model)` 分组，每个模型独立一行
- summary: period="Total", daily: 日期, monthly: YYYY-MM

### display.py
- `display_table(rows, mode)` → Rich Table，含 Period | Model | Input | Output | Cache Write | Cache Read | Requests | Cost
- `display_csv(rows, mode)` → CSV 输出
- `format_number(n)` 千位分隔，`format_cost(c)` 2-4 位小数
- Console 使用 `force_terminal=True, legacy_windows=False` 避免 GBK 编码问题

### realtime.py
- `run_realtime(data_path, config_path, refresh_rate)` → Rich Live 轮询循环
- `screen=True` 使用交替屏幕，0.5s 粒度检查刷新
- Header: `Claude Monitor — YYYY-MM-DD HH:MM:SS  refresh:Xs  next:Xs`
- 表格：每模型一行 + Total 汇总行
- Ctrl+C 退出

### cli.py
- argparse，参数名与参考应用一致
- `main()` 编排：realtime 走 `run_realtime()`，静态模式走 `load → calculate → aggregate → display`
- summary 模式默认 days_back=1，daily/monthly 默认 days_back=0

## 实时界面布局

```
Claude Monitor — 2026-06-04 17:30:00  refresh:10s  next:3s

Model               Input       Output    Cache Write   Cache Read  Requests    Cost (CNY)
─────────────────────────────────────────────────────────────────────────────────────────
deepseek-v4-pro  2,482,967      985,500             0  147,772,032        142       17.06
deepseek-v4-flash  685,879        6,514             0    2,772,352         25        0.76
─────────────────────────────────────────────────────────────────────────────────────────
Total            3,168,846      992,014             0  150,544,384        167       17.82
```

## 与参考应用的区别

| 特性 | Claude-Code-Usage-Monitor | claude-monitor |
|------|--------------------------|----------------|
| 定价方式 | 硬编码价格表 | monitor.ini 自定义 |
| 依赖 | pytz, pydantic, numpy, sentry, pyyaml | 仅 rich |
| Plan/限额 | Pro/Max5/Max20/Custom + P90 ML | 无，纯用量统计 |
| 实时模式 | 进度条 + 燃尽率 + 预测 | 简单表格刷新 |
| 代码量 | 50+ 文件 | 9 个源文件 |
| 时区处理 | pytz | stdlib datetime.astimezone() |
