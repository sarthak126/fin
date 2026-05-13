from __future__ import annotations

import pytest

from services.bank_statement_local_parser import (
    classify_bank_transactions_locally,
    extract_bank_transactions_locally,
)
from services import gemini_service


SAMPLE_STATEMENT_TEXT = """
DATE     PARTICULARS    CHQ.NO.      WITHDRAWALS        DEPOSITS         BALANCE
--------------------------------------------------------------------------------
01-04-21 B/F                                                           23,039.51
03-04-21 TRTR/109314915 14915075       10,000.00                       13,039.51
        TRTR/109314915075/03-04-2021 14:22:58/FIT
03-04-21 Salary Credit ACME INFOTECH                  50,000.00       63,039.51
        NEFT/SALARY/APRIL
30-04-21 Loan Recovery                  6,751.00                       56,288.51
        Loan Recovery For04560600020456
Page Total:                          16,751.00       50,000.00       56,288.51Cr
"""


def test_extract_bank_transactions_locally_parses_multiline_statement_rows():
    transactions = extract_bank_transactions_locally(SAMPLE_STATEMENT_TEXT)

    assert len(transactions) == 4
    assert transactions[0]["date"] == "01-04-21"
    assert transactions[0]["balance"] == 23039.51
    assert transactions[1]["debit"] == 10000.0
    assert transactions[1]["credit"] is None
    assert "TRTR/109314915075/03-04-2021" in transactions[1]["description"]
    assert transactions[2]["credit"] == 50000.0
    assert transactions[2]["balance"] == 63039.51
    assert "NEFT/SALARY/APRIL" in transactions[2]["description"]
    assert transactions[3]["debit"] == 6751.0


def test_classify_bank_transactions_locally_uses_conservative_financial_rules():
    transactions = classify_bank_transactions_locally(
        extract_bank_transactions_locally(SAMPLE_STATEMENT_TEXT)
    )

    assert transactions[0]["category"] == "UNKNOWN"
    assert transactions[1]["category"] == "EXPENSE"
    assert transactions[2]["category"] == "VERIFIED_INCOME"
    assert transactions[3]["category"] == "EMI"
    assert transactions[2]["notes"]


def test_local_parser_keeps_fee_like_loan_transactions_out_of_emi():
    transactions = classify_bank_transactions_locally(
        [
            {
                "date": "01-04-21",
                "description": "Loan Processing Fee GST",
                "debit": 499.0,
                "credit": None,
                "balance": 23039.51,
            }
        ]
    )

    assert transactions[0]["category"] == "EXPENSE"


@pytest.mark.asyncio
async def test_gemini_bank_statement_helpers_fall_back_to_local_parser(monkeypatch):
    async def raise_provider_error(*args, **kwargs):
        raise RuntimeError("403 PERMISSION_DENIED")

    monkeypatch.setattr(
        gemini_service,
        "_call_gemini_json_with_validate_and_retry",
        raise_provider_error,
    )

    extracted = await gemini_service.extract_bank_transactions(SAMPLE_STATEMENT_TEXT)
    classified = await gemini_service.classify_bank_transactions(extracted)

    assert len(extracted) == 4
    assert classified[2]["category"] == "VERIFIED_INCOME"
    assert classified[3]["category"] == "EMI"
