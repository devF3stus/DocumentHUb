from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Response, UploadFile, status
from pydantic import BaseModel, Field

from app.core.auth import AuthenticatedUser, get_current_user_optional
from app.core.config import settings
from app.core.file_security import validate_upload
from app.services.workflows import workflow_service
from app.services.workflows.workflow_service import workflow_store

router = APIRouter(prefix="/api/v1/workflows", tags=["Smart Workflows"])

WORKFLOW_ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".docx"}


class BuildWorkflowRequest(BaseModel):
    workflow_id: str = Field(..., min_length=1)
    ordered_ids: list[str] = Field(..., min_length=2)
    output_filename: str = Field(default="document_bundle.pdf", min_length=1, max_length=100)


@router.post("/analyze")
async def analyze_workflow_endpoint(
    files: list[UploadFile] = File(...),
    use_ai: bool = Form(default=True),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> dict:
    """Validate, normalize, and optionally AI-classify/order multiple uploaded documents."""
    uploads = [
        await validate_upload(
            file=f,
            max_size_bytes=settings.max_upload_size_bytes,
            allowed_extensions=WORKFLOW_ALLOWED_EXTENSIONS,
        )
        for f in files
    ]
    return await workflow_service.analyze_documents(uploads, use_ai=use_ai)


@router.post("/build", status_code=status.HTTP_202_ACCEPTED)
async def build_workflow_endpoint(
    payload: BuildWorkflowRequest,
    background_tasks: BackgroundTasks,
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> dict:
    """Start a background job to merge user-ordered workflow documents into one PDF."""
    # Validate session & IDs eagerly before queuing background work.
    session = workflow_store.get_session(payload.workflow_id)
    for doc_id in payload.ordered_ids:
        if doc_id not in session.documents:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown document ID '{doc_id}'.",
            )

    safe_out = payload.output_filename.replace("/", "").replace("\\", "").strip() or "bundle.pdf"
    if not safe_out.lower().endswith(".pdf"):
        safe_out += ".pdf"

    job = workflow_store.create_job(output_filename=safe_out)
    background_tasks.add_task(
        workflow_service.execute_build_job,
        payload.workflow_id,
        payload.ordered_ids,
        job.id,
    )
    return {"job_id": job.id, "status": job.status}


@router.get("/jobs/{job_id}")
async def get_workflow_job_status(
    job_id: str,
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> dict:
    """Poll background workflow job progress."""
    job = workflow_store.get_job(job_id)
    return {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "output_filename": job.output_filename,
        "error": job.error,
    }


@router.get("/jobs/{job_id}/download")
async def download_workflow_result(
    job_id: str,
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Download the completed combined PDF."""
    data, filename = workflow_store.pop_job_result(job_id)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
