"""Настройки бота: читаются из файла .env (или переменных окружения)."""

import logging
import os
from dataclasses import dataclass
from datetime import tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Config:
    bot_token: str
    allowed_users: frozenset[int]
    db_path: Path
    timezone: tzinfo | None  # None — локальное время сервера


def _parse_allowed_users(raw: str) -> frozenset[int]:
    users: set[int] = set()
    for part in raw.replace(";", ",").replace(" ", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            users.add(int(part))
        except ValueError:
            raise SystemExit(f"ALLOWED_USERS: «{part}» — не число (нужен Telegram ID)")
    return frozenset(users)


def _parse_timezone(raw: str) -> tzinfo | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return ZoneInfo(raw)
    except (ZoneInfoNotFoundError, ValueError):
        raise SystemExit(f"TIMEZONE: неизвестный часовой пояс «{raw}» (пример: Europe/Moscow)")


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("Не задан BOT_TOKEN. Скопируйте .env.example в .env и укажите токен бота.")

    allowed = _parse_allowed_users(os.getenv("ALLOWED_USERS", ""))
    if not allowed:
        logger.warning("ALLOWED_USERS пуст — бот никому не будет отвечать, кроме «У вас нет доступа».")

    db_path = Path(os.getenv("DB_PATH", "").strip() or BASE_DIR / "data" / "sklad.db")
    if not db_path.is_absolute():
        db_path = BASE_DIR / db_path

    return Config(
        bot_token=token,
        allowed_users=allowed,
        db_path=db_path,
        timezone=_parse_timezone(os.getenv("TIMEZONE", "")),
    )
