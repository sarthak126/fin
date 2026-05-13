import { expect, test } from "@playwright/test";

test("bank statement short-history regression detail stays internally consistent", async ({ page }) => {
  await page.goto("/demo/bank-statement-detail");

  await expect(page.getByRole("heading", { name: /bank statement detail regression fixture/i })).toBeVisible();
  await expect(page.locator('[data-testid="final-decision-block"]')).toHaveCount(1);
  await expect(page.locator('[data-testid="final-decision-block"]')).toHaveAttribute(
    "data-decision-status",
    "insufficient_history"
  );
  await expect(page.locator('[data-testid="decision-badge"]')).toHaveText("INSUFFICIENT HISTORY");
  await expect(page.locator('[data-testid="recommendation-copy"]')).toContainText(
    "Manual review / request 3–6 months statement history"
  );
  await expect(page.locator('[data-testid="primary-reasoning"]')).toContainText(
    "Insufficient history: coverage_days=8"
  );
  await expect(page.locator('[data-testid="confidence-layer"]')).toBeVisible();
  await expect(page.locator('[data-testid="analysis-limitations"]')).toBeVisible();
  await expect(page.locator('[data-testid="statement-summary"]')).toBeVisible();
  await expect(
    page.locator('[data-testid="final-decision-block"] span').filter({
      hasText: "Request 3–6 months of bank statement history",
    })
  ).toBeVisible();
  await expect(page.getByText("Total credits")).toBeVisible();
  await expect(page.getByText("Rs11,381.00")).toBeVisible();
  await expect(page.getByText("Total debits")).toBeVisible();
  await expect(page.getByText("Rs12,804.00")).toBeVisible();
  await expect(page.getByText("Minimum balance")).toBeVisible();
  await expect(
    page.locator('[data-testid="statement-summary"]').getByText("Rs157.14").first()
  ).toBeVisible();

  const confidenceValues = await page.locator('[data-testid="confidence-value"]').allTextContents();
  expect(confidenceValues.length).toBeGreaterThan(0);
  for (const value of confidenceValues) {
    const numeric = Number(value.replace("%", "").trim());
    expect(Number.isFinite(numeric)).toBeTruthy();
    expect(numeric).toBeLessThanOrEqual(100);
  }

  await expect(page.getByText("Loan Amount")).toHaveCount(0);
  await expect(page.getByText("Interest Rate")).toHaveCount(0);
  await expect(page.getByText("Employment")).toHaveCount(0);
});
