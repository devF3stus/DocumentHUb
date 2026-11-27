from fastapi import APIRouter, Depends, File, Form, Response, UploadFile

from app.core.auth import AuthenticatedUser, get_current_user_optional
from app.core.config import settings
from app.core.file_security import validate_upload
from app.services.word import word_service

router = APIRouter(prefix="/api/v1", tags=["Word & Conversion"])


def _attachment(content: bytes, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/word/merge")
async def merge_word_endpoint(
    files: list[UploadFile] = File(...),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Merge 2 or more DOCX files."""
    validated = [
        (await validate_upload(f, settings.max_upload_size_bytes, {".docx"})).content
        for f in files
    ]
    result = word_service.merge_docx(validated)
    return _attachment(
        result,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "merged.docx",
    )


@router.post("/word/generate")
async def generate_word_endpoint(
    text: str = Form(...),
    title: str | None = Form(default=None),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Generate a DOCX document from text and an optional title."""
    result = word_service.generate_docx_from_text(text=text, title=title)
    return _attachment(
        result,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "generated.docx",
    )


@router.post("/convert/docx-to-txt")
async def docx_to_txt_endpoint(
    file: UploadFile = File(...),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Extract plain text from a DOCX file."""
    uploaded = await validate_upload(file, settings.max_upload_size_bytes, {".docx"})
    text = word_service.extract_docx_text(uploaded.content)
    return _attachment(text.encode("utf-8"), "text/plain; charset=utf-8", "extracted.txt")


@router.post("/convert/docx-to-html")
async def docx_to_html_endpoint(
    file: UploadFile = File(...),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Convert DOCX to semantic HTML."""
    uploaded = await validate_upload(file, settings.max_upload_size_bytes, {".docx"})
    html = word_service.docx_to_html(uploaded.content)
    return _attachment(html.encode("utf-8"), "text/html; charset=utf-8", "converted.html")


@router.post("/convert/txt-to-docx")
async def txt_to_docx_endpoint(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Convert a TXT file to DOCX."""
    uploaded = await validate_upload(file, settings.max_upload_size_bytes, {".txt"})
    result = word_service.txt_to_docx(uploaded.content, title=title)
    return _attachment(
        result,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "converted.docx",
    )


@router.post("/convert/txt-to-pdf")
async def txt_to_pdf_endpoint(
    file: UploadFile = File(...),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Convert a TXT file to PDF."""
    uploaded = await validate_upload(file, settings.max_upload_size_bytes, {".txt"})
    result = word_service.txt_to_pdf(uploaded.content)
    return _attachment(result, "application/pdf", "converted.pdf")


@router.post("/convert/images-to-pdf")
async def images_to_pdf_endpoint(
    files: list[UploadFile] = File(...),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Convert one or more JPG/PNG images into a single PDF."""
    validated = [
        (await validate_upload(f, settings.max_upload_size_bytes, {".png", ".jpg", ".jpeg"})).content
        for f in files
    ]
    result = word_service.images_to_pdf(validated)
    return _attachment(result, "application/pdf", "images.pdf")


@router.post("/convert/pdf-to-docx")
async def pdf_to_docx_endpoint(
    file: UploadFile = File(...),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Convert a digital PDF into an editable DOCX file."""
    uploaded = await validate_upload(file, settings.max_upload_size_bytes, {".pdf"})
    result = word_service.pdf_to_docx(uploaded.content)
    return _attachment(
        result,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "converted.docx",
    )


@router.post("/convert/docx-to-pdf")
async def docx_to_pdf_endpoint(
    file: UploadFile = File(...),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Convert a DOCX file to PDF using headless LibreOffice."""
    uploaded = await validate_upload(file, settings.max_upload_size_bytes, {".docx"})
    result = word_service.docx_to_pdf(uploaded.content)
    return _attachment(result, "application/pdf", "converted.pdf")
