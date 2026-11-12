"""/start, /cancel, отмена кнопкой, нетекстовые сообщения и прочие «запасные» хендлеры."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ErrorEvent, Message

from keyboards import NOOP, CancelDialog, main_menu

from .utils import ERR_GENERIC, ERR_NOT_TEXT, drop_keyboard

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "Бот учёта товаров на складе.\n\n"
    "Кнопки меню:\n"
    "• Добавить товар — приход (если товар уже есть, количество прибавится)\n"
    "• Списать товар — расход, в минус уйти нельзя\n"
    "• Остатки — весь список (/list)\n"
    "• Найти товар — поиск по части названия (/find <запрос>)\n"
    "• Удалить товар — убрать позицию полностью\n"
    "• История операций — последние 20 действий (/history)\n\n"
    "/cancel — прервать текущий диалог."
)

# Роутер, который подключается первым: команды работают в любом состоянии.
entry = Router(name="common-entry")
# Роутер «после диалогов»: обрабатывает всё, что не подошло ни одному хендлеру.
fallback = Router(name="common-fallback")


@entry.message(CommandStart())
@entry.message(Command("help"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(HELP_TEXT, reply_markup=main_menu())


@entry.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    had_dialog = await state.get_state() is not None
    await state.clear()
    text = "Действие отменено." if had_dialog else "Нечего отменять."
    await message.answer(text, reply_markup=main_menu())


@entry.callback_query(CancelDialog.filter())
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Отменено")
    if isinstance(callback.message, Message):
        await drop_keyboard(callback.message, "Действие отменено.")
        await callback.message.answer("Выберите действие:", reply_markup=main_menu())


@entry.callback_query(F.data == NOOP)
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# Внутри любого диалога: на стикер, фото, голосовое и т.п. просим текст.
@entry.message(~StateFilter(None), ~F.text)
async def not_text_in_dialog(message: Message) -> None:
    await message.answer(ERR_NOT_TEXT)


@fallback.message(StateFilter(None))
async def outside_dialog(message: Message) -> None:
    if message.text and message.text.startswith("/"):
        text = "Неизвестная команда. Выберите действие в меню или отправьте /help."
    else:
        text = "Выберите действие в меню 👇"
    await message.answer(text, reply_markup=main_menu())


@fallback.message()
async def unexpected_in_dialog(message: Message) -> None:
    await message.answer("Ответьте на вопрос выше или отправьте /cancel, чтобы отменить.")


@fallback.callback_query()
async def stale_callback(callback: CallbackQuery) -> None:
    await callback.answer("Это меню устарело. Выберите действие заново.", show_alert=True)
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass


async def on_error(event: ErrorEvent) -> bool:
    logger.exception("Ошибка при обработке обновления %s", event.update.update_id, exc_info=event.exception)
    update = event.update
    try:
        if update.message:
            await update.message.answer(ERR_GENERIC)
        elif update.callback_query:
            await update.callback_query.answer(ERR_GENERIC, show_alert=True)
    except Exception:  # noqa: BLE001 — сообщить об ошибке не получилось, просто логируем
        logger.exception("Не удалось отправить сообщение об ошибке")
    return True

