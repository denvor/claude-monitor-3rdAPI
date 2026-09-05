# Changelog

## 2026-09-05

### 修复：模型匹配时更具体的 section 优先
- `config.py` — `resolve_pricing()` 在做生效日期版本选择前，先按 `base_name` 最长匹配过滤（如 `qwen3.8-flash` 命中 `[Qwen3.8-flash]` 而非 `[Qwen3.8]`；此前平局由文件顺序决定）
- `monitor.ini` — 新增 `Qwen3.8-flash` 定价预设（0.8 / 2.7 / 1.25 / 0.1 CNY）

## 2026-08-19

### 峰谷分时计价支持（v1.1.0）
- `config.py` — section 名支持 `@YYYY-MM-DD` 生效日期后缀；section 支持 `peak_hours`、`tz` 与 `peak_*` 价格键；新增 `resolve_pricing()` 按模型与记录时间解析 (entry, is_peak, used_default)；移除 `find_model_pricing()`
- `config.py` — 配置搜索改为遵循文档化优先级（取第一个存在的文件；原先 `./monitor.ini` 与 `~/.claude/monitor.ini` 会被合并加载）
- `reader.py` — `TokenRecord` 增加 `peak_cost`/`offpeak_cost` 字段
- `calculator.py` — 按记录时间（生效日期 + 峰谷层级）逐条计价，成本拆分为峰/谷
- `aggregator.py` — `AggregatedRow` 增加 `peak_cost`/`offpeak_cost` 累加
- `display.py`、`realtime.py` — 表格与 CSV 增加 `Peak`/`Off-peak`（CSV: `PeakCost`/`OffpeakCost`）列
- `monitor.ini` — DeepSeek v4-pro/v4-flash 增加 `@2026-08-17` 官方峰谷价格 section；旧 section 保留用于 2026-08-17 之前的数据
- `monitor.ini` — 新增 `Qwen3.8`（零价）与 `LongCat-2.0` 定价预设
- 版本 1.0.0 → 1.1.0

## 2026-06-23

### 默认参数变更
- `cli.py` — 无参数时默认只看今天（`--today`），realtime/summary 视图默认 `today_only=True`
- `cli.py` — 显式传 `--days-back` 后恢复按天回溯
- `reader.py` — `read_records()` 默认 `today_only=True`
- `realtime.py` — `run_realtime()` 默认 `today_only=True`

## 2026-06-16

### 代码审查修复
- `calculator.py` — 未知模型检测改用 `is` 标识比较，消除重复的 O(n*m) 子串扫描
- `display.py` — 新增 `_table_currency()` 和 `PERIOD_HEADERS` 常量，消除多币种表头和 period 标签的重复代码
- `cli.py` — 移除无效的 `--theme`/`--timezone`/`--clear` 参数
- `cli.py` — 新增 `--days-back` CLI 参数，支持自定义查询时间范围
- `cli.py` — 新增 `DEFAULT_DAYS_BACK` 模块常量，统一各视图的默认回溯天数
- `cli.py`, `reader.py` — 新增 `--today` 参数，仅显示当天（本地零点至今）的数据
- `realtime.py` — `run_realtime()` 接受 `days_back` 参数替代硬编码 `1`
- `realtime.py` — 移除未使用的 `CURRENCY_SYMBOLS` 本地副本
- `realtime.py` — 移除 `_build_table()`/`_empty_table()` 的死参数 `refresh_rate`
- `realtime.py` — 导入 `display._table_currency()` 消除重复

## 2026-06-05

### 初始版本
- 项目初始化，基于 `Claude-Code-Usage-Monitor` 参考应用重写，专为第三方 API（如 DeepSeek）设计
- 9 个源文件：`config.py`, `reader.py`, `calculator.py`, `aggregator.py`, `display.py`, `realtime.py`, `cli.py`, `__init__.py`, `__main__.py`
- 功能：实时监视、摘要/日/月视图、自定义 `monitor.ini` 定价、CSV 导出
- 依赖：仅 `rich`
- `monitor.ini` — DeepSeek V4 Pro/Flash 定价预设（CNY）
- `PLAN.md`, `README.md`, `README_zh.md` 文档

### 仓库清理
- `PLAN.md` 加入 `.gitignore` 并从版本控制中移除
- `CLAUDE.md`, `CLAUDE_en.md`, `.gitignore` 从仓库中移除（保留本地）
- README 中的 `git clone` URL 更新为 `https://github.com/denvor/claude-monitor-3rdAPI.git`
