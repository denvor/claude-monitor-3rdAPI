# Claude Monitor

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[English](README.md) | [中文](README_zh.md)

A lightweight token usage and cost monitor for Claude Code with third-party API providers. Built for DeepSeek users who need visibility into their API consumption.

## Motivation

When using Claude Code with third-party APIs like **DeepSeek**, there's no built-in way to track token usage or calculate costs. Existing tools only work with Anthropic's official models and hardcoded pricing. This project adapts [Claude-Code-Usage-Monitor](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor) to fill that gap — providing a customizable pricing model via `monitor.ini` that works with any API provider.

> **Acknowledgments**: Huge thanks to [@Maciek-roboblog](https://github.com/Maciek-roboblog) and contributors for the original [Claude-Code-Usage-Monitor](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor), which served as the inspiration and reference for this project.

### DeepSeek Users

If you're using **Claude Code + DeepSeek**, this tool ships with built-in DeepSeek pricing presets. Just copy `monitor.ini` to `~/.claude/` and you're ready to go.

## Features

- **Real-time monitoring** — live-updating token usage table via Rich TUI
- **Summary / Daily / Monthly views** — aggregated statistics with per-model breakdown
- **Custom pricing** — define your own token prices in `monitor.ini` instead of hardcoded rates
- **CSV export** — pipeable CSV output for further analysis
- **Minimal dependencies** — only requires `rich`

## Installation

```bash
git clone https://github.com/denvor/claude-monitor-3rdAPI.git
cd claude-monitor

python -m venv .venv
source .venv/Scripts/activate   # Windows
# source .venv/bin/activate     # macOS / Linux

pip install .
```

For system-wide availability:

```bash
pip install .
mkdir -p ~/.claude
cp monitor.ini ~/.claude/monitor.ini
```

## Usage

```bash
claude-monitor                          # today's data, realtime mode (default), Ctrl+C to exit
claude-monitor --view summary           # today's summary
claude-monitor --view daily             # daily breakdown (all days)
claude-monitor --view monthly           # monthly breakdown (all months)
claude-monitor --days-back 7            # last 7 days, realtime
claude-monitor --view daily --days-back 0  # all available data, daily view
claude-monitor --view daily --csv       # CSV output
claude-monitor --refresh-rate 5         # 5-second refresh
```

## CLI Options

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--view` | realtime, summary, daily, monthly | realtime | Display mode |
| `--data-path` | path | ~/.claude/projects | Claude data directory |
| `--config` | path | auto-search | monitor.ini path |
| `--refresh-rate` | int | 10 | Data refresh interval (seconds) |
| `--days-back` | int | — | Look back N days (0=all time); overrides today-only default |
| `--today` | flag | true (realtime/summary) | Show only today's data (00:00 local time) |
| `--csv` | flag | false | Output as CSV |
| `--version`, `-v` | flag | false | Show version |

## Custom Pricing — monitor.ini

Define your own token pricing. The config file is searched in this order:

| Priority | Path | Use Case |
|----------|------|----------|
| 1 | `--config` argument | One-off overrides |
| 2 | `./monitor.ini` | Per-project pricing |
| 3 | `~/.claude/monitor.ini` | Global user default |

A built-in fallback (CNY, input=3.0, output=6.0) is used when no config file is found.

### Configuration Format

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

- Prices are **per 1 million tokens**
- Model matching: **case-insensitive substring match** against section names; when multiple sections match, the longest (most specific) name wins (e.g. `[Qwen3.8-flash]` beats `[Qwen3.8]`)
- Unmatched models fall back to `[default]`
- Cost formula: `(tokens / 1,000,000) * price_per_million`

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

## How It Works

Claude Code writes session data as JSONL files under `~/.claude/projects/`. `claude-monitor` scans these files, extracts token usage from `type=assistant` entries, applies pricing from `monitor.ini`, and displays the results.

## Differences from the Reference App

| Aspect | Claude-Code-Usage-Monitor | claude-monitor |
|--------|--------------------------|----------------|
| Pricing | Hardcoded price tables | monitor.ini — user-defined |
| Dependencies | pytz, pydantic, numpy, sentry, pyyaml | rich only |
| Plan / Limits | Pro/Max5/Max20/Custom + ML predictions | Usage statistics only |
| Codebase | 50+ files | 9 source files |
| Timezone | pytz | stdlib `datetime.astimezone()` |

## Requirements

- Python >= 3.9
- [rich](https://github.com/Textualize/rich) >= 13.0.0

## License

MIT
