## Why

Cache hit rate is the most直观指标 for cost efficiency — the higher the cache hit rate, the more tokens are served from cache rather than billed at full input price. Users currently have to mentally compute this ratio from the Cache Read / Cache Write / Input columns. Adding a dedicated column makes cost efficiency immediately visible.

## What Changes

- Add a `cache_hit_rate` property to `AggregatedRow` that computes `cache_read / (cache_read + cache_create + input) * 100%`
- Add a "Cache Hit Rate" column between "Requests" and "Cost" in `display_table()` and `display_csv()`
- Add the same column in `realtime.py:_build_table()` for the live TUI
- Handle edge cases: division by zero (no tokens → "—" or "0%")

## Capabilities

### New Capabilities
- `cache-hit-rate`: Cache hit rate computation and display in all output modes

### Modified Capabilities
<!-- No existing specs to modify -->

## Impact

- `src/claude_monitor/aggregator.py` — Add `cache_hit_rate` property to `AggregatedRow`
- `src/claude_monitor/display.py` — Add column to `display_table()` and `display_csv()`
- `src/claude_monitor/realtime.py` — Add column to `_build_table()`
