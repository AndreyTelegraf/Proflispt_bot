# Reviews special-case verdict

Date: 2026-06-08
HEAD before layer: 5efda68

## Audit scope

Checked whether `reviews` is still a legacy special branch or a valid business-specific special case.

Targets inspected:

- handlers/reviews_schema_flow.py
- services/catalog_specialized_renderers.py
- services/catalog_listing_renderer.py
- handlers/premium_admin.py
- database.py
- handlers/section_catalog.py
- main.py
- config/section_groups.json

## Result

No runtime patch is required.

`reviews` is a valid business-specific special case, not leftover legacy.

## Confirmed special behavior

Reviews use:

- dedicated entrypoint: `section:reviews`
- dedicated handler: `handlers/reviews_schema_flow.py`
- mode: `premium_posts.mode = reviews`
- free moderation flow with `payment_amount = 0.00`
- no expiry: `_premium_post_ttl_days("reviews") -> None`
- exclusion from normal monthly directory limits
- exclusion from user-managed “Мои объявления”
- dedicated renderer: `render_review_listing_html`
- dedicated review index table: `review_index`
- performer review lookup via `catalog_listing_renderer.py`

## Why this must remain special

Reviews are not ordinary directory listings.

They are linked to performer usernames and then surfaced inside performer listings through `review_index`.

This creates a cross-listing relation:

- review author publishes a review
- review targets a performer username
- approved review is indexed
- performer listing can show total/latest reviews

The generic schema flow does not currently model that relation.

## Decision

Do not merge reviews into generic schema flow yet.

Keep reviews as a special-case flow until the generic architecture supports cross-entity relations and indexed secondary projections.

## Accepted state

The following are accepted special-case components:

- `handlers/reviews_schema_flow.py`
- `review_index` table and DB helpers
- `render_review_listing_html`
- `build_review_listing_html_from_premium_post`
- premium_admin branches for `mode == "reviews"`
- catalog listing review backlinks
- `REVIEWS_SECTION_NAME`

## Future refactor condition

Reviews can be generalized only after introducing a formal shared mechanism for:

- non-listing submissions
- moderation without payment
- secondary indexes/projections
- cross-entity links by normalized Telegram username
- section-specific publication side effects

Until then, treating reviews as a normal listing section would hide important business logic and increase risk.
