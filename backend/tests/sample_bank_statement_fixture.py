from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.bank_statement_local_parser import (
    classify_bank_transactions_locally,
    extract_bank_transactions_locally,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SHORT_HISTORY_SAMPLE_TEXT_PATH = FIXTURE_DIR / "bank_statement_short_history_sample.txt"
SHORT_HISTORY_SAMPLE_EXPECTED_PATH = FIXTURE_DIR / "bank_statement_short_history_expected.json"


def load_short_history_sample_text() -> str:
    return SHORT_HISTORY_SAMPLE_TEXT_PATH.read_text(encoding="utf-8")


def load_short_history_sample_expected() -> dict[str, Any]:
    return json.loads(SHORT_HISTORY_SAMPLE_EXPECTED_PATH.read_text(encoding="utf-8"))


def load_short_history_sample_transactions() -> list[dict[str, Any]]:
    return classify_bank_transactions_locally(
        extract_bank_transactions_locally(load_short_history_sample_text())
    )
