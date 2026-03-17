from functools import wraps
from aiogram import types

from src.core.config import ADMIN_ID


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id == ADMIN_ID


def admin_only(func):
    """Декоратор для команд, доступных только админу."""
    @wraps(func)
    async def wrapper(message: types.Message, *args, **kwargs):
        if not is_admin(message.from_user.id):
            await message.answer("⛔ У вас нет прав для выполнения этой команды.")
            return
        return await func(message, *args, **kwargs)
    return wrapper


def admin_only_callback(func):
    """Декоратор для callback'ов, доступных только админу."""
    @wraps(func)
    async def wrapper(callback: types.CallbackQuery, *args, **kwargs):
        if not is_admin(callback.from_user.id):
            await callback.answer("⛔ У вас нет прав для этого действия.", show_alert=True)
            return
        return await func(callback, *args, **kwargs)
    return wrapper