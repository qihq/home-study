# 家庭学习助手 / Home Study

面向家庭的学习 PWA，可部署在群晖 NAS：孩子用 iPhone、iPad 或电脑完成中英文阅读打卡、单词默写和词典查询，视频保存在家庭 NAS。

A family-learning PWA for Synology NAS. It supports Chinese and English reading check-ins, spelling dictation, local-first dictionary lookup, and private video storage.

## 功能 / Features

- 动森风格的中英文阅读录制页，显示录制时长，录制完成后可返回主页或进入视频库。
- 花滑视频录制：首页与导航新增「花滑录制」入口，冰蓝主题录制页、视频库「花滑录制」类别与上传选项、日历「滑」标记；花滑视频不计入阅读统计。
- 视频后台自动组装、转码、心跳续约、有限重试和恢复；不需要靠重启容器恢复普通处理中任务。
- 视频库按日历筛选当天打卡视频，支持不会离开 PWA 的在线预览、下载进度、系统照片保存和失败后手动重新处理。
- 默写页以听音为主，答案默认隐藏，点击答案卡显示单词并评分。
- 本地优先辞典三层查询：英文 ECDICT、中文 CC-CEDICT，本地未命中转免费在线词典（有道 + Free Dictionary），最后才用设置页配置的 AI；显示多词性、其他释义、英/美双音标、考纲/词频标签、英文说明和双语例句。
- 单词发音用真人词典音频（英/美可切换），句子与短语用 MiMo 低延迟流式朗读；可重新生成发音，普通音色和克隆音色均只朗读目标正文。支持家庭成员、学习本、生词、统计和可选声音配置。
- 学习本采用“我的学习本 / 创建学习本”分层界面；支持粘贴、图片识别和文件导入，并在保存前逐条确认单词、短语或句子。
- 生词本可把选中的生词生成命名学习本，并以 Tab 方式保留多个草稿；确认后可直接进入默写。
- 电脑端视频下载完成后优先显示“保存 MP4 / 分享视频”操作；手机和平板继续支持系统照片保存流程。

### v0.2.4 更新 / What's new in v0.2.4

- 新增花滑视频录制：独立入口、冰蓝主题录制页、视频库类别与上传选项、日历「滑」标记，桌面/平板/手机三端自适应。
- 录制恢复页支持「放弃并重新开始」；服务端已无记录的残留会话会自动清理，不再卡在「继续录制」。
- 首页任务卡与「本周完成率 / 连续打卡」接入真实数据：按当天各语言录制状态显示，完成卡可直接进视频库。
- New figure-skating video category with its own entry, ice-blue recording page, library category, upload option and calendar marker, responsive across desktop, tablet and mobile PWA.
- Recovery offers "abandon and start over", and stale sessions whose server recording is gone are cleaned up automatically instead of wedging the page on "continue recording".

### v0.3.x 更新 / What's new in v0.3.x

- **发音全面升级**：
  - 单词发音改用真人词典音频（有道 dictvoice 英/美音 + Free Dictionary API），本地缓存、失败自动降级，不再依赖 LLM 式语音朗读单词；
  - 辞典页支持英/美音切换、英/美双音标展示；
  - MiMo TTS 调用修正：按场景（单词/句子）构造指令、语速映射为风格指令、中英文自动选音色、官方模型名/音色校验，句子与短语走 `stream + pcm16` 低延迟流式朗读；
  - 声音克隆质量优化：样本下限 8 秒、中英双语预览、录音引导稿。
- **辞典三层查询链**：本地 ECDICT/CC-CEDICT → 免费在线词典（有道 + Free Dictionary，30 天缓存）→ AI 兜底；未配置 AI 也能查本地未收录单词。
- **ECDICT 全字段**：词性、柯林斯星级、牛津 3000、考纲标签（中考/高考/四级…）、词频入库；生词本按词频排序并展示标签。
- **运维**：TTS 缓存自动清理（90 天 + 容量上限）、本地词库定时自动更新（原子替换、校验和版本化），均随 worker 后台运行。
- Word pronunciation now uses real dictionary audio (Youdao + Free Dictionary, cached) instead of LLM-style TTS; added UK/US accent switch and dual phonetics, three-tier dictionary lookup (local → free online → AI), full ECDICT fields with exam/frequency tags, streaming MiMo TTS for sentences, and background TTS-cache cleanup + dictionary auto-update.

### v0.2.3 更新 / What's new in v0.2.3

- 录制前检查麦克风音轨：没有声音轨时停止录制并提示检查麦克风权限，不再产生无声视频。
- 提前打开摄像头后锁屏再继续录制时，失效的音视频轨会自动重新申请，避免录出无声或黑屏视频。
- 视频校验区分「无画面 / 无声音 / 源无效」并在视频库显示失败原因；源文件永久无效时不再反复重试。
- Before recording, the app verifies the microphone track and refuses to start with a clear permission hint when audio is missing.
- Streams left over from opening the camera before locking the screen are re-acquired when their tracks go stale, avoiding silent or black recordings.
- Video validation now reports the real reason (no video / no audio / invalid source) in the video library, and permanently invalid sources stop being retried endlessly.

### v0.2.2 更新 / What's new in v0.2.2

- 修复 MiMo TTS 发音失败：MiMo API 不再允许 system 角色消息，改为 user 角色。
- Fix MiMo TTS pronunciation failure: MiMo API no longer allows system-role messages; switched to user role.

### v0.2.1 更新 / What's new in v0.2.1

- 学习本把已保存内容与创建流程分为独立 Tab，并将粘贴、图片识别和文件导入拆成清晰入口。
- Learning books now separate saved content from creation, with focused paste, image-recognition, and file-import tabs.
- 生词本会持续保留从生词生成的多个学习本，并可确认草稿后直接开始默写。
- Unknown-word books retain multiple generated learning books and let a parent confirm a draft before starting dictation.
- 电脑端下载完成不会自动遮挡式弹出分享；用户可明确选择保存 MP4 或分享视频。
- Desktop downloads now present explicit Save MP4 or Share Video actions instead of automatically opening a disruptive share flow.

## NAS 快速发布 / NAS Quick Release

> **推荐：一键部署脚本**。本机装好 Docker（含 buildx）与 `pip install paramiko` 后：
>
> ```powershell
> $env:NAS_SSH_PASSWORD='<admin密码>'   # 仅本次会话，不落盘
> python scripts/deploy-nas.py --version v0.3.1
> ```
>
> 脚本自动完成构建 `linux/amd64` 镜像 → 导出 tar → SSH 上传 → 备份数据 → 停旧容器 → `docker load` → **`docker-compose`（v1）** 重建 → 删除被顶替的旧镜像 → 轮询 `/api/health` 直到 `worker:true`。详见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。

手动发布流程（镜像以 `linux/amd64` 面向 DS918+）：

```powershell
backend/scripts/build_local_dictionary.py --download --output backend/dictionary-data/local-dictionary.sqlite3 --version <版本>
docker buildx build --platform linux/amd64 --load -t family-learning:latest -f deploy/Dockerfile .
docker save -o family-learning-ds918plus-amd64.tar family-learning:latest
Get-FileHash family-learning-ds918plus-amd64.tar -Algorithm SHA256
```

将 tar 复制到 NAS 的项目目录（数据目录即项目目录自身，`volumes: - ./:/data`），在同目录放好 `compose.yaml` 后导入并重建：

```sh
docker load -i family-learning-ds918plus-amd64.tar
docker-compose -f compose.yaml up -d --force-recreate   # 群晖只有 docker-compose v1，没有 `docker compose`
curl http://127.0.0.1:6633/api/health   # 需返回 "worker":true
```

首次访问 `http://NAS-IP:6633` 时创建管理员账号。手机录音需要 HTTPS，请在群晖反向代理或其他 HTTPS 代理后访问。完整发布、校验和恢复说明见 [docs/ALL_IN_ONE_RELEASE.md](docs/ALL_IN_ONE_RELEASE.md) 与 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。

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
