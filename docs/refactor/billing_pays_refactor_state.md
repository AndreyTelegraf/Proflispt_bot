# Billing and Pays Refactor State

Staging billing/pays refactor finalized and stabilized.

## Commits

- 72027e4 — split /pays executive summary and /billing audit/details.
- 538cfc5 — fixed repost accounting and separated Directory reposts from Baraholka reposts.

## Source of truth

premium_posts remains the canonical accounting source.

## What changed

/pays became a short executive summary layer.

Supported forms:

- /pays
- /pays MM.YYYY

/billing was added as the audit/detail layer.

Supported forms:

- /billing
- /billing MM.YYYY

Shared billing helpers:

- _billing_is_allowed()
- _parse_billing_period()
- _fetch_billing_report()
- _rows_sum()
- _append_billing_rows()
- _send_long_text()

## Business semantics

Before:

- all reposts were mixed together
- deleted/superseded reposts polluted totals
- Baraholka reposts were double-counted as Directory апы

After:

- Directory reposts and Baraholka reposts are separated
- deleted/superseded items are excluded from executive summary totals
- /pays shows only actually published monetized actions

Invariant:

/pays intentionally excludes deleted/superseded monetization artifacts from executive totals.

## Current /pays summary structure

- posts with media, currently 20 EUR
- Directory reposts / апы, currently 10 EUR
- pins
- total Directory revenue
- Baraholka reposts as a separate informational block

## Repost stream semantics

Directory reposts are repost monetization inside the Directory lifecycle.

Baraholka reposts are an external cross-product monetization stream and must stay separated from Directory revenue totals.

## Current Baraholka classification

Current Baraholka repost-capable modes:

    baraholka_modes = {"owner_real_estate", "housing_wanted"}

This classification remains explicit/hardcoded pending a canonical product segmentation layer.

If additional Baraholka repost-capable modes appear later, they must be added here or extracted into a canonical helper/constant layer.

## Verified manually

- /pays
- /pays 04.2026
- /pays 05.2026
- /billing 04.2026
- /billing 05.2026

## Final validated May accounting

- media posts: 13 / 260 EUR
- Directory reposts: 6 / 60 EUR
- pins: 2 / 10 EUR
- total Directory revenue: 21 / 330 EUR
- Baraholka reposts: 23 / 230 EUR

## Architecture outcome

/pays = executive summary.

/billing = accounting/audit layer.

Directory revenue and Baraholka repost monetization are cleanly separated.

Prepared foundation for:

- yearly reports
- exports/CSV
- accounting segmentation
- separate product revenue streams
