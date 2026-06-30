## ADDED Requirements

### Requirement: System computes cache hit rate
The system SHALL compute cache hit rate as `cache_read_tokens / (cache_read_tokens + cache_create_tokens + input_tokens) * 100` for each aggregated row.

#### Scenario: Normal cache hit rate
- **WHEN** a row has cache_read=1_000_000, cache_create=200_000, input=800_000
- **THEN** the cache hit rate SHALL be 50.0%

#### Scenario: Zero total tokens
- **WHEN** a row has no tokens (all counts are 0)
- **THEN** the cache hit rate SHALL be 0.0 (zero-division safe)

#### Scenario: No cache activity
- **WHEN** a row has input=1000, output=500, cache_read=0, cache_create=0
- **THEN** the cache hit rate SHALL be 0.0%

### Requirement: Table displays cache hit rate column
All three display modes (realtime TUI, static table, CSV) SHALL show a "Cache Hit Rate" column positioned between the Requests and Cost columns.

#### Scenario: Realtime TUI shows column
- **WHEN** the realtime table is rendered via `realtime.py:_build_table()`
- **THEN** a "Cache Hit Rate" column SHALL appear between "Requests" and "Cost (CNY)"

#### Scenario: Static table shows column
- **WHEN** `display.py:display_table()` renders a table
- **THEN** a "Cache Hit Rate" column SHALL appear between "Requests" and "Cost (CNY)"

#### Scenario: CSV output includes column
- **WHEN** `display.py:display_csv()` writes CSV output
- **THEN** a `CacheHitRate` column SHALL appear between `Requests` and `Cost(CNY)`

### Requirement: Cache hit rate display format
The cache hit rate SHALL be displayed as a percentage string with one decimal place (e.g., "50.0%"). When the rate is 0.0 (zero total tokens), the display SHALL show "—" (em dash).

#### Scenario: Format with data
- **WHEN** cache hit rate is 50.0
- **THEN** the display string SHALL be "50.0%"

#### Scenario: Zero total
- **WHEN** total input tokens are 0 (no data)
- **THEN** the display string SHALL be "—"

### Requirement: Total row shows weighted average
The total/summary row SHALL show the cache hit rate computed from total aggregates (sum of all tokens), not an average of per-model rates.

#### Scenario: Total row computation
- **WHEN** totals are summed across all rows
- **THEN** the total row's cache hit rate SHALL be computed from the summed token counts
