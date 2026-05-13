"""
Durable analysis job queue backed by filesystem manifests.

This keeps queued jobs alive across app restarts and lets the worker resume
unfinished analysis jobs on startup without requiring a database migration.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.config import get_settings
from core.database import db as prisma_db
from models import DocumentStatus
from services.analysis_service import run_analysis_for_document
from services.extraction_service import resolve_ocr_quality_status

settings = get_settings()

JOB_STATUS_QUEUED = "queued"
JOB_STATUS_PROCESSING = "processing"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"

_queue_lock = asyncio.Lock()
_wake_event = asyncio.Event()
_stop_event = asyncio.Event()
_worker_task: asyncio.Task | None = None
_worker_id = f"analysis-worker-{uuid.uuid4().hex[:8]}"


@dataclass
class AnalysisJobManifest:
    job_id: str
    document_id: str
    status: str
    attempts: int
    max_attempts: int
    created_at: str
    updated_at: str
    stage: str | None = None
    stage_message: str | None = None
    ocr_provider: str | None = None
    pages_processed: int | None = None
    total_pages: int | None = None
    ocr_required_pages: list[int] | None = None
    ocr_failed_pages: list[int] | None = None
    ocr_unreliable_pages: list[int] | None = None
    ocr_fallback_used: bool | None = None
    started_at: str | None = None
    completed_at: str | None = None
    last_error: str | None = None
    worker_id: str | None = None
    force_reanalysis: bool = False


def classify_analysis_error(error: str | None) -> tuple[str | None, str | None]:
    """Convert raw worker failures into stable UI-facing codes/messages."""
    if not error:
        return None, None

    normalized = error.lower()

    if "permission_denied" in normalized or "denied access" in normalized:
        return (
            "ai_provider_access_denied",
            "AI analysis is blocked because the configured Gemini project was denied access. Check the Google API key/project permissions.",
        )

    if "ocr provider unavailable" in normalized:
        return (
            "ocr_provider_unavailable",
            "OCR is unavailable because the configured Document AI processor or dependency is not ready. Check OCR configuration and credentials.",
        )

    if "tesseract missing" in normalized:
        return (
            "tesseract_missing",
            "OCR fallback is unavailable because Tesseract is not installed on the backend.",
        )

    if "image decode failure" in normalized:
        return (
            "image_decode_failed",
            "The uploaded image could not be decoded for OCR. Try a different PNG or JPEG file.",
        )

    if "ocr completed with no readable text" in normalized:
        return (
            "ocr_no_readable_text",
            "OCR finished but we could not recover any readable text from this file. Try a clearer scan or higher-resolution image.",
        )

    if "ocr quality is insufficient" in normalized:
        return (
            "ocr_quality_blocked",
            "Analysis is blocked because OCR did not recover reliable text for every required page. Review the failed or unreliable pages and re-upload a clearer file if needed.",
        )

    if "password-protected" in normalized:
        return (
            "pdf_password_required",
            "This PDF is password-protected. Re-upload it with the correct password to continue analysis.",
        )

    if "no text could be extracted" in normalized:
        return (
            "document_text_extraction_failed",
            "We could not extract readable text from this document. Try a clearer PDF or a higher-quality scan.",
        )

    if "failed to open stream" in normalized:
        return (
            "document_stream_unreadable",
            "The uploaded document could not be opened for analysis. Re-upload the file or try a fresh PDF export.",
        )

    if "gemini analysis failed" in normalized or "gemini api error" in normalized:
        return (
            "ai_provider_error",
            "The AI provider failed while analyzing this document. Check the backend AI configuration and logs.",
        )

    return (
        "analysis_failed",
        "Analysis failed in the background worker. Check the backend logs for the full error.",
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _manifest_ocr_quality_status(
    manifest: AnalysisJobManifest,
    *,
    error_code: str | None = None,
) -> str:
    return resolve_ocr_quality_status(
        ocr_required_pages=manifest.ocr_required_pages,
        ocr_failed_pages=manifest.ocr_failed_pages,
        ocr_unreliable_pages=manifest.ocr_unreliable_pages,
        ocr_fallback_used=bool(manifest.ocr_fallback_used),
        job_status=manifest.status,
        stage=manifest.stage,
        pages_processed=manifest.pages_processed,
        total_pages=manifest.total_pages,
        error_code=error_code,
    )


def _queue_dir() -> Path:
    root = Path(settings.ANALYSIS_JOBS_PATH)
    if root.is_absolute():
        return root
    return (Path(__file__).resolve().parent.parent / root).resolve()


def _job_path(document_id: str) -> Path:
    return _queue_dir() / f"{document_id}.json"


def _read_manifest_sync(document_id: str) -> AnalysisJobManifest | None:
    path = _job_path(document_id)
    if not path.exists():
        return None
    return AnalysisJobManifest(**json.loads(path.read_text(encoding="utf-8")))


def _write_manifest_sync(manifest: AnalysisJobManifest) -> None:
    path = _job_path(manifest.document_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _delete_manifest_sync(document_id: str) -> None:
    path = _job_path(document_id)
    if path.exists():
        path.unlink()


def _list_manifests_sync() -> list[AnalysisJobManifest]:
    queue_dir = _queue_dir()
    if not queue_dir.exists():
        return []

    manifests: list[AnalysisJobManifest] = []
    for path in queue_dir.glob("*.json"):
        try:
            manifests.append(AnalysisJobManifest(**json.loads(path.read_text(encoding="utf-8"))))
        except Exception as exc:
            print(f"[queue][warn] Failed to read job manifest {path.name}: {exc}")
    return manifests


async def enqueue_analysis_job(
    document_id: str,
    *,
    force_reanalysis: bool = False,
) -> AnalysisJobManifest:
    """
    Persist a queued job manifest so the worker can pick it up immediately and
    again after a restart if needed.
    """
    async with _queue_lock:
        existing = await asyncio.to_thread(_read_manifest_sync, document_id)
        now = _utc_now()

        if existing and existing.status in {JOB_STATUS_QUEUED, JOB_STATUS_PROCESSING}:
            if force_reanalysis and not existing.force_reanalysis:
                existing.force_reanalysis = True
                existing.updated_at = now
                await asyncio.to_thread(_write_manifest_sync, existing)
            _wake_event.set()
            return existing

        manifest = AnalysisJobManifest(
            job_id=uuid.uuid4().hex,
            document_id=document_id,
            status=JOB_STATUS_QUEUED,
            stage="queued",
            stage_message="Analysis queued.",
            attempts=0,
            max_attempts=settings.ANALYSIS_JOB_MAX_ATTEMPTS,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            ocr_provider=None,
            pages_processed=0,
            total_pages=None,
            ocr_required_pages=[],
            ocr_failed_pages=[],
            ocr_unreliable_pages=[],
            ocr_fallback_used=False,
            completed_at=None,
            started_at=None,
            last_error=None,
            worker_id=None,
            force_reanalysis=bool(force_reanalysis),
        )
        await asyncio.to_thread(_write_manifest_sync, manifest)
        _wake_event.set()
        return manifest


async def start_analysis_job_worker() -> None:
    """Boot the durable queue worker and recover unfinished jobs."""
    global _worker_task

    queue_dir = _queue_dir()
    queue_dir.mkdir(parents=True, exist_ok=True)
    _stop_event.clear()

    await _recover_unfinished_jobs()

    if _worker_task and not _worker_task.done():
        _wake_event.set()
        return

    _worker_task = asyncio.create_task(_analysis_worker_loop(), name="analysis-job-worker")
    _wake_event.set()


async def stop_analysis_job_worker() -> None:
    """Stop the durable queue worker gracefully."""
    global _worker_task

    if not _worker_task:
        return

    _stop_event.set()
    _wake_event.set()

    try:
        await _worker_task
    finally:
        _worker_task = None


async def _recover_unfinished_jobs() -> None:
    """
    Recover any processing documents and manifests after a restart.

    - Documents still marked `processing` get a queued manifest if one is missing.
    - Manifests left in `processing` are reset to `queued`.
    """
    processing_docs = await prisma_db.document.find_many(
        where={"status": DocumentStatus.PROCESSING.value}
    )

    async with _queue_lock:
        for document in processing_docs:
            existing = await asyncio.to_thread(_read_manifest_sync, document.id)
            if existing:
                if existing.status == JOB_STATUS_PROCESSING:
                    existing.status = JOB_STATUS_QUEUED
                    existing.stage = "queued"
                    existing.stage_message = "Recovered queued analysis job."
                    existing.worker_id = None
                    existing.started_at = None
                    existing.updated_at = _utc_now()
                    existing.last_error = "Recovered after restart before job completion."
                    await asyncio.to_thread(_write_manifest_sync, existing)
                continue

            manifest = AnalysisJobManifest(
                job_id=uuid.uuid4().hex,
                document_id=document.id,
                status=JOB_STATUS_QUEUED,
                stage="queued",
                stage_message="Recovered queued analysis job.",
                attempts=0,
                max_attempts=settings.ANALYSIS_JOB_MAX_ATTEMPTS,
                created_at=_utc_now(),
                updated_at=_utc_now(),
                ocr_provider=None,
                pages_processed=0,
                total_pages=None,
                ocr_required_pages=[],
                ocr_failed_pages=[],
                ocr_unreliable_pages=[],
                ocr_fallback_used=False,
                started_at=None,
                completed_at=None,
                last_error="Recovered queued job from processing document state.",
                worker_id=None,
                force_reanalysis=False,
            )
            await asyncio.to_thread(_write_manifest_sync, manifest)


async def _analysis_worker_loop() -> None:
    poll_seconds = max(1, settings.ANALYSIS_JOB_POLL_SECONDS)

    while not _stop_event.is_set():
        manifest = await _lease_next_job()
        if manifest is None:
            _wake_event.clear()
            try:
                await asyncio.wait_for(_wake_event.wait(), timeout=poll_seconds)
            except asyncio.TimeoutError:
                pass
            continue

        try:
            result = await run_analysis_for_document(
                manifest.document_id,
                progress_callback=lambda **payload: update_analysis_job_progress(
                    manifest.document_id,
                    **payload,
                ),
                force_reanalysis=bool(manifest.force_reanalysis),
            )
            if result in {"completed", "already_analyzed"}:
                await _mark_job_completed(manifest.document_id)
            else:
                await _mark_job_failed(manifest.document_id, f"Unexpected job result: {result}")
        except Exception as exc:
            await _mark_job_failed(manifest.document_id, str(exc))


async def _lease_next_job() -> AnalysisJobManifest | None:
    async with _queue_lock:
        manifests = await asyncio.to_thread(_list_manifests_sync)
        queued = [
            manifest
            for manifest in manifests
            if manifest.status == JOB_STATUS_QUEUED
        ]
        if not queued:
            return None

        queued.sort(key=lambda manifest: (manifest.created_at, manifest.updated_at))
        manifest = queued[0]
        manifest.status = JOB_STATUS_PROCESSING
        manifest.stage = manifest.stage or "queued"
        manifest.stage_message = manifest.stage_message or "Analysis queued."
        manifest.attempts += 1
        manifest.started_at = _utc_now()
        manifest.updated_at = manifest.started_at
        manifest.worker_id = _worker_id
        await asyncio.to_thread(_write_manifest_sync, manifest)
        return manifest


async def update_analysis_job_progress(
    document_id: str,
    *,
    stage: str | None = None,
    stage_message: str | None = None,
    ocr_provider: str | None = None,
    pages_processed: int | None = None,
    total_pages: int | None = None,
    ocr_required_pages: list[int] | None = None,
    ocr_failed_pages: list[int] | None = None,
    ocr_unreliable_pages: list[int] | None = None,
    ocr_fallback_used: bool | None = None,
) -> None:
    async with _queue_lock:
        manifest = await asyncio.to_thread(_read_manifest_sync, document_id)
        if not manifest:
            return

        if stage is not None:
            manifest.stage = stage
        if stage_message is not None:
            manifest.stage_message = stage_message
        if ocr_provider is not None:
            manifest.ocr_provider = ocr_provider
        if pages_processed is not None:
            manifest.pages_processed = pages_processed
        if total_pages is not None:
            manifest.total_pages = total_pages
        if ocr_required_pages is not None:
            manifest.ocr_required_pages = list(ocr_required_pages)
        if ocr_failed_pages is not None:
            manifest.ocr_failed_pages = list(ocr_failed_pages)
        if ocr_unreliable_pages is not None:
            manifest.ocr_unreliable_pages = list(ocr_unreliable_pages)
        if ocr_fallback_used is not None:
            manifest.ocr_fallback_used = bool(ocr_fallback_used)

        if manifest.status not in {JOB_STATUS_COMPLETED, JOB_STATUS_FAILED}:
            manifest.status = JOB_STATUS_PROCESSING
        manifest.updated_at = _utc_now()
        await asyncio.to_thread(_write_manifest_sync, manifest)


async def _mark_job_completed(document_id: str) -> None:
    async with _queue_lock:
        manifest = await asyncio.to_thread(_read_manifest_sync, document_id)
        if not manifest:
            return

        now = _utc_now()
        manifest.status = JOB_STATUS_COMPLETED
        manifest.stage = "completed"
        manifest.stage_message = "Analysis complete."
        manifest.completed_at = now
        manifest.updated_at = now
        manifest.worker_id = _worker_id
        manifest.last_error = None
        if manifest.total_pages is not None and manifest.pages_processed is None:
            manifest.pages_processed = manifest.total_pages
        await asyncio.to_thread(_write_manifest_sync, manifest)


async def _mark_job_failed(document_id: str, error: str) -> None:
    async with _queue_lock:
        manifest = await asyncio.to_thread(_read_manifest_sync, document_id)
        if not manifest:
            return

        error_code, user_message = classify_analysis_error(error)
        manifest.status = JOB_STATUS_FAILED
        manifest.stage = "failed"
        manifest.stage_message = user_message or "Analysis failed."
        manifest.updated_at = _utc_now()
        manifest.worker_id = _worker_id
        manifest.last_error = error[:2000]
        await asyncio.to_thread(_write_manifest_sync, manifest)


async def get_analysis_job(document_id: str) -> dict[str, Any] | None:
    """Return the persisted manifest for a document if one exists."""
    async with _queue_lock:
        manifest = await asyncio.to_thread(_read_manifest_sync, document_id)
        if not manifest:
            return None
        payload = asdict(manifest)
        error_code, user_message = classify_analysis_error(manifest.last_error)
        payload["error_code"] = error_code
        payload["user_message"] = user_message
        payload["ocr_quality_status"] = _manifest_ocr_quality_status(
            manifest,
            error_code=error_code,
        )
        return payload


async def delete_analysis_job(document_id: str) -> None:
    """Delete the persisted analysis job manifest for a document if present."""
    async with _queue_lock:
        await asyncio.to_thread(_delete_manifest_sync, document_id)
