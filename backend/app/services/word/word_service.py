from io import BytesIO
from pathlib import Path
import shutil
import subprocess

from docx import Document
from docxcompose.composer import Composer
from fastapi import HTTPException, status
import fitz
import mammoth
from pdf2docx import Converter
from PIL import Image, UnidentifiedImageError

from app.core.file_security import isolated_temp_dir


def _open_docx(data: bytes) -> Document:
    """Load a .docx byte payload safely, raising 400 if corrupted."""
    try:
        return Document(BytesIO(data))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted DOCX file.",
        ) from exc


def merge_docx(files_bytes: list[bytes]) -> bytes:
    """Merge two or more DOCX files while preserving styles, tables, and media."""
    if len(files_bytes) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload at least 2 DOCX files to merge.",
        )
    master = _open_docx(files_bytes[0])
    composer = Composer(master)
    for extra_bytes in files_bytes[1:]:
        composer.append(_open_docx(extra_bytes))

    out = BytesIO()
    composer.save(out)
    return out.getvalue()


def extract_docx_text(data: bytes) -> str:
    """Extract paragraph and table text from a DOCX file."""
    doc = _open_docx(data)
    lines: list[str] = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                lines.append(row_text)
    return "\n".join(lines)


def generate_docx_from_text(text: str, title: str | None = None) -> bytes:
    """Generate a formatted DOCX document from plain text and an optional heading."""
    doc = Document()
    if title and title.strip():
        doc.add_heading(title.strip(), level=1)
    for line in text.splitlines():
        doc.add_paragraph(line)
    out = BytesIO()
    doc.save(out)
    return out.getvalue()


def docx_to_html(data: bytes) -> str:
    """Convert DOCX content into semantic HTML using Mammoth."""
    try:
        result = mammoth.convert_to_html(BytesIO(data))
        return result.value
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not convert DOCX to HTML.",
        ) from exc


def txt_to_docx(data: bytes, title: str | None = None) -> bytes:
    """Convert UTF-8 plain text bytes into a DOCX document."""
    text = data.decode("utf-8", errors="replace")
    return generate_docx_from_text(text=text, title=title)


def txt_to_pdf(data: bytes) -> bytes:
    """Convert UTF-8 plain text into a clean multi-page PDF using PyMuPDF."""
    text = data.decode("utf-8", errors="replace")
    doc = fitz.open()
    page_width, page_height = 595, 842  # A4 in points
    margin = 50
    y = margin
    line_height = 14
    page = doc.new_page(width=page_width, height=page_height)

    for raw_line in text.splitlines() or [""]:
        # Wrap long lines every 85 characters so text stays inside margins.
        wrapped = [raw_line[i : i + 85] for i in range(0, max(len(raw_line), 1), 85)]
        for segment in wrapped:
            if y + line_height > page_height - margin:
                page = doc.new_page(width=page_width, height=page_height)
                y = margin
            page.insert_text((margin, y), segment, fontsize=11)
            y += line_height

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def images_to_pdf(images_bytes: list[bytes]) -> bytes:
    """Convert one or more PNG/JPG images into a single PDF using Pillow."""
    if not images_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload at least one image.",
        )

    pil_images: list[Image.Image] = []
    try:
        for img_data in images_bytes:
            try:
                img = Image.open(BytesIO(img_data))
                pil_images.append(img.convert("RGB"))
            except (UnidentifiedImageError, Exception) as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or corrupted image file.",
                ) from exc

        out = BytesIO()
        pil_images[0].save(
            out,
            format="PDF",
            save_all=True,
            append_images=pil_images[1:],
        )
        return out.getvalue()
    finally:
        for img in pil_images:
            img.close()


def pdf_to_docx(data: bytes) -> bytes:
    """Convert a digital PDF to an editable DOCX using pdf2docx inside an isolated temp dir."""
    with isolated_temp_dir(prefix="pdf2docx_") as temp_dir:
        pdf_path = temp_dir / "input.pdf"
        docx_path = temp_dir / "output.docx"
        pdf_path.write_bytes(data)
        try:
            converter = Converter(str(pdf_path))
            converter.convert(str(docx_path))
            converter.close()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to convert PDF to DOCX. Ensure the PDF is valid and not encrypted.",
            ) from exc

        if not docx_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="DOCX output was not generated.",
            )
        return docx_path.read_bytes()


def docx_to_pdf(data: bytes, timeout_seconds: int = 30) -> bytes:
    """Convert DOCX to PDF via headless LibreOffice (shell=False, strict timeout)."""
    soffice_bin = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice_bin:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LibreOffice is not installed in this environment (included in Docker production build).",
        )

    with isolated_temp_dir(prefix="lo_convert_") as temp_dir:
        input_path = temp_dir / "input.docx"
        input_path.write_bytes(data)

        cmd = [
            soffice_bin,
            "--headless",
            "--norestore",
            "--convert-to",
            "pdf",
            "--outdir",
            str(temp_dir),
            str(input_path),
        ]
        try:
            proc = subprocess.run(
                cmd,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="DOCX to PDF conversion timed out.",
            ) from exc

        output_path = Path(temp_dir) / "input.pdf"
        if proc.returncode != 0 or not output_path.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="LibreOffice could not convert this DOCX file.",
            )
        return output_path.read_bytes()
