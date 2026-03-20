# Stage 1: Build web UI
FROM node:22-alpine AS ui-builder
WORKDIR /ui
COPY web-ui/package.json web-ui/package-lock.json ./
RUN npm ci --legacy-peer-deps
COPY web-ui/ .
RUN npm run build

# Stage 2: Python backend
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Cache-friendly: install deps before copying source
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# Copy backend source
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .

# Copy pre-built UI from stage 1
COPY --from=ui-builder /ui/dist web-ui/dist

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
