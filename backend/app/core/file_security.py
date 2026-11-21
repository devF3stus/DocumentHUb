from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile
import uuid

from fastapi import HTTPException, UploadFile, status


@dataclass(frozen=True)
class FileTypeRule:
    """Validation rule for an allowed document format."""

    extension: str
    mime_types: tuple[str, ...]
    magic_prefixes: tuple[bytes, ...]


# Table-driven rules so all supported formats are validated uniformly.
ALLOWED_FILE_TYPES: dict[str, FileTypeRule] = {
    ".pdf": FileTypeRule(
        extension=".pdf",
        mime_types=("application/pdf",),
        magic_prefixes=(b"%PDF-",),
    ),
    ".docx": FileTypeRule(
        extension=".docx",
        mime_types=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
        ),
        magic_prefixes=(b"PK\x03\x04",),
    ),
    ".png": FileTypeRule(
        extension=".png",
        mime_types=("image/png",),
        magic_prefixes=(b"\x89PNG\r\n\x1a\n",),
    ),
    ".jpg": FileTypeRule(
        extension=".jpg",
        mime_types=("image/jpeg",),
        magic_prefixes=(b"\xff\xd8\xff",),
    ),
    ".jpeg": FileTypeRule(
        extension=".jpeg",
        mime_types=("image/jpeg",),
        magic_prefixes=(b"\xff\xd8\xff",),
    ),
    ".txt": FileTypeRule(
        extension=".txt",
        mime_types=("text/plain",),
        magic_prefixes=(),
    ),
}

# Known executable signatures that must always be rejected immediately.
FORBIDDEN_EXECUTABLE_PREFIXES: tuple[bytes, ...] = (
    b"MZ",        # Windows PE / .exe / .dll
    b"\x7fELF",   # Linux ELF binary
    b"#!",        # Shell / script shebang
)


@dataclass(frozen=True)
class ValidatedUpload:
    """Result of validating an uploaded file safely."""

    safe_filename: str
    display_filename: str
    extension: str
    mime_type: str
    size_bytes: int
    content: bytes


def sanitize_display_filename(raw_filename: str | None) -> str:
    """Strip directory paths so user-supplied filenames cannot cause path traversal."""
    if not raw_filename:
        return "document"
    # Handle both POSIX (/) and Windows (\) separators regardless of host OS.
    cleaned = raw_filename.replace("\\", "/").split("/")[-1].strip()
    return cleaned or "document"


def _verify_magic_bytes(rule: FileTypeRule, data: bytes) -> None:
    """Verify the file's leading bytes match its claimed format and are not executable."""
    if any(data.startswith(sig) for sig in FORBIDDEN_EXECUTABLE_PREFIXES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Executable or script files are not permitted.",
        )

    if rule.extension == ".txt":
        if b"\x00" in data[:4096]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File contains binary data and is not valid plain text.",
            )
        try:
            data[:8192].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text file must be valid UTF-8.",
            ) from exc
        return

    if not any(data.startswith(prefix) for prefix in rule.magic_prefixes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File content does not match expected {rule.extension} signature.",
        )


async def validate_upload(
    file: UploadFile,
    max_size_bytes: int,
    allowed_extensions: set[str] | None = None,
) -> ValidatedUpload:
    """Validate extension, MIME type, size limit, and magic bytes for an UploadFile."""
    display_name = sanitize_display_filename(file.filename)
    ext = Path(display_name).suffix.lower()

    allowed = allowed_extensions or set(ALLOWED_FILE_TYPES.keys())
    if ext not in allowed or ext not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext or '(none)'}'.",
        )

    rule = ALLOWED_FILE_TYPES[ext]
    claimed_mime = (file.content_type or "").split(";")[0].strip().lower()
    if claimed_mime and claimed_mime != "application/octet-stream" and claimed_mime not in rule.mime_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"MIME type '{claimed_mime}' does not match extension '{ext}'.",
        )

    # Read in chunks up to max_size_bytes + 1 to block oversized payloads early.
    chunks: list[bytes] = []
    total_bytes = 0
    chunk_size = 64 * 1024
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {max_size_bytes // (1024 * 1024)} MB.",
            )
        chunks.append(chunk)

    if total_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    data = b"".join(chunks)
    _verify_magic_bytes(rule, data)

    safe_filename = f"{uuid.uuid4().hex}{ext}"
    return ValidatedUpload(
        safe_filename=safe_filename,
        display_filename=display_name,
        extension=ext,
        mime_type=rule.mime_types[0],
        size_bytes=total_bytes,
        content=data,
    )


@contextmanager
def isolated_temp_dir(prefix: str = "dochub_") -> Iterator[Path]:
    """Create an isolated temporary directory and guarantee deletion on exit."""
    temp_path = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield temp_path
    finally:
        if temp_path.exists():
            shutil.rmtree(temp_path, ignore_errors=True)
