"""Identity/key helpers for My Postings."""

PREMIUM_POST_KEY_PREFIX = "premium"


def build_premium_post_key(post_id):
    return f"{PREMIUM_POST_KEY_PREFIX}:{post_id}"


def parse_post_key(item_key):
    post_type, post_id_str = item_key.split(":", 1)
    return post_type, int(post_id_str)
