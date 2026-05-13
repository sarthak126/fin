export const demoBankStatementCase = {
  documentName: "XXXXXXXXXX6604_20240129151130336063.pdf",
  documentType: "bank_statement",
  statementQuality: "Clean",
  coverageDays: 8,
  decision: {
    decision_status: "insufficient_history",
    decision_recommendation: "Manual review / request 3–6 months statement history",
    decision_reason:
      "Insufficient history: coverage_days=8 (< 90 required); stable_income_status=no verifiable stable income detected; liquidity_signal=low (min_balance=Rs157.14; outflows=Rs12,804 > inflows=Rs11,381); next_action=Request 3–6 months of bank statement history.",
    extraction_confidence: 91,
    risk_confidence: 40,
    data_completeness: "40%",
    required_followups: ["Request 3–6 months of bank statement history"],
    analysis_limitations: [
      "Statement coverage is only 8 day(s), below the 90-day minimum required for full underwriting.",
      "Long-term income stability, recurring obligations, and balance behavior cannot be evidenced from the available statement history.",
      "Income and DTI inference were intentionally skipped to avoid projecting 3-6 month repayment capacity from a short sample.",
    ],
  },
  statementSummary: [
    { label: "Statement period", value: "22 Jan 2024 - 29 Jan 2024" },
    { label: "Coverage days", value: "8" },
    { label: "Opening balance", value: "Rs1,580.14" },
    { label: "Closing balance", value: "Rs157.14" },
    { label: "Total credits", value: "Rs11,381.00" },
    { label: "Total debits", value: "Rs12,804.00" },
    { label: "Net flow", value: "Rs-1,423.00" },
    { label: "Minimum balance", value: "Rs157.14" },
    { label: "Maximum balance", value: "Rs12,961.14" },
    { label: "Transactions", value: "4" },
    { label: "Low-balance events", value: "1" },
  ],
} as const;
