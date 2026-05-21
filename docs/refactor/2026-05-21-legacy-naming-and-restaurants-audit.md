# Legacy naming and restaurants artifact audit — 2026-05-21

## Current status

Latest completed audit layers:

- legacy naming audit tool
- restaurants artifact audit tool

Both layers are audit-only. No runtime rename was performed.

## Legacy naming audit result

Audit command:

- `scripts/refactor_legacy_naming_audit.sh`

Latest observed counts:

- all matches: 81
- runtime-critical / high-risk: 46
- user-facing or docs: 33
- historical / diagnostics: 8
- review-required: 81

Verdict:

- direct rename is blocked
- runtime-critical matches must be reviewed one by one
- historical diagnostics/backups should not be rewritten
- docs/user-facing strings may be renamed first after review

Important categories found:

- module docstrings
- deployment scripts
- service files
- old documentation
- historical deployment references
- runtime log message in `main.py`
- active/frozen deployment references in `docs/refactor`

Do not blindly rename `workinportugal`, `Work in Portugal`, `workinportugal_bot`, or `workinportugal-bot`.

## Restaurants artifact audit result

Audit command:

- `scripts/refactor_restaurants_artifact_audit.sh`

Latest observed counts:

- all matches: 260
- runtime-critical: 252
- real restaurants section: 216
- template artifact candidates: 213
- historical / diagnostics: 4

Verdict:

- direct rename is blocked
- real section references are tightly mixed with reusable schema-flow logic
- historical diagnostics/backups should not be rewritten
- first refactor target should be extracting reusable helpers, not renaming callback namespaces

## Practical implication

`restaurants` currently means several different things at once:

- real user-facing section
- DB mode / publication mode
- callback namespace
- FSM state namespace
- handler filename
- renderer source for premium admin
- original canonical template used to bootstrap generic sections

Therefore `restaurants -> template` or `restaurants -> catalog_schema_flow` cannot be one rename.

## Safe next order

1. Keep existing `restaurants` callback and DB mode unchanged.
2. Extract reusable renderer/helper functions from `handlers/restaurants_schema.py`.
3. Make premium admin depend on neutral renderer/helper module instead of importing `_render_html` from restaurants handler.
4. Keep `handlers/restaurants_schema.py` as a thin adapter for the real Restaurants section.
5. Only after that consider neutral naming for reusable layer, likely `catalog_schema_flow` or `catalog_listing_renderer`.

## Explicit non-goals for next layer

- no DB migration
- no callback rename
- no service/path rename
- no historical diagnostics rewrite
- no backup rewrite
- no blind search-and-replace
