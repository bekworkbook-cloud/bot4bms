"""3.3. Остатки."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database import Database
from keyboards import BTN_STOCK, main_menu

from .utils import answer_long, product_lines

entry = Router(name="stock-entry")


@entry.message(F.text == BTN_STOCK)
@entry.message(Command("list"))
async def show_stock(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    products = await db.list_products()
    if not products:
        await message.answer("Склад пуст. Добавьте первый товар", reply_markup=main_menu())
        return

    total_units = sum(p.quantity for p in products)
    lines = [
        "Остатки на складе:",
        *product_lines(products),
        f"Всего позиций: {len(products)} · Всего единиц: {total_units}",
    ]
    await answer_long(message, lines, reply_markup=main_menu())
