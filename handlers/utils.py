"""Общие вспомогательные функции для хендлеров."""

from __future__ import annotations

import re
from datetime import datetime, tzinfo
from typing import Iterable

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, User

from database import Product, clean_name

TELEGRAM_CHUNK = 4000

NAME_MIN = 2
NAME_MAX = 100
QTY_MAX = 1_000_000

_INT_RE = re.compile(r"[+-]?[0-9]+")

ERR_QTY = "Введите целое число больше 0"
ERR_QTY_MAX = f"Слишком большое число. Максимум — {QTY_MAX:,} шт.".replace(",", " ")
ERR_NOT_TEXT = "Пожалуйста, отправьте текст"
ERR_GENERIC = "Что-то пошло не так, попробуйте ещё раз"


def user_name(user: User | None) -> str:
    if user is None:
        return "неизвестный"
    return user.full_name.strip() or (f"@{user.username}" if user.username else str(user.id))


def parse_quantity(text: str) -> tuple[int | None, str | None]:
    """Возвращает (число, None) или (None, текст ошибки)."""
    text = text.strip().replace(" ", "").replace(" ", "")
    # Проверяем длину до int(): огромная строка цифр не должна грузить бота.
    if not text or len(text) > 12 or not _INT_RE.fullmatch(text):
        return None, ERR_QTY
    value = int(text)
    if value <= 0:
        return None, ERR_QTY
    if value > QTY_MAX:
        return None, ERR_QTY_MAX
    return value, None


def validate_name(text: str) -> tuple[str | None, str | None]:
    """Возвращает (очищенное название, None) или (None, текст ошибки)."""
    name = clean_name(text)
    if not name:
        return None, "Название не может быть пустым."
    if name.startswith("/"):
        return None, "Название не может начинаться с «/»."
    if len(name) < NAME_MIN:
        return None, f"Название слишком короткое — минимум {NAME_MIN} символа."
    if len(name) > NAME_MAX:
        return None, f"Название слишком длинное — максимум {NAME_MAX} символов (сейчас {len(name)})."
    return name, None


def format_dt(dt: datetime, tz: tzinfo | None) -> str:
    return dt.astimezone(tz).strftime("%d.%m.%Y %H:%M")


def format_delta(delta: int) -> str:
    return f"+{delta}" if delta >= 0 else f"−{abs(delta)}"


def product_lines(products: Iterable[Product]) -> list[str]:
    return [f"{i}. {p.display_name} — {p.quantity} шт." for i, p in enumerate(products, 1)]


def split_text(lines: list[str], limit: int = TELEGRAM_CHUNK) -> list[str]:
    """Склеивает строки в сообщения не длиннее limit символов (по границам строк)."""
    chunks: list[str] = []
    current = ""
    for line in lines:
        while len(line) > limit:  # на всякий случай — строка длиннее лимита
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


async def answer_long(message: Message, lines: list[str], **kwargs) -> None:
    """Отправляет текст, при необходимости разбивая на несколько сообщений.

    kwargs (например, reply_markup) применяются к последнему сообщению.
    """
    chunks = split_text(lines)
    for i, chunk in enumerate(chunks):
        if i == len(chunks) - 1:
            await message.answer(chunk, **kwargs)
        else:
            await message.answer(chunk)


async def drop_keyboard(message: Message, text: str) -> None:
    """Заменяет текст сообщения с инлайн-кнопками и убирает кнопки."""
    try:
        await message.edit_text(text, reply_markup=None)
    except TelegramBadRequest:
        pass
