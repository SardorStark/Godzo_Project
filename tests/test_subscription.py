from __future__ import annotations

from bot.subscription import is_member_status_subscribed


def test_subscribed_statuses() -> None:
    assert is_member_status_subscribed("member")
    assert is_member_status_subscribed("administrator")
    assert is_member_status_subscribed("creator")


def test_unsubscribed_statuses() -> None:
    assert not is_member_status_subscribed("left")
    assert not is_member_status_subscribed("kicked")
    assert not is_member_status_subscribed("restricted")
    assert not is_member_status_subscribed("unknown")
