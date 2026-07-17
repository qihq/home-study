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
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY backend ./backend
# PyPI downloads can be slow; keep transient reads from aborting the image build.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    PIP_DEFAULT_TIMEOUT=300 PIP_RETRIES=10 pip install --no-cache-dir ./backend
COPY backend/app ./app
COPY deploy/entrypoint.sh /entrypoint.sh
COPY --from=frontend-build /workspace/frontend/dist /app/frontend-dist
RUN chmod +x /entrypoint.sh
ENV APP_DATA_DIR=/data
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["single"]
