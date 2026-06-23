# Changelog

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
