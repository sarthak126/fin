"""
Spending categorization and merchant summaries for bank statements.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from services.bank_statement_engine_common import normalize_description, safe_float

SPENDING_CATEGORIES = {
    "utilities": [
        "billdesk", "bill", "electricity", "electric", "water", "gas",
        "broadband", "wifi", "internet", "recharge", "mobile recharge",
        "dth", "tata sky", "airtel", "jio", "vodafone", "bsnl",
        "postpaid", "prepaid", "telecom",
    ],
    "groceries": [
        "grocery", "groceries", "supermarket", "dmart", "big bazaar",
        "big basket", "bigbasket", "best basket", "reliance fresh",
        "more", "spencer", "nature's basket", "zepto", "blinkit",
        "instamart", "swiggy instamart", "vegetables", "kirana",
    ],
    "food_dining": [
        "swiggy", "zomato", "food", "restaurant", "hotel", "cafe",
        "dominos", "pizza", "mcdonald", "kfc", "burger", "dining",
        "eat", "canteen", "mess",
    ],
    "transport": [
        "uber", "ola", "rapido", "metro", "bus", "train", "irctc",
        "fuel", "petrol", "diesel", "parking", "toll", "fastag",
        "cab", "auto", "rickshaw",
    ],
    "shopping": [
        "amazon", "flipkart", "myntra", "ajio", "meesho", "nykaa",
        "shopping", "mall", "store", "purchase", "electronics",
        "croma", "reliance digital",
    ],
    "rent": ["rent", "house rent", "room rent", "rental"],
    "insurance": [
        "insurance", "lic", "premium", "policy", "health insurance",
        "term plan", "sbi life", "hdfc life", "icici pru", "max life",
    ],
    "medical": [
        "medical", "hospital", "pharmacy", "pharma", "doctor",
        "clinic", "health", "apollo", "medplus", "netmeds",
    ],
    "education": [
        "school", "college", "university", "tuition", "fees",
        "education", "course", "udemy", "coursera",
    ],
    "entertainment": [
        "netflix", "hotstar", "prime video", "spotify", "youtube",
        "gaming", "movie", "pvr", "inox", "cinema", "entertainment",
    ],
    "p2p_transfers": [
        "upi", "upi/", "upi-", "phonepe", "gpay", "google pay",
        "paytm", "transfer", "fund transfer", "neft", "imps", "rtgs",
    ],
    "cash_withdrawal": ["atm", "cash withdrawal", "cash wdl", "withdrawal", "wdl"],
    "emi_loan": [
        "emi", "loan", "autodebit", "auto-debit", "nach",
        "bajaj finserv", "hdfc loan", "sbi loan",
    ],
}


def _categorize_spending(description: str) -> str:
    for category, keywords in SPENDING_CATEGORIES.items():
        if any(keyword in description for keyword in keywords):
            return category
    return "other"


def compute_spending_intelligence(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    category_totals: dict[str, float] = defaultdict(float)
    merchant_totals: dict[str, dict[str, Any]] = defaultdict(lambda: {"total": 0.0, "count": 0})
    total_spending = 0.0

    for transaction in transactions:
        if transaction.get("duplicate"):
            continue

        debit = safe_float(transaction.get("debit")) or 0.0
        if debit <= 0:
            continue

        description = normalize_description(transaction.get("description"))
        category = _categorize_spending(description)
        category_totals[category] += debit
        total_spending += debit

        words = description.split()[:3]
        merchant = " ".join(word for word in words if len(word) > 2)[:30]
        if merchant:
            merchant_totals[merchant]["total"] += debit
            merchant_totals[merchant]["count"] += 1

    spending_categories = {}
    category_amounts = {}
    for category, amount in sorted(category_totals.items(), key=lambda item: -item[1]):
        percentage = round((amount / total_spending * 100) if total_spending > 0 else 0, 1)
        spending_categories[category] = percentage
        category_amounts[category] = round(amount, 2)

    top_merchants = [
        {"name": name, "total": round(info["total"], 2), "count": info["count"]}
        for name, info in sorted(merchant_totals.items(), key=lambda item: -item[1]["total"])[:10]
    ]

    return {
        "spending_categories": spending_categories,
        "category_amounts": category_amounts,
        "top_merchants": top_merchants,
        "total_spending": round(total_spending, 2),
    }
