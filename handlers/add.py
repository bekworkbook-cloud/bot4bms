"""3.1. Добавить товар."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database import Database
from keyboards import BTN_ADD, main_menu

from .states import AddProduct
from .utils import parse_quantity, user_name, validate_name

ASK_NAME = "Введите вид (название) товара"
ASK_QTY = "Введите количество"

entry = Router(name="add-entry")
dialog = Router(name="add-dialog")


@entry.message(F.text == BTN_ADD)
@entry.message(Command("add"))
async def start_add(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddProduct.name)
    await message.answer(ASK_NAME)


@dialog.message(AddProduct.name, F.text)
async def got_name(message: Message, state: FSMContext) -> None:
    name, error = validate_name(message.text or "")
    if error:
        await message.answer(f"{error}\n\n{ASK_NAME}")
        return
    await state.update_data(name=name)
    await state.set_state(AddProduct.quantity)
    await message.answer(ASK_QTY)


@dialog.message(AddProduct.quantity, F.text)
async def got_quantity(message: Message, state: FSMContext, db: Database) -> None:
    quantity, error = parse_quantity(message.text or "")
    if error:
        await message.answer(f"{error}\n\n{ASK_QTY}")
        return

    data = await state.get_data()
    result = await db.add_product(data["name"], quantity, message.from_user.id, user_name(message.from_user))
    await state.clear()
    product = result.product
    await message.answer(
        f"Добавлено: {product.display_name} — {result.added} шт. Всего на складе: {product.quantity} шт.",
        reply_markup=main_menu(),
    )
