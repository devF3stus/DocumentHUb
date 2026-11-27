from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.convert import router as v1_convert_router
from app.api.v1.ocr import router as v1_ocr_router
from app.api.v1.pdf import router as v1_pdf_router
from app.api.v1.uploads import router as v1_uploads_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Free, privacy-first intelligent document processing API.",
)

# Allow our Next.js frontend origin to communicate with this backend API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(v1_uploads_router)
app.include_router(v1_pdf_router)
app.include_router(v1_convert_router)
app.include_router(v1_ocr_router)


@app.get("/health", tags=["System"])
def health_check() -> dict[str, str]:
    """Return basic service health status for monitoring and frontend checks."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }
