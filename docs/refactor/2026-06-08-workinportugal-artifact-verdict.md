# WorkInPortugal artifact verdict

Date: 2026-06-08
HEAD before layer: e3263cc

## Audit scope

Checked live references for:

- workinportugal
- workinportugal_bot
- @workinportugal_bot
- Work in Portugal
- proflistpt

Targets inspected:

- main.py
- database.py
- handlers/
- services/
- config/
- docs/
- sections_registry.json

## Result

No runtime patch is required.

Live runtime and user-facing code is clean from WorkInPortugal identity references.

Confirmed:

- `workinportugal_bot`: no live references
- `@workinportugal_bot`: no live references
- `Work in Portugal`: no live references
- runtime code path is `/opt/bots/proflistpt_bot`
- active service is `proflistpt_bot.service`

## Remaining references

The only remaining relevant live repository reference is historical documentation:

- `docs/refactor/current-state.md`
  - states that workinportugal references may remain only as historical refactor documentation or venv metadata

There are also old diagnostic/audit artifacts under `data/`, including previous audit output. These are not runtime code and do not affect the bot.

## Decision

Do not patch runtime code.

`workinportugal` may remain only in:

- historical refactor docs
- old audit artifacts
- backups
- diagnostics
- external server/service history references

It must not appear in:

- active runtime code
- user-facing bot text
- README active instructions
- active systemd/service references
- current deployment paths

## Accepted state

The active project identity is ProflistPT.

The accepted active service/path names are:

- `proflistpt_bot.service`
- `/opt/bots/proflistpt_bot`

The old WorkInPortugal naming is considered historical only.
