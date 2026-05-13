export function normalizeConfidence(value: number | string | null | undefined): number | null {
  if (value === null || value === undefined) return null;

  if (typeof value === "string") {
    const trimmed = value.trim().toLowerCase();
    if (!trimmed) return null;
    if (trimmed === "high") return 1;
    if (trimmed === "medium") return 0.6;
    if (trimmed === "low") return 0.3;

    const numericPortion = trimmed.endsWith("%") ? trimmed.slice(0, -1) : trimmed;
    const parsed = Number(numericPortion);
    if (!Number.isFinite(parsed)) return null;
    if (trimmed.endsWith("%")) return Math.max(0, Math.min(1, parsed / 100));
    value = parsed;
  }

  if (!Number.isFinite(value)) return null;
  if (value < 0) return 0;
  if (value <= 1) return value;
  if (value <= 5) return 1;
  if (value <= 100) return Math.max(0, Math.min(1, value / 100));
  return 1;
}

export function formatConfidencePercent(
  value: number | string | null | undefined,
  fractionDigits = 1
): string {
  const normalized = normalizeConfidence(value);
  if (normalized === null) return "—";
  return `${(normalized * 100).toFixed(fractionDigits)}%`;
}

export function confidenceTone(value: number | string | null | undefined): "good" | "warning" | "danger" {
  const normalized = normalizeConfidence(value);
  if (normalized === null) return "warning";
  if (normalized >= 0.8) return "good";
  if (normalized >= 0.5) return "warning";
  return "danger";
}
