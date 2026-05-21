# Refactor sandbox bootstrap runbook

## Paths

- Repo: /opt/bots/proflistpt_bot_refactor
- Service: proflistpt_bot_refactor.service
- Sandbox bot: @tester_pt_bot
- Live runtime reference: /opt/bots/workinportugal_bot_staging

## Safety model

The refactor sandbox isolates architectural cleanup from the live bot.

Do not edit these paths unless the task explicitly targets live deployment:

- /opt/bots/workinportugal_bot
- /opt/bots/workinportugal_bot_staging

## Mandatory workflow

1. Dump exact target block with nl -ba and sed.
2. Confirm traceback or exact runtime symptom.
3. Patch one isolated layer only.
4. Compile immediately.
5. Restart service.
6. Smoke in @tester_pt_bot.
7. Commit only after green smoke.

## Compile command

    venv/bin/python -m py_compile \
      main.py \
      database.py \
      handlers/generic_schema_flow.py \
      handlers/housing_schema_flow.py \
      handlers/restaurants_schema.py \
      services/listing_validation.py

## Service control

    sudo systemctl restart proflistpt_bot_refactor.service
    systemctl is-active proflistpt_bot_refactor.service
    journalctl -u proflistpt_bot_refactor.service -n 100 --no-pager

## Current shared layer

Shared validation module:

    services/listing_validation.py

Current responsibilities:

- normalize skip-values
- validate PT mobile numbers
- validate required publish payload
- shared publish-boundary validation

Telegram backfill remains duplicated intentionally for now because attempted extraction became unstable during automated patching.

## Git hygiene

Ignored:

- .env.*
- data/
- runtime DBs
- backups
- tarballs
- pycache
- logs

Never commit:

- copied live env files
- runtime DB snapshots
- diagnostics exports
- temporary patch scripts

## Operational warnings

Never recursively clean pycache inside venv.

## Current architectural direction

- shrink handler duplication
- extract pure shared services
- keep handler-specific FSM and UI logic local
- preserve exact runtime behaviour during refactor
- move toward stable schema-driven publish pipeline
