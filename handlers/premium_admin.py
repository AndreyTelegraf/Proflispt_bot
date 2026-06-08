"""Admin handlers for premium posts."""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from services.premium_admin_workflow import (
    PremiumAdminWorkflowError,
    approve_premium_request,
    load_premium_post_and_user,
    reject_premium_request,
)

router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id == 336224597


@router.callback_query(F.data.startswith("admin:approve_premium:"))
async def admin_approve_premium(callback: CallbackQuery):
    """Admin approves premium post payment."""
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для выполнения этой команды.", show_alert=True)
        return

    post_id = int(callback.data.split(":")[2])
    post, user = load_premium_post_and_user(post_id)

    if not post:
        await callback.answer("🚫 Пост не найден.", show_alert=True)
        return

    if not user:
        await callback.answer("🚫 Пользователь не найден.", show_alert=True)
        return

    try:
        result = await approve_premium_request(
            bot=callback.bot,
            admin_message=callback.message,
            post=post,
            user=user,
            post_id=post_id,
            admin_id=callback.from_user.id,
        )
    except PremiumAdminWorkflowError:
        await callback.answer("Не удалось одобрить пост. Проверьте лог и попробуйте ещё раз.", show_alert=True)
        return

    if result == "pin_disabled":
        await callback.answer("Закрепление отключено.", show_alert=True)
        return

    await callback.answer("✅ Пост одобрен!")


@router.callback_query(F.data.startswith("admin:reject_premium:"))
async def admin_reject_premium(callback: CallbackQuery):
    """Admin rejects premium post."""
    if not _is_admin(callback.from_user.id):
        await callback.answer("🚫 У вас нет прав для выполнения этой команды.", show_alert=True)
        return

    post_id = int(callback.data.split(":")[2])
    post, user = load_premium_post_and_user(post_id)

    if not post:
        await callback.answer("🚫 Пост не найден.", show_alert=True)
        return

    if not user:
        await callback.answer("🚫 Пользователь не найден.", show_alert=True)
        return

    await reject_premium_request(
        bot=callback.bot,
        admin_message=callback.message,
        post=post,
        user=user,
        post_id=post_id,
        admin_id=callback.from_user.id,
    )

    await callback.answer("🚫 Пост отклонен!")
