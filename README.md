# 家庭学习助手 / Home Study

面向家庭的学习 PWA，可部署在群晖 NAS：孩子用 iPhone、iPad 或电脑完成中英文阅读打卡、单词默写和词典查询，视频保存在家庭 NAS。

A family-learning PWA for Synology NAS. It supports Chinese and English reading check-ins, spelling dictation, local-first dictionary lookup, and private video storage.

## 功能 / Features

- 动森风格的中英文阅读录制页，显示录制时长，录制完成后可返回主页或进入视频库。
- 视频后台自动组装、转码、心跳续约、有限重试和恢复；不需要靠重启容器恢复普通处理中任务。
- 视频库按日历筛选当天打卡视频，支持不会离开 PWA 的在线预览、下载进度、系统照片保存和失败后手动重新处理。
- 默写页以听音为主，答案默认隐藏，点击答案卡显示单词并评分。
- 本地优先辞典：英文使用 ECDICT、中文使用 CC-CEDICT；显示多词性、其他释义、英文说明和双语例句；短语、句子和本地未命中时才使用设置页配置的 AI。
- 可重新生成词典发音；普通音色和克隆音色均只朗读目标正文。支持家庭成员、学习本、生词、统计和可选声音配置。

## NAS 快速发布 / NAS Quick Release

发布镜像以 `linux/amd64` 为目标，适用于 DS918+。构建机器需要 Docker、Node.js、Python，并需要先准备本地词典数据：

```powershell
backend/scripts/download_local_dictionary.ps1
docker buildx build --platform linux/amd64 --load -t family-learning:latest -f deploy/Dockerfile .
docker save -o family-learning-ds918plus-amd64-v0.2.0.tar family-learning:latest
Get-FileHash family-learning-ds918plus-amd64-v0.2.0.tar -Algorithm SHA256
```

将 tar 文件复制到 NAS 后，在同一目录新建 `.env`（不要提交此文件）：

```dotenv
FAMILY_LEARNING_DATA_DIR=/volume1/family-learning
FAMILY_LEARNING_PORT=8000
```

再新建 `compose.yaml`：

```yaml
name: family-learning
services:
  family-learning:
    image: family-learning:latest
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

```sh
docker load -i family-learning-ds918plus-amd64.tar
docker compose up -d
```

首次访问 `http://NAS-IP:8000` 时创建管理员账号。手机录音需要 HTTPS，请在群晖反向代理或其他 HTTPS 代理后访问。完整发布、校验和恢复说明见 [docs/ALL_IN_ONE_RELEASE.md](docs/ALL_IN_ONE_RELEASE.md) 与 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。

## 本地开发 / Development

```powershell
npm install
npm --workspace frontend run build
cd backend
pip install -e .
pytest -q
```

本地运行前端开发服务器时，后端默认代理地址为 `http://127.0.0.1:8001`。

## 配置与隐私 / Configuration and Privacy

- 持久数据仅放在 NAS 映射的 `/data`：SQLite、视频分片与成品、声音样本均不进入 Git 或镜像。
- API Key 通过应用设置页或 NAS 环境变量配置；`.env`、数据库、私有语音包、视频和镜像 tar 均已被 Git 忽略。
- 不要将真实 API Key、账号密码、NAS 地址或私钥写进源码、Compose 文件、镜像标签或 Git 提交信息。
- `APP_MIMO_API_KEY` 只应在 NAS 后端环境中设置；本地词典无需 AI Key 即可查询常见中英文词。

示例变量见 [.env.example](.env.example)。更详细的声音隐私与备份说明见 [docs/VOICE-PRIVACY-AND-BACKUP.md](docs/VOICE-PRIVACY-AND-BACKUP.md)。

## 技术栈 / Tech Stack

| 层 / Layer | 技术 / Technology |
| --- | --- |
| 前端 / Frontend | React, TypeScript, Vite, PWA |
| 后端 / Backend | Python 3.12, FastAPI, SQLAlchemy |
| 数据 / Data | SQLite, ECDICT, CC-CEDICT |
| 媒体 / Media | FFmpeg, H.264/AAC |
| 部署 / Deployment | Docker all-in-one image |

## 许可与署名 / License and Attribution

Animal Island UI 素材遵循 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)。ECDICT 使用 MIT License，CC-CEDICT 使用 [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)。其余代码保留所有权利。
