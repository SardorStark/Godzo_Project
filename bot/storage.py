"""Excel storage for user registration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook, load_workbook

EXCEL_FILE = Path("data/users.xlsx")
HEADERS = (
    "user_id",
    "username",
    "full_name",
    "phone_number",
    "entered_name",
    "registered_at_utc",
)

_LOCK = asyncio.Lock()


@dataclass(frozen=True)
class UserRegistration:
    user_id: int
    username: str
    full_name: str
    phone_number: str
    entered_name: str


def _ensure_file() -> None:
    EXCEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    if EXCEL_FILE.exists():
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "users"
    ws.append(list(HEADERS))
    wb.save(EXCEL_FILE)
    wb.close()


def _find_row(ws, user_id: int) -> int | None:
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if row[0] == user_id:
            return idx
    return None


def _save_sync(item: UserRegistration) -> None:
    _ensure_file()
    wb = load_workbook(EXCEL_FILE)
    ws = wb.active
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    values = [
        item.user_id,
        item.username,
        item.full_name,
        item.phone_number,
        item.entered_name,
        now,
    ]
    row = _find_row(ws, item.user_id)
    if row is None:
        ws.append(values)
    else:
        for col, value in enumerate(values, start=1):
            ws.cell(row=row, column=col, value=value)
    wb.save(EXCEL_FILE)
    wb.close()


def _is_registered_sync(user_id: int) -> bool:
    _ensure_file()
    wb = load_workbook(EXCEL_FILE, read_only=True)
    ws = wb.active
    found = _find_row(ws, user_id) is not None
    wb.close()
    return found


async def save_registration(item: UserRegistration) -> None:
    async with _LOCK:
        await asyncio.to_thread(_save_sync, item)


async def is_registered(user_id: int) -> bool:
    async with _LOCK:
        return await asyncio.to_thread(_is_registered_sync, user_id)
