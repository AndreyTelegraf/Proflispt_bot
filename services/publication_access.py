"""Per-account publication access policy helpers."""

PAID_ONLY_NOTICE = "Для вашего аккаунта доступны только платные публикации."


def free_publication_availability(database, user_id: int) -> tuple[bool, str | None]:
    """Return a free-publication decision suitable for preview handlers."""
    if database.is_paid_only_user(user_id):
        return False, PAID_ONLY_NOTICE
    return True, None
