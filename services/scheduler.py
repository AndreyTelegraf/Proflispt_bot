"""Scheduler service for automatic cleanup tasks."""

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Optional
from aiogram import Bot

from database import db
from services.post_identity import format_premium_post_identity_text
from services.directory_links import directory_message_url

logger = logging.getLogger(__name__)


def _compact_job_posting_text(value, limit: int = 100) -> str:
    text = str(value or "").strip().replace("\n", " ")
    text = " ".join(text.split())
    if len(text) > limit:
        return text[:limit].rstrip() + "…"
    return text


def _format_expired_job_posting_identity(posting: dict) -> str:
    section = posting.get("mode") or "Объявление"
    title = _compact_job_posting_text(
        posting.get("name") or posting.get("description") or "Объявление",
        limit=80,
    )

    lines = [
        f"Раздел: {section}",
        f"Объявление: {title}",
    ]

    if posting.get("message_id"):
        lines.append(
            "Ссылка: "
            + directory_message_url(posting.get("message_id"), posting.get("topic_id"))
        )

    return "\n".join(lines)


class CleanupScheduler:
    """Scheduler for automatic cleanup of expired postings."""
    
    def __init__(self, bot: Bot, db_instance=None):
        self.bot = bot
        self.db = db_instance or db
        self._task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        """Start the scheduler."""
        if self._running:
            logger.warning("Scheduler is already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Cleanup scheduler started")
    
    async def stop(self):
        """Stop the scheduler."""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Cleanup scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                # Calculate next cleanup time
                next_cleanup = self._get_next_cleanup_time()
                now = datetime.utcnow()
                
                # Wait until next cleanup time
                wait_seconds = (next_cleanup - now).total_seconds()
                if wait_seconds > 0:
                    logger.info(f"Next cleanup scheduled for {next_cleanup.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                    await asyncio.sleep(wait_seconds)
                
                # Perform cleanup
                if self._running:  # Check again after sleep
                    await self._perform_cleanup()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                # Wait 1 hour before retrying
                await asyncio.sleep(3600)
    
    def _get_next_cleanup_time(self) -> datetime:
        """Get next cleanup time (00:00 or 12:00 UTC)."""
        now = datetime.utcnow()
        
        # Today's cleanup times
        today_00 = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_12 = now.replace(hour=12, minute=0, second=0, microsecond=0)
        
        # Tomorrow's 00:00
        tomorrow_00 = today_00 + timedelta(days=1)
        
        # Find the next cleanup time
        if now < today_00:
            return today_00
        elif now < today_12:
            return today_12
        else:
            return tomorrow_00
    
    async def _perform_cleanup(self):
        """Perform the cleanup of expired postings and bans."""
        try:
            logger.info("Starting cleanup of expired postings and bans...")
            
            # Legacy job_postings expiry disabled: job_postings creation flow is no longer routed.
            
            # Clean up expired bans
            try:
                cleaned_bans = db.cleanup_expired_bans()
                if cleaned_bans > 0:
                    logger.info(f"Cleaned up {cleaned_bans} expired bans")
                else:
                    logger.info("No expired bans found")
            except Exception as e:
                logger.error(f"Error cleaning up expired bans: {e}")

            # Unpin expired premium pin posts
            await self._unpin_expired_premium_posts()

            # Warn and expire premium posts by TTL
            await self._expire_premium_posts()

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def _unpin_expired_premium_posts(self):
        """Unpin premium pin posts whose pinned_until has passed."""
        posts = db.get_premium_posts_to_unpin()
        if not posts:
            logger.info("No expired premium pins found")
            return
        for post in posts:
            try:
                await self.bot.unpin_chat_message(
                    chat_id=post['chat_id'],
                    message_id=post['message_id'],
                )
                db.clear_premium_post_pin(post['id'])
                logger.info(f"Unpinned premium post #{post['id']} (message {post['message_id']})")
            except Exception as e:
                err = str(e).lower()
                if (
                    "message to unpin not found" in err
                    or "message to edit not found" in err
                    or "message_id_invalid" in err
                    or "message not found" in err
                ):
                    db.clear_premium_post_pin(post['id'])
                    logger.warning(
                        f"Cleared expired premium pin marker for post #{post['id']} "
                        f"after Telegram reported missing/unpinned message: {e}"
                    )
                else:
                    logger.warning(f"Failed to unpin premium post #{post['id']}: {e}")

    async def _expire_premium_posts(self):
        db = self.db
        bot = self.bot

        # T-1 warning
        posts = db.get_premium_posts_to_warn_1d()
        for post in posts:
            try:
                if post.get('telegram_id'):
                    identity = format_premium_post_identity_text(post)
                    await bot.send_message(
                        chat_id=post['telegram_id'],
                        text=(
                            f"{identity}\n\n"
                            "Через 1 день будет автоматически удалено ваше объявление.\n\n"
                            "Если объявление ещё актуально, поднимите его или опубликуйте новую версию.\n"
                            "Если ничего не делать, объявление будет удалено автоматически."
                        ),
                        disable_web_page_preview=True,
                    )
            except Exception:
                pass
            db.mark_premium_post_warned_1d(post['id'])

        # Expiry T+0
        posts = db.get_expired_premium_posts()
        for post in posts:
            message_ids = post.get('published_message_ids') or []
            if not message_ids and post.get('message_id'):
                message_ids = [post['message_id']]

            for mid in message_ids:
                try:
                    await bot.delete_message(
                        chat_id=int(post['chat_id']),
                        message_id=int(mid)
                    )
                except Exception:
                    pass

            db.mark_premium_post_expired(post['id'])

            try:
                if post.get('telegram_id'):
                    identity = format_premium_post_identity_text(post)
                    await bot.send_message(
                        chat_id=post['telegram_id'],
                        text=(
                            f"{identity}\n\n"
                            "Объявление удалено по истечении срока публикации.\n\n"
                            "Если объявление всё ещё актуально, создайте новую публикацию через бота."
                        ),
                        disable_web_page_preview=True,
                    )
            except Exception:
                pass

    async def run_cleanup_now(self):
        """Run cleanup immediately (for testing)."""
        logger.info("Running immediate cleanup...")
        await self._perform_cleanup()


# Global scheduler instance
scheduler: Optional[CleanupScheduler] = None


async def start_scheduler(bot: Bot):
    """Start the global scheduler."""
    global scheduler
    if scheduler is None:
        scheduler = CleanupScheduler(bot)
    await scheduler.start()


async def stop_scheduler():
    """Stop the global scheduler."""
    global scheduler
    if scheduler:
        await scheduler.stop()
        scheduler = None


async def run_cleanup_now(bot: Bot):
    """Run cleanup immediately."""
    global scheduler
    if scheduler is None:
        scheduler = CleanupScheduler(bot)
    await scheduler.run_cleanup_now()
