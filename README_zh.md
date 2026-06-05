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
git clone <repo-url>
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
claude-monitor                          # 实时模式（默认），Ctrl+C 退出
claude-monitor --view summary           # 今日摘要
claude-monitor --view daily             # 按日统计
claude-monitor --view monthly           # 按月统计
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
| `--theme` | light, dark, classic, auto | auto | 显示主题 |
| `--timezone` | string | auto | 时区 |
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
- 模型匹配：section 名对 model 做**大小写不敏感子串匹配**
- 未匹配模型回退到 `[default]`
- 费用公式：`(tokens / 1,000,000) * price_per_million`

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
