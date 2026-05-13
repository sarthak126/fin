"""
Gemini Service — RAG-powered loan document analysis using Gemini 2.0 Flash.

Pipeline step: Upload → Extraction → Chunking → Vectors → [THIS] → Insights

Two capabilities:
  1. analyze_document() — Full structured analysis with JSON output
  2. ask_about_document() — Conversational Q&A ("Ask AI about this loan")
"""

import asyncio
import json
import re
from dataclasses import dataclass, field

from google import genai
from google.genai import types
from core.database import db as prisma_db
from services.bank_statement_local_parser import (
    classify_bank_transactions_locally,
    extract_bank_transactions_locally,
)
from core.config import get_settings
from services.document_analysis_local_fallback import build_local_analysis_fallback
from services.vector_service import retrieve_relevant_chunks
from typing import Any, Callable, Dict, List, Optional


_TRANSIENT_GEMINI_ERROR_MARKERS = (
    "RESOURCE_EXHAUSTED",
    "UNAVAILABLE",
    "DEADLINE_EXCEEDED",
    "INTERNAL",
    "429",
    "500",
    "503",
)


def _is_transient_gemini_error(error: Exception) -> bool:
    message = str(error).upper()
    return any(marker in message for marker in _TRANSIENT_GEMINI_ERROR_MARKERS)


def _retry_delay_seconds(error: Exception, attempt: int) -> float:
    match = re.search(r"retry in ([0-9.]+)s", str(error), flags=re.IGNORECASE)
    if match:
        try:
            return min(float(match.group(1)), 8.0)
        except ValueError:
            pass
    return min(2.0 * (attempt + 1), 8.0)


async def _generate_content_with_retry(
    client: genai.Client,
    *,
    model: str,
    contents,
    config: types.GenerateContentConfig | None = None,
    retries: int = 2,
):
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return await asyncio.to_thread(
                client.models.generate_content,
                model=model,
                contents=contents,
                config=config,
            )
        except Exception as error:
            last_error = error
            if attempt == retries or not _is_transient_gemini_error(error):
                raise
            delay_seconds = _retry_delay_seconds(error, attempt)
            print(
                "[warn] Gemini request failed with a transient provider error; "
                f"retrying in {delay_seconds:.1f}s ({error})"
            )
            await asyncio.sleep(delay_seconds)

    raise RuntimeError(f"Gemini request failed after retries: {last_error}")


# ────────────────────────────────────────
# System Prompts
# ────────────────────────────────────────

ANALYSIS_SYSTEM_PROMPT = """You are LoanLens AI — an expert financial document analyst for the Indian lending market.

You analyze loan-related documents (bank statements, salary slips, ITRs, employment letters, loan agreements) and produce structured risk assessments.

TASK: Analyze the provided document text and return a JSON object with the following fields.

REQUIRED OUTPUT FORMAT (strict JSON, no markdown, no commentary):
{
  "applicant_name": <string or null>,
  "interest_rate": <number or null>,
  "processing_fee": <number or null>,
  "loan_amount": <number or null>,
  "tenure_months": <number or null>,
  "monthly_income": <number or null>,
  "annual_income": <number or null>,
  "monthly_expenses": <number or null>,
  "debt_to_income_ratio": <number or null>,
  "employment_type": <string: "salaried" | "self_employed" | "business" | null>,
  "employment_tenure_years": <number or null>,
  "employer_name": <string or null>,
  "avg_monthly_balance": <number or null>,
  "min_balance_6m": <number or null>,
  "existing_emis": <number or null>,
  "credit_utilization_pct": <number or null>,
  "penalty_clauses": [
    {"type": <string>, "amount": <number or null>, "description": <string>}
  ],
  "hidden_charges": [
    {"name": <string>, "amount": <number or null>, "description": <string>}
  ],
  "risk_score": <integer 0-100>,
  "risk_reasoning": <string explaining the risk score>,
  "risk_alerts": [
    {
      "severity": <"high" | "medium" | "low">,
      "message": <short alert title>,
      "field": <which field this relates to>,
      "details": <detailed explanation>
    }
  ],
  "recommendation": <"approve" | "review" | "reject">,
  "summary": <2-3 sentence executive summary of the document and findings>,
  "document_type_detected": <string describing what type of document this appears to be>,
  "confidence_notes": <string noting any data quality issues, missing info, or uncertainties>
}

ANALYSIS RULES:
- Extract ALL available financial data points from the text.
- When a salary slip, tax return, or other income document explicitly names the
  employee / assessee / applicant, extract that into `applicant_name`.
- For Indian currency, values should be in INR (₹). Report as plain numbers without currency symbols.
- If a field is not present in the document, set it to null. Do NOT fabricate data.
- Risk score calculation guidelines:
  * Interest rate > 12% → higher risk
  * Late payment penalty > ₹500 → higher risk
  * Prepayment penalty exists → moderate risk
  * DTI ratio > 35% → higher risk
  * Low average balance relative to income → moderate risk
  * Employment tenure < 1 year → moderate risk
  * Multiple hidden charges → higher risk
- recommendation: "approve" (risk < 40), "review" (40-70), "reject" (> 70)
- Be thorough in identifying hidden charges, penalty clauses, and unfavorable terms.
- The summary should be written for a loan underwriter — professional and actionable.

Return ONLY the JSON object. No markdown code blocks, no explanation text."""


ASK_AI_SYSTEM_PROMPT = """You are LoanLens AI — an expert financial document analyst.

The user has uploaded a loan-related document and wants to ask questions about it.
You have access to relevant sections of the document below.

RULES:
- Answer based ONLY on the provided document context.
- If the answer is not in the context, say "I couldn't find that information in this document."
- Be specific and cite relevant numbers, clauses, or sections.
- Use clear, professional language suitable for a loan underwriter.
- Keep answers concise but thorough.
- For financial figures, always specify the currency (INR/₹).
"""

STAGE1_EXTRACTION_PROMPT = """You are a fintech OCR normalization and transaction extraction engine.
Input: Raw OCR bank statement text.
Tasks: Normalize noise, detect transaction lines, extract fields.
Output: Strict JSON array of objects.

JSON schema per object:
{
  "date": "YYYY-MM-DD or raw format if unclear",
  "description": "Cleaned transaction description",
  "debit": <number or null>,
  "credit": <number or null>,
  "balance": <number or null>,
  "confidence": <"high" | "medium" | "low">,
  "source_line": "Original OCR line for reference"
}

Rules:
- If a value is unreadable, leave it null.
- Do not infer or hallucinate values or dates if unclear.
- Handle merged numbers and OCR swaps (O vs 0) responsibly.
- Return ONLY the JSON array.
"""

STAGE2_CLASSIFICATION_PROMPT = """You are a fintech transaction classification engine.
Input: JSON array of structured bank transactions.
Task: Classify each transaction into one of the following categories strictly:
- VERIFIED_INCOME (Salary, payroll, recurring employer credits)
- UNVERIFIED_CREDIT (Unknown credits, random credits, cash deposits)
- EXPENSE (Rent, bills, food, shopping, etc.)
- EMI (Loan repayment, installments)
- CASH_FLOW (ATM withdrawals, cash withdrawals, self-transfers)
- PENALTY (Bank fees, bounce charges, late fees, low balance charges)
- SUSPICIOUS (Circular transfers, duplicated, fraud-like)
- UNKNOWN

Rules:
- ATM/Cash withdrawal is CASH_FLOW, never EXPENSE.
- Cash deposit is UNVERIFIED_CREDIT or CASH_FLOW, never VERIFIED_INCOME.
- Reversals/Refunds can be marked as UNKNOWN or UNVERIFIED_CREDIT.
- Return EXACTLY the same JSON array provided, but add two new keys to each object: "category" (string) and "notes" (string explaining reasoning).
- Keep all original fields intact.
- Return ONLY the JSON array.
"""

# Stricter prompts used for the second retry to reduce schema drift.
STAGE1_EXTRACTION_PROMPT_STRICT = """You are a fintech OCR normalization and transaction extraction engine.
Return ONLY strict JSON with NO markdown.

STRICT JSON array schema per object (MUST match exactly):
{
  "date": string,
  "description": string,
  "debit": number|null,
  "credit": number|null,
  "balance": number|null,
  "confidence": "high"|"medium"|"low",
  "source_line": string|null
}

Rules:
- If a value is unclear, use null (never fabricate).
- Ensure debit/credit/balance are numbers or null.
- Return ONLY the JSON array."""

STAGE2_CLASSIFICATION_PROMPT_STRICT = """You are a fintech transaction classification engine.
Return ONLY strict JSON with NO markdown.

STRICT JSON array schema per object:
For each object, the response MUST include:
- category in ["VERIFIED_INCOME","UNVERIFIED_CREDIT","EXPENSE","EMI","CASH_FLOW","PENALTY","SUSPICIOUS","UNKNOWN"]
- notes as a string

Rules:
- Do not remove existing keys from the input objects.
- Keep all original fields intact.
- Return ONLY the JSON array."""


# ────────────────────────────────────────
# Analysis
# ────────────────────────────────────────

@dataclass
class GeminiAnalysisResult:
    raw_json: dict = field(default_factory=dict)
    success: bool = False
    error: str = ""
    model_used: str = ""


def _local_analysis_result(
    full_text: str,
    document_type: str,
    reason: str,
) -> GeminiAnalysisResult | None:
    fallback = build_local_analysis_fallback(full_text, document_type)
    if not fallback:
        return None

    print(
        "[fallback] Using deterministic local analysis for "
        f"{fallback.document_type}: {reason}"
    )
    return GeminiAnalysisResult(
        raw_json=fallback.raw_json,
        success=True,
        model_used=fallback.model_used,
    )


async def analyze_document(
    document_id: str,
    full_text: str,
    document_type: str = "",
    use_rag: bool = True,
) -> GeminiAnalysisResult:
    """
    Run full structured analysis on a document using Gemini.
    
    If use_rag=True, retrieves relevant chunks for key analysis queries.
    If the document is small enough, sends the full text directly.
    """
    settings = get_settings()
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    try:
        # Build context
        if use_rag and len(full_text) > 8000:
            # For large documents, use RAG — retrieve relevant chunks for key queries
            analysis_queries = [
                "interest rate and loan terms",
                "income salary and employment details",
                "penalties hidden charges and fees",
                "repayment schedule EMI details",
                "risk factors and red flags",
                "credit history and existing debts",
            ]
            
            all_relevant = []
            seen_texts = set()
            for query in analysis_queries:
                chunks = retrieve_relevant_chunks(document_id, query, top_k=3)
                for chunk in chunks:
                    if chunk["text"] not in seen_texts:
                        seen_texts.add(chunk["text"])
                        all_relevant.append(chunk)
            
            if all_relevant:
                # Build context from relevant chunks
                context_parts = []
                for chunk in all_relevant:
                    section = chunk.get("section_title", "")
                    prefix = f"[Section: {section}] " if section else ""
                    context_parts.append(f"{prefix}{chunk['text']}")
                document_context = "\n\n---\n\n".join(context_parts)
            else:
                document_context = full_text
        else:
            # Small enough to send full text
            document_context = full_text

        doc_type_hint = (document_type or "").strip().lower()
        type_guidance = {
            "bank_statement": "This is a BANK STATEMENT. Prioritize: salary/income credits, average balance, min balance, cash deposits, bounced/returned payments, EMI/NACH debits, overdraft usage, and expense patterns. If you infer DTI, be explicit about assumptions.",
            "salary_slip": "This is a SALARY SLIP/PAYSLIP. Prioritize: net pay, gross pay, deductions (PF/ESI/tax), employer name, pay period, and consistency. Treat missing banking behavior fields as null.",
            "tax_return": "This is an ITR/TAX RETURN. Prioritize: declared income, business/profession indicators, inconsistencies, and income stability. Do not invent EMI or bank balance fields if not present.",
            "employment_letter": "This is an EMPLOYMENT/OFFER LETTER. Prioritize: employment type, tenure/start date, compensation, employer details, and contractual risks. Most financial fields may be null.",
            "income_proof": "This is an INCOME PROOF document. Prioritize: recurring income evidence, amount, frequency, payer/employer, and confidence notes about completeness.",
            "id_document": "This is an ID DOCUMENT. Prioritize: identity fields if present, but set financial fields to null and keep risk score conservative with clear confidence notes.",
            "other": "Document type is OTHER. Use best-effort extraction; be explicit in confidence_notes about what could not be reliably derived.",
            "": "Document type is unknown. First infer document type, then apply the appropriate extraction focus.",
        }.get(doc_type_hint, "Document type is unknown. First infer document type, then apply the appropriate extraction focus.")

        # Call Gemini
        prompt = f"""Analyze this financial document.

DOCUMENT TYPE (user-provided): {doc_type_hint or "unknown"}
TYPE-SPECIFIC GUIDANCE: {type_guidance}

--- DOCUMENT START ---
{document_context}
--- DOCUMENT END ---

Return the structured JSON analysis as specified."""

        response = await _generate_content_with_retry(
            client,
            model=settings.GEMINI_MODEL,
            contents=[ANALYSIS_SYSTEM_PROMPT, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=8192,
            ),
        )

        if not response.text:
            fallback_result = _local_analysis_result(
                full_text,
                document_type,
                "Gemini returned an empty response",
            )
            if fallback_result:
                return fallback_result
            return GeminiAnalysisResult(
                success=False,
                error="Gemini returned empty response",
                model_used=settings.GEMINI_MODEL,
            )

        # Strip markdown if present
        text = response.text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # Parse JSON response
        raw_json = json.loads(text)

        return GeminiAnalysisResult(
            raw_json=raw_json,
            success=True,
            model_used=settings.GEMINI_MODEL,
        )

    except json.JSONDecodeError as e:
        fallback_result = _local_analysis_result(
            full_text,
            document_type,
            f"Gemini JSON parsing failed: {e}",
        )
        if fallback_result:
            return fallback_result
        return GeminiAnalysisResult(
            success=False,
            error=f"Failed to parse Gemini JSON output: {str(e)}",
            model_used=settings.GEMINI_MODEL,
        )
    except Exception as e:
        fallback_result = _local_analysis_result(
            full_text,
            document_type,
            f"Gemini analysis request failed: {e}",
        )
        if fallback_result:
            return fallback_result
        return GeminiAnalysisResult(
            success=False,
            error=f"Gemini analysis failed: {str(e)}",
            model_used=settings.GEMINI_MODEL,
        )


def _safe_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _coerce_amount(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _format_inr(value: Any) -> str | None:
    amount = _coerce_amount(value)
    if amount is None:
        return None
    if float(amount).is_integer():
        return f"INR {amount:,.0f}"
    return f"INR {amount:,.2f}"


def _format_ratio_pct(value: Any) -> str | None:
    ratio = _coerce_amount(value)
    if ratio is None:
        return None
    if ratio <= 1:
        ratio *= 100
    return f"{ratio:.1f}%"


def _trim_list(value: Any, limit: int) -> Any:
    if isinstance(value, list):
        return value[:limit]
    return value


def _question_keywords(question: str) -> set[str]:
    stopwords = {
        "about",
        "after",
        "and",
        "are",
        "can",
        "did",
        "does",
        "for",
        "from",
        "have",
        "how",
        "into",
        "loan",
        "show",
        "that",
        "the",
        "this",
        "there",
        "were",
        "what",
        "when",
        "where",
        "which",
        "with",
        "would",
        "your",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]{3,}", question.lower())
        if token not in stopwords
    }


def _select_relevant_transactions(
    transactions: Any,
    question: str,
    limit: int = 8,
) -> list[dict[str, Any]]:
    if not isinstance(transactions, list):
        return []

    keywords = _question_keywords(question)
    lowered_question = question.lower()
    category_hints = {
        "salary": {"VERIFIED_INCOME"},
        "income": {"VERIFIED_INCOME", "UNVERIFIED_CREDIT"},
        "credit": {"VERIFIED_INCOME", "UNVERIFIED_CREDIT"},
        "emi": {"EMI"},
        "obligation": {"EMI"},
        "penalty": {"PENALTY"},
        "charge": {"PENALTY"},
        "bounce": {"PENALTY"},
        "cash": {"CASH_FLOW", "UNVERIFIED_CREDIT"},
        "atm": {"CASH_FLOW"},
        "withdraw": {"CASH_FLOW"},
        "deposit": {"UNVERIFIED_CREDIT", "CASH_FLOW"},
        "expense": {"EXPENSE"},
        "spend": {"EXPENSE"},
        "suspicious": {"SUSPICIOUS"},
        "duplicate": {"SUSPICIOUS"},
    }

    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, raw_txn in enumerate(transactions):
        if not isinstance(raw_txn, dict):
            continue
        txn = dict(raw_txn)
        searchable_fields = " ".join(
            str(txn.get(field, "")).lower()
            for field in ("date", "description", "category", "notes")
        )
        description = str(txn.get("description", "")).lower()
        category = str(txn.get("category", "")).upper()

        score = 0
        for keyword in keywords:
            if keyword in searchable_fields:
                score += 3 if keyword in description else 1

        for hint, categories in category_hints.items():
            if hint in lowered_question and category in categories:
                score += 4

        if score > 0:
            scored.append((score, index, txn))

    if not scored:
        return [dict(txn) for txn in transactions[:limit] if isinstance(txn, dict)]

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [txn for _, _, txn in scored[:limit]]


async def _load_saved_analysis_payload(document_id: str) -> tuple[Any | None, dict[str, Any]]:
    try:
        analysis = await prisma_db.analysis.find_first(
            where={"document_id": document_id},
            order={"created_at": "desc"},
        )
    except Exception as error:
        print(f"[warn] Failed to load saved analysis for Ask AI fallback: {error}")
        return None, {}

    if not analysis:
        return None, {}

    payload = _safe_json_object(getattr(analysis, "raw_response", None))
    if not payload:
        payload = _safe_json_object(getattr(analysis, "extracted_fields", None))
    if not payload:
        return analysis, {}

    if getattr(analysis, "summary", None) and "summary" not in payload:
        payload["summary"] = analysis.summary
    if getattr(analysis, "recommendation", None) and "recommendation" not in payload:
        payload["recommendation"] = analysis.recommendation
    if getattr(analysis, "risk_score", None) is not None and "risk_score" not in payload:
        payload["risk_score"] = analysis.risk_score
    if getattr(analysis, "model_used", None) and "model_used" not in payload:
        payload["model_used"] = analysis.model_used

    return analysis, payload


def _build_saved_analysis_context(
    analysis: Any,
    payload: dict[str, Any],
    question: str,
) -> tuple[str, list[dict[str, Any]]]:
    context_payload = json.loads(json.dumps(payload))
    transactions = context_payload.pop("transactions", [])

    context_payload["riskFlags"] = _trim_list(context_payload.get("riskFlags"), 10)
    context_payload["reasoning"] = _trim_list(context_payload.get("reasoning"), 8)
    context_payload["uncertaintyNotes"] = _trim_list(context_payload.get("uncertaintyNotes"), 6)

    risk_findings = context_payload.get("risk_findings")
    if isinstance(risk_findings, dict):
        risk_findings["flags"] = _trim_list(risk_findings.get("flags"), 10)
        risk_findings["alerts"] = _trim_list(risk_findings.get("alerts"), 8)
        behavioral_flags = risk_findings.get("behavioral_flags")
        if isinstance(behavioral_flags, dict):
            behavioral_flags["flag_details"] = _trim_list(behavioral_flags.get("flag_details"), 8)

    reasoning_payload = context_payload.get("reasoning")
    if isinstance(reasoning_payload, dict):
        reasoning_payload["narrative"] = _trim_list(reasoning_payload.get("narrative"), 8)
        reasoning_payload["analysis_limitations"] = _trim_list(
            reasoning_payload.get("analysis_limitations"),
            6,
        )

    behavioral_flags = context_payload.get("behavioralFlags")
    if isinstance(behavioral_flags, dict):
        behavioral_flags["flag_details"] = _trim_list(behavioral_flags.get("flag_details"), 8)

    transaction_insights = context_payload.get("transaction_insights")
    if isinstance(transaction_insights, dict):
        income_engine = transaction_insights.get("income_engine")
        if isinstance(income_engine, dict):
            income_engine["income_sources"] = _trim_list(income_engine.get("income_sources"), 8)

    income_engine = context_payload.get("incomeEngine")
    if isinstance(income_engine, dict):
        income_engine["income_sources"] = _trim_list(income_engine.get("income_sources"), 8)

    sources = [{"section_title": "Structured Analysis", "page_num": 0}]
    context_sections = [
        "SAVED STRUCTURED ANALYSIS\n" + json.dumps(context_payload, indent=2)
    ]

    summary = payload.get("summary") or getattr(analysis, "summary", None)
    if summary:
        context_sections.insert(0, f"EXECUTIVE SUMMARY\n{summary}")
        sources.insert(0, {"section_title": "Executive Summary", "page_num": 0})

    selected_transactions = _select_relevant_transactions(transactions, question)
    if selected_transactions:
        context_sections.append(
            "RELEVANT TRANSACTIONS\n" + json.dumps(selected_transactions, indent=2)
        )
        sources.append({"section_title": "Relevant Transactions", "page_num": 0})

    return "\n\n---\n\n".join(context_sections), sources


def _answer_from_saved_analysis_locally(question: str, payload: dict[str, Any]) -> str:
    lowered_question = question.lower()
    decision_payload = payload.get("decision") or {}
    decision = (
        decision_payload.get("decision_recommendation")
        if isinstance(decision_payload, dict)
        else payload.get("recommendation")
    ) or payload.get("recommendation")
    transaction_insights = payload.get("transaction_insights") or {}
    risk_findings = payload.get("risk_findings") or {}
    reasoning_payload = payload.get("reasoning") or {}
    risk_score = (
        _coerce_amount((risk_findings.get("risk_score") or {}).get("final_score"))
        or _coerce_amount((payload.get("riskScore") or {}).get("finalScore"))
        or _coerce_amount(payload.get("risk_score"))
    )

    balance = transaction_insights.get("balance") or payload.get("balance") or {}
    expenses = transaction_insights.get("expenses") or payload.get("expenses") or {}
    income = transaction_insights.get("income") or payload.get("income") or {}
    cash_flow = transaction_insights.get("cash_flow") or payload.get("cashFlow") or {}
    income_engine = transaction_insights.get("income_engine") or payload.get("incomeEngine") or {}
    dti = transaction_insights.get("dti") or payload.get("dti") or {}

    if "average balance" in lowered_question or "avg balance" in lowered_question:
        avg_balance = _format_inr(balance.get("average") or payload.get("avg_monthly_balance"))
        min_balance = _format_inr(balance.get("min") or payload.get("min_balance_6m"))
        if avg_balance:
            answer = f"The saved analysis shows an average balance of {avg_balance}"
            if min_balance:
                answer += f" and a minimum balance of {min_balance}."
            else:
                answer += "."
            if risk_score is not None:
                answer += f" The current risk score is {risk_score:.0f}/100."
            return answer

    if "minimum balance" in lowered_question or "min balance" in lowered_question:
        min_balance = _format_inr(balance.get("min") or payload.get("min_balance_6m"))
        if min_balance:
            return f"The saved analysis shows a minimum balance of {min_balance}."

    if any(token in lowered_question for token in ("salary", "monthly income", "income pattern", "income")):
        monthly_income = _format_inr(
            income.get("verified_monthly_estimate")
            or income.get("monthly_estimate")
            or income.get("verified")
            or payload.get("monthly_income")
        )
        unverified_range = income.get("unverified_monthly_inflow_range")
        unverified_display = None
        if isinstance(unverified_range, dict):
            low = _format_inr(unverified_range.get("min"))
            high = _format_inr(unverified_range.get("max"))
            if low and high:
                unverified_display = low if low == high else f"{low}-{high}"
        unverified_income = _format_inr(
            income_engine.get("monthly_income_estimate") if unverified_display is None else None
        )
        if unverified_display is not None:
            unverified_income = unverified_display
        annual_income = _format_inr(income.get("annual_estimate") or payload.get("annual_income"))
        income_type = income.get("income_type") or income_engine.get("income_type") or payload.get("employment_type")
        if monthly_income or annual_income or unverified_income:
            answer = "The saved analysis indicates "
            if monthly_income:
                answer += f"verified monthly income of about {monthly_income}"
            elif unverified_income:
                answer += f"unverified monthly inflows of about {unverified_income}"
            if annual_income:
                answer += f"{' and ' if monthly_income or unverified_income else ''}annual income of about {annual_income}"
            if income_type:
                answer += f", with the income profile classified as {str(income_type).replace('_', ' ')}"
            answer += "."
            return answer

    if any(token in lowered_question for token in ("emi", "obligation", "dti", "debt-to-income", "debt to income")):
        emi = _format_inr(expenses.get("emi") or payload.get("existing_emis"))
        dti_pct = _format_ratio_pct(dti.get("value") or payload.get("debt_to_income_ratio"))
        dti_reliability = str(dti.get("reliability") or "").strip().lower()
        parts: list[str] = []
        if emi:
            parts.append(f"existing EMI obligations of about {emi}")
        if dti_pct:
            if dti_reliability and dti_reliability != "verified":
                parts.append(f"a debt-to-income ratio of roughly {dti_pct}, not reliable without verified income")
            else:
                parts.append(f"a debt-to-income ratio of roughly {dti_pct}")
        if parts:
            return "The saved analysis shows " + " and ".join(parts) + "."

    if any(token in lowered_question for token in ("cash", "withdraw", "deposit")):
        withdrawals = _format_inr(cash_flow.get("withdrawals"))
        deposits = _format_inr(cash_flow.get("deposits"))
        parts: list[str] = []
        if withdrawals:
            parts.append(f"cash withdrawals of about {withdrawals}")
        if deposits:
            parts.append(f"cash deposits of about {deposits}")
        if parts:
            return "The saved analysis records " + " and ".join(parts) + "."

    if any(token in lowered_question for token in ("alert", "flag", "issue", "concern", "risk")):
        alerts = risk_findings.get("flags") or payload.get("riskFlags")
        if isinstance(alerts, list) and alerts:
            return "The main saved risk flags are: " + "; ".join(str(flag) for flag in alerts[:5]) + "."

    if any(token in lowered_question for token in ("decision", "recommend", "approve", "reject", "review")):
        if decision:
            answer = f"The saved analysis recommendation is {str(decision)}"
            if risk_score is not None:
                answer += f" with a risk score of {risk_score:.0f}/100"
            answer += "."
            return answer

    matched_transactions = _select_relevant_transactions(payload.get("transactions"), question, limit=3)
    if matched_transactions:
        formatted_transactions = []
        for transaction in matched_transactions:
            parts = [
                str(transaction.get("date") or "unknown date"),
                str(transaction.get("description") or "transaction"),
            ]
            credit = _format_inr(transaction.get("credit"))
            debit = _format_inr(transaction.get("debit"))
            if credit:
                parts.append(f"credit {credit}")
            if debit:
                parts.append(f"debit {debit}")
            category = transaction.get("category")
            if category:
                parts.append(f"category {category}")
            formatted_transactions.append(", ".join(part for part in parts if part))
        return "The closest matching saved transactions are: " + " | ".join(formatted_transactions) + "."

    summary = reasoning_payload.get("summary") or payload.get("summary")
    if summary:
        return f"Based on the saved analysis, {summary}"

    return (
        "I found saved structured analysis for this document, but not enough "
        "detail to answer that question confidently without the original chunk context."
    )


async def _answer_from_saved_analysis(document_id: str, question: str) -> dict | None:
    analysis, payload = await _load_saved_analysis_payload(document_id)
    if not analysis or not payload:
        return None

    context, sources = _build_saved_analysis_context(analysis, payload, question)
    settings = get_settings()
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    prompt = f"""{ASK_AI_SYSTEM_PROMPT}

You are answering from a saved structured analysis and matched transactions for a previously analyzed document.
Treat these saved analysis results as the source of truth. If the answer is still not present, say so clearly.

--- SAVED ANALYSIS CONTEXT ---
{context}
--- END CONTEXT ---

User Question: {question}

Answer:"""

    try:
        response = await _generate_content_with_retry(
            client,
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2),
        )
        answer = response.text.strip() if response.text else ""
    except Exception as error:
        print(f"[warn] Ask AI fallback generation failed; using local saved-analysis answer: {error}")
        answer = ""

    if not answer:
        answer = _answer_from_saved_analysis_locally(question, payload)

    return {
        "answer": answer,
        "sources": sources,
    }


# ────────────────────────────────────────
# Ask AI (Conversational Q&A)
# ────────────────────────────────────────

async def ask_about_document(
    document_id: str,
    question: str,
    top_k: int = 5,
) -> dict:
    """
    Answer a user's question about a specific document using RAG.
    
    Returns { answer, sources: [{ section_title, page_num }] }
    """
    try:
        relevant_chunks = retrieve_relevant_chunks(document_id, question, top_k=top_k)
    except Exception as error:
        print(f"[warn] Vector retrieval failed for Ask AI; falling back to saved analysis: {error}")
        relevant_chunks = []

    if not relevant_chunks:
        saved_analysis_result = await _answer_from_saved_analysis(document_id, question)
        if saved_analysis_result:
            return saved_analysis_result
        return {
            "answer": "I couldn't find any relevant information in this document to answer your question.",
            "sources": [],
        }

    # Build context
    context_parts = []
    sources = []
    for chunk in relevant_chunks:
        section = chunk.get("section_title", "Unknown Section")
        page = chunk.get("page_num", 0)
        context_parts.append(f"[Section: {section}, Page: {page}]\n{chunk['text']}")
        sources.append({"section_title": section, "page_num": page})

    context = "\n\n---\n\n".join(context_parts)

    prompt = f"""{ASK_AI_SYSTEM_PROMPT}

--- DOCUMENT CONTEXT ---
{context}
--- END CONTEXT ---

User Question: {question}

Answer:"""

    try:
        settings = get_settings()
        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        response = await _generate_content_with_retry(
            client,
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3),
        )
        answer = response.text.strip() if response.text else "Unable to generate an answer."
    except Exception as e:
        answer = f"Sorry, I encountered an error while analyzing: {str(e)}"

    return {
        "answer": answer,
        "sources": sources,
    }

# ────────────────────────────────────────
# Bank Statement Specific Pipeline Methods
# ────────────────────────────────────────

async def _call_gemini_json_with_retry(system_prompt: str, user_prompt: str, retries: int = 1) -> list | dict:
    settings = get_settings()
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    
    for attempt in range(retries + 1):
        try:
            response = await _generate_content_with_retry(
                client,
                model=settings.GEMINI_MODEL,
                contents=[system_prompt, user_prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                    max_output_tokens=8192,
                ),
                retries=1,
            )
            if not response.text:
                raise ValueError("Empty response from Gemini")
            return json.loads(response.text)
        except (json.JSONDecodeError, ValueError) as e:
            if attempt == retries:
                raise RuntimeError(f"Failed to parse Gemini JSON after {retries} retries: {e}")
            print(f"[warn] Gemini JSON parse failed, retrying... ({e})")
        except Exception as e:
            if attempt == retries:
                raise RuntimeError(f"Gemini API error: {e}")
            print(f"[warn] Gemini API exception, retrying... ({e})")
    
    return []


def _validate_extracted_transaction(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    required_keys = ["date", "description", "debit", "credit", "balance", "confidence", "source_line"]
    for k in required_keys:
        if k not in obj:
            return False
    if not isinstance(obj["date"], str):
        return False
    if not isinstance(obj["description"], str):
        return False
    conf = obj.get("confidence")
    if isinstance(conf, str):
        conf_l = conf.strip().lower()
        if conf_l not in {"high", "medium", "low"}:
            return False
    else:
        return False
    for key in ["debit", "credit", "balance"]:
        v = obj.get(key)
        if v is None:
            continue
        if isinstance(v, (int, float)):
            continue
        if isinstance(v, str):
            # Allow numeric strings; downstream code will coerce safely.
            try:
                float(v.replace(",", "").strip())
                continue
            except Exception:
                return False
        return False
    src = obj.get("source_line")
    if src is not None and not isinstance(src, str):
        return False
    return True


def _validate_classified_transaction(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    if "category" not in obj or "notes" not in obj:
        return False
    allowed = {
        "VERIFIED_INCOME",
        "UNVERIFIED_CREDIT",
        "EXPENSE",
        "EMI",
        "CASH_FLOW",
        "PENALTY",
        "SUSPICIOUS",
        "UNKNOWN",
    }
    cat = obj.get("category")
    if not isinstance(cat, str):
        return False
    if cat.strip().upper() not in allowed:
        return False
    if not isinstance(obj["notes"], str):
        return False
    return True


async def _call_gemini_json_with_validate_and_retry(
    system_prompt: str,
    strict_system_prompt: str,
    user_prompt: str,
    validate_fn: Callable[[Any], bool],
    retries: int = 1,
) -> list[dict]:
    """
    Parse + validate Gemini JSON output.
    If parsing or validation fails, retry once with a stricter prompt.
    """
    settings = get_settings()
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        sys = strict_system_prompt if attempt == retries else system_prompt
        try:
            response = await _generate_content_with_retry(
                client,
                model=settings.GEMINI_MODEL,
                contents=[sys, user_prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                    max_output_tokens=8192,
                ),
                retries=1,
            )
            if not response.text:
                raise ValueError("Empty response from Gemini")

            text = response.text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines).strip()

            parsed = json.loads(text)
            if not isinstance(parsed, list):
                raise ValueError("Expected a JSON array")

            if parsed and not all(validate_fn(item) for item in parsed):
                raise ValueError("JSON array failed schema validation")

            return parsed
        except Exception as e:
            last_error = e
            if attempt == retries:
                raise RuntimeError(f"Gemini JSON parse/validation failed after retries: {e}") from e
            print(f"[warn] Gemini JSON parse/validation failed, retrying... ({e})")

    raise RuntimeError(f"Gemini JSON failed: {last_error}")

async def extract_bank_transactions(text: str) -> list[dict]:
    """Stage 1: Extract structured transactions from raw OCR text."""
    # Split text into 12,000 char (approx 3,000 tokens) chunks to prevent output truncation
    chunk_size = 12000
    text_chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    
    all_transactions = []

    try:
        for chunk in text_chunks:
            prompt = f"--- START OCR TEXT ---\n{chunk}\n--- END OCR TEXT ---\nExtract transactions."
            result = await _call_gemini_json_with_validate_and_retry(
                system_prompt=STAGE1_EXTRACTION_PROMPT,
                strict_system_prompt=STAGE1_EXTRACTION_PROMPT_STRICT,
                user_prompt=prompt,
                validate_fn=_validate_extracted_transaction,
                retries=1,
            )
            all_transactions.extend(result)
    except Exception as error:
        print(f"[fallback] Gemini extraction unavailable, using local parser: {error}")
        return extract_bank_transactions_locally(text)

    if all_transactions:
        return all_transactions

    print("[fallback] Gemini extraction returned no transactions, using local parser.")
    return extract_bank_transactions_locally(text)

async def classify_bank_transactions(transactions: list[dict]) -> list[dict]:
    """Stage 2: Classify transactions using Gemini."""
    prompt = f"--- START TRANSACTIONS ---\n{json.dumps(transactions, indent=2)}\n--- END TRANSACTIONS ---\nClassify."
    try:
        result = await _call_gemini_json_with_validate_and_retry(
            system_prompt=STAGE2_CLASSIFICATION_PROMPT,
            strict_system_prompt=STAGE2_CLASSIFICATION_PROMPT_STRICT,
            user_prompt=prompt,
            validate_fn=_validate_classified_transaction,
            retries=1,
        )
        if result:
            return result
    except Exception as error:
        print(f"[fallback] Gemini classification unavailable, using local classifier: {error}")

    return classify_bank_transactions_locally(transactions)


async def extract_and_classify_bank_transactions(text: str) -> list[dict]:
    """
    Convenience multi-stage method:
    - Stage 1: OCR cleanup + transaction extraction (Gemini)
    - Stage 2: transaction classification (Gemini)

    Note: This function must not do any deterministic math/scoring.
    """
    raw_txns = await extract_bank_transactions(text)
    if not raw_txns:
        return []
    return await classify_bank_transactions(raw_txns)

async def generate_risk_explanation(data: dict) -> list[str]:
    """Stage 6: Generate explainable reasoning for the risk score and decision."""
    prompt = f"""You are a fintech underwriter explaining a lending decision.
Input Data: {json.dumps(data)}
Generate a clear, 3-5 bullet point reasoning for the risk score and decision.
Strict JSON format expected: ["Bullet 1", "Bullet 2", ...]"""
    
    settings = get_settings()
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    try:
        response = await _generate_content_with_retry(
            client,
            model=settings.GEMINI_MODEL,
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
            retries=1,
        )
        text = response.text.strip() if response.text else ""
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
            
        parsed = json.loads(text) if text else []
        if isinstance(parsed, list) and parsed and all(isinstance(x, str) for x in parsed):
            return parsed
        return ["Unable to generate explanation due to unexpected Gemini output."]
    except Exception:
        return ["Unable to generate explanation due to an error."]
