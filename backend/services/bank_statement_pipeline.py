"""
Bank statement analysis pipeline orchestration.

The heavy lifting now lives in smaller pipeline helpers so this module can
stay focused on the public API and stage orchestration.
"""

from typing import Any, Dict

from services.bank_statement_pipeline_metrics import (
    analyze_cash_behavior,
    compute_dti,
    deterministic_aggregate,
)
from services.bank_statement_pipeline_output import build_bank_statement_output
from services.bank_statement_pipeline_rules import apply_bank_statement_rule_engine
from services.bank_statement_pipeline_scoring import compute_risk_scores
from services.bank_statement_pipeline_types import statement_confidence_from_txns
from services.bank_statement_profile import extract_bank_statement_evidence_profile
from services.gemini_service import (
    classify_bank_transactions,
    extract_bank_transactions,
    generate_risk_explanation,
)


async def run_strict_bank_statement_pipeline(
    raw_text: str,
    document_type_hint: str = "bank_statement",
) -> Dict[str, Any]:
    evidence_profile = extract_bank_statement_evidence_profile(raw_text)
    print("[stage1] Extracting bank transactions (Gemini with local fallback)...")
    try:
        raw_transactions = await extract_bank_transactions(raw_text)
    except Exception as error:
        print(f"[stage1][error] {error}")
        return build_bank_statement_output(
            [],
            statement_confidence=0.0,
            document_type=document_type_hint,
            evidence_profile=evidence_profile,
        )

    if not isinstance(raw_transactions, list) or not raw_transactions:
        print("[stage1] No transactions extracted; returning REVIEW MANUALLY-safe output.")
        return build_bank_statement_output(
            [],
            statement_confidence=0.0,
            document_type=document_type_hint,
            evidence_profile=evidence_profile,
        )

    print("[stage2] Classifying transactions (Gemini with local fallback)...")
    try:
        classified_transactions = await classify_bank_transactions(raw_transactions)
    except Exception as error:
        print(f"[stage2][error] {error}")
        return build_bank_statement_output(
            raw_transactions,
            statement_confidence=statement_confidence_from_txns(raw_transactions),
            document_type=document_type_hint,
            evidence_profile=evidence_profile,
        )

    normalized_transactions = (
        classified_transactions if isinstance(classified_transactions, list) else raw_transactions
    )
    overall_confidence = statement_confidence_from_txns(normalized_transactions)

    print("[stage2.5] Applying deterministic rule engine corrections...")
    final_output = build_bank_statement_output(
        transactions=normalized_transactions,
        statement_confidence=overall_confidence,
        document_type=document_type_hint,
        evidence_profile=evidence_profile,
    )
    decision_payload = final_output.get("decision") or {}
    decision_verdict = (
        decision_payload.get("decision_status")
        if isinstance(decision_payload, dict)
        else final_output.get("decision")
    )

    print("[stage3] Aggregation + Stage4 DTI + Stage5 cash behavior + Stage6 risk scoring done.")
    print("[stage7] Final decision:", decision_verdict)

    try:
        print("[stage6] Generating explanation text via Gemini (non-math)...")
        transaction_insights = final_output.get("transaction_insights") or {}
        risk_findings = final_output.get("risk_findings") or {}
        reasoning = final_output.get("reasoning") or {}
        explanation = await generate_risk_explanation(
            {
                "risk_score": risk_findings.get("risk_score"),
                "dti": transaction_insights.get("dti"),
                "cash_behavior": transaction_insights.get("cash_behavior"),
                "risk_flags": risk_findings.get("flags"),
                "decision": decision_payload.get("decision_recommendation", decision_verdict)
                if isinstance(decision_payload, dict)
                else decision_verdict,
            }
        )
        if isinstance(explanation, list) and all(isinstance(item, str) for item in explanation) and explanation:
            reasoning["narrative"] = (reasoning.get("narrative") or []) + explanation
            final_output["reasoning"] = reasoning
    except Exception as error:
        print(f"[stage6] Explanation generation failed, keeping deterministic reasoning: {error}")

    return final_output


__all__ = [
    "analyze_cash_behavior",
    "apply_bank_statement_rule_engine",
    "build_bank_statement_output",
    "compute_dti",
    "compute_risk_scores",
    "deterministic_aggregate",
    "run_strict_bank_statement_pipeline",
]
