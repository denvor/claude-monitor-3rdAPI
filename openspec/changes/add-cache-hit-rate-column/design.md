## Context

The current display shows per-model Cache Read, Cache Write, Input, Output token counts and a computed cost. Users must manually compute cache hit rate (cache_read / total_input) to gauge cost efficiency. Adding a computed column makes this insight instant.

The change is purely cosmetic in the display layer — the data needed (cache_read, cache_create, input_tokens) already exists in `AggregatedRow`. No new data sources or aggregation changes are required.

## Goals / Non-Goals

**Goals:**
- Add `cache_hit_rate` as a computed property on `AggregatedRow`
- Display as a new column between Requests and Cost in all output modes (realtime TUI, static table, CSV)
- Handle division by zero (no tokens) gracefully

**Non-Goals:**
- No changes to data collection, pricing, or aggregation logic
- No changes to the `TokenRecord` dataclass in `reader.py`
- No new command-line arguments

## Decisions

1. **Property on AggregatedRow vs. in display layer**: Putting the computation on `AggregatedRow` as a `@property` keeps it testable and avoids duplicating the formula across display.py and realtime.py.

2. **Formula**: `cache_read_tokens / (cache_read_tokens + cache_create_tokens + input_tokens) * 100`. This represents the percentage of "input-side tokens" served from cache, which is the standard metric for prompt caching efficiency. Zero tokens → returns 0.0 to avoid division by zero.

3. **Format**: Display as percentage with one decimal place (e.g., `85.3%`). For zero total → show `—`. This is consistent with how cost uses adaptive precision.

## Risks / Trade-offs

- [Low] Division by zero: when a model has zero input + cache tokens, hit rate is undefined. Mitigation: return 0.0 and display as `—`.
