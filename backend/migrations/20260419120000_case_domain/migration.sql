-- Add the case relationship to documents first so legacy data can be wired up
-- during this same migration.
ALTER TABLE "documents"
ADD COLUMN "case_id" TEXT;

-- Cases become the aggregate root. For legacy rows we keep an explicit pointer to
-- the original seed document so old one-document cases remain traceable even
-- after more documents are attached later.
CREATE TABLE "cases" (
    "id" TEXT NOT NULL,
    "name" TEXT,
    "status" TEXT NOT NULL DEFAULT 'draft',
    "legacy_source_document_id" TEXT,
    "user_id" TEXT NOT NULL,
    "org_id" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "cases_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "case_analyses" (
    "id" TEXT NOT NULL,
    "case_id" TEXT NOT NULL,
    "case_status" TEXT NOT NULL DEFAULT 'draft',
    "risk_score" DOUBLE PRECISION,
    "confidence" DOUBLE PRECISION,
    "recommendation" TEXT,
    "decision_status" TEXT,
    "decision_recommendation" TEXT,
    "decision_reason" TEXT,
    "extraction_confidence" DOUBLE PRECISION,
    "risk_confidence" DOUBLE PRECISION,
    "data_completeness" DOUBLE PRECISION,
    "required_followups_json" TEXT,
    "analysis_limitations_json" TEXT,
    "extracted_fields" TEXT,
    "risk_alerts" TEXT,
    "summary" TEXT,
    "processing_time_seconds" DOUBLE PRECISION,
    "model_used" TEXT,
    "raw_response" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "case_analyses_pkey" PRIMARY KEY ("id")
);

-- Legacy backfill strategy:
-- 1. Create one deterministic case per existing document.
-- 2. Reuse the original document UUID as the legacy case UUID.
-- 3. Persist the seed document reference on the case row.
-- 4. Promote analyzed documents to finalized cases; everything else is
--    considered still collecting.
INSERT INTO "cases" (
    "id",
    "name",
    "status",
    "legacy_source_document_id",
    "user_id",
    "org_id",
    "created_at",
    "updated_at"
)
SELECT
    d."id",
    COALESCE(
        NULLIF(d."original_filename", ''),
        NULLIF(d."filename", ''),
        CONCAT('Legacy case ', d."id")
    ),
    CASE
        WHEN d."status" = 'analyzed' THEN 'finalized'
        ELSE 'collecting'
    END,
    d."id",
    d."user_id",
    d."org_id",
    d."created_at",
    d."updated_at"
FROM "documents" d;

-- Point every pre-existing document at its newly created legacy case.
UPDATE "documents"
SET "case_id" = "id"
WHERE "case_id" IS NULL;

-- Mirror historical document analyses into case analyses so legacy cases retain
-- their prior decision history under the new aggregate model.
INSERT INTO "case_analyses" (
    "id",
    "case_id",
    "case_status",
    "risk_score",
    "confidence",
    "recommendation",
    "decision_status",
    "decision_recommendation",
    "decision_reason",
    "extraction_confidence",
    "risk_confidence",
    "data_completeness",
    "required_followups_json",
    "analysis_limitations_json",
    "extracted_fields",
    "risk_alerts",
    "summary",
    "processing_time_seconds",
    "model_used",
    "raw_response",
    "created_at"
)
SELECT
    a."id",
    d."id",
    CASE
        WHEN d."status" = 'analyzed' THEN 'finalized'
        ELSE 'collecting'
    END,
    a."risk_score",
    a."confidence",
    a."recommendation",
    a."decision_status",
    a."decision_recommendation",
    a."decision_reason",
    a."extraction_confidence",
    a."risk_confidence",
    a."data_completeness",
    a."required_followups_json",
    a."analysis_limitations_json",
    a."extracted_fields",
    a."risk_alerts",
    a."summary",
    a."processing_time_seconds",
    a."model_used",
    a."raw_response",
    a."created_at"
FROM "analyses" a
INNER JOIN "documents" d
    ON d."id" = a."document_id";

CREATE INDEX "documents_case_id_idx" ON "documents"("case_id");
CREATE UNIQUE INDEX "cases_legacy_source_document_id_key" ON "cases"("legacy_source_document_id");
CREATE INDEX "cases_user_id_idx" ON "cases"("user_id");
CREATE INDEX "cases_org_id_idx" ON "cases"("org_id");
CREATE INDEX "cases_status_idx" ON "cases"("status");
CREATE INDEX "case_analyses_case_id_idx" ON "case_analyses"("case_id");
CREATE INDEX "case_analyses_case_status_idx" ON "case_analyses"("case_status");

ALTER TABLE "documents"
ADD CONSTRAINT "documents_case_id_fkey"
FOREIGN KEY ("case_id") REFERENCES "cases"("id") ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE "cases"
ADD CONSTRAINT "cases_legacy_source_document_id_fkey"
FOREIGN KEY ("legacy_source_document_id") REFERENCES "documents"("id") ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE "cases"
ADD CONSTRAINT "cases_user_id_fkey"
FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "cases"
ADD CONSTRAINT "cases_org_id_fkey"
FOREIGN KEY ("org_id") REFERENCES "organizations"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "case_analyses"
ADD CONSTRAINT "case_analyses_case_id_fkey"
FOREIGN KEY ("case_id") REFERENCES "cases"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
