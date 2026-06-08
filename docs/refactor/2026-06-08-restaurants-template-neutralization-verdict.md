# Restaurants/template neutralization verdict

Date: 2026-06-08
HEAD before layer: d3b7b44

## Audit scope

Checked live references for:

- restaurants
- restaurants_v1
- Рестораны

Targets inspected:

- config/fsm_schemas/restaurants.json
- services/catalog_modes.py
- database.py
- sections_registry.json
- config/section_groups.json
- handlers/
- services/

## Result

No runtime neutralization patch is required.

The remaining live `restaurants` references are not template artifacts. They are valid identifiers for the real catalog section `Рестораны`.

Confirmed live references:

- `config/fsm_schemas/restaurants.json`
  - `schema_id = restaurants_v1`
  - `section_name = Рестораны`
- `services/catalog_modes.py`
  - `restaurants -> Рестораны`
- `database.py`
  - TTL rule for mode `restaurants`
- `sections_registry.json`
  - topic mapping for section `Рестораны`
- `config/section_groups.json`
  - visible section placement for `Рестораны`

## Decision

Do not rename the runtime mode slug `restaurants`.

Reason: existing rows in `premium_posts.mode`, TTL logic, section routing, topic mapping, and user-facing catalog behavior depend on this slug representing the real Restaurants section.

Renaming it to `template` would be semantically wrong and would introduce migration risk without architectural benefit.

## What was already neutralized earlier

The old dedicated `handlers/restaurants_schema.py` flow is no longer part of the live routing layer. Restaurants now behaves as a normal schema-driven catalog section.

## Accepted state

`restaurants` may remain as:

- real category slug
- schema file name
- schema_id prefix
- mode key in `premium_posts`
- section mapping to `Рестораны`

It must not be used as a generic template name for unrelated sections.
