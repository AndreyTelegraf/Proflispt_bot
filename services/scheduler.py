"""Scheduler service for automatic cleanup tasks."""

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Optional
from aiogram import Bot

from database import db
from services.publisher import Publisher

logger = logging.getLogger(__name__)


class CleanupScheduler:
    """Scheduler for automatic cleanup of expired postings."""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.publisher = Publisher(bot)
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
            
            # Clean up expired postings
            deleted_count, deleted_postings = db.cleanup_expired_postings()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired postings")
                
                # Delete messages from Telegram channel
                await self._delete_telegram_messages(deleted_postings)
                
                # Log detailed information
                for posting in deleted_postings:
                    logger.info(
                        f"Deleted posting ID {posting['id']} by user {posting['user_id']} "
                        f"({posting['mode']}, {posting['cities']}, {posting['name']}) "
                        f"created at {posting['created_at']}"
                    )
            else:
                logger.info("No expired postings found")
            
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

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def _delete_telegram_messages(self, deleted_postings: list[dict]):
        """Delete messages from Telegram channel."""
        for posting in deleted_postings:
            try:
                if posting['message_id'] and posting['chat_id']:
                    await self.bot.delete_message(
                        chat_id=posting['chat_id'],
                        message_id=posting['message_id']
                    )
                    logger.info(f"Deleted Telegram message {posting['message_id']} for posting {posting['id']}")
            except Exception as e:
                logger.warning(f"Failed to delete Telegram message for posting {posting['id']}: {e}")

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
                logger.warning(f"Failed to unpin premium post #{post['id']}: {e}")

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
