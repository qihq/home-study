# 家庭学习助手 · Home Study

[简体中文](#简体中文) · [English](#english)

一个跑在自家 NAS 上的家庭学习 PWA：孩子用 iPhone、iPad 或电脑完成中英文阅读打卡、单词默写和词典查询，录制的视频只留在自己家里。

A self-hosted family learning PWA for Synology NAS. Kids use their iPhone, iPad, or computer for reading check-ins, spelling dictation, and dictionary lookup — and every recorded video stays inside the home network.

![React](https://img.shields.io/badge/React-19-149eca?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178c6?logo=typescript&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Python_3.12-009688?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-all--in--one-2496ed?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 简体中文

### 功能特性

- **阅读打卡录制**：动森风格的中英文录制页，实时显示录制时长，录完可直接回主页或进视频库。
- **花滑视频录制**：独立入口、冰蓝主题录制页、视频库类别与上传选项、日历「滑」标记；花滑视频不计入阅读统计，桌面 / 平板 / 手机三端自适应。
- **录制健壮性**：起录前检查麦克风音轨，无声不录；锁屏或切后台导致的死流会自动重新申请；`MediaRecorder` 静默失效时看门狗自动重启一次，而不是录了半天什么都没录到。
- **后台视频流水线**：分片上传不占用数据库连接，后台自动组装、转码（H.264/AAC）、心跳续约、有限重试与崩溃恢复，普通处理中任务不需要靠重启容器救活。
- **视频库**：按日历筛选当天打卡视频，PWA 内在线预览、下载进度、系统照片保存，失败后可手动重新处理。
- **默写**：听音为主，答案默认隐藏，点卡片显示单词并评分；支持英 / 美音逐词切换。
- **本地优先辞典**：三层查询链 —— 本地 ECDICT（英）/ CC-CEDICT（中）→ 免费在线词典（有道 + Free Dictionary，30 天缓存）→ 设置页配置的 AI 兜底。展示多词性、其他释义、英 / 美双音标、考纲与词频标签、英文说明和双语例句。
- **发音**：英文单词优先真人录音（Wiktionary / Wikimedia Commons 直连，自动选英 / 美音、预转码 mp3），Free Dictionary、有道、百度 TTS 逐级兜底，最后才回退 MiMo TTS；句子与短语走 MiMo 低延迟流式朗读。发音源熔断状态落盘，重启后不再重复等待不可达源。
- **学习本**：粘贴、图片识别（OCR）与文件导入三种入口，保存前逐条确认单词 / 短语 / 句子；生词本可把选中的生词生成命名学习本，多个草稿以 Tab 保留。
- **家庭与声音**：支持家庭成员、学习本、生词、统计和可选的声音克隆；私有语音包 `.flvoice` 可加密导入导出。
- **运维自动化**：TTS 缓存 90 天 + 容量上限自动清理，本地词库定时原子更新并校验，均由后台 worker 执行。

### 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | React、TypeScript、Vite、PWA |
| 后端 | Python 3.12、FastAPI、SQLAlchemy、Alembic |
| 数据 | SQLite、ECDICT、CC-CEDICT |
| 媒体 | FFmpeg、H.264 / AAC |
| 部署 | Docker all-in-one 镜像（群晖 Container Manager） |

### 项目结构

```
backend/     FastAPI 应用、Alembic 迁移、worker、测试
frontend/    React + Vite PWA
deploy/      Dockerfile、entrypoint、compose 示例
docs/        部署、发布、隐私与设计文档
scripts/     一键发布脚本
```

### 快速开始

```powershell
npm install
npm --workspace frontend run build

cd backend
pip install -e .
pytest -q
```

本地开发时，前端 Vite 代理默认指向 `http://127.0.0.1:8001`。

### 部署到群晖 NAS

推荐用一键脚本：本机准备好 Docker（含 buildx）与 `pip install paramiko` 后：

```powershell
$env:NAS_HOST='<NAS 地址>'            # 仅本次会话，不落盘、不写进脚本
$env:NAS_SSH_PASSWORD='<管理员密码>'   # 仅本次会话，不落盘
python scripts/deploy-nas.py --version <版本号>
```

脚本会依次完成：构建 `linux/amd64` 镜像 → 导出 tar → SSH 上传 → 备份数据 → 停旧容器 → `docker load` → `docker-compose`（v1）重建 → 清理被顶替的旧镜像 → 轮询 `/api/health` 直到 `worker:true`。

手动流程（镜像以 `linux/amd64` 面向 DS918+）：

```powershell
backend/scripts/build_local_dictionary.py --download --output backend/dictionary-data/local-dictionary.sqlite3 --version <版本>
docker buildx build --platform linux/amd64 --load -t family-learning:latest -f deploy/Dockerfile .
docker save -o family-learning-ds918plus-amd64.tar family-learning:latest
Get-FileHash family-learning-ds918plus-amd64.tar -Algorithm SHA256
```

把 tar 复制到 NAS 的项目目录（数据目录即项目目录本身，`volumes: - ./:/data`），同目录放好 `compose.yaml` 后导入并重建：

```sh
docker load -i family-learning-ds918plus-amd64.tar
docker-compose -f compose.yaml up -d --force-recreate   # 群晖只有 docker-compose v1，没有 `docker compose`
curl http://127.0.0.1:6633/api/health                   # 需返回 "worker": true
```

首次访问 `http://<NAS-IP>:6633` 时创建管理员账号。手机录音需要 HTTPS，请走群晖反向代理或其他 HTTPS 代理。

完整说明见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)、[docs/ALL_IN_ONE_RELEASE.md](docs/ALL_IN_ONE_RELEASE.md)。

### 配置与脱敏

- 持久数据只放在 NAS 映射的 `/data`：SQLite、视频分片与成品、声音样本都不进 Git，也不进镜像。
- API Key 通过应用设置页或 NAS 环境变量配置，落盘时加密；`.env`、数据库、私有语音包、视频、镜像 tar 均已被 `.gitignore` 排除。
- **不要把真实 API Key、账号密码、NAS 内网地址或私钥写进源码、Compose 文件、镜像标签或提交信息。** 仓库里的示例统一使用占位符：`NAS_HOST`、`<NAS 地址>`、`APP_MIMO_API_KEY=`（留空）。
- `APP_MIMO_API_KEY` 只在 NAS 后端环境中设置；本地词典不配 AI Key 也能查常见中英文词。

示例变量见 [.env.example](.env.example)，声音隐私与备份见 [docs/VOICE-PRIVACY-AND-BACKUP.md](docs/VOICE-PRIVACY-AND-BACKUP.md)。

### 更新日志

#### v0.3.2

- **电子辞典 AI 兼容 DeepSeek / OpenCode Go**：请求开启 JSON 模式时，若 prompt 未提及 JSON 会自动补一条 system 指令；上游（含网关轮询到的部分节点）不支持 `response_format` 时，自动去掉该参数重试一次。修复设置页「测试连接」在 DeepSeek 系列模型上必然失败（上游返回 400 `prompt must contain 'json'`），以及网关多上游轮询造成的偶发请求失败。
- 设置页「测试连接」读取的是已保存的配置：请先保存 AI 配置，再点测试。

排障手册与接入细节见 [docs/AI-PROVIDER-TROUBLESHOOTING.md](docs/AI-PROVIDER-TROUBLESHOOTING.md)。

#### v0.3.1

- **发音全面升级（真人录音优先）**：英文单词优先 Wiktionary 真人录音（Wikimedia Commons 直连，自动选英 / 美音与预转码 mp3，Ogg 自动转码），Free Dictionary、有道、百度 TTS 逐级兜底（有道瞬时失败自动重试），最后才回退 MiMo TTS；本地缓存版本化，旧音频自动刷新；发音源熔断状态落盘。
- 中文词发音同样走有道 + 百度兜底，词典、生词本与默写共用同一套发音源与缓存。
- 辞典页「朗读声音」新增四档来源：跟随设置 / 辞典原生发音 / AI 生成（接口音色）/ 我的克隆声音，播放后显示实际来源；查询单词即后台预取缓存。
- 生词本支持逐词英 / 美音切换（迁移 `0014_word_pronunciation_accent`）。

#### v0.3.x

- 单词发音改用真人词典音频，本地缓存、失败自动降级；辞典页支持英 / 美音切换与双音标展示。
- MiMo TTS 调用修正：按场景（单词 / 句子）构造指令、语速映射为风格指令、中英文自动选音色、官方模型名与音色校验，句子与短语走 `stream + pcm16` 低延迟流式朗读。
- 声音克隆质量优化：样本下限 8 秒、中英双语预览、录音引导稿。
- 辞典三层查询链与 ECDICT 全字段（词性、柯林斯星级、牛津 3000、考纲标签、词频）入库；生词本按词频排序并展示标签。
- 运维：TTS 缓存自动清理、本地词库定时原子更新。

#### v0.2.4

- 新增花滑视频录制：独立入口、冰蓝主题录制页、视频库类别与上传选项、日历「滑」标记。
- 录制恢复页支持「放弃并重新开始」；服务端已无记录的残留会话自动清理。
- 首页任务卡与「本周完成率 / 连续打卡」接入真实数据。

#### v0.2.3

- 录制前检查麦克风音轨，无声音轨时停止录制并提示权限。
- 提前打开摄像头后锁屏再继续录制时，失效音视频轨自动重新申请，避免无声或黑屏视频。
- 视频校验区分「无画面 / 无声音 / 源无效」，失败原因在视频库可见，永久无效源不再重复重试。

#### v0.2.2

- 修复 MiMo TTS 发音失败：MiMo API 不再允许 system 角色消息，改为 user 角色。

#### v0.2.1

- 学习本把已保存内容与创建流程拆为独立 Tab，粘贴 / 图片识别 / 文件导入各有清晰入口。
- 生词本保留多个生成的学习本，确认草稿后可直接开始默写。
- 电脑端下载完成不再自动弹分享，改为明确的「保存 MP4 / 分享视频」。

### 许可与署名

Animal Island UI 素材遵循 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)。ECDICT 使用 MIT License，CC-CEDICT 使用 [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)。本项目代码以 [MIT License](LICENSE) 发布。

---

## English

### Overview

Home Study is a self-hosted PWA for a family NAS. Children record Chinese and English reading check-ins, practise spelling dictation, and look up words — while all video footage stays on the home Synology NAS. The app is built for iPhone, iPad, and desktop browsers, and behaves like a native app via a PWA service worker.

### Features

- **Reading check-in recording** — an Animal-Crossing-style recording page for Chinese and English, with a live duration counter and direct jumps to the home page or video library.
- **Figure-skating recording** — a dedicated entry with an ice-blue theme, its own library category, upload option, and calendar marker. Skating clips are excluded from reading statistics and adapt to desktop, tablet, and mobile.
- **Recording robustness** — the microphone track is verified before recording starts, dead tracks caused by locking the screen are re-acquired automatically, and a watchdog restarts a silently broken `MediaRecorder` instead of recording nothing for minutes.
- **Background video pipeline** — chunk uploads never hold a database connection; assembly, transcoding (H.264/AAC), heartbeat renewal, bounded retries, and crash recovery all run in the background, so in-flight jobs recover without restarting the container.
- **Video library** — filter the day's check-ins on a calendar, preview inside the PWA, track download progress, save to the system photo library, and re-process failed videos manually.
- **Spelling dictation** — audio-first, answers hidden by default, tap a card to reveal the word and grade yourself; per-word US/UK accent switching.
- **Local-first dictionary** — a three-tier lookup chain: local ECDICT (English) and CC-CEDICT (Chinese) → free online dictionaries (Youdao + Free Dictionary, 30-day cache) → the AI provider configured in settings. Results show POS, alternative senses, dual phonetics, exam/frequency tags, English glosses, and bilingual examples.
- **Pronunciation** — English words prefer real human recordings (Wiktionary / Wikimedia Commons, with UK/US selection and pre-transcoded mp3), falling back through Free Dictionary, Youdao, and Baidu TTS before MiMo TTS. Sentences and phrases use low-latency MiMo streaming TTS. Circuit-breaker state is persisted so unreachable sources are not retried after a restart.
- **Learning books** — paste, OCR image recognition, and file import, with per-entry confirmation before saving. Unknown-word books can generate named learning books, with multiple drafts kept as tabs.
- **Family and voices** — family members, learning books, unknown words, statistics, and optional voice cloning; private `.flvoice` voice packages can be exported and imported with encryption.
- **Maintenance** — TTS cache cleanup (90 days plus a size cap) and scheduled, checksum-verified atomic dictionary updates run in the background worker.

### Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React, TypeScript, Vite, PWA |
| Backend | Python 3.12, FastAPI, SQLAlchemy, Alembic |
| Data | SQLite, ECDICT, CC-CEDICT |
| Media | FFmpeg, H.264 / AAC |
| Deployment | Docker all-in-one image (Synology Container Manager) |

### Repository Layout

```
backend/     FastAPI app, Alembic migrations, worker, tests
frontend/    React + Vite PWA
deploy/      Dockerfile, entrypoint, compose example
docs/        Deployment, release, privacy, and design docs
scripts/     One-command release script
```

### Quick Start

```powershell
npm install
npm --workspace frontend run build

cd backend
pip install -e .
pytest -q
```

During local development the Vite dev server proxies `/api` to `http://127.0.0.1:8001`.

### Deploying to a Synology NAS

The one-command script is recommended. Prepare Docker (with buildx) and `pip install paramiko` on your machine, then:

```powershell
$env:NAS_HOST='<nas address>'         # session only, never written to disk or the script
$env:NAS_SSH_PASSWORD='<admin pass>'  # session only, never written to disk
python scripts/deploy-nas.py --version <version>
```

The script builds a `linux/amd64` image, exports it to a tar, uploads it over SSH, backs up data, stops the old container, runs `docker load`, recreates with `docker-compose` (v1), prunes the superseded image, and polls `/api/health` until `worker:true`.

Manual release (`linux/amd64`, targeting the DS918+):

```powershell
backend/scripts/build_local_dictionary.py --download --output backend/dictionary-data/local-dictionary.sqlite3 --version <version>
docker buildx build --platform linux/amd64 --load -t family-learning:latest -f deploy/Dockerfile .
docker save -o family-learning-ds918plus-amd64.tar family-learning:latest
Get-FileHash family-learning-ds918plus-amd64.tar -Algorithm SHA256
```

Copy the tar into the project directory on the NAS (the data directory is the project directory itself, `volumes: - ./:/data`), place `compose.yaml` beside it, then import and recreate:

```sh
docker load -i family-learning-ds918plus-amd64.tar
docker-compose -f compose.yaml up -d --force-recreate   # Synology ships docker-compose v1, not `docker compose`
curl http://127.0.0.1:6633/api/health                   # must return "worker": true
```

Create the admin account on first visit to `http://<nas-ip>:6633`. Phone recording requires HTTPS, so put the app behind the Synology reverse proxy or another HTTPS proxy.

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) and [docs/ALL_IN_ONE_RELEASE.md](docs/ALL_IN_ONE_RELEASE.md) for the full procedure, checksums, and recovery steps.

### Configuration and Sanitization

- Persistent data lives only in the NAS-mounted `/data`: SQLite, video chunks and outputs, and voice samples never enter Git or the image.
- API keys are configured through the settings page or NAS environment variables and are encrypted at rest. `.env`, databases, private voice packages, videos, and image tars are all excluded by `.gitignore`.
- **Never commit real API keys, account passwords, NAS LAN addresses, or private keys** to source, Compose files, image tags, or commit messages. This repository uses placeholders throughout: `NAS_HOST`, `<nas address>`, and an empty `APP_MIMO_API_KEY=`.
- `APP_MIMO_API_KEY` belongs only in the NAS backend environment; the local dictionary works for common words without any AI key.

Sample variables are in [.env.example](.env.example); voice privacy and backup guidance is in [docs/VOICE-PRIVACY-AND-BACKUP.md](docs/VOICE-PRIVACY-AND-BACKUP.md).

### Changelog

#### v0.3.2

- **The dictionary AI now works with DeepSeek / OpenCode Go** — when JSON mode is requested and no prompt mentions JSON, a system instruction is added automatically; if an upstream (including nodes a gateway rotates to) rejects `response_format`, the request is retried once without it. This fixes the settings-page “test connection” button failing for every DeepSeek model (upstream 400 `prompt must contain 'json'`) and the intermittent failures caused by gateways spreading requests across upstreams.
- “Test connection” uses the saved configuration: save the AI settings first, then test.

See [docs/AI-PROVIDER-TROUBLESHOOTING.md](docs/AI-PROVIDER-TROUBLESHOOTING.md) for the troubleshooting guide and provider setup.

#### v0.3.1

- **Pronunciation overhaul, human recordings first** — English words prefer real Wiktionary recordings (direct from Wikimedia Commons, automatic UK/US selection, pre-transcoded mp3, Ogg transcoding), falling back through Free Dictionary, Youdao, and Baidu TTS before MiMo TTS. Local caches are versioned and refreshed automatically, and circuit-breaker state is persisted.
- Chinese words use the same Youdao + Baidu fallback, shared by the dictionary, word lists, and dictation.
- The dictionary page gained four pronunciation sources (follow settings / native dictionary audio / AI voice / cloned voice) and shows the actual source after playback; caches are prefetched on lookup.
- Word lists support per-word US/UK accent switching (migration `0014_word_pronunciation_accent`).

#### v0.3.x

- Word pronunciation moved to real dictionary audio with local caching and automatic degradation; the dictionary page gained UK/US switching and dual phonetics.
- MiMo TTS calls were corrected: scenario-aware instructions (word vs. sentence), speed mapped to style prompts, automatic voice selection per language, official model/voice validation, and `stream + pcm16` low-latency streaming for sentences and phrases.
- Voice-cloning quality improved: 8-second sample minimum, bilingual preview, and a recording guide script.
- Three-tier dictionary lookup plus all ECDICT fields (POS, Collins stars, Oxford 3000, exam tags, frequency); word lists sort by frequency and show tags.
- Maintenance: automatic TTS cache cleanup and scheduled atomic dictionary updates.

#### v0.2.4

- Added figure-skating recording with its own entry, ice-blue recording page, library category, upload option, and calendar marker.
- The recovery page offers "abandon and start over", and stale sessions whose server recording is gone are cleaned up automatically.
- The home task cards and "weekly completion / streak" widgets now use real data.

#### v0.2.3

- The microphone track is verified before recording; recording refuses to start with a clear permission hint when audio is missing.
- Streams left over from opening the camera before locking the screen are re-acquired when their tracks go stale, avoiding silent or black recordings.
- Video validation now distinguishes no-video / no-audio / invalid-source and surfaces the reason in the library; permanently invalid sources stop being retried.

#### v0.2.2

- Fixed MiMo TTS pronunciation failure: the MiMo API no longer allows system-role messages, so the client switched to the user role.

#### v0.2.1

- Learning books separate saved content from creation, with focused paste, OCR, and file-import entries.
- Unknown-word books retain multiple generated learning books and let a parent confirm a draft before starting dictation.
- Desktop downloads present explicit Save MP4 or Share Video actions instead of automatically opening a disruptive share flow.

### License and Attribution

Animal Island UI assets are licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). ECDICT is MIT-licensed and CC-CEDICT is licensed under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/). The project's own code is released under the [MIT License](LICENSE).
