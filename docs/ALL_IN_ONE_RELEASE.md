# DS918+ All-in-One Release Guide

The DS918+ uses `linux/amd64`. Release one image and one Compose service; the
Compose command must be `single`, which starts database migrations, the API,
and the worker in the same container.

## Build and verify

Run these commands from the repository root. Do not put API keys in the image,
Compose file, version file, or source code.

```sh
PYTHONPATH=backend python -m pytest backend/tests -q
npm --prefix frontend test -- --run
npm --prefix frontend run build

VERSION=v0.2.0
TAG=family-learning:0.2.0
OUT=dist/ds918plus-$VERSION
mkdir -p "$OUT"

docker buildx build --platform linux/amd64 --load -t "$TAG" -t family-learning:latest -f deploy/Dockerfile .
docker save -o "$OUT/family-learning-ds918plus-amd64-$VERSION.tar" "$TAG"
sha256sum "$OUT/family-learning-ds918plus-amd64-$VERSION.tar" > "$OUT/family-learning-ds918plus-amd64-$VERSION.tar.sha256"
```

## Release compose.yaml

Create `$OUT/compose.yaml`, replacing the image tag with the newly built tag:

```yaml
name: family-learning
services:
  family-learning:
    image: family-learning:0.2.0
    command: ["single"]
    environment:
      APP_DATA_DIR: /data
      APP_DATABASE_URL: sqlite:////data/app.db
      APP_ENVIRONMENT: production
    volumes:
      - ${FAMILY_LEARNING_DATA_DIR:-./data}:/data
    ports:
      - "${FAMILY_LEARNING_PORT:-8000}:8000"
    restart: unless-stopped
```

Also create `$OUT/VERSION.md` with the image tag, release date, `linux/amd64`,
SHA-256, and the test/build results.

## Before delivery

Validate the generated Compose file, then verify that the tar can be imported:

```sh
docker compose -f "$OUT/compose.yaml" config --quiet
docker image rm "$TAG"
docker load -i "$OUT/family-learning-ds918plus-amd64-$VERSION.tar"
docker image inspect "$TAG" --format '{{.Os}}/{{.Architecture}}'
```

The final command must print `linux/amd64`.

## Synology deployment

Copy the `.tar`, `.tar.sha256`, `compose.yaml`, and `VERSION.md` to the NAS.
In the project directory create `.env`:

```dotenv
FAMILY_LEARNING_DATA_DIR=/volume1/family-learning
FAMILY_LEARNING_PORT=8000
```

Then import the tar, verify its checksum, and start the project:

```sh
sha256sum -c family-learning-ds918plus-amd64-v0.2.0.tar.sha256
docker load -i family-learning-ds918plus-amd64-v0.2.0.tar
docker compose up -d
```

Use an HTTPS reverse proxy for phone camera and microphone access. Configure
OCR from the app's Settings page: it can reuse the dictionary AI or use a
separate OpenAI-compatible vision model and API key.
