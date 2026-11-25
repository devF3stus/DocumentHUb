from io import BytesIO
import zipfile

import fitz  # PyMuPDF
from fastapi import HTTPException, status
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from app.core.config import settings


def _open_pdf_reader(data: bytes, password: str | None = None) -> PdfReader:
    """Load a PDF safely, handle encryption, and enforce maximum page limits."""
    try:
        reader = PdfReader(BytesIO(data))
    except (PdfReadError, Exception) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted PDF file.",
        ) from exc

    if reader.is_encrypted:
        if not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This PDF is password-protected. Please provide the password.",
            )
        try:
            decrypt_result = reader.decrypt(password)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to decrypt PDF with the provided password.",
            ) from exc
        if decrypt_result == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect PDF password.",
            )

    page_count = len(reader.pages)
    if page_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDF contains zero pages.",
        )
    if page_count > settings.max_pdf_pages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PDF exceeds the maximum limit of {settings.max_pdf_pages} pages.",
        )
    return reader


def _open_fitz_doc(data: bytes, password: str | None = None) -> fitz.Document:
    """Load a PDF with PyMuPDF safely, handling encryption and page limits."""
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted PDF file.",
        ) from exc

    if doc.needs_pass:
        if not password:
            doc.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This PDF is password-protected. Please provide the password.",
            )
        if not doc.authenticate(password):
            doc.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect PDF password.",
            )

    if doc.page_count == 0 or doc.page_count > settings.max_pdf_pages:
        count = doc.page_count
        doc.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PDF page count ({count}) must be between 1 and {settings.max_pdf_pages}.",
        )
    return doc


def parse_page_spec(spec: str, total_pages: int) -> list[int]:
    """Parse 1-based page specs like '1,3,5-7' into validated 0-based indices."""
    cleaned = spec.strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page specification cannot be empty.",
        )

    indices: list[int] = []
    for part in cleaned.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            bounds = token.split("-", maxsplit=1)
            if len(bounds) != 2 or not bounds[0].strip().isdigit() or not bounds[1].strip().isdigit():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid page range '{token}'. Use format like '1-3'.",
                )
            start, end = int(bounds[0].strip()), int(bounds[1].strip())
            if start < 1 or end > total_pages or start > end:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Page range '{token}' is out of bounds (1-{total_pages}).",
                )
            indices.extend(range(start - 1, end))
        else:
            if not token.isdigit():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid page number '{token}'.",
                )
            page_num = int(token)
            if page_num < 1 or page_num > total_pages:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Page {page_num} is out of bounds (1-{total_pages}).",
                )
            indices.append(page_num - 1)

    if not indices:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid pages specified.",
        )
    return indices


def _write_pdf_bytes(writer: PdfWriter) -> bytes:
    """Serialize a pypdf PdfWriter to raw PDF bytes."""
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def merge_pdfs(files_bytes: list[bytes]) -> bytes:
    """Merge two or more PDFs in order."""
    if len(files_bytes) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload at least 2 PDF files to merge.",
        )
    writer = PdfWriter()
    total_pages = 0
    for data in files_bytes:
        reader = _open_pdf_reader(data)
        total_pages += len(reader.pages)
        if total_pages > settings.max_pdf_pages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Combined PDF exceeds {settings.max_pdf_pages} pages.",
            )
        for page in reader.pages:
            writer.add_page(page)
    return _write_pdf_bytes(writer)


def split_pdf(data: bytes, ranges_spec: str, password: str | None = None) -> bytes:
    """Split a PDF by semicolon-separated ranges (e.g. '1-2;3-4') into a ZIP archive."""
    reader = _open_pdf_reader(data, password=password)
    groups = [g.strip() for g in ranges_spec.split(";") if g.strip()]
    if not groups:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide ranges separated by ';' (e.g. '1-2;3-4').",
        )

    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for idx, group in enumerate(groups, start=1):
            page_indices = parse_page_spec(group, len(reader.pages))
            writer = PdfWriter()
            for page_idx in page_indices:
                writer.add_page(reader.pages[page_idx])
            zf.writestr(f"split_part_{idx}.pdf", _write_pdf_bytes(writer))
    return zip_buf.getvalue()


def extract_pages(data: bytes, pages_spec: str, password: str | None = None) -> bytes:
    """Extract selected pages into a new PDF."""
    reader = _open_pdf_reader(data, password=password)
    indices = parse_page_spec(pages_spec, len(reader.pages))
    writer = PdfWriter()
    for idx in indices:
        writer.add_page(reader.pages[idx])
    return _write_pdf_bytes(writer)


def delete_pages(data: bytes, pages_spec: str, password: str | None = None) -> bytes:
    """Delete specified pages and return the remaining PDF."""
    reader = _open_pdf_reader(data, password=password)
    to_delete = set(parse_page_spec(pages_spec, len(reader.pages)))
    if len(to_delete) >= len(reader.pages):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete all pages from a PDF.",
        )
    writer = PdfWriter()
    for idx, page in enumerate(reader.pages):
        if idx not in to_delete:
            writer.add_page(page)
    return _write_pdf_bytes(writer)


def rearrange_pages(data: bytes, order_spec: str, password: str | None = None) -> bytes:
    """Rearrange PDF pages according to a 1-based order (e.g. '3,1,2')."""
    return extract_pages(data, order_spec, password=password)


def rotate_pages(
    data: bytes,
    angle: int,
    pages_spec: str | None = None,
    password: str | None = None,
) -> bytes:
    """Rotate selected pages (or all pages if omitted) by 90, 180, or 270 degrees."""
    if angle not in (90, 180, 270):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rotation angle must be 90, 180, or 270 degrees.",
        )
    reader = _open_pdf_reader(data, password=password)
    target_indices = (
        set(parse_page_spec(pages_spec, len(reader.pages)))
        if pages_spec and pages_spec.strip()
        else set(range(len(reader.pages)))
    )

    writer = PdfWriter()
    for idx, page in enumerate(reader.pages):
        if idx in target_indices:
            page.rotate(angle)
        writer.add_page(page)
    return _write_pdf_bytes(writer)


def compress_pdf(data: bytes, password: str | None = None) -> bytes:
    """Compress PDF streams and remove unused objects using PyMuPDF."""
    doc = _open_fitz_doc(data, password=password)
    try:
        return doc.tobytes(garbage=4, deflate=True, clean=True)
    finally:
        doc.close()


def pdf_to_images(
    data: bytes,
    image_format: str = "png",
    dpi: int = 150,
    password: str | None = None,
) -> bytes:
    """Render each PDF page to PNG or JPEG images inside a ZIP archive."""
    fmt = image_format.lower().strip()
    if fmt not in ("png", "jpg", "jpeg"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image format must be 'png' or 'jpg'.",
        )
    if dpi < 72 or dpi > 300:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DPI must be between 72 and 300.",
        )

    pil_ext = "jpeg" if fmt in ("jpg", "jpeg") else "png"
    out_ext = "jpg" if pil_ext == "jpeg" else "png"

    doc = _open_fitz_doc(data, password=password)
    zip_buf = BytesIO()
    try:
        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for page_idx in range(doc.page_count):
                page = doc.load_page(page_idx)
                pix = page.get_pixmap(dpi=dpi)
                zf.writestr(f"page_{page_idx + 1}.{out_ext}", pix.tobytes(output=pil_ext))
    finally:
        doc.close()
    return zip_buf.getvalue()


def protect_pdf(data: bytes, new_password: str, current_password: str | None = None) -> bytes:
    """Encrypt a PDF with AES-256 using the user-supplied password."""
    if len(new_password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 4 characters long.",
        )
    reader = _open_pdf_reader(data, password=current_password)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(user_password=new_password, algorithm="AES-256")
    return _write_pdf_bytes(writer)


def unlock_pdf(data: bytes, password: str) -> bytes:
    """Remove password protection from a PDF when the user supplies the valid password."""
    reader = _open_pdf_reader(data, password=password)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    return _write_pdf_bytes(writer)
