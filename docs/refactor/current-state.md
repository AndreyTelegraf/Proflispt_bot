# Refactor current state

Status: canonical current refactor snapshot.

Updated after cleanup through commit d7cf6a2.

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
- Remaining acceptance target:
  - published/deleted/superseded/pending states are shown clearly
  - multi-message publications are managed consistently
  - expiry/repost/delete actions identify the concrete post

## Legacy names

- workinportugal references may remain only as historical refactor documentation or venv metadata.
- proflistpt is the active project/bot identity.
- Do not patch venv path metadata as part of application refactor.

## Remaining refactor priorities

1. My postings final manual smoke across active modes.
2. Generic/schema-driven flow audit.
4. Docs consolidation: old docs/refactor files are historical notes unless superseded here.
5. Repository hygiene pass for temporary scripts, diagnostics policy, and stale README/spec sections.
