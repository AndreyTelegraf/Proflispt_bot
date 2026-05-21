# Refactor sandbox status — 2026-05-21

## Runtime model

The active live bot is still `@proflistpt_bot` running from `/opt/bots/workinportugal_bot_staging`.

The refactor sandbox is `/opt/bots/proflistpt_bot_refactor`, running as `proflistpt_bot_refactor.service` with test bot `@tester_pt_bot`.

The old `/opt/bots/workinportugal_bot` / `@workinportugal_bot` deployment is frozen and must not be touched during this refactor.

## Stable sandbox commits

- `16b129e` — Extract generic listing publish validation
- `db5ed12` — Apply shared publish validation to housing flow
- `39dcd1c` — Apply shared publish validation to restaurants flow
- `9b5927c` — Harden premium publish boundaries
- `f432f0e` — Backfill telegram before shared publish validation
- `0e72ac6` — Backfill telegram before generic free publish validation
- `8a53a1d` — Persist housing telegram backfill in state
- `c9d3756` — Ignore runtime artifacts in refactor sandbox

## Refactor decisions

Shared publish-boundary validation is now extracted to `services/listing_validation.py`.

Telegram backfill remains local in handlers for now. The attempted extraction into a shared helper was rolled back because repeated count-mismatch failures made the layer unsafe.

Runtime/local artifacts are ignored through `.gitignore`, including `.env.*`, `data/`, DB files, backup files, tarballs, logs, and pycache files.

## Current safety rules

- Do not patch without exact target dump.
- One patch = one isolated layer.
- If the same error repeats twice, stop and rollback/audit.
- Do not clean inside `venv/`.
- Do not touch live DB files during refactor unless the task explicitly requires it.
- Keep `@tester_pt_bot` manual smoke separate from live `@proflistpt_bot`.

## Known operational notes

`bot_database.db` in sandbox is the runtime DB copy. Zero-byte DB files under `data/` are ignored artifacts and should not be used as runtime truth.

`.env.copied_from_live_*` is ignored and must not be committed.
