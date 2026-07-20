FROM node:24-bookworm-slim AS frontend-build
WORKDIR /workspace
COPY package.json ./
COPY package-lock.json ./
COPY frontend/package.json frontend/package.json
RUN npm ci
COPY frontend frontend
RUN npm --workspace frontend run build

FROM python:3.12-slim-bookworm
WORKDIR /app
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ENV PIP_DEFAULT_TIMEOUT=300 PIP_RETRIES=10
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY backend ./backend
RUN test -f /app/backend/dictionary-data/local-dictionary.sqlite3 || (echo "Missing backend/dictionary-data/local-dictionary.sqlite3; run backend/scripts/download_local_dictionary.ps1" >&2; exit 1)
# PyPI downloads can be slow; keep transient reads from aborting the image build.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir ./backend
COPY backend/app ./app
RUN mkdir -p /app/dictionary && cp /app/backend/dictionary-data/local-dictionary.sqlite3 /app/dictionary/local-dictionary.sqlite3
COPY deploy/entrypoint.sh /entrypoint.sh
COPY --from=frontend-build /workspace/frontend/dist /app/frontend-dist
RUN chmod +x /entrypoint.sh
ENV APP_DATA_DIR=/data
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["single"]
