FROM python:3.12-slim

WORKDIR /app

# Prevent Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Ensure logs appear immediately
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install uv + dependencies
RUN pip install --no-cache-dir uv && \
    uv sync --frozen && \
    pip install --no-cache-dir python-box redis

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY artifacts/ ./artifacts/
COPY monitoring/ ./monitoring/
COPY reports/ ./reports/
COPY test/ ./test/
COPY app.py ./

# Create logs directory
RUN mkdir -p logs

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start FastAPI server
CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]