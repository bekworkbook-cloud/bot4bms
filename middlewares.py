"""Проверка доступа: бот отвечает только пользователям из ALLOWED_USERS."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

logger = logging.getLogger(__name__)

NO_ACCESS = "У вас нет доступа"


class AccessMiddleware(BaseMiddleware):
    def __init__(self, allowed_users: frozenset[int]) -> None:
        self.allowed_users = allowed_users

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is not None and user.id in self.allowed_users:
            return await handler(event, data)

        logger.info("Отказано в доступе: user_id=%s", user.id if user else None)
        if isinstance(event, Message):
            await event.answer(NO_ACCESS)
        elif isinstance(event, CallbackQuery):
            await event.answer(NO_ACCESS, show_alert=True)
        return None
