"""Helpers for keeping case follow-ups action-oriented."""

from __future__ import annotations

from typing import Any


_ACTION_PREFIXES = (
    "collect ",
    "request ",
    "ask ",
    "obtain ",
    "upload ",
    "provide ",
    "verify ",
    "confirm ",
    "reconcile ",
    "resolve ",
    "finish ",
    "retry ",
    "replace ",
    "review ",
)
_NON_ACTION_PREFIXES = (
    "risk score",
    "final risk score",
    "income stability",
    "balance health",
    "obligation load",
    "spending discipline",
    "cash behavior",
    "risk penalty",
    "high dti",
    "extreme dti",
    "low dti",
    "moderate dti",
    "no verified",
    "weak balance",
    "heavy unverified",
    "poor liquidity",
    "expenses ",
    "emi load",
)


def is_action_followup(value: Any) -> bool:
    text = str(value or "").strip().lstrip("->* ").strip()
    if not text:
        return False
    lowered = text.lower()
    if lowered.startswith(_NON_ACTION_PREFIXES):
        return False
    return lowered.startswith(_ACTION_PREFIXES)


def filter_action_followups(values: list[Any] | None) -> list[str]:
    actions: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value or "").strip().lstrip("->* ").strip()
        if not text or not is_action_followup(text):
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        actions.append(text)
    return actions


__all__ = ["filter_action_followups", "is_action_followup"]
