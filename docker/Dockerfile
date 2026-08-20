# Pinned version instead of floating "python" tag (reproducibility)
FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better layer caching
COPY api/requirements.txt .

# System dependency: poppler-utils needed by pdf2image (kept for future use)
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api/ .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000", "--reload"]
