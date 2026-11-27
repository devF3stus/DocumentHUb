from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status

from app.core.auth import AuthenticatedUser, get_current_user_optional
from app.core.config import settings
from app.core.file_security import validate_upload
from app.services.ocr import ocr_service
from app.services.word import word_service

router = APIRouter(prefix="/api/v1/ocr", tags=["OCR Studio"])

OCR_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".pdf"}


@router.post("/extract")
async def ocr_extract_endpoint(
    file: UploadFile = File(...),
    language: str = Form(default="eng"),
    preprocess: bool = Form(default=True),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> dict:
    """Extract text and confidence scores from a scanned image or PDF."""
    uploaded = await validate_upload(
        file=file,
        max_size_bytes=settings.max_upload_size_bytes,
        allowed_extensions=OCR_ALLOWED_EXTENSIONS,
    )
    result = ocr_service.run_ocr(
        data=uploaded.content,
        extension=uploaded.extension,
        language=language,
        preprocess=preprocess,
    )
    return {
        "language": result.language,
        "average_confidence": result.average_confidence,
        "full_text": result.full_text,
        "pages": [
            {
                "page_number": p.page_number,
                "text": p.text,
                "confidence": p.confidence,
            }
            for p in result.pages
        ],
    }


@router.post("/export")
async def ocr_export_endpoint(
    text: str = Form(...),
    export_format: str = Form(default="txt", description="'txt' or 'docx'"),
    title: str | None = Form(default=None),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Export user-reviewed/corrected OCR text as TXT or DOCX."""
    fmt = export_format.strip().lower()
    if fmt == "txt":
        return Response(
            content=text.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="ocr_result.txt"'},
        )
    if fmt == "docx":
        docx_bytes = word_service.generate_docx_from_text(text=text, title=title)
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": 'attachment; filename="ocr_result.docx"'},
        )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Export format must be 'txt' or 'docx'.",
    )


@router.post("/searchable-pdf")
async def ocr_searchable_pdf_endpoint(
    file: UploadFile = File(...),
    language: str = Form(default="eng"),
    preprocess: bool = Form(default=True),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Generate a searchable PDF with an embedded OCR text layer."""
    uploaded = await validate_upload(
        file=file,
        max_size_bytes=settings.max_upload_size_bytes,
        allowed_extensions=OCR_ALLOWED_EXTENSIONS,
    )
    pdf_bytes = ocr_service.generate_searchable_pdf(
        data=uploaded.content,
        extension=uploaded.extension,
        language=language,
        preprocess=preprocess,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="searchable.pdf"'},
    )
