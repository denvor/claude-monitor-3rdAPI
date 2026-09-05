# Changelog

## 2026-09-05

### Fix: most-specific section wins in model matching
- `config.py` — `resolve_pricing()` now prefers the longest matching `base_name` before applying effective-date selection (e.g. `[Qwen3.8-flash]` beats `[Qwen3.8]` for model `qwen3.8-flash`; previously file order decided the tie)
- `monitor.ini` — Added `Qwen3.8-flash` pricing preset (0.8 / 2.7 / 1.25 / 0.1 CNY)

## 2026-08-19

### Peak/off-peak pricing support (v1.1.0)
- `config.py` — Section names support `@YYYY-MM-DD` effective-date suffix; sections support `peak_hours`, `tz` and `peak_*` price keys; new `resolve_pricing()` resolves (entry, is_peak, used_default) per model and record time; removed `find_model_pricing()`
- `config.py` — Config search now honors the documented priority (first existing file wins; previously `./monitor.ini` and `~/.claude/monitor.ini` were merged)
- `reader.py` — `TokenRecord` gains `peak_cost`/`offpeak_cost` fields
- `calculator.py` — Per-record pricing resolved by timestamp (effective date + peak/off-peak tier); cost split into peak/off-peak
- `aggregator.py` — `AggregatedRow` gains `peak_cost`/`offpeak_cost` accumulation
- `display.py`, `realtime.py` — Tables and CSV gain `Peak`/`Off-peak` (CSV: `PeakCost`/`OffpeakCost`) columns
- `monitor.ini` — DeepSeek v4-pro/v4-flash gain `@2026-08-17` sections with official peak/off-peak prices; old sections kept for pre-2026-08-17 data
- `monitor.ini` — Added `Qwen3.8` (zero-cost) and `LongCat-2.0` pricing presets
- Version 1.0.0 → 1.1.0

## 2026-06-23

### Default parameter change
- `cli.py` — Default to today-only view (`--today`); realtime/summary now default to `today_only=True`
- `cli.py` — Passing `--days-back` explicitly reverts to day-based lookback
- `reader.py` — `read_records()` defaults to `today_only=True`
- `realtime.py` — `run_realtime()` defaults to `today_only=True`

## 2026-06-16

### Code review fixes
- `calculator.py` — Unknown model detection uses identity (`is`) comparison, removing redundant O(n*m) substring scans
- `display.py` — Added `_table_currency()` helper and `PERIOD_HEADERS` constant, eliminating duplicate multi-currency header and period label code
- `cli.py` — Removed dead `--theme`/`--timezone`/`--clear` arguments
- `cli.py` — Added `--days-back` CLI argument for custom lookback range
- `cli.py` — Added `DEFAULT_DAYS_BACK` module constant unifying default lookback across views
- `cli.py`, `reader.py` — Added `--today` flag to show only current day's data (from local midnight)
- `realtime.py` — `run_realtime()` accepts `days_back` parameter instead of hardcoded `1`
- `realtime.py` — Removed unused local `CURRENCY_SYMBOLS` copy
- `realtime.py` — Removed dead `refresh_rate` parameter from `_build_table()`/`_empty_table()`
- `realtime.py` — Imports `display._table_currency()` to eliminate duplication

## 2026-06-05

### Initial release
- Project initialization, rewritten from `Claude-Code-Usage-Monitor` reference app, tailored for third-party APIs (e.g. DeepSeek)
- 9 source files: `config.py`, `reader.py`, `calculator.py`, `aggregator.py`, `display.py`, `realtime.py`, `cli.py`, `__init__.py`, `__main__.py`
- Features: real-time monitoring, summary/daily/monthly views, custom `monitor.ini` pricing, CSV export
- Dependencies: `rich` only
- `monitor.ini` — DeepSeek V4 Pro/Flash pricing presets (CNY)
- `PLAN.md`, `README.md`, `README_zh.md` documentation

### Repository cleanup
- `PLAN.md` added to `.gitignore` and removed from version control
- `CLAUDE.md`, `CLAUDE_en.md`, `.gitignore` removed from repo (kept locally)
- README `git clone` URL updated to `https://github.com/denvor/claude-monitor-3rdAPI.git`
