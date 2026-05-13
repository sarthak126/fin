# LoanLens Data Flow - Current Implementation

This note describes what the application stores today. It is intentionally written as an engineering source of truth, not marketing copy.

## Uploaded Documents

- Users upload PDF, PNG, or JPEG files through the document upload API.
- The backend validates file type by sniffing file bytes before creating the document record.
- Document blobs are stored through `storage_service`:
  - S3 mode stores objects in the configured S3 bucket and applies server-side encryption parameters.
  - Local mode writes encrypted blobs under the backend upload directory.
- The `Document` database record stores metadata including file URL/path, original filename, file type, status, owner user, organization, and optional case ID.

## Password-Protected PDFs

- If a PDF password is supplied, the password can be stored temporarily through the same storage service using a password-specific storage key.
- Password cleanup helpers exist, but retention behavior should be verified before any live pilot data is used.

## Extraction And Analysis Outputs

- Extracted fields, summaries, risk alerts, confidence values, processing metadata, and raw model/analysis payloads are persisted in analysis records.
- Case-level analysis stores aggregated decision fields, follow-ups, limitations, extracted fields, risk alerts, and raw response payloads.
- These records are retained for review and reporting; the product should not claim that analysis data is never stored.

## Vector Search Data

- Document chunks and embeddings can be stored in ChromaDB for retrieval and Ask AI workflows.
- Vector entries include document-linked chunk text and metadata such as page number, section title, and document ID.
- Deleting a document should also delete its vectors before live pilot usage is considered safe.

## Background Job Artifacts

- Analysis job status is currently persisted as JSON manifests under the configured analysis jobs path.
- These manifests include document ID, status, timestamps, progress fields, OCR status, and error details.
- This queue is suitable for local/dev use and should be replaced or hardened before multi-instance production deployment.

## Deletion Controls

- `DELETE /api/v1/documents/{document_id}` deletes an org-scoped document, its document analysis rows, stored file, password sidecar, extraction sidecar, ChromaDB vectors, job manifest, and any final case analysis snapshot for the parent case.
- `DELETE /api/v1/cases/{case_id}` deletes an org-scoped case, its case analysis rows, all attached documents, and the same per-document artifacts listed above.
- Deletion is hard-delete behavior today. It is scoped by organization and restricted to admin/analyst roles.
- Retention cleanup can be run with `python backend/scripts/run_retention_cleanup.py --pretty`.
- Retention windows are configurable with `RETENTION_CASE_DAYS`, `RETENTION_DOCUMENT_DAYS`, `RETENTION_AUDIT_LOG_DAYS`, and `RETENTION_BATCH_SIZE`.
- Cases are purged by `updated_at`; documents are purged by `created_at`; audit logs are purged by `created_at`.
- Expired document cleanup uses the same storage/password/extraction/vector/job-manifest cleanup path as manual document deletion.

## Role Controls

- Viewer users can read org-scoped documents, cases, saved analyses, and analysis job status.
- Admin and analyst users can create cases, upload documents, update applicant info, queue analysis/reanalysis, finalize cases, export case reports, use Ask AI, and delete documents/cases.
- Role checks are enforced at the API route layer today.

## Audit Logs

- Sensitive API actions now write audit log records through the existing `audit_logs` table.
- Logged events include document upload/view/delete, document analysis/reanalysis requests, saved analysis views, case create/view/update/finalize/delete, case report export, and Ask AI usage.
- Audit metadata includes organization ID, user role, resource identifiers, request IP when available, and small operational facts such as file type or question length.
- Ask AI audit logs intentionally store question length rather than the raw question text.
- Critical audit writes fail closed at the API response boundary today. Upload, analyze/reanalyze, case create/update/finalize/delete, document/case Ask AI, and case report export return `503` if their audit row cannot be written.
- Passive read audit writes are best-effort today: failures are logged by the backend but do not block document/case/analysis reads.

## Production Readiness Gate

- Run `python backend/scripts/check_production_readiness.py --pretty` before a production deploy.
- Add `--include-storage` to verify a live S3/KMS document and password round-trip.
- Add `--include-clerk` to verify Clerk JWKS can be fetched with the configured Clerk secret.
- The readiness gate fails on unsafe production config, stale Prisma client/schema issues, missing audit log columns, and failed audit write/delete round-trips.

## Current Gaps Before Live Pilot Data

- Schedule `run_retention_cleanup.py` through the production scheduler and alert on failures.
- Make audit logging fully atomic with the primary mutation using a transaction/outbox for production compliance requirements.
- Confirm production storage encryption, backup, and access policies in the deployment environment.
