from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock
import uuid

from fastapi import HTTPException, status
import fitz

from app.core.file_security import ValidatedUpload
from app.services.ai.ai_factory import get_ai_provider
from app.services.ai.exceptions import AIServiceError
from app.services.ai.schemas import DocumentOrderInput
from app.services.pdf import pdf_service
from app.services.word import word_service

WORKFLOW_TTL_MINUTES = 15


@dataclass
class StagedDocument:
    id: str
    original_filename: str
    extension: str
    pdf_bytes: bytes
    text_snippet: str
    category: str = "Document"
    suggested_filename: str = ""
    suggested_position: int = 1


@dataclass
class WorkflowSession:
    id: str
    documents: dict[str, StagedDocument]
    expires_at: datetime


@dataclass
class WorkflowJob:
    id: str
    status: str = "pending"  # pending | processing | completed | failed
    progress: int = 0
    output_filename: str = "workflow_bundle.pdf"
    result_bytes: bytes | None = None
    error: str | None = None
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=WORKFLOW_TTL_MINUTES)
    )


class WorkflowStore:
    """Thread-safe in-memory store for short-lived workflow sessions and background jobs."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions: dict[str, WorkflowSession] = {}
        self._jobs: dict[str, WorkflowJob] = {}

    def _purge_expired(self) -> None:
        now = datetime.now(timezone.utc)
        expired_sessions = [k for k, v in self._sessions.items() if v.expires_at < now]
        for k in expired_sessions:
            del self._sessions[k]
        expired_jobs = [k for k, v in self._jobs.items() if v.expires_at < now]
        for k in expired_jobs:
            del self._jobs[k]

    def save_session(self, session: WorkflowSession) -> None:
        with self._lock:
            self._purge_expired()
            self._sessions[session.id] = session

    def get_session(self, workflow_id: str) -> WorkflowSession:
        with self._lock:
            self._purge_expired()
            session = self._sessions.get(workflow_id)
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workflow session not found or expired.",
                )
            return session

    def create_job(self, output_filename: str) -> WorkflowJob:
        with self._lock:
            self._purge_expired()
            job = WorkflowJob(id=uuid.uuid4().hex, output_filename=output_filename)
            self._jobs[job.id] = job
            return job

    def get_job(self, job_id: str) -> WorkflowJob:
        with self._lock:
            self._purge_expired()
            job = self._jobs.get(job_id)
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workflow job not found or expired.",
                )
            return job

    def pop_job_result(self, job_id: str) -> tuple[bytes, str]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workflow job not found or expired.",
                )
            if job.status != "completed" or job.result_bytes is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Job is not ready for download (status: {job.status}).",
                )
            data = job.result_bytes
            filename = job.output_filename
            # Clean up binary payload once downloaded to minimize retention.
            job.result_bytes = None
            return data, filename


workflow_store = WorkflowStore()


def _normalize_to_pdf_and_snippet(upload: ValidatedUpload) -> tuple[bytes, str]:
    """Convert any supported document upload to PDF bytes and extract a short text snippet."""
    ext = upload.extension.lower()
    if ext == ".pdf":
        doc = fitz.open(stream=upload.content, filetype="pdf")
        try:
            snippet = "\n".join(doc[i].get_text() for i in range(min(2, doc.page_count))).strip()
        finally:
            doc.close()
        return upload.content, snippet[:1500]

    if ext in (".png", ".jpg", ".jpeg"):
        return word_service.images_to_pdf([upload.content]), f"Image document: {upload.display_filename}"

    if ext == ".txt":
        snippet = upload.content.decode("utf-8", errors="replace")[:1500]
        return word_service.txt_to_pdf(upload.content), snippet

    if ext == ".docx":
        snippet = word_service.extract_docx_text(upload.content)[:1500]
        # Use LibreOffice if available, otherwise render extracted text to PDF cleanly.
        try:
            pdf_bytes = word_service.docx_to_pdf(upload.content)
        except HTTPException:
            pdf_bytes = word_service.txt_to_pdf(snippet.encode("utf-8"))
        return pdf_bytes, snippet

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported workflow file type '{ext}'.",
    )


async def analyze_documents(uploads: list[ValidatedUpload], use_ai: bool = True) -> dict:
    """Stage uploaded documents, convert to PDF, and optionally enrich with AI suggestions."""
    if len(uploads) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload at least 2 documents for a Smart Workflow.",
        )

    staged: dict[str, StagedDocument] = {}
    for idx, up in enumerate(uploads, start=1):
        pdf_bytes, snippet = _normalize_to_pdf_and_snippet(up)
        doc_id = uuid.uuid4().hex[:12]
        staged[doc_id] = StagedDocument(
            id=doc_id,
            original_filename=up.display_filename,
            extension=up.extension,
            pdf_bytes=pdf_bytes,
            text_snippet=snippet,
            suggested_filename=up.display_filename,
            suggested_position=idx,
        )

    ai_used = False
    ai_note = "AI suggestions disabled by user; manual ordering ready."
    if use_ai:
        try:
            provider = get_ai_provider()
            for doc in staged.values():
                if doc.text_snippet.strip():
                    cls_res = await provider.classify_document(doc.text_snippet)
                    fn_res = await provider.suggest_filename(doc.text_snippet, doc.original_filename)
                    doc.category = cls_res.category
                    doc.suggested_filename = f"{fn_res.suggested_filename}.pdf"

            order_inputs = [
                DocumentOrderInput(
                    id=d.id,
                    filename=d.suggested_filename,
                    summary_or_snippet=d.text_snippet or d.original_filename,
                )
                for d in staged.values()
            ]
            order_res = await provider.suggest_document_order(order_inputs)
            for item in order_res.ordered_documents:
                if item.id in staged:
                    staged[item.id].suggested_position = item.position

            ai_used = True
            ai_note = "AI suggestions generated. Review and adjust order before building."
        except AIServiceError as exc:
            ai_used = False
            ai_note = f"AI unavailable ({exc}); manual ordering ready."

    session = WorkflowSession(
        id=uuid.uuid4().hex,
        documents=staged,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=WORKFLOW_TTL_MINUTES),
    )
    workflow_store.save_session(session)

    ordered_list = sorted(staged.values(), key=lambda d: d.suggested_position)
    return {
        "workflow_id": session.id,
        "ai_used": ai_used,
        "ai_note": ai_note,
        "documents": [
            {
                "id": d.id,
                "original_filename": d.original_filename,
                "category": d.category,
                "suggested_filename": d.suggested_filename,
                "suggested_position": d.suggested_position,
            }
            for d in ordered_list
        ],
    }


def execute_build_job(workflow_id: str, ordered_ids: list[str], job_id: str) -> None:
    """Background task that merges user-ordered documents into a single PDF."""
    job = workflow_store.get_job(job_id)
    try:
        job.status = "processing"
        job.progress = 25

        session = workflow_store.get_session(workflow_id)
        pdf_list: list[bytes] = []
        for doc_id in ordered_ids:
            doc = session.documents.get(doc_id)
            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown document ID '{doc_id}' in order list.",
                )
            pdf_list.append(doc.pdf_bytes)

        job.progress = 65
        merged = pdf_service.merge_pdfs(pdf_list)
        job.result_bytes = merged
        job.progress = 100
        job.status = "completed"
    except Exception as exc:
        job.status = "failed"
        job.error = getattr(exc, "detail", str(exc))
