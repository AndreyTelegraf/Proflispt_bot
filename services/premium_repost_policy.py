"""Eligibility policy for reusing one source post from My Postings.

This policy must never gate creation of a separate new paid post.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


BUMP_KIND = "bump"
REPUBLISH_KIND = "republish"


@dataclass(frozen=True)
class PremiumRepostPolicy:
    allowed: bool
    kind: str | None
    reason: str


def premium_repost_policy(post: dict) -> PremiumRepostPolicy:
    if post.get("repost_blocked_at"):
        return PremiumRepostPolicy(False, None, "admin_blocked")

    status = post.get("status")
    if status == "published":
        return PremiumRepostPolicy(True, BUMP_KIND, "published")

    if status == "deleted" and post.get("expired_notified_at"):
        return PremiumRepostPolicy(True, REPUBLISH_KIND, "expired")

    if status == "deleted":
        return PremiumRepostPolicy(False, None, "user_deleted")

    return PremiumRepostPolicy(False, None, "status_not_eligible")


def premium_repost_denied_text(policy: PremiumRepostPolicy) -> str:
    if policy.reason == "admin_blocked":
        return "Повторная публикация этого объявления запрещена администратором."
    if policy.reason == "user_deleted":
        return "Вы удалили это объявление. Для новой публикации создайте новую заявку."
    return "Это объявление нельзя поднять или опубликовать повторно."


def validate_premium_repost_request(db, request_post: dict) -> tuple[dict, PremiumRepostPolicy]:
    """Resolve the live source and reject stale/ineligible repost requests."""
    if request_post.get("action_type") != "repost":
        raise ValueError("Request is not a repost")

    try:
        notes = json.loads(request_post.get("admin_notes") or "{}")
    except Exception as exc:
        raise ValueError("Repost request has invalid admin notes") from exc

    source_post_id = int(
        notes.get("old_post_id")
        or notes.get("source_post_id")
        or 0
    )
    if not source_post_id:
        raise ValueError("Repost request has no source post")

    source_post = db.get_premium_post(source_post_id)
    if not source_post:
        raise ValueError(f"Source post #{source_post_id} not found")
    if source_post.get("user_id") != request_post.get("user_id"):
        raise ValueError("Repost request and source post belong to different users")

    policy = premium_repost_policy(source_post)
    if not policy.allowed:
        raise ValueError(premium_repost_denied_text(policy))

    requested_kind = notes.get("repost_kind")
    if requested_kind and requested_kind != policy.kind:
        raise ValueError("Source post state changed after the repost request was created")

    return source_post, policy
