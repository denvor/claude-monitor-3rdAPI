## 1. AggregatedRow — cache_hit_rate property

- [x] 1.1 Add `cache_hit_rate` property to `AggregatedRow` in `aggregator.py`

## 2. Display — add column to static table and CSV

- [x] 2.1 Add "Cache Hit Rate" column to `display_table()` in `display.py`, between Requests and Cost
- [x] 2.2 Add "CacheHitRate" column to `display_csv()` in `display.py`, between Requests and Cost
- [x] 2.3 Add cache hit rate to the total/summary row in `display_table()`

## 3. Realtime TUI — add column to live table

- [x] 3.1 Add "Cache Hit Rate" column to `_build_table()` in `realtime.py`, between Requests and Cost
- [x] 3.2 Add cache hit rate to the total row in `_build_table()`
