"""
Deterministic bank-statement header and evidence extraction.

The underwriting math works from transactions. This module extracts document
evidence that should be displayed as provenance, not silently promoted into
applicant intake fields.
"""

from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any

from services.bank_statement_engine_common import parse_statement_date


_DATE_TOKEN_RE = re.compile(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b|\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b")
_IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.IGNORECASE)
_MICR_RE = re.compile(r"\b\d{9}\b")
_STOP_HEADER_RE = re.compile(
    r"^\s*(?:"
    r"account\s*(?:number|no|name|open)|a/c\s*(?:number|no|name)|customer|branch|ifsc|micr|"
    r"phone|mobile|email|statement|date|nomination|scheme|joint|page|transaction|particulars"
    r")\b",
    re.IGNORECASE,
)
_LABEL_SEPARATOR_RE = re.compile(r"\s*[:=-]\s*")


def _clean_text(value: Any) -> str | None:
    text = " ".join(str(value or "").replace("\u00a0", " ").split()).strip(" :-")
    return text or None


def _clean_phone(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    match = re.search(r"\+?\d[\d\s().-]{5,}\d", text)
    return _clean_text(match.group(0)) if match else None


def _mask_account_number(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None

    visible_tail_match = re.search(r"(?:X+|\*+)[\s-]*(\d{4})\b", text, re.IGNORECASE)
    if visible_tail_match:
        return f"****{visible_tail_match.group(1)}"

    digits = re.sub(r"\D", "", text)
    if len(digits) >= 4:
        return f"****{digits[-4:]}"
    return None


def _parse_date_token(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None

    parsed = parse_statement_date(text)
    if parsed is not None:
        return parsed

    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _date_iso(value: Any) -> str | None:
    parsed = _parse_date_token(value)
    return parsed.isoformat() if parsed is not None else None


def _line_value(line: str, *labels: str) -> str | None:
    for label in labels:
        pattern = re.compile(rf"\b{label}\b\s*(?:no\.?|number)?\s*[:=-]?\s*(.+)$", re.IGNORECASE)
        match = pattern.search(line)
        if match:
            return _clean_text(match.group(1))
    return None


def _first_matching_line(lines: list[str], *labels: str) -> str | None:
    for line in lines:
        value = _line_value(line, *labels)
        if value:
            return value
    return None


def _extract_address_lines(lines: list[str]) -> list[str]:
    address_lines: list[str] = []
    capture = False

    for line in lines:
        if not capture:
            match = re.search(r"\b(?:address|customer address|branch address)\b\s*[:=-]\s*(.*)$", line, re.IGNORECASE)
            if not match:
                continue
            capture = True
            first_value = _clean_text(match.group(1))
            if first_value:
                address_lines.append(first_value)
            continue

        if _STOP_HEADER_RE.search(line) or len(address_lines) >= 4:
            break
        cleaned = _clean_text(line)
        if cleaned:
            address_lines.append(cleaned)

    return address_lines


def _extract_declared_period(text: str) -> tuple[str | None, str | None]:
    collapsed = " ".join(str(text or "").split())
    patterns = (
        r"(?:statement\s*)?period\s*(?:from)?\s*[:=-]?\s*(?P<start>{date})\s*(?:to|-|through)\s*(?P<end>{date})",
        r"(?:from\s*date|date\s*from|from)\s*[:=-]?\s*(?P<start>{date})\s*(?:to\s*date|date\s*to|to|-)\s*[:=-]?\s*(?P<end>{date})",
        r"statement\s*(?:from|period)\s*[:=-]?\s*(?P<start>{date})\s*(?:to|-)\s*(?P<end>{date})",
    )
    date_pattern = r"(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})"
    for pattern in patterns:
        match = re.search(pattern.format(date=date_pattern), collapsed, re.IGNORECASE)
        if match:
            return _date_iso(match.group("start")), _date_iso(match.group("end"))
    return None, None


def _extract_last_transaction_date(text: str) -> str | None:
    dates: list[date] = []
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("--- page"):
            continue
        if not re.match(r"^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b", stripped):
            continue
        match = _DATE_TOKEN_RE.search(stripped)
        if not match:
            continue
        parsed = _parse_date_token(match.group(0))
        if parsed is not None:
            dates.append(parsed)
    return max(dates).isoformat() if dates else None


def extract_bank_statement_evidence_profile(text: str) -> dict[str, Any]:
    """Extract bank/account/period evidence from native statement text."""
    lines = [_clean_text(line) for line in str(text or "").splitlines()]
    lines = [line for line in lines if line]
    joined = "\n".join(lines)

    bank_name = "Bank of Baroda" if re.search(r"\bbank\s+of\s+baroda\b", joined, re.IGNORECASE) else None
    account_holder = _first_matching_line(
        lines,
        r"account\s*holder\s*name",
        r"account\s*name",
        r"a/c\s*name",
        r"customer\s*name",
    )
    account_number = _first_matching_line(
        lines,
        r"account\s*number",
        r"account\s*no",
        r"a/c\s*number",
        r"a/c\s*no",
    )
    branch_name = _first_matching_line(lines, r"branch\s*name", r"branch")

    ifsc = None
    ifsc_match = _IFSC_RE.search(joined)
    if ifsc_match:
        ifsc = ifsc_match.group(0).upper()

    micr = None
    for line in lines:
        if "micr" not in line.lower():
            continue
        micr_match = _MICR_RE.search(line)
        if micr_match:
            micr = micr_match.group(0)
            break

    branch_phone = None
    for line in lines:
        if not re.search(r"\b(?:branch\s*)?(?:phone|tel|telephone|contact)\b", line, re.IGNORECASE):
            continue
        branch_phone = _clean_phone(_LABEL_SEPARATOR_RE.split(line, maxsplit=1)[-1])
        if branch_phone:
            break

    declared_start, declared_end = _extract_declared_period(joined)
    account_profile = {
        "bank_name": bank_name,
        "branch_name": branch_name,
        "branch_phone": branch_phone,
        "ifsc": ifsc,
        "micr": micr,
        "account_holder_name": account_holder,
        "account_number_masked": _mask_account_number(account_number),
        "address_lines": _extract_address_lines(lines),
    }

    return {
        "account_profile": account_profile,
        "declared_period_start_date": declared_start,
        "declared_period_end_date": declared_end,
        "last_transaction_date": _extract_last_transaction_date(joined),
    }


def merge_statement_evidence(
    primary: dict[str, Any] | None,
    fallback: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge two evidence profiles without overwriting concrete values."""
    primary = dict(primary or {})
    fallback = dict(fallback or {})
    merged_account = dict(fallback.get("account_profile") or {})
    merged_account.update(
        {
            key: value
            for key, value in dict(primary.get("account_profile") or {}).items()
            if value not in (None, "", [])
        }
    )

    merged = {**fallback, **{key: value for key, value in primary.items() if value not in (None, "", [])}}
    merged["account_profile"] = merged_account
    return merged


__all__ = [
    "extract_bank_statement_evidence_profile",
    "merge_statement_evidence",
]
