# review_links cleanup deferred — 2026-05-28

## Status

`review_links` is no longer present in active FSM schemas.

Confirmed:

- `schema_review_links_hits = NONE`
- staging service remains active
- `services.schema_smoke` passes
- no partial patch was applied to `handlers/generic_schema_flow.py`

## Current runtime remnants

`review_links` still exists in runtime compatibility code:

- `handlers/generic_schema_flow.py`
- `database.py`
- `handlers/my_postings.py`
- `services/catalog_listing_renderer.py`
- `handlers/reviews_schema_flow.py`

## Why cleanup is deferred

Several attempts to remove `review_links` from `handlers/generic_schema_flow.py` failed because patch scripts were too brittle:

- multiline block replacement failed on escaping
- line-index patch failed on guard mismatch

Per engineering rule: after repeated failures in the same patch layer, stop patching and switch to audit/defer.

## Required next pass

Do not continue this cleanup by ad-hoc patching.

Next pass must start from:

1. exact fresh dump of full `handlers/generic_schema_flow.py`
2. AST/token-aware or function-aware rewrite, not raw brittle multiline strings
3. one isolated change: remove generic-flow `review_links` handling only
4. keep DB compatibility column untouched in the same layer
5. run:
   - `py_compile`
   - `services.schema_smoke`
   - restart staging
   - manual smoke of generic post flow

## Intended architecture

Reviews are attached through `review_index`, not manually collected through FSM field `review_links`.

`review_links` should remain only as a historical DB compatibility field until a separate DB/data migration layer is designed.
