"""Работа с базой данных SQLite.

Все изменения остатков выполняются внутри транзакции (BEGIN IMMEDIATE),
а записи в рамках процесса дополнительно сериализуются asyncio.Lock —
так одновременные действия нескольких пользователей не теряют данные.
"""

from __future__ import annotations

import asyncio
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

_SPACES_RE = re.compile(r"\s+")

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL UNIQUE,
    display_name TEXT    NOT NULL,
    quantity     INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    updated_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS operations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT    NOT NULL,
    user_id      INTEGER NOT NULL,
    user_name    TEXT    NOT NULL,
    delta        INTEGER NOT NULL,
    action       TEXT    NOT NULL CHECK (action IN ('add', 'remove', 'delete')),
    created_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_operations_created ON operations (created_at);
"""


def clean_name(text: str) -> str:
    """Убирает лишние пробелы: по краям и повторяющиеся внутри."""
    return _SPACES_RE.sub(" ", text).strip()


def normalize_name(text: str) -> str:
    """Нормализованное название для сравнения: без лишних пробелов и регистра."""
    return clean_name(text).casefold()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Product:
    id: int
    name: str
    display_name: str
    quantity: int
    updated_at: datetime


@dataclass(frozen=True)
class Operation:
    id: int
    product_name: str
    user_id: int
    user_name: str
    delta: int
    action: str
    created_at: datetime


@dataclass(frozen=True)
class AddResult:
    product: Product
    added: int
    created: bool


@dataclass(frozen=True)
class RemoveResult:
    """Результат списания. ok=False — не хватило остатка (product содержит текущий)."""

    ok: bool
    product: Product | None
    removed: int = 0


def _row_to_product(row: aiosqlite.Row) -> Product:
    return Product(
        id=row["id"],
        name=row["name"],
        display_name=row["display_name"],
        quantity=row["quantity"],
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _row_to_operation(row: aiosqlite.Row) -> Operation:
    return Operation(
        id=row["id"],
        product_name=row["product_name"],
        user_id=row["user_id"],
        user_name=row["user_name"],
        delta=row["delta"],
        action=row["action"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None
        self._write_lock = asyncio.Lock()

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("База данных не подключена")
        return self._conn

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None — транзакции управляются вручную (BEGIN/COMMIT).
        self._conn = await aiosqlite.connect(self.path, isolation_level=None)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA busy_timeout=5000")
        await self._conn.executescript(SCHEMA)

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
            except BaseException:
                await self.conn.execute("ROLLBACK")
                raise
            else:
                await self.conn.execute("COMMIT")

    @staticmethod
    async def _log_operation(
        conn: aiosqlite.Connection,
        product_name: str,
        user_id: int,
        user_name: str,
        delta: int,
        action: str,
        created_at: str,
    ) -> None:
        await conn.execute(
            "INSERT INTO operations (product_name, user_id, user_name, delta, action, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (product_name, user_id, user_name, delta, action, created_at),
        )

    # ---------- изменения ----------

    async def add_product(self, raw_name: str, quantity: int, user_id: int, user_name: str) -> AddResult:
        """Создаёт товар или прибавляет количество к существующему."""
        display_name = clean_name(raw_name)
        name = normalize_name(raw_name)
        now = _now()
        async with self._transaction() as conn:
            cur = await conn.execute("SELECT id FROM products WHERE name = ?", (name,))
            created = await cur.fetchone() is None
            cur = await conn.execute(
                "INSERT INTO products (name, display_name, quantity, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET quantity = quantity + excluded.quantity, "
                "updated_at = excluded.updated_at "
                "RETURNING *",
                (name, display_name, quantity, now),
            )
            product = _row_to_product(await cur.fetchone())
            await cur.close()
            await self._log_operation(conn, product.display_name, user_id, user_name, quantity, "add", now)
        return AddResult(product=product, added=quantity, created=created)

    async def remove_quantity(self, product_id: int, quantity: int, user_id: int, user_name: str) -> RemoveResult:
        """Списывает количество, не допуская ухода в минус."""
        now = _now()
        async with self._transaction() as conn:
            cur = await conn.execute(
                "UPDATE products SET quantity = quantity - ?, updated_at = ? "
                "WHERE id = ? AND quantity >= ? RETURNING *",
                (quantity, now, product_id, quantity),
            )
            row = await cur.fetchone()
            await cur.close()
            if row is None:
                cur = await conn.execute("SELECT * FROM products WHERE id = ?", (product_id,))
                current = await cur.fetchone()
                return RemoveResult(ok=False, product=_row_to_product(current) if current else None)
            product = _row_to_product(row)
            await self._log_operation(conn, product.display_name, user_id, user_name, -quantity, "remove", now)
        return RemoveResult(ok=True, product=product, removed=quantity)

    async def delete_product(self, product_id: int, user_id: int, user_name: str) -> Product | None:
        """Удаляет товар полностью. Возвращает удалённый товар или None, если его уже нет."""
        now = _now()
        async with self._transaction() as conn:
            cur = await conn.execute("DELETE FROM products WHERE id = ? RETURNING *", (product_id,))
            row = await cur.fetchone()
            await cur.close()
            if row is None:
                return None
            product = _row_to_product(row)
            await self._log_operation(conn, product.display_name, user_id, user_name, -product.quantity, "delete", now)
        return product

    # ---------- чтение ----------

    async def get_product(self, product_id: int) -> Product | None:
        cur = await self.conn.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = await cur.fetchone()
        await cur.close()
        return _row_to_product(row) if row else None

    async def list_products(self) -> list[Product]:
        # name хранится в нормализованном (нижнем) регистре — сортировка по алфавиту без учёта регистра.
        cur = await self.conn.execute("SELECT * FROM products ORDER BY name, id")
        rows = await cur.fetchall()
        await cur.close()
        return [_row_to_product(r) for r in rows]

    async def search_products(self, query: str) -> list[Product]:
        pattern = f"%{_escape_like(normalize_name(query))}%"
        cur = await self.conn.execute(
            "SELECT * FROM products WHERE name LIKE ? ESCAPE '\\' ORDER BY name, id", (pattern,)
        )
        rows = await cur.fetchall()
        await cur.close()
        return [_row_to_product(r) for r in rows]

    async def last_operations(self, limit: int = 20) -> list[Operation]:
        cur = await self.conn.execute("SELECT * FROM operations ORDER BY id DESC LIMIT ?", (limit,))
        rows = await cur.fetchall()
        await cur.close()
        return [_row_to_operation(r) for r in rows]
