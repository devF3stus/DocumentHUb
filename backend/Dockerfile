FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr for clear logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install LibreOffice Writer (headless) for high-fidelity DOCX -> PDF conversion.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user so the container never runs with root privileges.
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Install Python dependencies first for better Docker layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code.
COPY app ./app

# Switch to the non-root user.
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
