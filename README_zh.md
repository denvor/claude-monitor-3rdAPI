# Claude Monitor

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[English](README.md) | [中文](README_zh.md)

轻量级 Claude Code token 用量与费用监视器，专为第三方 API 设计。如果你用 Claude Code 搭配 DeepSeek 等第三方模型，这就是你需要的工具。

## 为什么写这个工具

使用 Claude Code 连接**第三方 API（如 DeepSeek）**时，官方没有提供 token 用量和费用查询的功能。现有工具只适配 Anthropic 官方模型，价格也是硬编码的。本项目借鉴了 [Claude-Code-Usage-Monitor](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor)，通过 `monitor.ini` 实现可自定义的定价模型，适配任意 API 供应商。

> **致谢**: 衷心感谢 [@Maciek-roboblog](https://github.com/Maciek-roboblog) 和贡献者们开发的 [Claude-Code-Usage-Monitor](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor)，本项目以此为参考实现。

### DeepSeek 用户

如果你正在使用 **Claude Code + DeepSeek**，本工具内置了 DeepSeek 定价预设，将 `monitor.ini` 复制到 `~/.claude/` 即可直接使用。

## 功能

- **实时监视** — 基于 Rich TUI 的实时刷新 token 用量表格
- **摘要 / 每日 / 每月视图** — 聚合统计，每个模型独立成行
- **自定义定价** — 在 `monitor.ini` 中自定义 token 价格，告别硬编码
- **CSV 导出** — 可管道的 CSV 输出，便于进一步分析
- **极简依赖** — 仅依赖 `rich`

## 安装

```bash
git clone https://github.com/denvor/claude-monitor-3rdAPI.git
cd claude-monitor

python -m venv .venv
source .venv/Scripts/activate   # Windows
# source .venv/bin/activate     # macOS / Linux

pip install .
```

全局安装（任意终端可用）：

```bash
pip install .
mkdir -p ~/.claude
cp monitor.ini ~/.claude/monitor.ini
```

## 使用

```bash
claude-monitor                          # 今天数据，实时模式（默认），Ctrl+C 退出
claude-monitor --view summary           # 今日摘要
claude-monitor --view daily             # 按日统计（全部天数）
claude-monitor --view monthly           # 按月统计（全部月份）
claude-monitor --days-back 7            # 最近 7 天，实时模式
claude-monitor --view daily --days-back 0  # 全部数据，日报视图
claude-monitor --view daily --csv       # CSV 输出
claude-monitor --refresh-rate 5         # 5 秒刷新
```

## CLI 参数

| 参数 | 可选值 | 默认值 | 说明 |
|------|--------|--------|------|
| `--view` | realtime, summary, daily, monthly | realtime | 显示模式 |
| `--data-path` | path | ~/.claude/projects | Claude 数据目录 |
| `--config` | path | 自动搜索 | monitor.ini 路径 |
| `--refresh-rate` | int | 10 | 数据刷新间隔（秒） |
| `--days-back` | int | — | 回溯 N 天（0=全部）；覆盖 today-only 默认 |
| `--today` | flag | 是（realtime/summary） | 仅显示当天（本地零点起）的数据 |
| `--csv` | flag | false | CSV 格式输出 |
| `--version`, `-v` | flag | false | 显示版本 |

## 自定义定价 — monitor.ini

自定义 token 定价。配置文件按以下顺序搜索：

| 优先级 | 路径 | 适用场景 |
|--------|------|----------|
| 1 | `--config` 参数 | 临时覆盖 |
| 2 | `./monitor.ini` | 项目级定价 |
| 3 | `~/.claude/monitor.ini` | 用户全局默认 |

未找到配置文件时使用内置回退定价（CNY，input=3.0，output=6.0）。

### 配置格式

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

- 价格单位：**每百万 token**
- 模型匹配：section 名（不含 `@日期` 后缀）与 model 做**大小写不敏感完全匹配**，模型字符串须与 section 名相等才命中
- 未匹配模型回退到 `[default]`
- 费用公式：`(tokens / 1,000,000) * price_per_million`

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

## 工作原理

Claude Code 将对话数据写入 `~/.claude/projects/` 下的 JSONL 文件。`claude-monitor` 扫描这些文件，从 `type=assistant` 条目中提取 token 用量，应用 `monitor.ini` 中的定价，然后展示结果。

## 与参考应用的区别

| 方面 | Claude-Code-Usage-Monitor | claude-monitor |
|------|--------------------------|----------------|
| 定价 | 硬编码价格表 | monitor.ini — 用户自定义 |
| 依赖 | pytz, pydantic, numpy, sentry, pyyaml | 仅 rich |
| Plan / 限额 | Pro/Max5/Max20/Custom + ML 预测 | 纯用量统计 |
| 代码规模 | 50+ 文件 | 9 个源文件 |
| 时区处理 | pytz | stdlib `datetime.astimezone()` |

## 环境要求

- Python >= 3.9
- [rich](https://github.com/Textualize/rich) >= 13.0.0

## 许可证

MIT
