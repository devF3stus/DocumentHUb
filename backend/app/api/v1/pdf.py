from fastapi import APIRouter, Depends, File, Form, Response, UploadFile

from app.core.auth import AuthenticatedUser, get_current_user_optional
from app.core.config import settings
from app.core.file_security import isolated_temp_dir, validate_upload
from app.services.pdf import pdf_service

router = APIRouter(prefix="/api/v1/pdf", tags=["PDF Engine"])


def _attachment_response(content: bytes, media_type: str, filename: str) -> Response:
    """Return a downloadable binary file response with Content-Disposition header."""
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _validate_pdf_bytes(file: UploadFile) -> bytes:
    """Validate an uploaded PDF and stage/clean it in an isolated temp directory."""
    validated = await validate_upload(
        file=file,
        max_size_bytes=settings.max_upload_size_bytes,
        allowed_extensions={".pdf"},
    )
    with isolated_temp_dir() as temp_dir:
        temp_file = temp_dir / validated.safe_filename
        temp_file.write_bytes(validated.content)
        return temp_file.read_bytes()


@router.post("/merge")
async def merge_pdf_endpoint(
    files: list[UploadFile] = File(...),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Merge multiple uploaded PDFs into a single PDF."""
    pdf_bytes_list = [await _validate_pdf_bytes(f) for f in files]
    result = pdf_service.merge_pdfs(pdf_bytes_list)
    return _attachment_response(result, "application/pdf", "merged.pdf")


@router.post("/split")
async def split_pdf_endpoint(
    file: UploadFile = File(...),
    ranges: str = Form(..., description="Semicolon-separated ranges, e.g. '1-2;3-4'"),
    password: str | None = Form(default=None),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Split a PDF into multiple parts and return them as a ZIP archive."""
    data = await _validate_pdf_bytes(file)
    result = pdf_service.split_pdf(data, ranges_spec=ranges, password=password)
    return _attachment_response(result, "application/zip", "split_pdfs.zip")


@router.post("/extract")
async def extract_pages_endpoint(
    file: UploadFile = File(...),
    pages: str = Form(..., description="Pages to extract, e.g. '1,3-4'"),
    password: str | None = Form(default=None),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Extract selected pages from a PDF."""
    data = await _validate_pdf_bytes(file)
    result = pdf_service.extract_pages(data, pages_spec=pages, password=password)
    return _attachment_response(result, "application/pdf", "extracted.pdf")


@router.post("/delete")
async def delete_pages_endpoint(
    file: UploadFile = File(...),
    pages: str = Form(..., description="Pages to delete, e.g. '2,4'"),
    password: str | None = Form(default=None),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Delete specified pages from a PDF."""
    data = await _validate_pdf_bytes(file)
    result = pdf_service.delete_pages(data, pages_spec=pages, password=password)
    return _attachment_response(result, "application/pdf", "updated.pdf")


@router.post("/rearrange")
async def rearrange_pages_endpoint(
    file: UploadFile = File(...),
    order: str = Form(..., description="New 1-based page order, e.g. '3,1,2'"),
    password: str | None = Form(default=None),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Rearrange pages of a PDF in the requested order."""
    data = await _validate_pdf_bytes(file)
    result = pdf_service.rearrange_pages(data, order_spec=order, password=password)
    return _attachment_response(result, "application/pdf", "rearranged.pdf")


@router.post("/rotate")
async def rotate_pages_endpoint(
    file: UploadFile = File(...),
    angle: int = Form(..., description="90, 180, or 270"),
    pages: str | None = Form(default=None, description="Optional pages, e.g. '1,3' (blank = all)"),
    password: str | None = Form(default=None),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Rotate selected or all pages of a PDF."""
    data = await _validate_pdf_bytes(file)
    result = pdf_service.rotate_pages(data, angle=angle, pages_spec=pages, password=password)
    return _attachment_response(result, "application/pdf", "rotated.pdf")


@router.post("/compress")
async def compress_pdf_endpoint(
    file: UploadFile = File(...),
    password: str | None = Form(default=None),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Compress a PDF to reduce file size."""
    data = await _validate_pdf_bytes(file)
    result = pdf_service.compress_pdf(data, password=password)
    return _attachment_response(result, "application/pdf", "compressed.pdf")


@router.post("/to-images")
async def pdf_to_images_endpoint(
    file: UploadFile = File(...),
    image_format: str = Form(default="png"),
    dpi: int = Form(default=150),
    password: str | None = Form(default=None),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Convert PDF pages to PNG or JPG images inside a ZIP archive."""
    data = await _validate_pdf_bytes(file)
    result = pdf_service.pdf_to_images(data, image_format=image_format, dpi=dpi, password=password)
    return _attachment_response(result, "application/zip", "pdf_images.zip")


@router.post("/protect")
async def protect_pdf_endpoint(
    file: UploadFile = File(...),
    new_password: str = Form(...),
    current_password: str | None = Form(default=None),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Password-protect a PDF using AES-256 encryption."""
    data = await _validate_pdf_bytes(file)
    result = pdf_service.protect_pdf(data, new_password=new_password, current_password=current_password)
    return _attachment_response(result, "application/pdf", "protected.pdf")


@router.post("/unlock")
async def unlock_pdf_endpoint(
    file: UploadFile = File(...),
    password: str = Form(...),
    _user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> Response:
    """Unlock a password-protected PDF using the supplied password."""
    data = await _validate_pdf_bytes(file)
    result = pdf_service.unlock_pdf(data, password=password)
    return _attachment_response(result, "application/pdf", "unlocked.pdf")
