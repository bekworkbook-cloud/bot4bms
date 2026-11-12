"""3.6. История операций."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import Config
from database import Database
from keyboards import BTN_HISTORY, main_menu

from .utils import answer_long, format_delta, format_dt

HISTORY_LIMIT = 20

entry = Router(name="history-entry")


@entry.message(F.text == BTN_HISTORY)
@entry.message(Command("history"))
async def show_history(message: Message, state: FSMContext, db: Database, config: Config) -> None:
    await state.clear()
    operations = await db.last_operations(HISTORY_LIMIT)
    if not operations:
        await message.answer("История операций пуста", reply_markup=main_menu())
        return

    lines = [f"Последние операции ({len(operations)}):"]
    for op in reversed(operations):  # от старых к новым
        suffix = " (удалён)" if op.action == "delete" else ""
        lines.append(
            f"{format_dt(op.created_at, config.timezone)} — {op.user_name}: "
            f"{format_delta(op.delta)} {op.product_name}{suffix}"
        )
    await answer_long(message, lines, reply_markup=main_menu())
