"""3.2. Списать товар."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import Database
from keyboards import BTN_REMOVE, ProductPage, ProductPick, main_menu, products_keyboard

from .states import RemoveProduct
from .utils import drop_keyboard, parse_quantity, user_name

ACTION = "remove"
ASK_PRODUCT = "Выберите товар для списания:"
ASK_QTY = "Введите количество для списания"

entry = Router(name="remove-entry")
dialog = Router(name="remove-dialog")


@entry.message(F.text == BTN_REMOVE)
@entry.message(Command("remove"))
async def start_remove(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    products = await db.list_products()
    if not products:
        await message.answer("Склад пуст, списывать нечего", reply_markup=main_menu())
        return
    await state.set_state(RemoveProduct.choose)
    await message.answer(ASK_PRODUCT, reply_markup=products_keyboard(products, ACTION))


@dialog.callback_query(RemoveProduct.choose, ProductPage.filter(F.action == ACTION))
async def change_page(callback: CallbackQuery, callback_data: ProductPage, db: Database) -> None:
    products = await db.list_products()
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(
            reply_markup=products_keyboard(products, ACTION, callback_data.page)
        )


@dialog.callback_query(RemoveProduct.choose, ProductPick.filter(F.action == ACTION))
async def pick_product(callback: CallbackQuery, callback_data: ProductPick, state: FSMContext, db: Database) -> None:
    product = await db.get_product(callback_data.product_id)
    if product is None:
        await callback.answer("Этот товар уже удалён, выберите другой.", show_alert=True)
        products = await db.list_products()
        if isinstance(callback.message, Message):
            if products:
                await callback.message.edit_reply_markup(reply_markup=products_keyboard(products, ACTION))
            else:
                await state.clear()
                await drop_keyboard(callback.message, "Склад пуст, списывать нечего")
        return
    if product.quantity == 0:
        await callback.answer(f"«{product.display_name}»: остаток 0 шт., списывать нечего.", show_alert=True)
        return

    await callback.answer()
    await state.update_data(product_id=product.id)
    await state.set_state(RemoveProduct.quantity)
    if isinstance(callback.message, Message):
        await drop_keyboard(
            callback.message, f"Списание: {product.display_name} (на складе {product.quantity} шт.)"
        )
        await callback.message.answer(ASK_QTY)


@dialog.message(RemoveProduct.choose)
async def choose_by_text(message: Message) -> None:
    await message.answer("Выберите товар кнопкой в списке выше или отправьте /cancel.")


@dialog.message(RemoveProduct.quantity, F.text)
async def got_quantity(message: Message, state: FSMContext, db: Database) -> None:
    quantity, error = parse_quantity(message.text or "")
    if error:
        await message.answer(f"{error}\n\n{ASK_QTY}")
        return

    data = await state.get_data()
    result = await db.remove_quantity(
        data["product_id"], quantity, message.from_user.id, user_name(message.from_user)
    )

    if result.product is None:
        await state.clear()
        await message.answer("Этот товар уже удалён со склада.", reply_markup=main_menu())
        return
    if not result.ok:
        if result.product.quantity == 0:
            await state.clear()
            await message.answer("На складе только 0 шт. — списывать нечего.", reply_markup=main_menu())
        else:
            await message.answer(f"На складе только {result.product.quantity} шт.\n\n{ASK_QTY}")
        return

    await state.clear()
    await message.answer(
        f"Списано {result.removed} шт. Осталось: {result.product.quantity} шт.",
        reply_markup=main_menu(),
    )
