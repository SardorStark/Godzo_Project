"""Shared data models for bot configuration and flows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RequiredChat:
    check_chat_id: str
    join_url: str
    label: str
