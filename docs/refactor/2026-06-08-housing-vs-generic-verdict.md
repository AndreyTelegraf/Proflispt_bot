# Housing vs generic flow verdict

Date: 2026-06-08
HEAD before layer: df37bcc

## Audit scope

Compared:

- handlers/generic_schema_flow.py
- handlers/housing_schema_flow.py

Checked function shape, normalized function names, callback prefixes, and housing-specific behavior.

## Result

`housing_schema_flow.py` is the largest remaining duplicated flow.

It is not pure legacy, because it contains real product-specific behavior that the generic flow does not currently support.

## Confirmed duplication

Housing has close structural equivalents for the generic flow:

- media lock
- prompt resolver
- back keyboard
- choice keyboard
- step keyboard
- preview keyboard
- Telegram username gate
- media keyboard
- state getter/saver
- advance logic
- entrypoint
- choice handling
- custom geo input
- social links skip
- WhatsApp skip/same/none
- Telegram username created
- back navigation
- text input
- media input

This confirms that the normal FSM mechanics are duplicated.

## Confirmed housing-specific behavior

Housing contains behavior that is not present in generic flow:

- `housing_wanted`
- `owner_real_estate`
- `rental_term`
- `render_housing_listing_html`
- free housing publication via `publish_free_housing_post`
- automatic Baraholka publication for `housing_wanted`
- Baraholka paid upsell for other housing posts
- `baraholka_repost_target`
- `baraholka_auto_publish`
- `Config.BARAHOLKA_CHANNEL_ID`
- `Config.BARAHOLKA_HOUSING_TOPIC_ID`
- `_notify_admin_baraholka_from_post`

## Decision

Do not merge housing directly into generic flow yet.

Housing should remain a special-case flow for now, but it is the main candidate for future FSM-core extraction.

The right future direction is not to force housing into generic flow. The right direction is to extract a shared schema-flow core that both generic and housing use, with section-specific hooks.

## Future extraction target

A shared FSM flow core should cover:

- common state shape
- prompt rendering
- keyboard generation
- choice handling
- custom geo handling
- social links handling
- WhatsApp handling
- Telegram username gate
- back navigation
- text input validation
- media collection
- preview rendering

Housing-specific hooks should cover:

- renderer selection
- free publish behavior
- post persistence
- Baraholka auto-publish
- Baraholka paid upsell
- rental_term handling
- result message construction

## Accepted state

Accepted for now:

- `handlers/housing_schema_flow.py` remains separate
- `handlers/generic_schema_flow.py` remains separate
- housing-specific callbacks keep `hs:` prefix
- generic callbacks keep `gs:` prefix

Rejected future direction:

- blindly copy more generic logic into housing
- merge housing into generic without hook architecture
- add new housing-specific behavior into generic flow
- keep growing two independent duplicated FSM implementations indefinitely
