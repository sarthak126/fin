-- AlterTable
ALTER TABLE "analyses"
ADD COLUMN "decision_status" TEXT,
ADD COLUMN "decision_recommendation" TEXT,
ADD COLUMN "decision_reason" TEXT,
ADD COLUMN "extraction_confidence" DOUBLE PRECISION,
ADD COLUMN "risk_confidence" DOUBLE PRECISION,
ADD COLUMN "data_completeness" DOUBLE PRECISION,
ADD COLUMN "required_followups_json" TEXT;
