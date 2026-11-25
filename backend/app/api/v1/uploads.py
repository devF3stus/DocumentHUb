from fastapi import APIRouter, Depends, File, UploadFile

from app.core.auth import AuthenticatedUser, get_current_user_optional
from app.core.config import settings
from app.core.file_security import isolated_temp_dir, validate_upload

router = APIRouter(prefix="/api/v1", tags=["Uploads & Auth"])


@router.get("/auth/me")
async def get_auth_status(
    user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> dict[str, str | bool | None]:
    """Return current session mode: authenticated user or guest."""
    if user is None:
        return {
            "authenticated": False,
            "mode": "guest",
            "user_id": None,
            "email": None,
        }
    return {
        "authenticated": True,
        "mode": "authenticated",
        "user_id": user.id,
        "email": user.email,
    }


@router.post("/uploads/validate")
async def validate_uploaded_document(
    file: UploadFile = File(...),
    user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> dict[str, str | int | bool]:
    """Validate an uploaded document's signature, size, and filename inside an isolated temp dir."""
    validated = await validate_upload(file=file, max_size_bytes=settings.max_upload_size_bytes)

    # Write to an isolated temp folder using only the server-generated UUID filename,
    # then automatically delete the folder when exiting the context manager.
    with isolated_temp_dir() as temp_dir:
        temp_file = temp_dir / validated.safe_filename
        temp_file.write_bytes(validated.content)
        written_ok = temp_file.exists() and temp_file.parent == temp_dir

    return {
        "valid": written_ok,
        "safe_filename": validated.safe_filename,
        "display_filename": validated.display_filename,
        "extension": validated.extension,
        "mime_type": validated.mime_type,
        "size_bytes": validated.size_bytes,
        "user_mode": "authenticated" if user else "guest",
    }
