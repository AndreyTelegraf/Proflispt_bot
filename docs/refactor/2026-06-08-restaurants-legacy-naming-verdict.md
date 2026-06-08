# Restaurants legacy naming verdict

Date: 2026-06-08
HEAD before layer: 80a7ebe

## Audit scope

Checked whether `restaurants` remains in live runtime as a generic architectural/template artifact.

Searched for:

- restaurants
- restaurants_schema
- restaurants_payload
- restaurants_renderer
- restaurants_flow
- restaurants_

## Result

No runtime patch is required.

Live runtime references are clean from old architecture-specific restaurants naming.

## Confirmed live references

Only valid domain references remain:

- `config/fsm_schemas/restaurants.json`
  - schema file for the real section `Рестораны`
  - `schema_id = restaurants_v1`
- `services/catalog_modes.py`
  - mode slug `restaurants -> Рестораны`
- `database.py`
  - TTL rule for real mode `restaurants`

## Removed/obsolete architecture

The old dedicated `restaurants_schema` handler and related state names are not part of live runtime.

Remaining references to:

- `restaurants_schema`
- `restaurants_payload`
- `restaurants_premium_media`
- `restaurants_schema_step_index`
- `confirm:restaurants_post`

exist only in historical artifacts under:

- `data/backups_*`
- `data/diagnostics_*`

These are not active runtime code.

## Decision

Do not rename the live `restaurants` mode.

`restaurants` is now a valid domain slug for the Restaurants section, not a template name.

Do not treat `restaurants` as an architectural artifact unless it appears outside the accepted domain locations.

## Accepted state

Accepted live locations:

- `config/fsm_schemas/restaurants.json`
- `services/catalog_modes.py`
- `database.py` TTL configuration
- section registry / section group entries using the visible name `Рестораны`

Rejected future usage:

- dedicated `handlers/restaurants_schema.py`
- state keys prefixed with `restaurants_schema_*`
- callback flows named as if restaurants were the base template for all catalog sections
- generic helper names using `restaurants` as a synonym for schema/template
