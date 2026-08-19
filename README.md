# Proflistpt Bot

Telegram bot for the Proflistpt directory.

Current staging service:

- `proflistpt_bot.service`

Current staging path:

- `/opt/bots/proflistpt_bot`

## Current architecture

Managed publications are stored in `premium_posts`.

The legacy `job_postings` flow has been removed. Job-related sections now work as normal `premium_posts` modes:

- `job_seeker`
- `job_offer`

Ordinary catalog sections are handled by the generic schema-driven flow:

- `handlers/generic_schema_flow.py`
- `config/fsm_schemas/*.json`

Special flows:

- housing: `handlers/housing_schema_flow.py`
- reviews: `handlers/reviews_schema_flow.py`
- Talk to Me: schema-driven questionnaire with free moderation in `handlers/generic_schema_flow.py`
- user post management: `handlers/my_postings.py`
- premium moderation: `handlers/premium_admin.py`

Canonical mode and section identity helpers:

- `services/catalog_modes.py`
- `services/post_identity.py`

## Health checks

Run from the project root:

- `./venv/bin/python -m py_compile database.py main.py handlers/*.py services/*.py`
- `./venv/bin/python -m services.schema_smoke`
- `./healthcheck_local.sh`
- `systemctl is-active proflistpt_bot.service`

## Restart staging

- `sudo systemctl restart proflistpt_bot.service`
- `sleep 2`
- `systemctl is-active proflistpt_bot.service`

## Refactor state

Current canonical refactor snapshot:

- `docs/refactor/current-state.md`
