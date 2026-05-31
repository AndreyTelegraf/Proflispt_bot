# Accounting layer canonical state — 2026-05-31

## Canonical principle

`/pays` is an accounting report for paid services already delivered.

It must answer:

"Which paid services were provided?"

It must not answer:

"Which posts are currently alive?"

A paid service is counted when:

- `payment_status = 'approved'`
- `payment_amount > 0`
- `message_id IS NOT NULL`
- `status IN ('published', 'deleted', 'superseded')`

If a paid post was published and later deleted or superseded, it remains earned revenue.

## Operational lifecycle remains separate

`/billing` is the audit and lifecycle tool.

It may show:

- published
- deleted
- superseded
- pending
- historical artifacts
- technical rows

This separation is intentional:

- accounting layer -> `/pays`
- operational lifecycle layer -> `/billing`

## Current implementation

`_fetch_billing_report()` exposes separate accounting selectors:

- `accounting_posts`
- `accounting_reposts`
- `accounting_pins`

These are used only by `/pays`.

Operational selectors remain separate:

- `published_posts`
- `removed_posts`
- `published_reposts`
- `removed_reposts`
- `published_pins`

These are used by `/billing`.

## Known compatibility layer

`_exclude_known_non_billable_rows()` is temporary.

It excludes old technical/test rows by hardcoded IDs:

- 7
- 158
- 256
- 259
- 356
- 359
- 361
- 440
- 441
- 653

This is not the target architecture.

## Target architecture

Future schema should replace hardcoded ID exclusions with an explicit accounting field in `premium_posts`.

Recommended option:

- `accounting_status`

Possible values:

- `billable`
- `non_billable`
- `test`
- `technical_duplicate`
- `refund`

Then `/pays` should count only:

- `accounting_status = 'billable'`

## Product split

Directory bumps and Baraholka reposts are separate products.

Directory bumps:

- `action_type = 'repost'`
- mode not in housing Baraholka modes

Baraholka reposts:

- `action_type = 'repost'`
- mode in `owner_real_estate`, `housing_wanted`

`/billing` must keep them separated in detail blocks.

## Refactor guardrail

During future refactor, preserve this rule:

`premium_posts` remains the accounting source of truth until an explicit accounting ledger exists.

Accounting must follow paid service delivery, not current post visibility.
