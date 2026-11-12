"""3.4. Поиск товара."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database import Database, clean_name
from keyboards import BTN_FIND, main_menu

from .states import SearchProduct
from .utils import NAME_MAX, answer_long, product_lines

ASK_QUERY = "Введите название товара или его часть"

entry = Router(name="search-entry")
dialog = Router(name="search-dialog")


async def _search(message: Message, db: Database, query: str) -> None:
    products = await db.search_products(query)
    if not products:
        await message.answer("Ничего не найдено", reply_markup=main_menu())
        return
    lines = [f"Найдено: {len(products)}", *product_lines(products)]
    await answer_long(message, lines, reply_markup=main_menu())


@entry.message(Command("find"))
async def cmd_find(message: Message, command: CommandObject, state: FSMContext, db: Database) -> None:
    await state.clear()
    query = clean_name(command.args or "")
    if not query:
        await state.set_state(SearchProduct.query)
        await message.answer(ASK_QUERY)
        return
    if len(query) > NAME_MAX:
        await message.answer(f"Слишком длинный запрос — максимум {NAME_MAX} символов.")
        return
    await _search(message, db, query)


@entry.message(F.text == BTN_FIND)
async def start_find(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(SearchProduct.query)
    await message.answer(ASK_QUERY)


@dialog.message(SearchProduct.query, F.text)
async def got_query(message: Message, state: FSMContext, db: Database) -> None:
    query = clean_name(message.text or "")
    if not query:
        await message.answer(f"Запрос не может быть пустым.\n\n{ASK_QUERY}")
        return
    if len(query) > NAME_MAX:
        await message.answer(f"Слишком длинный запрос — максимум {NAME_MAX} символов.\n\n{ASK_QUERY}")
        return
    await state.clear()
    await _search(message, db, query)
