# Build context: system/. The fixed CodeQL Linux CLI requires linux/amd64.
ARG NODE_IMAGE=node:22.22.0-bookworm-slim@sha256:7cc56ef285a8568121537d17b05e72128f01b89c54607b51acf084a50ef483f3
ARG PYTHON_IMAGE=python:3.14.0-slim-bookworm@sha256:9bbb8720ae0a24a6ca8dd678bfdf57818fe70caf54c52a53ec01d8db43405056
ARG DOCKER_CLI_IMAGE=docker:28.5.2-cli@sha256:625d9431a9f54c5a2bc90f24f0e1c3d55b1349fd857dd85035f98c2c9acbdd4d
FROM ${DOCKER_CLI_IMAGE} AS docker-client
FROM ${NODE_IMAGE} AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_API_URL=""
RUN npm run build

FROM ${PYTHON_IMAGE} AS runtime
ENV PYTHONUNBUFFERED=1 UV_LINK_MODE=copy \
    PATH=/app/system/.venv/bin:/opt/codeql:/usr/local/bin:/usr/bin:/bin \
    PYTHONPATH=/app/system/backend:/app/system/scripts \
    ARTIFACT_ROOT=/app/artifacts CODEQL_PACK_PATH=/opt/packs \
    CODEQL_PYTHON_BIN=python3.11
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 curl ca-certificates unzip git libstdc++6 libatomic1 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.9.26
COPY --from=frontend /usr/local/bin/node /usr/local/bin/node
COPY --from=docker-client /usr/local/bin/docker /usr/local/bin/docker
RUN curl -fL --retry 3 https://github.com/github/codeql-cli-binaries/releases/download/v2.23.5/codeql-linux64.zip -o /tmp/codeql.zip \
    && echo '43d94a2ad35523d0c41623fe9c5396242a8b842d7bd2a00044d153d9be3bfa58  /tmp/codeql.zip' | sha256sum -c - \
    && unzip -q /tmp/codeql.zip -d /opt && rm /tmp/codeql.zip
WORKDIR /app/system
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/pyproject.toml
RUN uv sync --frozen --package app --no-dev --no-install-workspace
COPY docker/install_packs.py /tmp/install_packs.py
RUN python /tmp/install_packs.py && rm /tmp/install_packs.py
COPY backend/app backend/app
RUN uv sync --frozen --package app --no-dev
COPY backend/alembic.ini backend/alembic.ini
COPY scripts scripts
COPY knowledge knowledge
COPY runners runners
COPY docker docker
COPY --from=frontend /build/backend/app/frontend backend/app/frontend
WORKDIR /app/system/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
