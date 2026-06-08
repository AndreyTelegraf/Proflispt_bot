# Refactor current state

Status: canonical current refactor snapshot.

Updated after cleanup through commit d52f721.

## Runtime

- Active staging service: proflistpt_bot_staging.service
- Active bot code path: /opt/bots/proflistpt_bot_staging
- Runtime DB no longer contains job_postings.
- Active publication source is premium_posts.
- healthcheck_local.sh no longer expects job_postings.

## Completed cleanup

- Legacy job_postings handlers removed from My postings.
- Legacy main job flow removed.
- Legacy posting router disabled and deleted.
- JobPosting model deleted.
- Legacy publisher service deleted.
- Dead job_postings DB API removed.
- Runtime SQLite job_postings table dropped after verifying it was empty.
- Unreferenced infra_restructure_summary.md deleted.

## Current source of truth

- premium_posts is the canonical managed publication table.
- job_seeker and job_offer are normal premium_posts modes.
- restaurants is a live section mode, not a template artifact.
- restaurants is present in premium_posts runtime data and must remain stable.
- restaurants must not be renamed without a separate data migration and full mode-reference audit.

## Scheduler

- Scheduler no longer touches legacy job_postings.
- Scheduler still handles:
  - expired bans
  - expired premium pins
  - premium post TTL warnings/expiry
  - auto-repost related runtime handled outside this document where applicable
- Premium post expiry UX is accepted: warning and deletion notifications include section, concrete post title, and post link when available.
- Expiry cleanup runs at 00:00 and 12:00 UTC, so posts expiring between runs may remain published until the next scheduled cleanup.

## My postings

- My postings is now premium-post based.
- Final manual smoke accepted across active modes:
  - job_seeker
  - job_offer
  - housing_wanted
  - owner_real_estate multi-message
  - ordinary generic catalog mode
  - pending repost/payment states
  - deleted state
  - superseded state
- Status labels, section identity, post title, links, navigation, and action buttons are accepted.

## Generic/schema-driven flow

- Generic catalog flow topology is accepted.
- 34 ordinary catalog modes are handled by generic_schema_flow through config/fsm_schemas.
- housing_wanted and owner_real_estate are valid housing special-cases handled by housing_schema_flow.
- reviews is a valid special-case handled by reviews_schema_flow.
- restaurants is handled as an ordinary live catalog mode, not as a template artifact.
- No live restaurants_schema.py or posting.py handler remains.
- generic_schema_flow and housing_schema_flow share similar FSM mechanics, but housing remains a valid product special-case because it has different media, publish, and Baraholka repost behavior.
- Do not extract a shared flow base until there is a concrete bug or repeated product change requiring it.
- Runtime mode-specific branch audit is accepted: remaining explicit mode checks are valid product semantics, not legacy leakage.
- Valid remaining mode-specific branches: reviews indexing/limits, job_offer TTL, housing/Baraholka behavior, post identity labels.

## Legacy names

- workinportugal references may remain only as historical refactor documentation or venv metadata.
- proflistpt is the active project/bot identity.
- Do not patch venv path metadata as part of application refactor.

## Remaining refactor priorities

1. No open documentation cleanup priorities.
