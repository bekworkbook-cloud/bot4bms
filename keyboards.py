"""Клавиатуры бота: главное меню и инлайн-кнопки выбора товара."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import Product

# Тексты кнопок главного меню
BTN_ADD = "Добавить товар"
BTN_REMOVE = "Списать товар"
BTN_STOCK = "Остатки"
BTN_FIND = "Найти товар"
BTN_DELETE = "Удалить товар"
BTN_HISTORY = "История операций"

MENU_BUTTONS = (BTN_ADD, BTN_REMOVE, BTN_STOCK, BTN_FIND, BTN_DELETE, BTN_HISTORY)

PRODUCTS_PER_PAGE = 8
NOOP = "noop"  # кнопка-счётчик страниц, ничего не делает
_BUTTON_TEXT_LIMIT = 60


class ProductPick(CallbackData, prefix="pick"):
    action: str  # "remove" | "delete"
    product_id: int


class ProductPage(CallbackData, prefix="page"):
    action: str
    page: int


class DeleteConfirm(CallbackData, prefix="delc"):
    product_id: int
    confirm: bool


class CancelDialog(CallbackData, prefix="cancel"):
    pass


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_ADD), KeyboardButton(text=BTN_REMOVE)],
            [KeyboardButton(text=BTN_STOCK), KeyboardButton(text=BTN_FIND)],
            [KeyboardButton(text=BTN_DELETE), KeyboardButton(text=BTN_HISTORY)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выберите действие",
    )


def _short(text: str) -> str:
    return text if len(text) <= _BUTTON_TEXT_LIMIT else text[: _BUTTON_TEXT_LIMIT - 1] + "…"


def products_keyboard(products: list[Product], action: str, page: int = 0) -> InlineKeyboardMarkup:
    """Список товаров кнопками с постраничной навигацией."""
    pages = max(1, (len(products) + PRODUCTS_PER_PAGE - 1) // PRODUCTS_PER_PAGE)
    page = min(max(page, 0), pages - 1)
    chunk = products[page * PRODUCTS_PER_PAGE : (page + 1) * PRODUCTS_PER_PAGE]

    builder = InlineKeyboardBuilder()
    for p in chunk:
        builder.row(
            InlineKeyboardButton(
                text=_short(f"{p.display_name} — {p.quantity} шт."),
                callback_data=ProductPick(action=action, product_id=p.id).pack(),
            )
        )

    if pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(text="◀️", callback_data=ProductPage(action=action, page=page - 1).pack())
            )
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data=NOOP))
        if page < pages - 1:
            nav.append(
                InlineKeyboardButton(text="▶️", callback_data=ProductPage(action=action, page=page + 1).pack())
            )
        builder.row(*nav)

    builder.row(InlineKeyboardButton(text="Отмена", callback_data=CancelDialog().pack()))
    return builder.as_markup()


def delete_confirm_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да, удалить",
                    callback_data=DeleteConfirm(product_id=product_id, confirm=True).pack(),
                ),
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data=DeleteConfirm(product_id=product_id, confirm=False).pack(),
                ),
            ]
        ]
    )
