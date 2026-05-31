"""Telegram link builders for directory channel messages."""

from config import Config


def directory_channel_username() -> str:
    return Config.DIRECTORY_CHANNEL_USERNAME.lstrip("@")


def directory_message_url(message_id, topic_id=None) -> str:
    username = directory_channel_username()
    if topic_id:
        return f"https://t.me/{username}/{topic_id}/{message_id}"
    return f"https://t.me/{username}/{message_id}"
