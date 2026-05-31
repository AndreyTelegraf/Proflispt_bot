# Billing access canonical rule — 2026-05-31

## Current rule

Billing commands are internal administrative commands.

Protected commands:

- `/pays`
- `/pays MM.YYYY`
- `/billing`
- `/billing MM.YYYY`

Current temporary implementation in `main.py`:

- `andreytelegraf`
- `kak_odin`
- `kak_budto`

## Why access is restricted

These commands expose internal operational and financial data:

- revenue summaries
- client phone numbers
- client Telegram usernames
- publication links
- deleted and superseded post audit
- payment and lifecycle details

They must not be available to ordinary users.

## Refactor target

Do not keep billing access as a local username list inside `main.py`.

Future architecture should use one centralized admin/role layer, for example:

- `is_directory_admin(user)`
- `user.has_role("directory_admin")`

The same source of truth should protect:

- `/pays`
- `/billing`
- `/premium_posts`
- moderation actions
- financial reports
- future admin functions

## Guardrail

Billing commands must be available only to directory administrators.

Until centralized roles exist, the temporary allowed usernames are:

- `@andreytelegraf`
- `@kak_odin`
- `@kak_budto`
