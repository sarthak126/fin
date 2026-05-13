"""
Public facade for the bank statement underwriting engines.

The implementation now lives in focused modules so each engine can evolve
independently without turning this file back into a large monolith.
"""

from services.bank_statement_engine_behavior import compute_behavioral_flags
from services.bank_statement_engine_cashflow import compute_cashflow_intelligence
from services.bank_statement_engine_income import compute_income_engine
from services.bank_statement_engine_risk import compute_explainable_risk, compute_final_decision
from services.bank_statement_engine_spending import compute_spending_intelligence

__all__ = [
    "compute_behavioral_flags",
    "compute_cashflow_intelligence",
    "compute_explainable_risk",
    "compute_final_decision",
    "compute_income_engine",
    "compute_spending_intelligence",
]
