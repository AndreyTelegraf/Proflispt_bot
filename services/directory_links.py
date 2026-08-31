"""Telegram link builders for directory channel messages."""

from config import Config


def directory_channel_username() -> str:
    return Config.DIRECTORY_CHANNEL_USERNAME.lstrip("@")


def telegram_message_url(username, message_id, topic_id=None) -> str:
    """Build a public Telegram message URL, preserving forum topic context."""
    normalized_username = str(username or "").lstrip("@")
    if topic_id:
        return f"https://t.me/{normalized_username}/{topic_id}/{message_id}"
    return f"https://t.me/{normalized_username}/{message_id}"


def directory_message_url(message_id, topic_id=None) -> str:
    return telegram_message_url(
        directory_channel_username(),
        message_id,
        topic_id,
    )
