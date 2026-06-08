"""State/list helpers for My Postings handlers."""

POST_KEY_PREFIX = "premium"


def build_post_key(post_id):
    return f"{POST_KEY_PREFIX}:{post_id}"


def build_user_post_keys(db, user_id_db):
    manageable_posts = db.get_user_manageable_premium_posts(user_id_db)
    all_posts = sorted(
        manageable_posts,
        key=lambda p: p.get("created_at") or "",
        reverse=True,
    )
    return [build_post_key(p["id"]) for p in all_posts]


def clamp_index(index, total):
    if total <= 0:
        return 0
    return max(0, min(index, total - 1))


def remove_post_key(ids, key, current_index):
    new_ids = [x for x in ids if x != key]
    return new_ids, clamp_index(current_index, len(new_ids))
