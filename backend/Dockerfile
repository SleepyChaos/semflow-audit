# Build from repository root. CodeQL runner isolation is a separate milestone.
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
ARG VITE_API_URL=
RUN npm run build

FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/alembic.ini ./backend/
COPY backend/app ./backend/app
COPY backend/scripts ./backend/scripts
RUN uv sync --frozen --package app --no-dev
COPY --from=frontend-build /app/backend/app/frontend ./backend/app/frontend
ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app/backend
CMD ["fastapi", "run", "--workers", "4"]
