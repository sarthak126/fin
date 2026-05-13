import type { RiskTone } from "@/lib/argentnorth-prototype";

export type PrototypeSectionId =
  | "overview"
  | "command"
  | "queue"
  | "intake"
  | "dossier"
  | "modelOps"
  | "compliance";

export type PrototypeDecision = "Approve" | "Manual Review" | "Reject";

export const prototypeSections: Array<{
  id: PrototypeSectionId;
  label: string;
  shortLabel: string;
  description: string;
}> = [
    {
      id: "overview",
      label: "Overview",
      shortLabel: "Overview",
      description: "Product-first story and complete shell preview.",
    },
    {
      id: "command",
      label: "Command Center",
      shortLabel: "Command",
      description: "Control plane for exposure, SLA, drift, policy, and evidence graph.",
    },
    {
      id: "queue",
      label: "Case Queue",
      shortLabel: "Queue",
      description: "Dense underwriting workbench with recommendations and reviewer status.",
    },
    {
      id: "intake",
      label: "Evidence Intake",
      shortLabel: "Intake",
      description: "Guided case creation with validation and review summary.",
    },
    {
      id: "dossier",
      label: "Case Dossier",
      shortLabel: "Dossier",
      description: "Institutional review surface for one applicant and decision packet.",
    },
    {
      id: "modelOps",
      label: "Model/Risk Ops",
      shortLabel: "Risk Ops",
      description: "Model health, fairness, drift, cohorts, and policy battery.",
    },
    {
      id: "compliance",
      label: "Compliance/Settings",
      shortLabel: "Settings",
      description: "FREE-AI, DPDP, access, retention, API, and credit controls.",
    },
  ];

export const prototypeHeroMetrics: Array<{
  label: string;
  value: string;
  detail: string;
  tone: RiskTone;
}> = [
    {
      label: "Exposure cleared",
      value: "INR 18.2Cr",
      detail: "same-day decision value",
      tone: "good",
    },
    {
      label: "Reviewer load",
      value: "-18%",
      detail: "automation deflection",
      tone: "neutral",
    },
    {
      label: "SLA risk",
      value: "7",
      detail: "inside 4h review window",
      tone: "warning",
    },
    {
      label: "AA consent pulls",
      value: "0 stale",
      detail: "DPDP retention active",
      tone: "good",
    },
  ];

export const institutionalThesis = [
  "A governed credit decision fabric for banks, NBFCs, and embedded lenders.",
  "Every approval is a typed object: data, policy, model rationale, authority, audit.",
  "Agentic recommendations are allowed to reason, never to silently move capital.",
  "Built for India-first regulated lending, expandable to global credit rails.",
];

export const boardMetrics: Array<{
  label: string;
  value: string;
  detail: string;
  tone: RiskTone;
}> = [
    {
      label: "Credit demand observed",
      value: "INR 1,284Cr",
      detail: "rolling 30d across 11 lender programs",
      tone: "neutral",
    },
    {
      label: "Capital routed safely",
      value: "INR 312Cr",
      detail: "policy-cleared and audit sealed",
      tone: "good",
    },
    {
      label: "Loss prevented",
      value: "INR 8.7Cr",
      detail: "fraud, drift, and policy exceptions",
      tone: "good",
    },
    {
      label: "Human overrides",
      value: "2.8%",
      detail: "all override reasons captured",
      tone: "warning",
    },
  ];

export const capitalRails: Array<{
  label: string;
  value: string;
  detail: string;
  progress: number;
  tone: RiskTone;
}> = [
    {
      label: "Working capital rail",
      value: "INR 162Cr",
      detail: "MSME distributors, 41 bps expected loss",
      progress: 76,
      tone: "good",
    },
    {
      label: "Equipment finance rail",
      value: "INR 88Cr",
      detail: "secured asset programs, 29 bps expected loss",
      progress: 62,
      tone: "good",
    },
    {
      label: "Merchant cash rail",
      value: "INR 38Cr",
      detail: "velocity watch active in Delhi NCR cohort",
      progress: 48,
      tone: "warning",
    },
    {
      label: "Thin-file expansion",
      value: "INR 24Cr",
      detail: "human approval gate until fairness review clears",
      progress: 31,
      tone: "neutral",
    },
  ];

export const decisionObjects: Array<{
  object: string;
  source: string;
  latency: string;
  control: string;
  authority: string;
  tone: RiskTone;
}> = [
    {
      object: "Applicant Identity",
      source: "GSTIN, PAN, CKYC",
      latency: "142ms",
      control: "DPDP purpose bound",
      authority: "Read scoped",
      tone: "good",
    },
    {
      object: "Cash-flow Vector",
      source: "AA FIU + ISO 20022",
      latency: "388ms",
      control: "Consent expiry guard",
      authority: "Feature only",
      tone: "good",
    },
    {
      object: "Policy Battery",
      source: "BIAN product rules",
      latency: "51ms",
      control: "Dual approval",
      authority: "Human publish",
      tone: "warning",
    },
    {
      object: "Model Rationale",
      source: "credit-gbm-4.8",
      latency: "221ms",
      control: "SHAP/LIME attached",
      authority: "Assist only",
      tone: "neutral",
    },
    {
      object: "Capital Action",
      source: "LOS writeback",
      latency: "184ms",
      control: "Maker-checker",
      authority: "Signed action",
      tone: "good",
    },
  ];

export const agenticMoves: Array<{
  title: string;
  detail: string;
  impact: string;
  authority: string;
  tone: RiskTone;
}> = [
    {
      title: "Release low-risk MSME batch",
      detail: "31 applications have complete evidence, stable AA inflows, and no fairness or drift blockers.",
      impact: "Move INR 11.6Cr today",
      authority: "Human approval required",
      tone: "good",
    },
    {
      title: "Hold Delhi NCR retail cohort",
      detail: "PSI drift is above watch threshold; approvals stay assisted until Risk Ops clears.",
      impact: "Avoid silent portfolio shift",
      authority: "System guard enforced",
      tone: "warning",
    },
    {
      title: "Tighten bank-history exception lane",
      detail: "Short-history cases are clustering around elevated DTI and GST/AA mismatch.",
      impact: "Reduce manual review noise",
      authority: "Policy admin publish",
      tone: "neutral",
    },
  ];

export const operatingLanes: Array<{
  lane: string;
  volume: string;
  capital: string;
  risk: string;
  owner: string;
  tone: RiskTone;
}> = [
    {
      lane: "Auto-sanction",
      volume: "31 cases",
      capital: "INR 11.6Cr",
      risk: "Low",
      owner: "Signed policy",
      tone: "good",
    },
    {
      lane: "Senior reviewer",
      volume: "7 cases",
      capital: "INR 3.4Cr",
      risk: "SLA watch",
      owner: "Credit Ops",
      tone: "warning",
    },
    {
      lane: "Model guard",
      volume: "11 cases",
      capital: "INR 5.1Cr",
      risk: "Drift watch",
      owner: "Risk Ops",
      tone: "neutral",
    },
    {
      lane: "Adverse action",
      volume: "4 cases",
      capital: "INR 0.8Cr",
      risk: "Reject",
      owner: "Compliance",
      tone: "danger",
    },
  ];

export const commandMetrics: Array<{
  label: string;
  value: string;
  detail: string;
  tone: RiskTone;
}> = [
    {
      label: "Exposure cleared",
      value: "INR 18.2Cr",
      detail: "+12.4% vs trailing 7d",
      tone: "good",
    },
    {
      label: "Reviewer load",
      value: "71%",
      detail: "4 teams within target",
      tone: "neutral",
    },
    {
      label: "SLA at risk",
      value: "7",
      detail: "2 critical in Mumbai",
      tone: "warning",
    },
    {
      label: "Model drift",
      value: "PSI 0.21",
      detail: "retail cohort watch",
      tone: "warning",
    },
  ];

export const commandSignals: Array<{
  label: string;
  value: string;
  status: string;
  tone: RiskTone;
}> = [
    {
      label: "AA ingestion",
      value: "18.4k events",
      status: "Healthy",
      tone: "good",
    },
    {
      label: "BIAN Customer Offer",
      value: "184ms p50",
      status: "Healthy",
      tone: "good",
    },
    {
      label: "ISO 20022 mapping",
      value: "97.8%",
      status: "Mapped",
      tone: "good",
    },
    {
      label: "Policy battery",
      value: "4 alerts",
      status: "Watch",
      tone: "warning",
    },
    {
      label: "Fairness monitor",
      value: "1 cohort",
      status: "Guarded",
      tone: "neutral",
    },
  ];

export const commandEventStream: Array<{
  label: string;
  detail: string;
  time: string;
  tone: RiskTone;
}> = [
    {
      label: "AA consent packet normalized",
      detail: "Finvu stream mapped to income, obligations, and volatility features.",
      time: "10:42:13",
      tone: "good",
    },
    {
      label: "BIAN offer service updated",
      detail: "Hybrid credit pricing returned 3 tenure options for AN-2057.",
      time: "10:42:09",
      tone: "good",
    },
    {
      label: "Retail cohort PSI crossed watch",
      detail: "Model-assisted approvals routed to manual review until monitor clears.",
      time: "10:41:55",
      tone: "warning",
    },
    {
      label: "FREE-AI explanation attached",
      detail: "Reason codes and SHAP drivers sealed into case audit trail.",
      time: "10:40:48",
      tone: "neutral",
    },
    {
      label: "Policy battery published",
      detail: "MSME DTI manual-review band moved from 55% to 60%.",
      time: "10:38:20",
      tone: "warning",
    },
  ];

export const evidenceGraphNodes: Array<{
  source: string;
  target: string;
  detail: string;
  tone: RiskTone;
}> = [
    {
      source: "Applicant",
      target: "AA Consent",
      detail: "identity and consent joined",
      tone: "good",
    },
    {
      source: "AA Consent",
      target: "Cash-flow Intelligence",
      detail: "12m inflow stability scored",
      tone: "good",
    },
    {
      source: "Bank Evidence",
      target: "Policy Battery",
      detail: "DTI, velocity, GST, bureau checks",
      tone: "warning",
    },
    {
      source: "Bureau",
      target: "Model Score",
      detail: "credit-gbm-4.8 features",
      tone: "neutral",
    },
    {
      source: "Model Score",
      target: "Reviewer Action",
      detail: "rationale and pricing attached",
      tone: "good",
    },
  ];

export const queueCases: Array<{
  id: string;
  applicant: string;
  entityType: string;
  product: string;
  amount: string;
  region: string;
  riskBand: "Low" | "Medium" | "High";
  riskScore: number;
  evidence: number;
  sla: string;
  decision: PrototypeDecision;
  reviewer: string;
  status: string;
  pricing: string;
  tone: RiskTone;
}> = [
    {
      id: "AN-2057",
      applicant: "Kavya Foods Pvt Ltd",
      entityType: "MSME distributor",
      product: "Working Capital",
      amount: "INR 24.0L",
      region: "Mumbai",
      riskBand: "Medium",
      riskScore: 58,
      evidence: 92,
      sla: "1h 12m",
      decision: "Manual Review",
      reviewer: "Priya N.",
      status: "SLA risk",
      pricing: "16.8% APR",
      tone: "warning",
    },
    {
      id: "AN-2056",
      applicant: "Brightline Tools",
      entityType: "Manufacturer",
      product: "Equipment Finance",
      amount: "INR 42.0L",
      region: "Bengaluru",
      riskBand: "Low",
      riskScore: 24,
      evidence: 98,
      sla: "5h 40m",
      decision: "Approve",
      reviewer: "Auto",
      status: "Ready",
      pricing: "14.2% APR",
      tone: "good",
    },
    {
      id: "AN-2055",
      applicant: "Rohan Gupta",
      entityType: "Merchant",
      product: "Merchant Cash Advance",
      amount: "INR 12.0L",
      region: "Delhi NCR",
      riskBand: "High",
      riskScore: 83,
      evidence: 86,
      sla: "43m",
      decision: "Reject",
      reviewer: "Aman S.",
      status: "Adverse action",
      pricing: "Not offered",
      tone: "danger",
    },
    {
      id: "AN-2054",
      applicant: "Urban Freight Co",
      entityType: "Fleet operator",
      product: "Fleet Expansion",
      amount: "INR 58.0L",
      region: "Hyderabad",
      riskBand: "Medium",
      riskScore: 61,
      evidence: 74,
      sla: "2h 08m",
      decision: "Manual Review",
      reviewer: "Fatima K.",
      status: "Compliance hold",
      pricing: "17.4% APR",
      tone: "warning",
    },
    {
      id: "AN-2053",
      applicant: "Meera Iyer",
      entityType: "Clinic owner",
      product: "Professional Loan",
      amount: "INR 18.0L",
      region: "Chennai",
      riskBand: "Low",
      riskScore: 29,
      evidence: 100,
      sla: "6h 20m",
      decision: "Approve",
      reviewer: "Auto",
      status: "Sanction draft",
      pricing: "13.9% APR",
      tone: "good",
    },
    {
      id: "AN-2052",
      applicant: "Farhan Khan",
      entityType: "Retail trader",
      product: "Invoice Discounting",
      amount: "INR 31.0L",
      region: "Ahmedabad",
      riskBand: "Medium",
      riskScore: 47,
      evidence: 68,
      sla: "3h 16m",
      decision: "Manual Review",
      reviewer: "Nikhil R.",
      status: "Evidence gap",
      pricing: "16.1% APR",
      tone: "warning",
    },
  ];

export const intakeSteps: Array<{
  label: string;
  detail: string;
  status: "complete" | "active" | "blocked" | "pending";
  tone: RiskTone;
}> = [
    {
      label: "Applicant",
      detail: "Entity profile and lending product selected.",
      status: "complete",
      tone: "good",
    },
    {
      label: "Evidence",
      detail: "AA consent, GST, bureau, and bank packet validation.",
      status: "active",
      tone: "warning",
    },
    {
      label: "Policy",
      detail: "Map documents to product requirements and reviewer lane.",
      status: "pending",
      tone: "neutral",
    },
    {
      label: "Review",
      detail: "Confirm evidence summary before creating the case.",
      status: "blocked",
      tone: "warning",
    },
  ];

export const intakeFields: Array<{
  id: string;
  label: string;
  value: string;
  helper: string;
  error?: string;
}> = [
    {
      id: "legalName",
      label: "Legal business name",
      value: "Kavya Foods Pvt Ltd",
      helper: "Matched to GSTIN legal name.",
    },
    {
      id: "gstin",
      label: "GSTIN",
      value: "27AAACK4587C1Z9",
      helper: "Format valid and jurisdiction mapped to Maharashtra.",
    },
    {
      id: "aaConsent",
      label: "AA consent handle",
      value: "kavyafoods@finvu",
      helper: "Consent received for current accounts.",
    },
    {
      id: "bureauRef",
      label: "Bureau reference",
      value: "CIBIL-MSME-88421",
      helper: "Last pulled today at 10:31.",
    },
    {
      id: "bankWindow",
      label: "Bank statement window",
      value: "9 months",
      helper: "Working capital policy requires 12 months.",
      error: "Add 3 more months of bank evidence or route to exception review.",
    },
    {
      id: "turnover",
      label: "Annual turnover",
      value: "INR 3.8Cr",
      helper: "GST and AA inflow variance is 4.6%.",
    },
  ];

export const evidencePacket: Array<{
  label: string;
  value: string;
  tone: RiskTone;
}> = [
    {
      label: "AA consent",
      value: "Active until 23 May 2026",
      tone: "good",
    },
    {
      label: "Bank coverage",
      value: "9 of 12 months",
      tone: "warning",
    },
    {
      label: "GST returns",
      value: "GSTR-1 and 3B aligned",
      tone: "good",
    },
    {
      label: "Bureau",
      value: "Thin-file proprietor linked",
      tone: "neutral",
    },
    {
      label: "Fraud checks",
      value: "Velocity watch triggered",
      tone: "warning",
    },
  ];

export const dossier = {
  id: "AN-2057",
  applicant: "Kavya Foods Pvt Ltd",
  summary:
    "Mumbai packaged-foods distributor seeking working capital after three high-growth months. Cash inflows are strong, but bank coverage is short of policy and velocity anomalies require human judgment.",
  recommendation: "Manual Review" as PrototypeDecision,
  riskScore: 58,
  facts: [
    { label: "Product", value: "MSME Working Capital" },
    { label: "Requested limit", value: "INR 24.0L" },
    { label: "Region", value: "Mumbai" },
    { label: "Vintage", value: "4y 8m" },
    { label: "Sector", value: "FMCG distribution" },
    { label: "Reviewer lane", value: "SLA risk" },
  ],
  cashflow: [
    { label: "Median monthly inflow", value: "INR 31.4L", tone: "good" as RiskTone },
    { label: "Inflow volatility", value: "18.7%", tone: "neutral" as RiskTone },
    { label: "Debt service ratio", value: "57%", tone: "warning" as RiskTone },
    { label: "GST/AA variance", value: "4.6%", tone: "good" as RiskTone },
  ],
  drivers: [
    { label: "High DTI vs policy band", value: 17, direction: "raises" as const },
    { label: "Short bank history", value: 12, direction: "raises" as const },
    { label: "Stable GST turnover", value: 9, direction: "lowers" as const },
    { label: "Low cheque bounce rate", value: 8, direction: "lowers" as const },
    { label: "Recent velocity anomaly", value: 7, direction: "raises" as const },
  ],
  fraudFlags: [
    { label: "Same-day inflow spikes", detail: "3 deposits above cohort p95", tone: "warning" as RiskTone },
    { label: "Device/IP reuse", detail: "No linked fraud cluster", tone: "good" as RiskTone },
    { label: "GST identity", detail: "Legal name and address match", tone: "good" as RiskTone },
  ],
  policyChecks: [
    { label: "AA consent active", result: "Pass", tone: "good" as RiskTone },
    { label: "12m bank evidence", result: "Exception", tone: "warning" as RiskTone },
    { label: "DTI below reject band", result: "Pass", tone: "good" as RiskTone },
    { label: "Velocity anomaly", result: "Review", tone: "warning" as RiskTone },
    { label: "FREE-AI explanation", result: "Attached", tone: "good" as RiskTone },
  ],
  auditTrail: [
    { label: "Case assembled", detail: "AA, GST, bureau, and applicant profile joined.", time: "10:42", tone: "good" as RiskTone },
    { label: "Model score generated", detail: "credit-gbm-4.8 returned score 58 with SHAP drivers.", time: "10:43", tone: "neutral" as RiskTone },
    { label: "Policy exception created", detail: "Bank evidence window below product policy.", time: "10:44", tone: "warning" as RiskTone },
    { label: "Reviewer packet sealed", detail: "Decision controls enabled with audit trail.", time: "10:45", tone: "good" as RiskTone },
  ],
};

export const modelCards: Array<{
  label: string;
  value: string;
  detail: string;
  tone: RiskTone;
}> = [
    {
      label: "Champion model",
      value: "credit-gbm-4.8",
      detail: "MSME scorecard in production",
      tone: "good",
    },
    {
      label: "AUC",
      value: "0.842",
      detail: "+0.006 vs previous",
      tone: "good",
    },
    {
      label: "KS statistic",
      value: "0.61",
      detail: "within approval gate",
      tone: "good",
    },
    {
      label: "PSI drift",
      value: "0.21",
      detail: "retail cohort watch",
      tone: "warning",
    },
  ];

export const fairnessMetrics: Array<{
  label: string;
  value: string;
  threshold: string;
  tone: RiskTone;
}> = [
    {
      label: "Approval parity",
      value: "0.94",
      threshold: ">= 0.90",
      tone: "good",
    },
    {
      label: "False decline gap",
      value: "3.2pp",
      threshold: "< 5pp",
      tone: "good",
    },
    {
      label: "Regional drift",
      value: "0.18 PSI",
      threshold: "< 0.20",
      tone: "neutral",
    },
    {
      label: "Thin-file lift",
      value: "Watch",
      threshold: "manual guard",
      tone: "warning",
    },
  ];

export const cohortWatchlist: Array<{
  cohort: string;
  volume: string;
  drift: string;
  action: string;
  tone: RiskTone;
}> = [
    {
      cohort: "Retail traders - Delhi NCR",
      volume: "311 apps",
      drift: "PSI 0.21",
      action: "Manual-review assisted approvals",
      tone: "warning",
    },
    {
      cohort: "MSME distributors - West",
      volume: "528 apps",
      drift: "PSI 0.12",
      action: "Keep champion active",
      tone: "good",
    },
    {
      cohort: "Fleet operators - South",
      volume: "144 apps",
      drift: "PSI 0.16",
      action: "Monitor DTI sensitivity",
      tone: "neutral",
    },
  ];

export const policyBattery: Array<{
  rule: string;
  owner: string;
  coverage: string;
  effect: string;
  tone: RiskTone;
}> = [
    {
      rule: "DTI reject band",
      owner: "Credit Policy",
      coverage: "100%",
      effect: "12 routed to review",
      tone: "warning",
    },
    {
      rule: "AA consent expiry",
      owner: "Compliance",
      coverage: "100%",
      effect: "0 stale pulls",
      tone: "good",
    },
    {
      rule: "GST turnover variance",
      owner: "Risk Ops",
      coverage: "94%",
      effect: "5 exceptions",
      tone: "neutral",
    },
    {
      rule: "Fraud velocity",
      owner: "Fraud Ops",
      coverage: "98%",
      effect: "3 alerts open",
      tone: "warning",
    },
  ];

export const complianceControls: Array<{
  label: string;
  value: string;
  detail: string;
  tone: RiskTone;
}> = [
    {
      label: "FREE-AI",
      value: "Understandable",
      detail: "Reason codes, SHAP drivers, and reviewer notes are sealed per decision.",
      tone: "good",
    },
    {
      label: "DPDP",
      value: "Minimized",
      detail: "Purpose-bound AA evidence is retained for 180 days by default.",
      tone: "good",
    },
    {
      label: "SOC2 / ISO",
      value: "Mapped",
      detail: "Access reviews, audit exports, incident controls, and vendor evidence.",
      tone: "neutral",
    },
    {
      label: "Security scopes",
      value: "Role-based",
      detail: "Human and agent actions inherit explicit data and action permissions.",
      tone: "good",
    },
  ];

export const apiKeyPlaceholders = [
  { label: "AA FIU connector", value: "an_live_fiu_..._8Q2K", status: "Scoped" },
  { label: "LOS writeback", value: "an_live_los_..._4L1P", status: "Write guarded" },
  { label: "Audit export", value: "an_live_audit_..._9M7T", status: "Read only" },
];

export const roleAccess = [
  { role: "Credit Reviewer", users: "42", access: "Cases, decisions, rationale" },
  { role: "Risk Ops", users: "9", access: "Model monitors, policy battery" },
  { role: "Compliance Admin", users: "5", access: "Audit, retention, access reviews" },
  { role: "Agentic Recommender", users: "3 agents", access: "Read scoped data, suggest actions only" },
];

/* ═══════════════════════════════════════
   SPARKLINE & CHART DATA
   ═══════════════════════════════════════ */
export const metricSparklines: Record<string, number[]> = {
  "Exposure cleared": [11.2, 13.8, 12.1, 15.4, 14.6, 16.8, 18.2],
  "Reviewer load": [88, 82, 79, 76, 74, 73, 71],
  "SLA at risk": [3, 5, 4, 8, 6, 9, 7],
  "Model drift": [0.08, 0.1, 0.12, 0.14, 0.16, 0.19, 0.21],
  "Credit demand observed": [980, 1020, 1080, 1140, 1200, 1250, 1284],
  "Capital routed safely": [220, 240, 258, 270, 288, 298, 312],
  "Loss prevented": [5.2, 5.8, 6.4, 7.1, 7.6, 8.2, 8.7],
  "Human overrides": [4.1, 3.8, 3.5, 3.2, 3.0, 2.9, 2.8],
};

export const exposureTrendData = {
  values: [8.4, 10.2, 9.8, 12.6, 11.4, 14.8, 13.2, 15.6, 16.1, 17.4, 16.8, 18.2],
  labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
};

export const sidebarHealthSignals = [
  { label: "AA ingestion", value: "18.4k", spark: [12, 14, 13, 16, 15, 17, 18.4], tone: "good" as RiskTone },
  { label: "BIAN p50", value: "184ms", spark: [210, 198, 192, 188, 186, 185, 184], tone: "good" as RiskTone },
  { label: "PSI drift", value: "0.21", spark: [0.08, 0.1, 0.12, 0.14, 0.16, 0.19, 0.21], tone: "warning" as RiskTone },
];
