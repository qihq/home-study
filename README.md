# 家庭学习助手 / Home Study

A family learning PWA deployed on Synology NAS. Record reading sessions via iPhone/iPad browser, transcode to 720p on NAS, practice spelling dictation, and track study stats.

部署在群晖 NAS 上的家庭学习 PWA：通过 iPhone/iPad 浏览器录制阅读视频、NAS 转码 720p、单词默写练习、学习统计。

![screenshot](docs/screenshot.png)

---

## Features / 功能

- **Reading Recording / 阅读录制** — Record Chinese/English reading via browser, auto-upload in chunks, NAS transcodes to 720p
- **Spelling Dictation / 单词默写** — Create word lists, practice with TTS playback, track scores
- **Dictionary / 辞典** — Look up words, mark unknown items for review
- **Voice Profiles / 我的声音** — Record voice samples, generate TTS voice clones
- **Statistics / 学习统计** — Track reading streaks, dictation accuracy, review mistakes
- **Multi-user / 多用户** — Admin setup on first run, family member accounts

## Tech Stack / 技术栈

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, PWA |
| Backend | Python 3.12, FastAPI, SQLAlchemy |
| Database | SQLite |
| Audio | FFmpeg for transcoding |
| TTS | MiMo API / OpenAI-compatible API |
| Container | Docker, single-container all-in-one image |

## Quick Start / 快速开始

### One-line deploy / 一键部署

```yaml
# compose.yaml
name: family-learning
services:
  app:
    image: family-learning:latest
    command: ["single"]
    environment:
      APP_DATA_DIR: /data
      APP_DATABASE_URL: sqlite:////data/app.db
      APP_ENVIRONMENT: production
    volumes:
      - ./data:/data
    ports:
      - "8000:8000"
    restart: unless-stopped
```

```bash
docker compose up -d
```

Open **http://localhost:8000** and create the admin account on first visit.

### Development / 开发

```bash
# Backend
cd backend
pip install -e .
python -m pytest -q

# Frontend
npm install
npm --workspace frontend run build   # production build
npm --workspace frontend run dev     # dev server (requires backend on :8001)

# Full stack with Docker
docker build -f deploy/Dockerfile -t family-learning:local .
docker compose -f deploy/compose.yaml up -d
```

## Configuration / 配置

All settings are configured via environment variables (prefix `APP_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_DATA_DIR` | `/data` | Persistent data directory |
| `APP_DATABASE_URL` | `sqlite:////data/app.db` | Database connection string |
| `APP_FRONTEND_DIR` | `/app/frontend-dist` | Frontend static files directory |
| `APP_ENVIRONMENT` | `production` | Environment name |
| `APP_MIMO_API_KEY` | — | MiMo TTS API key (set in Settings page) |
| `APP_MIMO_API_BASE_URL` | `https://api.xiaomimimo.com/v1` | MiMo API endpoint |

TTS and AI settings are configured through the web UI Settings page after first login.

## Project Structure / 项目结构

```
family-learning/
├── backend/           # Python FastAPI backend
│   ├── app/           # Application code
│   │   ├── api/       # API routes
│   │   ├── core/      # Config, security
│   │   ├── db/        # Database session, migrations
│   │   ├── models/    # SQLAlchemy models
│   │   ├── services/  # Business logic (TTS, AI, OCR)
│   │   └── workers/   # Background workers
│   └── tests/         # Backend tests
├── frontend/          # React + TypeScript PWA
│   ├── src/
│   │   ├── api/       # API client
│   │   ├── features/  # Feature pages
│   │   ├── ui/        # Shared UI components
│   │   └── lib/       # Utilities
│   └── public/        # Static assets
├── deploy/            # Docker deployment files
├── docs/              # Documentation
└── scripts/           # Development scripts
```

## License / 许可

UI assets from [Animal Island UI](https://github.com/guokaigdg/animal-island-ui) — [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).

其余部分保留所有权利。
