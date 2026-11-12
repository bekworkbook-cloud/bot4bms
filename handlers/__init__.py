"""Сборка всех хендлеров в один роутер.

Порядок важен:
1. entry-роутеры — команды и кнопки главного меню. У них нет фильтра по состоянию,
   поэтому нажатие кнопки меню посреди диалога отменяет текущий диалог и начинает новый.
2. dialog-роутеры — шаги пошаговых диалогов (FSM).
3. fallback — всё остальное (неизвестный ввод, устаревшие инлайн-кнопки).
"""

from aiogram import Router

from . import add, common, delete, history, remove, search, stock


def setup_routers() -> Router:
    root = Router(name="root")
    root.include_routers(
        common.entry,
        add.entry,
        remove.entry,
        stock.entry,
        search.entry,
        delete.entry,
        history.entry,
        add.dialog,
        remove.dialog,
        search.dialog,
        delete.dialog,
        common.fallback,
    )
    # Ошибки из любого вложенного роутера всплывают сюда.
    root.errors.register(common.on_error)
    return root
