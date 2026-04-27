FROM python:3.12-slim

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first (cached layer unless pyproject.toml/uv.lock change)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

EXPOSE 8080

# PORT is set by Cloud Run (default 8080); WORKERS defaults to 1
ENV PORT=8080
ENV WORKERS=1

CMD ["sh", "-c", "uv run uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers ${WORKERS}"]
