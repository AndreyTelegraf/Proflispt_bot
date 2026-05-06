"""Fallback handlers for unmatched private text input."""
from aiogram import Router, F
from aiogram.types import Message

router = Router()


@router.message(F.text)
async def unknown_private_text(message: Message):
    await message.answer(
        "Я не понял это сообщение. Пожалуйста, используйте кнопки на экране. "
        "Если хотите начать заново, отправьте /start."
    )
