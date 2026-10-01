from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from database import add_or_update_user


class UserRegistrationMiddleware(BaseMiddleware):
    """
    Har bir xabar kelganda foydalanuvchini avtomatik ro'yxatdan o'tkazadi.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.from_user:
            user = event.from_user
            await add_or_update_user(
                user_id=user.id,
                full_name=user.full_name,
                username=user.username,
            )
        return await handler(event, data)
