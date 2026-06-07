"""Publisher service."""

import logging
from typing import Optional
from aiogram import Bot
from aiogram.types import Message

from config import Config
from models.job_posting import JobPosting
from services.catalog_listing_renderer import render_catalog_listing_html
from services.sections_registry import load_sections_registry
from database import db

logger = logging.getLogger(__name__)


def _job_posting_catalog_payload(posting: JobPosting) -> dict:
    return {
        "geo_tags": posting.cities,
        "description": posting.description,
        "social_links": posting.social_media,
        "telegram": posting.telegram_username,
        "phone_main": posting.phone_main,
        "phone_whatsapp": posting.phone_whatsapp,
        "contact_name": posting.name,
    }


class Publisher:
    """Service for publishing job postings to channel."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.registry = load_sections_registry()

    def _resolve_job_target(self, posting: JobPosting) -> tuple[int, int]:
        if posting.mode == "seeking":
            section_name = "Ищу работу"
        elif posting.mode == "offering":
            section_name = "Предлагаю работу"
        else:
            raise ValueError(f"Unsupported posting mode: {posting.mode}")

        channel_id = int(self.registry.channel_id or Config.CHANNEL_ID)
        topic_id = int(self.registry.get_topic_id(section_name))
        return channel_id, topic_id

    async def publish_posting(self, posting: JobPosting, user_id: int) -> Optional[Message]:
        """Publish job posting to channel."""
        try:
            posting_text = render_catalog_listing_html(_job_posting_catalog_payload(posting))
            channel_id, topic_id = self._resolve_job_target(posting)

            message = await self.bot.send_message(
                chat_id=channel_id,
                text=posting_text,
                message_thread_id=topic_id,
                disable_web_page_preview=True,
                parse_mode="HTML"
            )

            logger.info(
                "Published posting %s to channel via registry topic_id=%s",
                posting.id,
                topic_id,
            )

            if posting.id:
                db.update_posting(
                    posting.id,
                    message_id=message.message_id,
                    chat_id=message.chat.id,
                    topic_id=topic_id
                )

            return message

        except Exception as e:
            logger.error(f"Failed to publish posting: {e}")
            return None

    async def delete_posting(self, posting: JobPosting) -> bool:
        """Delete posting from channel."""
        try:
            if posting.message_id and posting.chat_id:
                await self.bot.delete_message(
                    chat_id=posting.chat_id,
                    message_id=posting.message_id
                )

                logger.info(f"Deleted posting {posting.id} from channel")
                return True
            else:
                logger.warning(f"No message info for posting {posting.id}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete posting: {e}")
            return False

    async def edit_posting(self, posting: JobPosting) -> bool:
        """Edit posting in channel."""
        try:
            if posting.message_id and posting.chat_id:
                posting_text = render_catalog_listing_html(_job_posting_catalog_payload(posting))

                await self.bot.edit_message_text(
                    chat_id=posting.chat_id,
                    message_id=posting.message_id,
                    text=posting_text,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )

                logger.info(f"Edited posting {posting.id} in channel")
                return True
            else:
                logger.warning(f"No message info for posting {posting.id}")
                return False

        except Exception as e:
            logger.error(f"Failed to edit posting: {e}")
            return False
