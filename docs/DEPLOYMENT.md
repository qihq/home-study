# 群晖 DS918+ 部署

## 数据目录和启动

单容器发布包的 `compose.yaml` 使用一个数据卷：

```text
${FAMILY_LEARNING_DATA_DIR:-./data}:/data
```

因此，数据库、上传文件、视频、TTS 缓存、备份、AI/TTS 密钥和声音文件都应位于同一个 NAS 共享目录。单容器镜像会在同一容器内启动 API 和 Worker，不需要为 Worker 创建第二个容器或第二个目录映射。

1. 在 DSM 的 Container Manager 中启用 Docker Compose 项目功能。
2. 创建 Container Manager 可读写的共享目录；DS918+ 可使用 `/volume1/family-learning`。
3. 将项目上传到 NAS，在项目目录创建 `.env`：

```dotenv
FAMILY_LEARNING_DATA_DIR=/volume1/family-learning
FAMILY_LEARNING_PORT=8000
```

4. 导入单容器发布包并启动项目：

```sh
docker load -i family-learning-ds918plus-amd64-20260715-single.tar
docker compose up -d
```

容器内数据目录固定为 `/data`，SQLite 地址为 `/data/app.db`。变更 `FAMILY_LEARNING_DATA_DIR` 前，先停止项目并完整迁移原数据目录；仅复制 `app.db` 不足以保留媒体、参考声音和密钥。

## HTTPS 和反向代理

使用群晖反向代理将 HTTPS 域名转发到主机端口 `8000`。不要直接暴露 DSM 管理端口。iPhone/iPad 的摄像头和麦克风权限依赖 HTTPS。

反向代理的请求体限制应覆盖两类上传：

- 至少 25 MB：为录制片段及普通声音样本预留的代理请求体上限。应用当前没有单独的通用 25 MB 服务端拦截规则，因此该数值是代理配置要求，不是文件格式保证。
- 至少 50 MB：`.flvoice` 声音包导入。应用会拒绝大于 50 MB 的声音包，并限制解密后的包内容总量不超过 50 MB；代理限制不能低于此值。

上传/响应超时建议至少 10 分钟，以免外网或较慢的 NAS 处理导致连接被代理提前中断。

## 首次使用与迁移

打开应用后会显示“创建管理员”。创建成功后以该账号登录。

升级已有部署前，先在“设置 - 数据备份”创建一份应用备份，并用 Hyper Backup 或其他 NAS 备份任务备份整个 `FAMILY_LEARNING_DATA_DIR`。随后再更新镜像和启动项目。当前数据库迁移也会在 `/data/backups/` 写入 `pre-0002-*.db` 形式的迁移前 SQLite 副本；这只是额外保护，不能代替升级前的完整备份。

## AI 和 TTS 配置

在“设置”中分别配置 AI 与英语发音服务；API Key 在 NAS 的数据目录中加密保存，设置界面仅显示掩码，保存后不会再次显示明文。

- AI 使用 OpenAI Chat 兼容协议，用于电子词典等 AI 功能；请填写服务地址、模型、API Key、超时和启用状态。
- TTS 可选择 MiMo TTS 或 OpenAI 兼容 TTS，并填写接口地址、模型、音色、语速和 API Key。默认 MiMo 参数为 `https://api.xiaomimimo.com/v1`、`mimo-v2.5-tts`、`Chloe`。
- OpenCode Go 的聊天模型接口可以作为 AI 服务，但不能直接代替 TTS 接口。
- 同一 TTS 配置下生成的 WAV 会在 NAS 缓存；更换接口、模型、音色或语速会生成新的缓存键。

声音克隆预览使用 MiMo 声音克隆接口，仍依赖部署时提供的 MiMo 环境变量 API Key；仅保存设置页的 TTS 配置并不能替代该运行时配置。

## 本地辞典数据

常用英文单词优先查询 ECDICT，中文词条优先查询 CC-CEDICT；短语、句子和本地未命中才调用 AI。因此，AI 未配置或外网临时不可用时，本地词条仍可查询。

构建镜像前在 Windows PowerShell 执行：

```powershell
backend/scripts/download_local_dictionary.ps1
```

脚本将 ECDICT 固定到提交 `bc015ed2e24a7abef49fc6dbbb7fe32c1dadaf8b`，下载 CC-CEDICT 发布包，并在 `backend/dictionary-data/` 生成只读 SQLite 与 `SHA256SUMS`。2026-07-20 验证的文件校验值为：

```text
1a6947e04785db63613a92e14903cdae7954f7e84860b10e68e5c7cbb3f9c3cf  ecdict.csv
ca51533573f692a0591b4be251cf65dda46ec987d525af2535677f409ded50f3  cedict_1_0_ts_utf-8_mdbg.txt.gz
2309ff5afd9fc5fde65144c770f8d7a3403742a62498075715592a673d592328  local-dictionary.sqlite3
```

源数据与 SQLite 不提交到 Git。Docker 构建缺少 `local-dictionary.sqlite3` 时会明确失败，避免误发布为只依赖 AI 的辞典。容器默认从 `/app/dictionary/local-dictionary.sqlite3` 只读查询；本地后端开发可设置 `APP_LOCAL_DICTIONARY_PATH` 指向生成文件。

ECDICT 使用 MIT License；CC-CEDICT 使用 CC BY-SA 3.0。应用侧边栏和 `frontend/public/animal-island/ATTRIBUTION.txt` 保留署名与许可证说明。

Dockerfile 默认使用当前网络可达的清华 PyPI 镜像，并把超时和重试应用到全部 pip 下载。若部署网络要求官方或内部镜像，可覆盖构建参数：

```sh
docker build --build-arg PIP_INDEX_URL=https://pypi.org/simple -f deploy/Dockerfile -t family-learning:local .
```

## 视频转码

系统默认使用软件 H.264 转码。DS918+ 上如果确认 `/dev/dri` 可用，可在单容器服务添加对应设备映射，将硬件转码作为后续优化；不得因为硬件编码不可用阻止源视频保存。

当前压缩版使用 H.264 Main Profile、AAC 80 kbps、CRF 27 和 900 kbps 峰值码率，并限制最长边不超过 720p、禁止放大低分辨率源视频。输出固定为 `yuv420p`、TV range、BT.709，并写入 fast-start 索引和约 2 秒关键帧间隔，以兼顾 iPhone/iPad Safari 播放、拖动预览和 NAS 存储体积。

预览与下载必须继续使用框架原生 `FileResponse`。生产环境的 Starlette 会原生处理 HTTP Range 并返回 `206 Partial Content`；不要再包一层自定义 Range 响应，否则 Safari 可能只播放声音或无法拖动。视频库只在用户展开某一条记录时创建播放器，`preload="metadata"` 避免列表页加载完整视频。下载响应应保持 `video/mp4`，并通过 `Content-Disposition` 提供 `.mp4` 文件名。

替换历史压缩文件时，先在同目录生成候选文件并校验视频流、音频流、时长、关键帧和浏览器画面，再原子替换 `720p.mp4`。保留替换前文件作为带日期的备份。不要通过 SMB 直接修改正在运行的 SQLite（尤其是 WAL 模式下的 `app.db`、`app.db-wal`、`app.db-shm`）；如确需数据库维护，应先停止容器并使用 SQLite 自身的备份/事务流程。

压缩版完成后，在 iPhone/iPad 点击下载，并通过系统分享菜单选择“存储视频”。网页不能静默写入照片相册。

Worker 在 FFmpeg 长任务期间每 5 秒刷新心跳与任务租约，因此“处理中”不会再被误报为离线，也不会因超过租约而被另一 Worker 重复领取。可恢复的组装/转码错误会按有限次数自动退避重试；启动时和 Worker 空闲期间会补齐 `assembling`、`transcoding` 但缺少任务的录像。

视频库每 5 秒后台刷新仍在处理的录像。只有自动重试耗尽后才显示“处理失败”和“重新处理”；该操作会复用已验证的源视频继续转码，或重新组装仍保留完整分片的录像，不需要重启后端或容器。健康接口同时返回兼容字段 `worker` 以及 `worker_state`（`online`、`busy`、`offline`）。

## 已知限制

- iOS 录制时 Safari/PWA 必须保持前台；锁屏或切换 App 可能终止录制。
- 断网片段临时保存在浏览器 IndexedDB；恢复网络后再上传。Safari 的本地空间由系统决定。
- 真机上线前请按 `docs/IOS-TEST-CHECKLIST.md` 验证。
- 声音授权、声音包、应用备份和恢复细节见 `docs/VOICE-PRIVACY-AND-BACKUP.md`。
