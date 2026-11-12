"""3.5. Удалить товар."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import Database
from keyboards import (
    BTN_DELETE,
    DeleteConfirm,
    ProductPage,
    ProductPick,
    delete_confirm_keyboard,
    main_menu,
    products_keyboard,
)

from .states import DeleteProduct
from .utils import drop_keyboard, user_name

ACTION = "delete"
ASK_PRODUCT = "Выберите товар для удаления:"

entry = Router(name="delete-entry")
dialog = Router(name="delete-dialog")


@entry.message(F.text == BTN_DELETE)
@entry.message(Command("delete"))
async def start_delete(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    products = await db.list_products()
    if not products:
        await message.answer("Склад пуст, удалять нечего", reply_markup=main_menu())
        return
    await state.set_state(DeleteProduct.choose)
    await message.answer(ASK_PRODUCT, reply_markup=products_keyboard(products, ACTION))


@dialog.callback_query(DeleteProduct.choose, ProductPage.filter(F.action == ACTION))
async def change_page(callback: CallbackQuery, callback_data: ProductPage, db: Database) -> None:
    products = await db.list_products()
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(
            reply_markup=products_keyboard(products, ACTION, callback_data.page)
        )


@dialog.callback_query(DeleteProduct.choose, ProductPick.filter(F.action == ACTION))
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
                await drop_keyboard(callback.message, "Склад пуст, удалять нечего")
        return

    await callback.answer()
    await state.update_data(product_id=product.id)
    await state.set_state(DeleteProduct.confirm)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"Удалить «{product.display_name}» ({product.quantity} шт.) полностью?",
            reply_markup=delete_confirm_keyboard(product.id),
        )


@dialog.callback_query(DeleteProduct.confirm, DeleteConfirm.filter())
async def confirm_delete(
    callback: CallbackQuery, callback_data: DeleteConfirm, state: FSMContext, db: Database
) -> None:
    data = await state.get_data()
    if data.get("product_id") != callback_data.product_id:
        await callback.answer("Это меню устарело.", show_alert=True)
        return

    await state.clear()
    if not callback_data.confirm:
        await callback.answer("Отменено")
        text = "Удаление отменено."
    else:
        deleted = await db.delete_product(callback_data.product_id, callback.from_user.id, user_name(callback.from_user))
        await callback.answer()
        text = "Товар удалён" if deleted else "Этот товар уже был удалён."

    if isinstance(callback.message, Message):
        await drop_keyboard(callback.message, text)
        await callback.message.answer("Выберите действие:", reply_markup=main_menu())


@dialog.message(DeleteProduct.choose)
@dialog.message(DeleteProduct.confirm)
async def choose_by_text(message: Message) -> None:
    await message.answer("Выберите вариант кнопкой в сообщении выше или отправьте /cancel.")
