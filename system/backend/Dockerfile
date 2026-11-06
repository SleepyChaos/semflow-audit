# Build context: system/. The default target preserves the combined image.
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.9.26 AS uv

FROM python:3.14-slim AS backend
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=uv /uv /uvx /bin/
# Preserve the repository layout: configuration locates its root via parents[4].
WORKDIR /app/system
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/alembic.ini ./backend/
COPY backend/app ./backend/app
COPY backend/scripts ./backend/scripts
COPY scripts ./scripts
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --package app --no-dev
ENV PATH="/app/system/.venv/bin:$PATH"
WORKDIR /app/system/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM nginx:1.27-alpine AS frontend
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /app/backend/app/frontend /usr/share/nginx/html
EXPOSE 80

FROM backend AS standalone
COPY --from=frontend-build /app/backend/app/frontend ./app/frontend
