# Renderer and catalog mode extraction status — 2026-05-21

## Current status

The reusable catalog listing renderer has been extracted from `handlers/restaurants_schema.py` into:

- `services/catalog_listing_renderer.py`

The catalog mode registry has been extracted from `handlers/generic_schema_flow.py` into:

- `services/catalog_modes.py`

## Completed extraction layers

- Restaurants renderer logic moved to shared renderer service.
- Generic schema flow now renders through shared renderer service.
- Premium admin no longer imports renderer wrappers from restaurants or generic handlers.
- Premium admin catalog payload building moved into shared renderer service.
- Generic catalog mode map ownership moved into `services/catalog_modes.py`.
- Premium admin topic lookup for generic catalog modes now uses `get_catalog_topic_id()`.
- Coupling audit guards were added:
  - `scripts/refactor_renderer_coupling_audit.sh`
  - `scripts/refactor_catalog_modes_coupling_audit.sh`

## Current accepted coupling

`handlers/restaurants_schema.py` remains the real Restaurants section handler.

It still owns:

- Restaurants callback namespace
- Restaurants FSM state names
- Restaurants premium media flow
- Restaurants free publish flow
- Restaurants section topic publishing

This is intentional. The current refactor did not rename callbacks, DB modes, FSM state keys, or section slugs.

## Neutral reusable layer

The neutral reusable layer is now:

- `render_catalog_listing_html(payload)`
- `build_catalog_listing_payload_from_premium_post(post)`
- `normalize_catalog_geo_tags_from_db(value)`
- `MODE_TO_SECTION_NAME`
- `get_catalog_mode_slugs()`
- `get_catalog_section_name(mode)`
- `get_catalog_topic_id(mode)`

## Guard status

Renderer coupling guard currently blocks these regressions:

- importing `_render_html` from `handlers.restaurants_schema`
- importing `_render_html` from `handlers.generic_schema_flow`
- importing `SLUG_TO_SECTION` from `handlers.generic_schema_flow`
- aliasing handler renderer wrappers in shared/admin layers

Catalog mode coupling guard currently blocks:

- reintroducing `SLUG_TO_SECTION` ownership inside `handlers/generic_schema_flow.py`
- importing `SLUG_TO_SECTION` from generic handler elsewhere

## Safety status

Last completed layer:

- HEAD before this doc: `16ba01b`
- compile sanity: green
- service: active
- renderer coupling audit: green
- catalog mode coupling audit: green

## Next safe layers

1. Move remaining generic catalog payload/topic helpers out of `premium_admin.py` where practical.
2. Add a dedicated smoke/audit script for shared catalog renderer parity.
3. Start low-risk legacy naming cleanup in docstrings/log messages only.
4. Keep service/path/deploy naming unchanged until a separate deployment naming plan exists.

## Explicit non-goals

- no DB mode rename
- no callback namespace rename
- no FSM state key rename
- no service unit rename
- no deployment path rename
- no historical diagnostics rewrite
- no backup rewrite
