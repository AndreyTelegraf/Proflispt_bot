import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from services.admin_moderation_notice import resolve_admin_moderation_chat_id

old = Config.ADMIN_MODERATION_CHAT_ID
try:
    Config.ADMIN_MODERATION_CHAT_ID = 0
    assert resolve_admin_moderation_chat_id(336224597) == 336224597

    Config.ADMIN_MODERATION_CHAT_ID = 8405113240
    assert resolve_admin_moderation_chat_id(336224597) == 8405113240
finally:
    Config.ADMIN_MODERATION_CHAT_ID = old

print("admin_moderation_notice_routing_smoke OK")
