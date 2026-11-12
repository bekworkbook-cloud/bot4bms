"""Состояния пошаговых диалогов (FSM)."""

from aiogram.fsm.state import State, StatesGroup


class AddProduct(StatesGroup):
    name = State()
    quantity = State()


class RemoveProduct(StatesGroup):
    choose = State()
    quantity = State()


class DeleteProduct(StatesGroup):
    choose = State()
    confirm = State()


class SearchProduct(StatesGroup):
    query = State()
