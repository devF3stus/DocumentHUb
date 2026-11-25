from fastapi import HTTPException, status

from app.core.auth import get_supabase_admin_client
from app.core.config import settings


class PrivateStorageService:
    """Manages private Supabase Storage uploads, short-lived signed URLs, and deletion."""

    def __init__(self) -> None:
        self._bucket = settings.supabase_storage_bucket

    def _require_client(self):
        client = get_supabase_admin_client()
        if client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Private cloud storage is not configured.",
            )
        return client

    def upload_user_file(self, user_id: str, safe_filename: str, content: bytes, mime_type: str) -> str:
        """Upload a validated file into the user's private folder and return its storage path."""
        client = self._require_client()
        storage_path = f"{user_id}/{safe_filename}"
        client.storage.from_(self._bucket).upload(
            path=storage_path,
            file=content,
            file_options={"content-type": mime_type, "upsert": "false"},
        )
        return storage_path

    def create_signed_download_url(self, storage_path: str) -> str:
        """Generate a short-lived signed URL for an authorized user."""
        client = self._require_client()
        result = client.storage.from_(self._bucket).create_signed_url(
            storage_path,
            settings.signed_url_expiry_seconds,
        )
        signed_url = result.get("signedURL") or result.get("signedUrl")
        if not signed_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not generate signed download URL.",
            )
        return str(signed_url)

    def delete_file(self, storage_path: str) -> None:
        """Delete a file from private storage."""
        client = self._require_client()
        client.storage.from_(self._bucket).remove([storage_path])
