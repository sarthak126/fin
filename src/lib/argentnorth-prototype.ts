export type RiskTone = "good" | "warning" | "danger" | "neutral";

export type DecisionStatus = "approve" | "manual_review" | "reject";

export const prototypeCases: Array<{
  id: string;
  applicant: string;
  priority: "Critical" | "Elevated" | "Standard";
  product: string;
  amount: string;
  region: string;
  workflow: string;
  decision: DecisionStatus;
  riskScore: number;
}> = [
  {
    id: "AN-2052",
    applicant: "Aarav Sharma",
    priority: "Elevated",
    product: "MSME Working Capital",
    amount: "Rs 24,00,000",
    region: "Mumbai",
    workflow: "Risk review",
    decision: "manual_review",
    riskScore: 64,
  },
  {
    id: "AN-2051",
    applicant: "Meera Iyer",
    priority: "Standard",
    product: "Equipment Finance",
    amount: "Rs 42,00,000",
    region: "Bengaluru",
    workflow: "Ready for sanction",
    decision: "approve",
    riskScore: 22,
  },
  {
    id: "AN-2050",
    applicant: "Rohan Gupta",
    priority: "Critical",
    product: "Merchant Cash Advance",
    amount: "Rs 12,00,000",
    region: "Delhi NCR",
    workflow: "Adverse action draft",
    decision: "reject",
    riskScore: 83,
  },
  {
    id: "AN-2049",
    applicant: "Farhan Khan",
    priority: "Elevated",
    product: "Fleet Expansion Loan",
    amount: "Rs 58,00,000",
    region: "Hyderabad",
    workflow: "Compliance hold",
    decision: "manual_review",
    riskScore: 57,
  },
];

export const eventStream: Array<{
  label: string;
  detail: string;
  time: string;
  tone: RiskTone;
}> = [
  {
    label: "AA consent packet received",
    detail: "Finvu -> ArgentNorth FIU bridge",
    time: "10:42:13",
    tone: "good",
  },
  {
    label: "BIAN Customer Offer event",
    detail: "Core LOS webhook accepted in 184ms",
    time: "10:42:09",
    tone: "good",
  },
  {
    label: "Model drift monitor",
    detail: "Retail cohort PSI crossed watch threshold",
    time: "10:41:55",
    tone: "warning",
  },
  {
    label: "Policy battery update",
    detail: "MSME DTI reject band changed to 60%",
    time: "10:38:20",
    tone: "neutral",
  },
];

export const auditEvents: Array<{
  action: string;
  actor: string;
  time: string;
  tone: RiskTone;
}> = [
  {
    action: "Changed DTI manual review band",
    actor: "Policy Admin",
    time: "Today 10:38",
    tone: "warning",
  },
  {
    action: "Logged fairness check pass",
    actor: "Model Monitor",
    time: "Today 10:21",
    tone: "good",
  },
  {
    action: "Archived stale consent event",
    actor: "System",
    time: "Today 09:58",
    tone: "neutral",
  },
];

export const operatingMetrics: Array<{
  label: string;
  value: string;
  detail: string;
  tone: RiskTone;
}> = [
  {
    label: "Exposure cleared",
    value: "Rs 18.2Cr",
    detail: "+12.4% vs trailing 7d",
    tone: "good",
  },
  {
    label: "Policy savings",
    value: "Rs 42L",
    detail: "prevented loss estimate",
    tone: "good",
  },
  {
    label: "Reviewer load",
    value: "-18%",
    detail: "automation deflection",
    tone: "neutral",
  },
  {
    label: "SLA at risk",
    value: "7",
    detail: "cases crossing 4h",
    tone: "warning",
  },
];

export const policyControls: Array<{
  control: string;
  owner: string;
  status: string;
  effect: string;
  tone: RiskTone;
}> = [
  {
    control: "DTI guardrail",
    owner: "Credit Policy",
    status: "Live",
    effect: "12 cases routed",
    tone: "good",
  },
  {
    control: "Velocity anomaly",
    owner: "Risk Ops",
    status: "Watch",
    effect: "3 alerts open",
    tone: "warning",
  },
  {
    control: "Consent expiry",
    owner: "Compliance",
    status: "Live",
    effect: "0 stale pulls",
    tone: "good",
  },
  {
    control: "Model drift PSI",
    owner: "ML Platform",
    status: "Watch",
    effect: "retail cohort",
    tone: "warning",
  },
];

export const evidenceGraph: Array<{
  source: string;
  target: string;
  detail: string;
  tone: RiskTone;
}> = [
  {
    source: "Applicant",
    target: "AA consent",
    detail: "identity and consent joined",
    tone: "good",
  },
  {
    source: "AA consent",
    target: "Bank evidence",
    detail: "12m cashflow normalized",
    tone: "good",
  },
  {
    source: "Bank evidence",
    target: "Policy battery",
    detail: "DTI and velocity checks",
    tone: "warning",
  },
  {
    source: "Bureau",
    target: "Model score",
    detail: "credit-gbm-4.8 features",
    tone: "neutral",
  },
  {
    source: "Model score",
    target: "Reviewer action",
    detail: "decision rationale attached",
    tone: "good",
  },
];

export const northstarBrief = {
  status: "Autopilot stable",
  headline: "ArgentNorth has already done the triage.",
  summary:
    "31 low-risk cases can move, 7 exceptions need human judgment, and 4 remain held until evidence is complete.",
  confidence: "92%",
  primaryAction: "Review exceptions",
  secondaryAction: "Open queue",
};

export const northstarRecommendations: Array<{
  title: string;
  detail: string;
  impact: string;
  action: string;
  tone: RiskTone;
}> = [
  {
    title: "Clear the SLA-risk lane",
    detail: "Seven applications are inside the four-hour review window and already have complete evidence packets.",
    impact: "Protect Rs 3.4Cr in active demand",
    action: "Review 7 cases",
    tone: "warning",
  },
  {
    title: "Release the low-risk batch",
    detail: "The policy battery found no new blockers across 31 scored applications.",
    impact: "Reduce reviewer queue by 66%",
    action: "Approve batch",
    tone: "good",
  },
  {
    title: "Hold the drift cohort",
    detail: "Retail cohort PSI is elevated; keep model-assisted decisions in review until the monitor clears.",
    impact: "Prevent silent policy drift",
    action: "Keep watch",
    tone: "neutral",
  },
];

export function getToneForDecision(decision: DecisionStatus): RiskTone {
  if (decision === "approve") return "good";
  if (decision === "manual_review") return "warning";
  return "danger";
}
