"use client";

import { useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  File,
  FileCheck2,
  Loader2,
  Lock,
  Shield,
  UploadCloud,
  X,
} from "lucide-react";

import {
  CheckItem,
  PageHeader,
  SectionHeading,
  StatusBadge,
  Surface,
  toneClass,
} from "@/components/argentnorth/prototype-ui";
import type { RiskTone } from "@/lib/argentnorth-prototype";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { getApiToken } from "@/lib/auth";
import { triggerAnalysis, uploadDocument } from "@/lib/api";
import { useOnboardingStore } from "@/store/onboarding";

import { DOCUMENT_TYPE_OPTIONS } from "./use-upload-analysis-progress";

const MAX_UPLOAD_SIZE_MB = 50;
const ACCEPTED_UPLOAD_EXTENSIONS = ".pdf,.png,.jpg,.jpeg";
const SUPPORTED_MIME_TYPES = new Set(["application/pdf", "image/png", "image/jpeg"]);
const IMAGE_HEADER_SEARCH_BYTES = 1024;
const UNSUPPORTED_FILE_MESSAGE = "Unsupported file content. Upload a valid PDF, PNG, or JPEG file.";

type UploadState = "idle" | "uploading" | "error";
type StepStatus = "complete" | "active" | "pending";

interface IntakeStep {
  label: string;
  detail: string;
  status: StepStatus;
}

function statusTone(status: StepStatus): RiskTone {
  if (status === "complete") return "good";
  if (status === "active") return "warning";
  return "neutral";
}

function inferMimeTypeFromFilename(filename: string): string {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".pdf")) return "application/pdf";
  if (lower.endsWith(".png")) return "image/png";
  if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
  return "";
}

function getFileMimeType(file: File | null): string {
  if (!file) return "";
  return file.type || inferMimeTypeFromFilename(file.name);
}

function byteSequenceMatches(bytes: Uint8Array, offset: number, signature: number[]): boolean {
  return signature.every((byte, index) => bytes[offset + index] === byte);
}

async function sniffFileMimeType(file: File): Promise<string> {
  const declaredMimeType = getFileMimeType(file);
  if (declaredMimeType === "application/pdf") {
    return declaredMimeType;
  }

  const header = new Uint8Array(await file.slice(0, IMAGE_HEADER_SEARCH_BYTES).arrayBuffer());

  if (byteSequenceMatches(header, 0, [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])) {
    return "image/png";
  }
  if (byteSequenceMatches(header, 0, [0xff, 0xd8, 0xff])) {
    return "image/jpeg";
  }

  return "";
}

function formatMimeLabel(mimeType: string): string {
  switch (mimeType) {
    case "application/pdf":
      return "PDF document";
    case "image/png":
      return "PNG image";
    case "image/jpeg":
      return "JPEG image";
    default:
      return "Document";
  }
}

function isPdfMimeType(mimeType: string): boolean {
  return mimeType === "application/pdf";
}

function trimToUndefined(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed || undefined;
}

export default function UploadPage() {
  const router = useRouter();
  const { getToken } = useAuth();
  const { markDocumentUploaded } = useOnboardingStore();

  const [isDragging, setIsDragging] = useState(false);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [localFile, setLocalFile] = useState<File | null>(null);
  const [localFileMimeType, setLocalFileMimeType] = useState("");
  const [password, setPassword] = useState("");
  const [documentType, setDocumentType] = useState<string>("auto");
  const [applicantName, setApplicantName] = useState("");
  const [applicantEmail, setApplicantEmail] = useState("");
  const [applicantPhone, setApplicantPhone] = useState("");
  const [uploadedDocumentId, setUploadedDocumentId] = useState<string | null>(null);
  const [createdCaseId, setCreatedCaseId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const showPasswordField = isPdfMimeType(localFileMimeType);

  const selectedDocTypeLabel =
    DOCUMENT_TYPE_OPTIONS.find((option) => option.value === documentType)?.label ??
    "Auto-detect (recommended)";
  const hasCreatedCaseContext = Boolean(uploadedDocumentId && createdCaseId);

  const intakeSteps = useMemo<IntakeStep[]>(() => {
    const fileSelected = Boolean(localFile);
    const applicantFilled = Boolean(applicantName.trim() || applicantEmail.trim() || applicantPhone.trim());
    const docTypeChosen = documentType !== "auto";
    const analyzed = hasCreatedCaseContext && uploadState !== "error";

    let activeIndex = 0;
    if (!fileSelected) activeIndex = 0;
    else if (!applicantFilled) activeIndex = 1;
    else if (!docTypeChosen) activeIndex = 2;
    else activeIndex = 3;

    const statuses: StepStatus[] = [
      fileSelected ? "complete" : "active",
      applicantFilled ? "complete" : fileSelected ? "active" : "pending",
      docTypeChosen ? "complete" : applicantFilled ? "active" : "pending",
      analyzed ? "complete" : activeIndex === 3 ? "active" : "pending",
    ];

    return [
      {
        label: "Select evidence",
        detail: "Pick a PDF, PNG, or JPEG document up to 50MB.",
        status: statuses[0],
      },
      {
        label: "Applicant details",
        detail: "Optional name, email, phone to label the case.",
        status: statuses[1],
      },
      {
        label: "Classify document",
        detail: "Auto-detect or pick a specific document type.",
        status: statuses[2],
      },
      {
        label: "Create case and analyze",
        detail: "Upload to org-scoped storage, then run analysis.",
        status: statuses[3],
      },
    ];
  }, [localFile, applicantName, applicantEmail, applicantPhone, documentType, hasCreatedCaseContext, uploadState]);

  const overallStatusBadge = useMemo(() => {
    if (uploadState === "uploading") return { label: "Analyzing…", tone: "warning" as RiskTone };
    if (uploadState === "error") return { label: "Action needed", tone: "danger" as RiskTone };
    if (hasCreatedCaseContext) return { label: "Case created", tone: "good" as RiskTone };
    if (localFile) return { label: "Ready to analyze", tone: "good" as RiskTone };
    return { label: "Awaiting file", tone: "neutral" as RiskTone };
  }, [uploadState, hasCreatedCaseContext, localFile]);

  const validateAndSetFile = async (selectedFile: File) => {
    const detectedMimeType = await sniffFileMimeType(selectedFile);
    if (!SUPPORTED_MIME_TYPES.has(detectedMimeType)) {
      setUploadState("error");
      setErrorMsg(UNSUPPORTED_FILE_MESSAGE);
      return;
    }
    if (selectedFile.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024) {
      setUploadState("error");
      setErrorMsg(`File must be under ${MAX_UPLOAD_SIZE_MB}MB.`);
      return;
    }

    setLocalFile(selectedFile);
    setLocalFileMimeType(detectedMimeType || getFileMimeType(selectedFile));
    setPassword("");
    setUploadState("idle");
    setErrorMsg("");
    setUploadedDocumentId(null);
    setCreatedCaseId(null);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      void validateAndSetFile(e.target.files[0]);
    }
  };

  const handleRemoveFile = () => {
    setLocalFile(null);
    setLocalFileMimeType("");
    setPassword("");
    setDocumentType("auto");
    setUploadState("idle");
    setErrorMsg("");
    setUploadedDocumentId(null);
    setCreatedCaseId(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const startAnalysisFlow = async () => {
    if (!localFile) return;

    try {
      setUploadState("uploading");
      setErrorMsg("");

      const token = await getApiToken(getToken);
      let documentId = uploadedDocumentId;
      let caseId = createdCaseId;

      if (!documentId || !caseId) {
        const doc = await uploadDocument({
          file: localFile,
          token,
          password: showPasswordField ? password || undefined : undefined,
          documentType: documentType === "auto" ? undefined : documentType,
          applicantName: trimToUndefined(applicantName),
          applicantEmail: trimToUndefined(applicantEmail),
          applicantPhone: trimToUndefined(applicantPhone),
        });

        documentId = doc.id;
        caseId = doc.case_id || doc.id;
        setUploadedDocumentId(documentId);
        setCreatedCaseId(caseId);
        markDocumentUploaded();
      }

      await triggerAnalysis(documentId, token);
      router.push(`/dashboard/cases/${caseId}`);
    } catch (err) {
      console.error("Unable to start analysis:", err);
      setUploadState("error");
      setErrorMsg(err instanceof Error ? err.message : "Something went wrong.");
    }
  };

  const showRecoveryActions = Boolean(uploadedDocumentId && createdCaseId && uploadState === "error");

  return (
    <div className="flex flex-col gap-6 pb-10">
      <PageHeader
        eyebrow="Evidence Intake"
        title="Guided case creation with live validation."
        description="Upload the first applicant document, classify it, and attach enough context for underwriting review."
      >
        <StatusBadge label={overallStatusBadge.label} tone={overallStatusBadge.tone} />
        <Button
          asChild
          variant="outline"
          className="h-9 rounded-lg border-[var(--border-card)] bg-[var(--surface-raised)] text-[13px]"
        >
          <Link href="/dashboard/cases">Open Queue</Link>
        </Button>
      </PageHeader>

      <div className="grid items-start gap-6 xl:grid-cols-[280px_1fr_360px]">
        <Surface className="overflow-hidden">
          <div className="border-b border-[var(--border-card)] px-5 py-4">
            <SectionHeading icon={ClipboardCheck} title="Workflow" />
          </div>
          <div className="divide-y divide-[var(--border-subtle)]">
            {intakeSteps.map((step, index) => {
              const style = toneClass(statusTone(step.status));

              return (
                <div
                  key={step.label}
                  className={cn(
                    "flex w-full gap-3 px-5 py-4",
                    step.status === "active" ? "bg-primary/[0.06]" : ""
                  )}
                >
                  <span
                    className={cn(
                      "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border font-mono text-[11px] font-semibold",
                      style.bg,
                      style.border,
                      style.text
                    )}
                  >
                    {step.status === "complete" ? (
                      <CheckCircle2 className="h-3.5 w-3.5" />
                    ) : (
                      index + 1
                    )}
                  </span>
                  <span className="min-w-0">
                    <span className="flex items-center gap-2">
                      <span className="text-[13px] font-semibold text-[var(--text-primary)]">{step.label}</span>
                      <span className={cn("h-1.5 w-1.5 rounded-full", style.dot)} />
                    </span>
                    <span className="mt-1 block text-[12px] leading-relaxed text-[var(--text-tertiary)]">
                      {step.detail}
                    </span>
                  </span>
                </div>
              );
            })}
          </div>
        </Surface>

        <Surface className="overflow-hidden">
          <div className="border-b border-[var(--border-card)] px-6 py-5">
            <SectionHeading
              icon={UploadCloud}
              title="Applicant and Evidence Details"
              description="PDF, PNG, and JPEG uploads are verified locally before the backend starts analysis."
              action={
                <StatusBadge
                  label={localFile ? "File ready" : "Awaiting file"}
                  tone={localFile ? "good" : "neutral"}
                />
              }
            />
          </div>

          <div className="p-5 md:p-6">
            <div
              className={`relative flex min-h-[280px] cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-4 py-14 text-center transition-all duration-300 ${
                isDragging
                  ? "border-primary/50 bg-primary/[0.06] shadow-[var(--shadow-card-hover)]"
                  : "border-[var(--border-card)] bg-[var(--surface-secondary)]/35 hover:bg-[var(--surface-hover)]"
              } ${uploadState === "error" ? "border-red-500/40 bg-red-500/[0.04]" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={(e) => {
                e.preventDefault();
                setIsDragging(false);
              }}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                if (e.dataTransfer.files?.[0]) {
                  void validateAndSetFile(e.dataTransfer.files[0]);
                }
              }}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                type="file"
                className="hidden"
                accept={ACCEPTED_UPLOAD_EXTENSIONS}
                ref={fileInputRef}
                onChange={handleFileChange}
              />

              <div
                className={`mb-5 flex h-14 w-14 items-center justify-center rounded-lg border transition-all duration-300 ${
                  isDragging
                    ? "scale-105 border-primary/20 bg-primary/15 shadow-lg shadow-primary/10"
                    : "border-[var(--border-card)] bg-[var(--surface-raised)]"
                }`}
              >
                {uploadState === "uploading" ? (
                  <Loader2 className="h-6 w-6 animate-spin text-primary" />
                ) : (
                  <UploadCloud className="h-6 w-6 text-primary" />
                )}
              </div>

              <h3 className="mb-1 text-[15px] font-semibold text-[var(--text-primary)]">
                {uploadState === "uploading"
                  ? hasCreatedCaseContext
                    ? "Starting analysis..."
                    : "Uploading and creating case..."
                  : isDragging
                    ? "Drop it here"
                    : "Drop a document here or click to browse"}
              </h3>
              <p className="text-[12px] text-[var(--text-muted)]">
                PDF, PNG, or JPG. Max {MAX_UPLOAD_SIZE_MB}MB.
              </p>

              {uploadState === "error" && (
                <div className="mt-5 flex max-w-md items-center gap-2 rounded-lg bg-red-500/10 px-3 py-2 text-[12px] font-medium text-red-500">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                  {errorMsg || `Invalid file. Please ensure it is a PDF, PNG, or JPEG under ${MAX_UPLOAD_SIZE_MB}MB.`}
                </div>
              )}
            </div>

            {localFile && uploadState !== "uploading" && (
              <div className="mt-5 grid gap-5" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center gap-3 rounded-lg border border-[var(--border-card)] bg-[var(--surface-glass)] px-4 py-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                    <File className="h-4 w-4 text-primary" />
                  </div>
                  <div className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate text-[13px] font-semibold text-[var(--text-primary)]">{localFile.name}</span>
                    <span className="text-[11px] text-[var(--text-muted)]">
                      {(localFile.size / 1024 / 1024).toFixed(2)} MB - {formatMimeLabel(localFileMimeType)}
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={handleRemoveFile}
                    className="shrink-0 cursor-pointer rounded-lg text-[var(--text-muted)] hover:text-red-500"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>

                <div className="grid gap-5 lg:grid-cols-[1fr_0.82fr]">
                  <div className="rounded-lg border border-[var(--border-card)] bg-[var(--surface-glass)] p-4">
                    <p className="text-[12px] font-semibold text-[var(--text-primary)]">Applicant details</p>
                    <p className="mt-1 text-[11px] text-[var(--text-muted)]">
                      Optional fields that help name and find the case after upload.
                    </p>

                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      <div className="space-y-1.5 sm:col-span-2">
                        <Label htmlFor="applicant-name" className="text-[11px] font-medium text-[var(--text-muted)]">
                          Applicant name
                        </Label>
                        <Input
                          id="applicant-name"
                          placeholder="Aarav Sharma"
                          value={applicantName}
                          onChange={(e) => setApplicantName(e.target.value)}
                          className="h-9 border-[var(--border-card)] bg-[var(--surface-glass)] text-[13px] text-[var(--text-primary)]"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <Label htmlFor="applicant-email" className="text-[11px] font-medium text-[var(--text-muted)]">
                          Email
                        </Label>
                        <Input
                          id="applicant-email"
                          type="email"
                          placeholder="applicant@example.com"
                          value={applicantEmail}
                          onChange={(e) => setApplicantEmail(e.target.value)}
                          className="h-9 border-[var(--border-card)] bg-[var(--surface-glass)] text-[13px] text-[var(--text-primary)]"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <Label htmlFor="applicant-phone" className="text-[11px] font-medium text-[var(--text-muted)]">
                          Phone
                        </Label>
                        <Input
                          id="applicant-phone"
                          type="tel"
                          placeholder="+91 98765 43210"
                          value={applicantPhone}
                          onChange={(e) => setApplicantPhone(e.target.value)}
                          className="h-9 border-[var(--border-card)] bg-[var(--surface-glass)] text-[13px] text-[var(--text-primary)]"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="rounded-lg border border-[var(--border-card)] bg-[var(--surface-glass)] p-4">
                    <p className="text-[12px] font-semibold text-[var(--text-primary)]">Analysis setup</p>
                    <p className="mt-1 text-[11px] text-[var(--text-muted)]">
                      Classification and protected-file handling for this evidence packet.
                    </p>

                    <div className="mt-4 space-y-4">
                      {showPasswordField && (
                        <div>
                          <div className="mb-1.5 flex items-center gap-2">
                            <Lock className="h-3 w-3 text-[var(--text-muted)]" />
                            <label className="text-[11px] font-medium text-[var(--text-muted)]">
                              PDF password
                            </label>
                          </div>
                          <Input
                            type="password"
                            placeholder="Enter password if protected"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="h-9 border-[var(--border-card)] bg-[var(--surface-glass)] text-[13px] text-[var(--text-primary)]"
                          />
                        </div>
                      )}

                      <div>
                        <div className="mb-1.5 flex items-center gap-2">
                          <Shield className="h-3 w-3 text-[var(--text-muted)]" />
                          <label className="text-[11px] font-medium text-[var(--text-muted)]">Document type</label>
                        </div>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              type="button"
                              variant="outline"
                              className="h-9 w-full justify-between rounded-lg border-[var(--border-card)] bg-[var(--surface-glass)] px-3 text-[13px] font-medium text-[var(--text-primary)]"
                            >
                              <span className="truncate">{selectedDocTypeLabel}</span>
                              <ChevronDown className="h-4 w-4 shrink-0 text-[var(--text-muted)]" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent
                            align="start"
                            className="w-[var(--radix-dropdown-menu-trigger-width)] border-[var(--border-card)] bg-[var(--popover)] text-[var(--popover-foreground)] shadow-2xl"
                          >
                            <DropdownMenuRadioGroup value={documentType} onValueChange={setDocumentType}>
                              {DOCUMENT_TYPE_OPTIONS.map((option) => (
                                <DropdownMenuRadioItem
                                  key={option.value}
                                  value={option.value}
                                  className="rounded-md px-2 py-2 focus:bg-[var(--surface-secondary)] data-[state=checked]:bg-[var(--surface-secondary)]"
                                >
                                  <div className="flex flex-col gap-0.5">
                                    <span className="text-[13px] font-medium text-[var(--text-primary)]">{option.label}</span>
                                    <span className="text-[11px] text-[var(--text-muted)]">{option.hint}</span>
                                  </div>
                                </DropdownMenuRadioItem>
                              ))}
                            </DropdownMenuRadioGroup>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>
                  </div>
                </div>

                {showRecoveryActions && createdCaseId ? (
                  <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-4">
                    <p className="text-[12px] font-medium text-[var(--text-secondary)]">
                      The document is uploaded, but analysis has not started yet.
                    </p>
                    <p className="mt-1 text-[11px] text-[var(--text-muted)]">
                      Retry the analysis now or open the case and continue from there.
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        className="h-8 cursor-pointer text-[12px]"
                        onClick={startAnalysisFlow}
                      >
                        Retry Analysis
                      </Button>
                      <Button asChild type="button" variant="ghost" className="h-8 cursor-pointer gap-1.5 text-[12px]">
                        <Link href={`/dashboard/cases/${createdCaseId}`}>
                          Open Case
                          <ArrowRight className="h-3 w-3" />
                        </Link>
                      </Button>
                    </div>
                  </div>
                ) : null}

                <Button
                  className="h-10 w-full cursor-pointer gap-2 rounded-lg bg-primary font-semibold text-primary-foreground shadow-lg shadow-primary/20 hover:bg-primary/90"
                  onClick={startAnalysisFlow}
                  disabled={!localFile}
                >
                  {hasCreatedCaseContext ? "Retry Analysis" : "Create Case and Analyze"}
                </Button>
              </div>
            )}
          </div>
        </Surface>

        <div className="flex flex-col gap-6">
          <Surface className="overflow-hidden">
            <div className="border-b border-[var(--border-card)] px-5 py-4">
              <SectionHeading icon={FileCheck2} title="Evidence Packet" />
            </div>
            <div className="px-5 py-4 space-y-3">
              <CheckItem>File type is verified from content, not only extension.</CheckItem>
              <CheckItem>Uploads stay under authenticated, org-scoped access.</CheckItem>
              <CheckItem>Document type guides extraction and risk checks.</CheckItem>
              <CheckItem tone="neutral">Protected PDFs can include a password before upload.</CheckItem>
            </div>
          </Surface>

          <Surface className="p-5">
            <SectionHeading icon={File} title="Accepted Evidence" />
            <div className="mt-4 grid grid-cols-3 gap-2">
              {["PDF", "PNG", "JPG"].map((item) => (
                <div
                  key={item}
                  className="rounded-lg border border-[var(--border-card)] bg-[var(--surface-secondary)]/45 px-3 py-3 text-center"
                >
                  <p className="font-mono text-[15px] font-semibold text-[var(--text-primary)]">{item}</p>
                  <p className="mt-1 text-[10px] uppercase tracking-[0.12em] text-[var(--text-muted)]">file</p>
                </div>
              ))}
            </div>
            <p className="mt-4 text-[11px] leading-relaxed text-[var(--text-tertiary)]">
              Max {MAX_UPLOAD_SIZE_MB}MB per file. PDFs may include a password if protected.
            </p>
          </Surface>
        </div>
      </div>
    </div>
  );
}
