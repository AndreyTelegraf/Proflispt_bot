# Catalog topology cleanup — 2026-05-28

## Final state

Catalog topology is clean after the cleanup/refactor pass.

Validated on staging at commit `32ed228`.

Checks passed:

- `CATALOG_TOPOLOGY_OK`
- `py_compile`
- `services.schema_smoke`
- staging service active

## Current architecture

`restaurants` is no longer a special-case runtime handler or reusable template artifact.

It remains only as a normal active catalog mode/section:

- `services/catalog_modes.py`
- `config/fsm_schemas/restaurants.json`
- `config/section_groups.json`
- `sections_registry.json`
- `database.py` premium TTL map
- `services/schema_smoke.py`

This is correct.

## Removed legacy contamination

Removed/neutralized during this pass:

- unused tracked `app/` shadow tree
- stale `restaurants_schema.py` runtime assumptions
- misleading generic flow docstring
- manual duplicate section callback mapping
- inactive premium TTL aliases
- inactive `Фермеры` registry/manual-only references
- Python runtime artifacts and backup noise from live audits

## Verified absent

Final live grep confirmed no active refs to:

- `restaurants_schema`
- `section:restaurants`
- `confirm:restaurants_post`
- `Фермеры`
- `farmers`
- `except restaurants/jobs`
- `app/config`
- `app/services`

## Source-of-truth direction

Catalog runtime is now driven by:

- `services/catalog_modes.py` for generic section modes
- `config/section_groups.json` for catalogue grouping
- `sections_registry.json` for Telegram topic ids
- `config/fsm_schemas/*.json` for schema-driven flows

Known special routes:

- housing sections use `section:housing:*`
- reviews use `section:reviews`
- `Поговори` remains manual-only / external button

## Important conclusion

Do not rename `restaurants` to `template`.

`restaurants` is no longer a template artifact. It is now a legitimate business section slug. Any future neutral-template work should use generic schema flow terminology, not overwrite the active Restaurants section identity.
