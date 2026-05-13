ALTER TABLE "case_analyses"
ADD COLUMN "is_final" BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX "case_analyses_case_id_is_final_idx" ON "case_analyses"("case_id", "is_final");
