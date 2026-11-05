# 电子辞典 AI 排障手册（OpenCode Go / DeepSeek）

> 适用：v0.3.2 及以后。本文既是排障手册，也是 2026-11-05 那次「电子辞典 AI 连接失败」的完整记录。
> 相关代码：[`backend/app/services/openai_chat.py`](../backend/app/services/openai_chat.py)、[`backend/app/api/settings.py`](../backend/app/api/settings.py)、[`backend/app/services/dictionary.py`](../backend/app/services/dictionary.py)。

## 1. 这条链路是怎么接的

辞典查询是三层链，AI 只是最后一层兜底：

```
本地 ECDICT / CC-CEDICT  →  在线词典（有道 / Free Dictionary，30 天缓存）  →  AI 兜底（OpenAI 兼容）
```

- 配置在 **设置 → 电子辞典 AI**：服务名称、接口地址、模型名称、API Key、温度、超时。
- 只有一个 AI 配置（`ai_provider_config` 表 id=1），拼写图片识别默认复用它，也可以单独配。
- API Key 用 Fernet 加密落库，密钥文件是数据目录下的 `ai-settings.key`；**这个文件丢了，库里的密文就再也解不开**。
- 客户端固定行为（不是可选项）：
  - `response_format: {"type": "json_object"}` —— 要求模型只回 JSON；
  - `x-opencode-session: <uuid>` —— 每次对话一个稳定 ID，OpenCode Go 从 2026-09-05 起强制要求；
  - `User-Agent: family-learning/0.1` —— 网关会拒绝通用 SDK 的 UA；
  - 温度只在配置了就发，没配就不发（有些模型不认这个参数）。

## 2. 错误对照表

前端只会显示「连接测试失败，请检查配置。」这类笼统文案，真正的原因在上游返回里。对照下表看：

| 上游原话 / 状态 | 含义 | 处理 |
| --- | --- | --- |
| `prompt must contain 'json' when using json_object response_format`（400） | 开了 json mode，但 prompt 里没有 “json” 字样。DeepSeek 官方强制这一条 | v0.3.2 起客户端自动补 system 指令；老版本会把设置页「测试连接」打挂（它的 prompt 就一个 `apple`） |
| `MissingSessionID`（400） | 缺 `x-opencode-session`，检查在鉴权之前 | 镜像必须是 2026-09-30 之后构建的（commit `3bca6cc`） |
| `api_key_expired` / `Invalid credential`（401） | Key 过期或无效，**重新登录不会续期** | 去 OpenCode Console → Account → Personal API keys 新建一把 `oc_sk_...` |
| `An active OpenCode Go subscription is required.`（403） | 没有 Go 订阅；或用了 `-free` 结尾的免费模型 | 订阅 Go（$10/月起）或在 Console 充按量余额；免费档模型只能在 OpenCode 客户端里用 |
| `ModelDeprecated`（410） | 模型下线，例如 `mimo-v2.5` → `mimo-v2.6-flash` | 换模型 ID |
| `this feature is not yet supported by atlas`（400） | 网关把请求轮询到不支持 `response_format` 的节点 | v0.3.2 起自动去掉该参数重试一次 |
| `AI_NOT_CONFIGURED`（409） | 「启用」没勾，或没存过 Key | 重新填 Key 并保存 |
| 设置页永远停在「正在加载设置…」 | `GET /api/settings/ai` 返回 500：`ai-settings.key` 丢失/不可读，Fernet 解密抛 `InvalidToken` | 从备份还原 `ai-settings.key`；或清空 `ai_provider_config` 的密文重填 |

### 一个常被忽略的坑

设置页的「测试连接」**用的是数据库里已保存的配置，不是表单里刚改的值**（接口不收 body）。所以顺序必须是：

```
先「保存 AI 配置」→ 看到“已保存” → 再点「测试连接」
```

改完模型直接点测试，测的还是旧配置，很容易误判成“改了没用”。

## 3. 正确配置：OpenCode Go + DeepSeek V4.1 Flash

| 字段 | 值 |
| --- | --- |
| 服务名称 | `OpenCode Go`（随意） |
| 接口地址 | `https://opencode.ai/inference/go/openai/v1`（当前文档口径）或 `https://opencode.ai/zen/go/v1`（旧域名，仍可用） |
| 模型名称 | `deepseek-v4.1-flash`（**点号**，不是横杠） |
| API Key | Console 新建的 `oc_sk_...` |
| 温度 / 超时 | `0.1` / `45`（DeepSeek 偶尔慢，60 也行） |

注意：

- 接口地址填到 `/v1` 即可，程序会自动补 `/chat/completions`；直接填完整 `/chat/completions` 也能识别。
- **不要填 `deepseek-v4.1-flash-free`**：免费档模型只允许在 OpenCode 客户端内调用，其他客户端一律 403。
- DeepSeek 的两个模型受工作区地区限制：默认只开 Europe & US，中国出口 IP 需要在 Console → Settings → Privacy 把 Regions 选上 **Global**（没保存过隐私设置的工作区对来自中国的请求默认放行 Global）。
- Go 与按量付费的 base URL 不同：Go 是 `https://opencode.ai/inference/go`，按量是 `https://opencode.ai/inference`。

## 4. 出问题怎么查（不用打开界面）

以下命令里的容器名以 `docker ps` 实际输出为准，默认 `family-learning-family-learning-1`。

```sh
# 1) 容器状态
sudo docker ps --filter name=family-learning

# 2) 看这两条路径的状态码：PATCH 200 说明保存成功，test 502 才是上游失败
sudo docker logs --timestamps --tail 400 <容器名> 2>&1 | grep -E 'settings/ai|dictionary/lookup'

# 3) 看数据目录里的密钥文件
sudo docker exec <容器名> ls -l /data/ai-settings.key /data/app.db

# 4) 健康检查
curl -fsS http://127.0.0.1:6633/api/health
```

想看上游到底说了什么，直接在容器里用应用自己的客户端发一次请求（不会改动任何数据）：

```sh
sudo docker exec <容器名> python - <<'PY'
import sys; sys.path.insert(0, '/app')
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.services.ai_config import ai_api_key, get_ai_config
from app.services.dictionary import _messages
from app.services.openai_chat import OpenAiChatClient, OpenAiChatError

cfg = get_ai_config(Session(create_engine('sqlite:////data/app.db')))
print('config:', cfg.base_url, cfg.model, cfg.temperature, cfg.timeout_seconds)
client = OpenAiChatClient(ai_api_key(cfg), cfg.base_url, cfg.model, cfg.timeout_seconds, temperature=cfg.temperature)
for label, msgs in [('test', [{'role': 'user', 'content': 'apple'}]), ('dictionary', _messages('serendipity', 'en', 'zh'))]:
    try:
        client.complete(msgs); print(label, 'OK')
    except OpenAiChatError as exc:
        print(label, 'FAIL', exc.code, exc.detail)
PY
```

再不行就直接打上游，排除应用因素：

```sh
curl -sS -m 30 https://opencode.ai/inference/go/openai/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -H "x-opencode-session: $(cat /proc/sys/kernel/random/uuid)" \
  -H "User-Agent: family-learning/0.1" \
  -d '{"model":"deepseek-v4.1-flash","messages":[{"role":"user","content":"say hi"}]}'
```

## 5. 2026-11-05 事故记录

**现象**：部署在 NAS 上的实例，设置页保存 AI 配置成功（`PATCH 200`），但只要点「测试连接」就 502，界面显示连接失败；换成 OpenCode Go 的 DeepSeek V4.1 Flash 也一样。

**排查过程**（按顺序排除）：

1. 镜像构建于 2026-09-30，已包含 `x-opencode-session`（`grep` 容器内文件确认），排除旧镜像问题；
2. 数据库里的配置已是 `https://opencode.ai/zen/go/v1/chat/completions` + `deepseek-v4.1-flash`，Key 能正常解密（`oc_sk` 开头，51 字符），DNS 正常，排除配置/网络问题；
3. 容器内直接调客户端，拿到上游原话：

   ```
   400 {"error":{"type":"server_error","message":"Upstream request failed: [InvalidParameter]
   Invalid request: prompt must contain 'json' when using json_object response_format ..."}}
   ```

4. 同一请求连发 6 次，还会间歇出现 `this feature is not yet supported by atlas`。

**根因两条**：

1. 客户端对所有请求都强制 `response_format: json_object`，而设置页测试发的 prompt 是 `apple`——DeepSeek 要求 json mode 下 prompt 必须出现 “json”，于是 400，被应用包成 502。
   辞典查词一直正常，是因为它的 system prompt 里本来就有 “Return exactly one JSON object”。
2. OpenCode Go 会把请求轮询到多个上游，其中一个（`atlas`）不支持 `response_format`，返回 `not yet supported`，造成约 1/6 的偶发失败。

**修复**（commit `276080b`，[`openai_chat.py`](../backend/app/services/openai_chat.py)）：

- prompt 里没有 “json” 时自动补一条 system 指令（已有 system 消息则合并，不新增第二段）；
- 上游明确拒绝 JSON mode 时，去掉 `response_format` 重试一次（prompt 本身仍要求 JSON，解析层还有校验与修复）；
- 新增两个单测：JSON 提示补齐、降级重试。

**验证**（用线上真实 Key 打真实上游）：

| 场景 | 修复前 | 修复后 |
| --- | --- | --- |
| 设置页测试 prompt（`apple`） | 0/6 成功 | 6/6 |
| 辞典 prompt | 5/6 成功 | 6/6 |
| 部署后复测（三种 prompt 各 6 次） | — | 18/18 |

**部署**：本机 `docker buildx` 构建 `linux/amd64` → 导出 tar `family-learning-ds918plus-amd64-v0.3.2.tar`（348 MB）→ 上传 → `docker load` → `docker-compose -f compose.yaml up -d --force-recreate`。部署脚本自动把 `app.db*`、两个密钥文件备份到 `backups/pre-upgrade-<时间戳>/`。部署后 `/api/health` 全绿、`worker: online`。

**清理**：NAS 的 `TAR/` 目录只保留最新一份 tar（2.4 G → 348 M），旧镜像由部署脚本顶替删除；`uploads/`、`videos/`、`backups/`、`app.db` 等数据一律不动。

## 6. 运维备忘

**数据目录**（NAS 上为 `/volume1/docker/family-learning/`，容器内挂到 `/data`）：

| 路径 | 内容 | 能不能删 |
| --- | --- | --- |
| `app.db`（+ `-wal`/`-shm`） | SQLite 主库 | 不能 |
| `ai-settings.key` / `tts-settings.key` | 加密密钥，丢失后库里的 API Key 全部解不开 | 不能 |
| `uploads/`、`videos/` | 视频分片与成品（占空间最大） | 不能 |
| `tts/` | 发音缓存，可重建 | 可以 |
| `backups/` | 升级前的自动备份 | 谨慎 |
| `TAR/` | 发布镜像包，可重新构建 | 只留最新一份即可 |

**SSH 开关**：DSM 控制面板 → 终端机和 SNMP → 启动 SSH 功能。注意 `SYNO.Core.Terminal` 的 WebAPI `set` 会返回 `success: true` 但**不生效**（试过 `enable_ssh`/`ssh_enable` 都不行），开只能靠界面点；关可以在 SSH 里执行：

```sh
sudo synosystemctl stop sshd                      # 立即生效
sudo /usr/syno/bin/synowebapi --exec api=SYNO.Core.Terminal version=3 method=set enable_ssh=false
```

**清理旧版本**：

```sh
sudo docker images | grep family-learning          # 正常情况下只应剩 family-learning:latest
ls -lh /volume1/docker/family-learning/TAR/        # 只保留最新 tar，其余可删
```

注意别误删其他项目的悬空镜像（`<none>` 也可能是别的 Node 应用留下的）。

## 7. 已知设计与限制

- 「测试连接」读已保存配置，必须先保存再测（见 §2）。
- 温度只在配置了才发送，未配置则省略，兼容不认该参数的模型。
- 上游错误里的 API Key 会自动替换成 `***` 再展示。
- 免费档模型（`*-free`）只能在 OpenCode 客户端里用，外部 harness 一律 403。
- Go 的用量限制是「按月美元额度」而不是请求数，5 小时 / 每周 / 每月分别是月额度的 20% / 50% / 100%。
