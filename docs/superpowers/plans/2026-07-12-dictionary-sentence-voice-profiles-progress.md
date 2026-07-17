# 电子辞典、句子默写与多人声音档案进度日志

> 本文件由开发模型持续更新。每完成实施计划中的一个步骤，必须立即追加记录；不得在任务结束后批量补写。

## 当前状态

| 项目 | 当前值 |
| --- | --- |
| 总体状态 | blocked |
| 当前任务 | Task 12 |
| 当前步骤 | 12.6 |
| 最后更新时间（北京时间） | 2026-07-15 08:40 |
| 当前阻塞 | 等待真实 iPhone/iPad HTTPS 验收及已授权 MiMo Key/声音完成克隆试听 |

## 任务汇总

| 任务 | 状态 | 完成步骤 | 验证摘要 |
| --- | --- | --- | --- |
| Task 1 迁移与统一条目 | complete | 6/6 | 迁移、单词本与默写回归共 8 项通过 |
| Task 2 句子默写 | complete | 6/6 | 学习列表、句子默写、默写 API 与统计回归共 7 项通过 |
| Task 3 AI 配置 | complete | 6/6 | AI 设置与 Chat 客户端回归共 6 项通过 |
| Task 4 双向辞典 | complete | 6/6 | 辞典服务与 API 回归共 10 项通过 |
| Task 5 生词本 | complete | 6/6 | 生词本与既有错词统计回归共 4 项通过 |
| Task 6 使用人与声音版本 | complete | 6/6 | 使用人与既有 TTS 回归共 4 项通过 |
| Task 7 MiMo 声音克隆 | complete | 6/6 | 自动测试共 7 项通过；真实 MiMo Key 手工试听待 NAS 验收 |
| Task 8 加密导入导出 | complete | 7/7 | 加密包与 API 安全回归共 11 项通过 |
| Task 9 辞典前端 | complete | 6/6 | 前端测试、构建与四宽度视觉检查通过 |
| Task 10 声音与默写前端 | complete | 7/7 | 全前端测试 30 项和生产构建通过 |
| Task 11 统计与安全 | complete | 5/5 | 完整后端测试 123 项通过 |
| Task 12 部署与镜像 | blocked | 5/6 | 桌面完整流程通过；外部真机与真实 MiMo 验收待用户完成 |

## 步骤记录格式

每条记录必须使用以下格式：

```markdown
### YYYY-MM-DD HH:mm（Asia/Shanghai）— Task N / Step N.N — passed|failed|blocked

- 完成内容：一句话描述实际完成的行为。
- 修改文件：`path/a`、`path/b`。
- RED 证据：命令；预期失败摘要。（非 TDD 步骤写“不适用”）
- GREEN/验证证据：命令；退出码；通过数量或关键响应。
- 设计偏差：无；或链接到已先行更新的设计/计划章节。
- 遗留问题：无；或明确下一步与阻塞条件。
```

## 执行记录

### 2026-07-12 23:48（Asia/Shanghai）— Task 1 / Step 1.1 — passed

- 完成内容：新增旧 SQLite 数据库升级回填与句子规范化行为的 RED 测试。
- 修改文件：`backend/tests/test_learning_item_migration.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤只创建测试，下一步骤运行失败验证。
- GREEN/验证证据：不适用；尚未实现生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 1 / Step 1.2，确认测试因缺少 0002 迁移和学习条目服务失败。

### 2026-07-13 08:47（Asia/Shanghai）— Task 1 / Step 1.2 — passed

- 完成内容：运行迁移兼容和句子规范化测试，确认它们因尚未实现的 0002 迁移和学习条目服务失败。
- 修改文件：`backend/tests/test_learning_item_migration.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_learning_item_migration.py -q`；退出码 1，2 failed：旧库迁移后 `word_items.item_type` 不存在，且 `app.services.learning_items` 不存在。
- GREEN/验证证据：不适用；尚未实现生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 1 / Step 1.3，实现 SQLite batch migration。

### 2026-07-13 08:50（Asia/Shanghai）— Task 1 / Step 1.3 — passed

- 完成内容：新增 0002 SQLite batch migration，先创建迁移前备份，再回填统一条目字段并增加默写声音/条目类型快照字段。
- 修改文件：`backend/alembic/versions/0002_learning_dictionary_voice_profiles.py`、`backend/tests/test_learning_item_migration.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_learning_item_migration.py -q`；退出码 1，新增备份断言失败（无 `pre-0002` 备份），迁移字段断言失败（无 `item_type`）。
- GREEN/验证证据：`python -m pytest backend/tests/test_learning_item_migration.py -q -k 'existing_word_item or pre_upgrade_sqlite_backup'`；退出码 0，2 passed，1 deselected。
- 设计偏差：无。
- 遗留问题：执行 Task 1 / Step 1.4，实现统一领域模型、文本规范化和旧名兼容别名。

### 2026-07-13 08:52（Asia/Shanghai）— Task 1 / Step 1.4 — passed

- 完成内容：增加统一学习条目模型和英文/中文规范化、类型推断服务，保留旧 WordList/WordListVersion/WordItem 导出为同一模型别名。
- 修改文件：`backend/app/models/learning_item.py`、`backend/app/models/word_list.py`、`backend/app/models/dictation.py`、`backend/app/models/__init__.py`、`backend/app/services/learning_items.py`、`backend/tests/test_learning_item_migration.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_learning_item_migration.py -q`；退出码 1，`app.models.learning_item` 与 `app.services.learning_items` 不存在。
- GREEN/验证证据：`python -m pytest backend/tests/test_learning_item_migration.py -q`；退出码 0，4 passed（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 1 / Step 1.5，核对并验证容器入口在 app/worker 启动前执行真实 Alembic migration。

### 2026-07-13 08:54（Asia/Shanghai）— Task 1 / Step 1.5 — passed

- 完成内容：验证既有容器入口在 app 和 worker 分支均先运行 `alembic upgrade head`，成功后才启动服务，且 `set -e` 使迁移失败中止启动。
- 修改文件：`backend/tests/test_entrypoint_migrations.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；`deploy/entrypoint.sh` 已在本步骤前满足该行为，未删除既有生产逻辑伪造失败。
- GREEN/验证证据：`python -m pytest backend/tests/test_entrypoint_migrations.py -q`；退出码 0，1 passed（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 1 / Step 1.6，运行迁移、单词本和默写回归。

### 2026-07-13 08:54（Asia/Shanghai）— Task 1 / Step 1.6 — passed

- 完成内容：完成迁移安全网与统一学习条目的指定 GREEN 和旧功能回归。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为 GREEN 回归验证。
- GREEN/验证证据：`python -m pytest backend/tests/test_learning_item_migration.py backend/tests/test_words.py backend/tests/test_dictation.py -q`；退出码 0，8 passed（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 2 / Step 2.1，编写单词与句子混排学习列表失败测试。

### 2026-07-13 08:55（Asia/Shanghai）— Task 2 / Step 2.1 — passed

- 完成内容：新增确认学习列表后保持单词和句子条目类型及顺序的失败测试。
- 修改文件：`backend/tests/test_learning_lists.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤只创建测试，下一步骤完成后统一执行 RED 验证。
- GREEN/验证证据：不适用；尚未实现 Task 2 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 2 / Step 2.2，编写句子答案隐藏和人工评分失败测试。

### 2026-07-13 08:56（Asia/Shanghai）— Task 2 / Step 2.2 — passed

- 完成内容：新增句子默写在揭示前隐藏答案、揭示后返回答案且仅由家长人工评分的失败测试。
- 修改文件：`backend/tests/test_sentence_dictation.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤只创建测试，下一步骤统一执行 RED 验证。
- GREEN/验证证据：不适用；尚未实现 Task 2 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 2 / Step 2.3，确认两份测试因缺少学习列表 API 和句子默写响应行为而失败。

### 2026-07-13 08:56（Asia/Shanghai）— Task 2 / Step 2.3 — passed

- 完成内容：运行混排学习列表和句子默写测试，确认新服务与答案响应契约尚未实现。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_learning_lists.py backend/tests/test_sentence_dictation.py -q`；退出码 1，2 failed：学习条目服务缺少 `create_learning_list`/`confirm_learning_list`，揭示响应缺少 `answer`。
- GREEN/验证证据：不适用；尚未实现 Task 2 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 2 / Step 2.4，实现新学习列表 API 并保留旧 API 兼容。

### 2026-07-13 08:58（Asia/Shanghai）— Task 2 / Step 2.4 — passed

- 完成内容：新增 `/api/learning-lists` 和共享学习列表服务；旧 `/api/word-lists` 通过兼容包装继续使用同一创建/确认逻辑，确认版本复制条目后不可原地修改。
- 修改文件：`backend/app/services/learning_items.py`、`backend/app/services/words.py`、`backend/app/api/learning_lists.py`、`backend/app/main.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_learning_lists.py backend/tests/test_sentence_dictation.py -q`；退出码 1，学习条目服务缺少创建/确认接口。
- GREEN/验证证据：`python -m pytest backend/tests/test_learning_lists.py backend/tests/test_sentence_dictation.py -q`；混排学习列表测试通过，句子揭示测试仍按预期失败于缺少 `answer`（属于下一步骤）。
- 设计偏差：无。
- 遗留问题：执行 Task 2 / Step 2.5，扩展默写会话快照、答案揭示契约和按条目类型统计。

### 2026-07-13 09:00（Asia/Shanghai）— Task 2 / Step 2.5 — passed

- 完成内容：默写会话接受朗读人/声音版本 ID，结果保存条目类型快照；句子在揭示后以 `answer` 返回；统计增加 word/phrase/sentence 的已评分准确率。
- 修改文件：`backend/app/services/dictation.py`、`backend/app/api/dictation.py`、`backend/app/services/dictation_stats.py`、`backend/tests/test_sentence_dictation.py`、`backend/tests/test_dictation_stats.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_sentence_dictation.py backend/tests/test_dictation_stats.py -q`；退出码 1，揭示响应缺少 `answer`，统计缺少 `word_accuracy`。
- GREEN/验证证据：`python -m pytest backend/tests/test_learning_lists.py backend/tests/test_sentence_dictation.py backend/tests/test_dictation_stats.py -q`；退出码 0，4 passed（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 2 / Step 2.6，运行学习列表、句子默写、既有默写 API 和统计回归。

### 2026-07-13 09:01（Asia/Shanghai）— Task 2 / Step 2.6 — passed

- 完成内容：完成学习列表、句子默写、既有默写 API 与统计的指定 GREEN 回归。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为 GREEN 回归验证。
- GREEN/验证证据：`python -m pytest backend/tests/test_learning_lists.py backend/tests/test_sentence_dictation.py backend/tests/test_dictation_api.py backend/tests/test_dictation_stats.py -q`；退出码 0，7 passed（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 3 / Step 3.1，编写 AI 密钥隔离和掩码失败测试。

### 2026-07-13 09:02（Asia/Shanghai）— Task 3 / Step 3.1 — passed

- 完成内容：新增独立 AI 配置保存/读取的密钥隔离、掩码与不影响 TTS 配置的失败测试。
- 修改文件：`backend/tests/test_ai_settings.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤只创建测试，下一步骤完成后统一执行 RED 验证。
- GREEN/验证证据：不适用；尚未实现 Task 3 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 3 / Step 3.2，编写 OpenAI-compatible 请求与敏感日志保护失败测试。

### 2026-07-13 09:03（Asia/Shanghai）— Task 3 / Step 3.2 — passed

- 完成内容：新增 OpenAI-compatible Chat 请求 URL、Bearer 鉴权、JSON 响应约束以及失败信息不泄漏 AI Key 的测试。
- 修改文件：`backend/tests/test_openai_chat.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤只创建测试，下一步骤统一执行 RED 验证。
- GREEN/验证证据：不适用；尚未实现 Task 3 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 3 / Step 3.3，确认 AI 设置与 OpenAI-compatible 请求测试因缺少实现而失败。

### 2026-07-13 09:03（Asia/Shanghai）— Task 3 / Step 3.3 — passed

- 完成内容：运行 AI 设置与 OpenAI-compatible 请求测试，确认独立配置路由和 Chat 客户端尚未实现。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_ai_settings.py backend/tests/test_openai_chat.py -q`；退出码 1，3 failed：`/api/settings/ai` 为 404，且 `app.services.openai_chat` 不存在。
- GREEN/验证证据：不适用；尚未实现 Task 3 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 3 / Step 3.4，实现独立 AI 配置、成熟库密钥加密和 Key 保留语义。

### 2026-07-13 09:06（Asia/Shanghai）— Task 3 / Step 3.4 — passed

- 完成内容：新增独立 `ai_provider_config` 持久化和 0003 Alembic migration；AI Key 使用独立 Fernet 密钥加密，空 Key 更新保留旧 Key，GET/PATCH 只返回掩码。
- 修改文件：`backend/pyproject.toml`、`backend/alembic/versions/0003_ai_provider_config.py`、`backend/app/models/ai_provider_config.py`、`backend/app/models/__init__.py`、`backend/app/services/ai_config.py`、`backend/app/api/settings.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_ai_settings.py backend/tests/test_openai_chat.py -q`；退出码 1，AI 设置路由为 404，Chat 客户端不存在。
- GREEN/验证证据：`python -m pytest backend/tests/test_ai_settings.py -q`；退出码 0，1 passed（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 3 / Step 3.5，实现 OpenAI-compatible 连接测试和稳定错误映射。

### 2026-07-13 09:11（Asia/Shanghai）— Task 3 / Step 3.5 — passed

- 完成内容：新增 OpenAI-compatible Chat 客户端与 `/api/settings/ai/test`；测试请求固定为 `apple`，返回稳定成功结构，401/403 和超时映射为稳定错误码。
- 修改文件：`backend/app/services/openai_chat.py`、`backend/app/api/settings.py`、`backend/tests/test_ai_settings.py`、`backend/tests/test_openai_chat.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_ai_settings.py backend/tests/test_openai_chat.py -q`；退出码 1，5 failed，均因 `app.services.openai_chat` 不存在。
- GREEN/验证证据：`python -m pytest backend/tests/test_ai_settings.py backend/tests/test_openai_chat.py -q`；退出码 0，6 passed（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 3 / Step 3.6，运行 Task 3 指定 GREEN 验证。

### 2026-07-13 09:11（Asia/Shanghai）— Task 3 / Step 3.6 — passed

- 完成内容：完成独立 AI 配置与 OpenAI-compatible Chat 客户端的指定 GREEN 验证。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为 GREEN 回归验证。
- GREEN/验证证据：`python -m pytest backend/tests/test_ai_settings.py backend/tests/test_openai_chat.py -q`；退出码 0，6 passed（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 4 / Step 4.1，编写双向辞典语言方向和结构化 schema 失败测试。

### 2026-07-13 09:12（Asia/Shanghai）— Task 4 / Step 4.1 — passed

- 完成内容：新增中英文自动方向识别和辞典结构化结果字段/列表上限的失败测试。
- 修改文件：`backend/tests/test_dictionary.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤只创建测试，下一步骤完成后统一执行 RED 验证。
- GREEN/验证证据：不适用；尚未实现 Task 4 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 4 / Step 4.2，编写 provider 指纹和 prompt 版本隔离的辞典缓存失败测试。

### 2026-07-13 09:13（Asia/Shanghai）— Task 4 / Step 4.2 — passed

- 完成内容：新增辞典缓存测试，要求相同规范化输入和 provider 指纹只请求一次，模型指纹变化重新请求；同时新增自动方向查询 API 契约测试。
- 修改文件：`backend/tests/test_dictionary.py`、`backend/tests/test_dictionary_api.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤只创建测试，下一步骤统一执行 RED 验证。
- GREEN/验证证据：不适用；尚未实现 Task 4 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 4 / Step 4.3，确认方向/schema、缓存和查询 API 测试因缺少辞典实现而失败。

### 2026-07-13 09:14（Asia/Shanghai）— Task 4 / Step 4.3 — passed

- 完成内容：运行辞典方向、结构化 schema、缓存和查询 API 测试，确认辞典服务、schema 和路由尚未实现。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_dictionary.py backend/tests/test_dictionary_api.py -q`；退出码 1，5 failed：`app.services.dictionary`、`app.schemas.dictionary` 不存在，`/api/dictionary/lookup` 为 404。
- GREEN/验证证据：不适用；尚未实现 Task 4 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 4 / Step 4.4，实现安全提示词、Pydantic schema 和一次 JSON 修复重试。

### 2026-07-13 09:16（Asia/Shanghai）— Task 4 / Step 4.4 — passed

- 完成内容：新增辞典 Pydantic schema、安全 system/user 提示词、一次 JSON 修复重试和稳定 `DICTIONARY_RESPONSE_INVALID`；新增查询 API 自动方向响应。
- 修改文件：`backend/app/schemas/__init__.py`、`backend/app/schemas/dictionary.py`、`backend/app/services/dictionary.py`、`backend/app/api/dictionary.py`、`backend/app/main.py`、`backend/pyproject.toml`、`backend/tests/test_dictionary.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_dictionary.py backend/tests/test_dictionary_api.py -q`；退出码 1，辞典服务/schema/路由不存在。
- GREEN/验证证据：`python -m pytest backend/tests/test_dictionary.py backend/tests/test_dictionary_api.py -q -k 'not cache'`；退出码 0，6 passed，1 deselected（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 4 / Step 4.5，实现 provider 指纹缓存、孩子隔离历史与历史删除语义。

### 2026-07-13 09:19（Asia/Shanghai）— Task 4 / Step 4.5 — passed

- 完成内容：新增 `dictionary_entries` 共享缓存和孩子隔离 `dictionary_history`，以规范化文本/方向/provider 指纹/prompt 版本构建哈希；删除历史仅删除孩子引用并保留缓存条目。
- 修改文件：`backend/alembic/versions/0004_dictionary_entries.py`、`backend/app/models/dictionary.py`、`backend/app/models/__init__.py`、`backend/app/services/dictionary.py`、`backend/tests/conftest.py`、`backend/tests/test_dictionary.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_dictionary.py -q -k 'cache or deleting_child_history'`；退出码 1，相同指纹的第二次查询未命中缓存，且历史删除服务不存在。
- GREEN/验证证据：`python -m pytest backend/tests/test_dictionary.py -q -k 'cache or deleting_child_history'`；退出码 0，2 passed，5 deselected（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 4 / Step 4.6，运行辞典服务与 API 指定 GREEN 验证。

### 2026-07-13 09:23（Asia/Shanghai）— Task 4 / Step 4.5 — blocked

- 完成内容：在 4.6 全量回归中发现 4.5 尚缺 `GET/DELETE /api/dictionary/history`，因此撤回该步骤勾选并补齐 API 测试与实现。
- 修改文件：`backend/tests/test_dictionary_api.py`、`backend/app/api/dictionary.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_dictionary_api.py -q -k history`；退出码 1，`GET /api/dictionary/history` 为 404。
- GREEN/验证证据：`python -m pytest backend/tests/test_dictionary_api.py -q -k history`；退出码 0，1 passed，1 deselected（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：继续 Task 4 / Step 4.5，补齐稳定 `created_at,id` 游标分页后重新验证整个步骤。

### 2026-07-13 09:25（Asia/Shanghai）— Task 4 / Step 4.5 — passed

- 完成内容：补齐孩子隔离的历史 GET/DELETE API 和以 `created_at,id` 稳定排序的游标分页；查询 API 依循既有默认孩子约定，避免历史外键失败。
- 修改文件：`backend/app/api/dictionary.py`、`backend/app/services/dictionary.py`、`backend/tests/test_dictionary_api.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_dictionary_api.py -q -k history`；退出码 1，历史路由为 404；`python -m pytest backend/tests/test_dictionary_api.py -q -k cursor`；退出码 1，端点忽略 limit/cursor 并返回两条记录。
- GREEN/验证证据：`python -m pytest backend/tests/test_dictionary_api.py -q -k 'history or cursor'`；退出码 0，2 passed，1 deselected（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 4 / Step 4.6，运行辞典服务与 API 指定 GREEN 验证。

### 2026-07-13 09:26（Asia/Shanghai）— Task 4 / Step 4.6 — passed

- 完成内容：完成双向辞典、结构化缓存、孩子隔离历史与 API 的指定 GREEN 验证。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为 GREEN 回归验证。
- GREEN/验证证据：`python -m pytest backend/tests/test_dictionary.py backend/tests/test_dictionary_api.py -q`；退出码 0，10 passed（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 5 / Step 5.1，编写生词本幂等标记和掌握状态失败测试。

### 2026-07-13 09:26（Asia/Shanghai）— Task 5 / Step 5.1 — passed

- 完成内容：新增相同辞典条目重复标记“不认识”幂等，以及标记掌握后可恢复为不认识的失败测试。
- 修改文件：`backend/tests/test_unknown_items.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤只创建测试，下一步骤完成后统一执行 RED 验证。
- GREEN/验证证据：不适用；尚未实现 Task 5 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 5 / Step 5.2，编写生词混排生成学习列表失败测试。

### 2026-07-13 09:28（Asia/Shanghai）— Task 5 / Step 5.2 — passed

- 完成内容：新增从单词和句子生词创建草稿学习列表的失败测试，要求保留类型、翻译、选择顺序且不改变生词状态。
- 修改文件：`backend/tests/test_unknown_items.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤只创建测试，下一步骤统一执行 RED 验证。
- GREEN/验证证据：不适用；尚未实现 Task 5 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 5 / Step 5.3，确认生词模型和服务因缺少实现而失败。

### 2026-07-13 09:28（Asia/Shanghai）— Task 5 / Step 5.3 — passed

- 完成内容：运行生词幂等标记和混排学习列表测试，确认生词服务尚未实现。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_unknown_items.py -q`；退出码 1，2 failed，`app.services.unknown_items` 不存在。
- GREEN/验证证据：不适用；尚未实现 Task 5 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 5 / Step 5.4，实现生词模型、唯一活跃约束、状态转换与 API。

### 2026-07-13 09:31（Asia/Shanghai）— Task 5 / Step 5.4 — passed

- 完成内容：新增 `unknown_items` 与 0005 migration，以 partial unique index 约束活跃生词；实现幂等标记、掌握/恢复状态以及筛选 API。
- 修改文件：`backend/alembic/versions/0005_unknown_items.py`、`backend/app/models/unknown_item.py`、`backend/app/models/__init__.py`、`backend/app/services/unknown_items.py`、`backend/app/api/unknown_items.py`、`backend/app/main.py`、`backend/tests/test_unknown_items.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_unknown_items.py -q`；退出码 1，2 failed，`app.services.unknown_items` 不存在。
- GREEN/验证证据：`python -m pytest backend/tests/test_unknown_items.py -q -k idempotent`；退出码 0，1 passed，1 deselected（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 5 / Step 5.5，从选中生词创建新的草稿学习列表且不改变生词状态。

### 2026-07-13 09:32（Asia/Shanghai）— Task 5 / Step 5.5 — passed

- 完成内容：实现从选中生词创建新草稿学习列表的服务和 API，保留选择顺序、类型和翻译，且不修改生词状态。
- 修改文件：`backend/app/services/unknown_items.py`、`backend/app/api/unknown_items.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_unknown_items.py -q`；退出码 1，2 failed，生词服务不存在。
- GREEN/验证证据：`python -m pytest backend/tests/test_unknown_items.py -q`；退出码 0，2 passed（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 5 / Step 5.6，运行生词本和既有错词统计回归。

### 2026-07-13 09:33（Asia/Shanghai）— Task 5 / Step 5.6 — passed

- 完成内容：完成生词本与既有错词统计的指定 GREEN 回归。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为 GREEN 回归验证。
- GREEN/验证证据：`python -m pytest backend/tests/test_unknown_items.py backend/tests/test_dictation_stats.py -q`；退出码 0，4 passed（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 6 / Step 6.1，编写每位使用人只有一个默认声音的失败测试。

### 2026-07-13 09:34（Asia/Shanghai）— Task 6 / Step 6.1 — passed

- 完成内容：新增同一使用人切换默认声音后仅保留最新默认版本的失败测试。
- 修改文件：`backend/tests/test_speakers.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤只创建测试，下一步骤完成后统一执行 RED 验证。
- GREEN/验证证据：不适用；尚未实现 Task 6 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 6 / Step 6.2，编写声音版本被历史默写引用时只能软删除的失败测试。

### 2026-07-13 09:35（Asia/Shanghai）— Task 6 / Step 6.2 — passed

- 完成内容：新增历史默写引用声音版本时仅可标记 disabled、不可物理删除且历史名称快照保持不变的失败测试。
- 修改文件：`backend/tests/test_speakers.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤只创建测试，下一步骤统一执行 RED 验证。
- GREEN/验证证据：不适用；尚未实现 Task 6 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 6 / Step 6.3，确认使用人、声音版本和历史引用保护因缺少实现而失败。

### 2026-07-13 09:35（Asia/Shanghai）— Task 6 / Step 6.3 — passed

- 完成内容：运行默认声音与历史引用软删除测试，确认使用人和声音版本服务尚未实现。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_speakers.py -q`；退出码 1，2 failed，`app.services.speakers` 不存在。
- GREEN/验证证据：不适用；尚未实现 Task 6 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 6 / Step 6.4，实现使用人和声音版本模型、默认版本、软删除与认证 API。

### 2026-07-13 09:37（Asia/Shanghai）— Task 6 / Step 6.4 — passed

- 完成内容：新增使用人、声音版本及 0006 migration；实现认证 API、ready 声音设默认、历史引用声音软删除和名称快照保留。
- 修改文件：`backend/alembic/versions/0006_speaker_profiles.py`、`backend/app/models/speaker.py`、`backend/app/models/__init__.py`、`backend/app/services/speakers.py`、`backend/app/api/speakers.py`、`backend/app/main.py`、`backend/tests/test_speakers.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_speakers.py -q`；退出码 1，2 failed，`app.services.speakers` 不存在。
- GREEN/验证证据：`python -m pytest backend/tests/test_speakers.py -q`；退出码 0，2 passed（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 6 / Step 6.5，创建带参考 WAV SHA-256 配置指纹的多声音音频缓存关系。

### 2026-07-13 09:38（Asia/Shanghai）— Task 6 / Step 6.5 — blocked

- 完成内容：新增多声音音频缓存关系测试，要求配置指纹包含参考 WAV SHA-256，且同一条目同一指纹仅复用一个音频资源。
- 修改文件：`backend/tests/test_speakers.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：待执行；本步骤没有独立的“写测试”子步骤，测试已写入，下一步将立即运行并实现。
- GREEN/验证证据：不适用；尚未实现多声音音频缓存关系。
- 设计偏差：无。
- 遗留问题：继续 Task 6 / Step 6.5，运行缓存关系 RED 测试并实现 migration/model/service。

### 2026-07-13 09:40（Asia/Shanghai）— Task 6 / Step 6.5 — passed

- 完成内容：新增 `learning_item_audio` 和 0007 migration；缓存唯一键为学习条目与配置指纹，指纹包含协议、模型、端点、音色、语速和参考 WAV SHA-256。
- 修改文件：`backend/alembic/versions/0007_learning_item_audio.py`、`backend/app/models/learning_item_audio.py`、`backend/app/models/__init__.py`、`backend/app/services/speakers.py`、`backend/tests/test_speakers.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_speakers.py -q -k audio_cache`；退出码 1，配置指纹与缓存服务无法导入。
- GREEN/验证证据：`python -m pytest backend/tests/test_speakers.py -q -k audio_cache`；退出码 0，1 passed，2 deselected（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 6 / Step 6.6，运行使用人与既有 TTS 回归。

### 2026-07-13 09:41（Asia/Shanghai）— Task 6 / Step 6.6 — passed

- 完成内容：完成使用人与多声音缓存关系及既有 TTS 的指定 GREEN 回归。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为 GREEN 回归验证。
- GREEN/验证证据：`python -m pytest backend/tests/test_speakers.py backend/tests/test_tts.py -q`；退出码 0，4 passed（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 7 / Step 7.1，编写音频归一化和安全限制失败测试。

### 2026-07-13 09:42（Asia/Shanghai）— Task 7 / Step 7.1 — passed

- 完成内容：新增 WAV 样本时长和 Base64 大小限制的失败测试。
- 修改文件：`backend/tests/test_voice_samples.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤只创建测试，下一步骤完成后统一执行 RED 验证。
- GREEN/验证证据：不适用；尚未实现 Task 7 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 7 / Step 7.2，编写 MiMo 声音克隆官方 payload 失败测试。

### 2026-07-13 09:44（Asia/Shanghai）— Task 7 / Step 7.2 — passed

- 完成内容：新增 MiMo 声音克隆官方 Chat Completions payload 测试，断言模型、api-key 和参考 WAV Data URI。
- 修改文件：`backend/tests/test_mimo_voice_clone.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤只创建测试，下一步骤统一执行 RED 验证。
- GREEN/验证证据：不适用；尚未实现 Task 7 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 7 / Step 7.3，确认音频验证和 MiMo clone payload 测试因缺少实现而失败。

### 2026-07-13 09:44（Asia/Shanghai）— Task 7 / Step 7.3 — passed

- 完成内容：运行音频验证和 MiMo clone payload 测试，确认音频服务与声音克隆客户端尚未实现。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_voice_samples.py backend/tests/test_mimo_voice_clone.py -q`；退出码 1，3 failed，`app.services.voice_samples` 和 `app.services.mimo_voice_clone` 不存在。
- GREEN/验证证据：不适用；尚未实现 Task 7 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 7 / Step 7.4，实现上传授权、随机文件名、FFmpeg 归一化和音频安全验证。

### 2026-07-13 09:47（Asia/Shanghai）— Task 7 / Step 7.4 — passed

- 完成内容：实现授权同意 multipart 上传、随机文件名落盘、归一化后台任务、FFmpeg 24 kHz mono PCM WAV 转换和 ffprobe/Base64 安全校验。
- 修改文件：`backend/app/services/voice_samples.py`、`backend/app/services/mimo_voice_clone.py`、`backend/app/workers/voice.py`、`backend/app/workers/runner.py`、`backend/app/api/speakers.py`、`backend/tests/test_voice_samples.py`、`backend/tests/test_mimo_voice_clone.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_voice_samples.py backend/tests/test_mimo_voice_clone.py -q`；退出码 1，音频服务与 clone 客户端不存在；`python -m pytest backend/tests/test_voice_samples.py -q -k voice_upload`；退出码 1，上传路由为 404。
- GREEN/验证证据：`python -m pytest backend/tests/test_voice_samples.py backend/tests/test_mimo_voice_clone.py -q`；退出码 0，3 passed；`python -m pytest backend/tests/test_voice_samples.py -q -k voice_upload`；退出码 0，1 passed，2 deselected（均有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 7 / Step 7.5，实现克隆试听和指定声音的任意文本 TTS。

### 2026-07-13 09:51（Asia/Shanghai）— Task 7 / Step 7.5 — passed

- 完成内容：归一化成功后自动入队固定英文试听；ready 声音版本可通过同一 MiMo clone 适配器生成任意英文文本 WAV 并按声音/文本缓存。
- 修改文件：`backend/app/workers/voice.py`、`backend/app/workers/runner.py`、`backend/tests/test_mimo_voice_clone.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_mimo_voice_clone.py -q -k preview`；退出码 1，试听 worker 不存在；`python -m pytest backend/tests/test_mimo_voice_clone.py -q -k arbitrary`；退出码 1，任意文本适配器不存在。
- GREEN/验证证据：`python -m pytest backend/tests/test_voice_samples.py backend/tests/test_mimo_voice_clone.py backend/tests/test_tts.py -q`；退出码 0，7 passed（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 7 / Step 7.6；当前无 `APP_MIMO_API_KEY`，真实已授权声音试听需留待 NAS 手工验收。

### 2026-07-13 09:51（Asia/Shanghai）— Task 7 / Step 7.6 — passed

- 完成内容：完成 Task 7 自动 GREEN 验证；检查确认当前环境未配置 `APP_MIMO_API_KEY`，因此未执行或伪造真实 MiMo 声音克隆试听。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为 GREEN 与手工验收记录。
- GREEN/验证证据：`python -m pytest backend/tests/test_voice_samples.py backend/tests/test_mimo_voice_clone.py backend/tests/test_tts.py -q`；退出码 0，7 passed；`APP_MIMO_API_KEY not configured`。
- 设计偏差：无。
- 遗留问题：真实 MiMo Key 与已授权本人声音试听待 NAS 手工验收；继续 Task 8 / Step 8.1，固定成熟密码学依赖。

### 2026-07-13 09:52（Asia/Shanghai）— Task 8 / Step 8.1 — passed

- 完成内容：验证已固定的 `cryptography>=43,<46` 依赖可用，且可导入 scrypt 与 AES-GCM 实现。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；依赖已在 Task 3 固定且本步骤验证其能力。
- GREEN/验证证据：`python -c "from cryptography.hazmat.primitives.kdf.scrypt import Scrypt; from cryptography.hazmat.primitives.ciphers.aead import AESGCM"`；退出码 0。
- 设计偏差：无。
- 遗留问题：执行 Task 8 / Step 8.2，编写加密往返、错误密码和篡改失败测试。

### 2026-07-13 10:17（Asia/Shanghai）— Task 8 / Step 8.2 — passed

- 完成内容：新增 `.flvoice` 加密往返、错误密码与篡改 ciphertext 统一稳定错误的失败测试。
- 修改文件：`backend/tests/test_voice_packages.py`、`backend/tests/test_voice_package_api.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤只创建测试，下一步骤完成后统一执行 RED 验证。
- GREEN/验证证据：不适用；尚未实现 Task 8 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 8 / Step 8.3，编写 ZIP 路径穿越与导入冲突策略失败测试。

### 2026-07-13 10:19（Asia/Shanghai）— Task 8 / Step 8.3 — passed

- 完成内容：新增加密包拒绝 ZIP 路径穿越和音频 SHA-256 不匹配的失败测试。
- 修改文件：`backend/tests/test_voice_packages.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤只创建测试，下一步骤统一执行 RED 验证。
- GREEN/验证证据：不适用；尚未实现 Task 8 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 8 / Step 8.4，确认加密格式、错误密码、篡改与包结构测试因缺少实现而失败。

### 2026-07-13 10:20（Asia/Shanghai）— Task 8 / Step 8.4 — passed

- 完成内容：运行加密包、错误密码、篡改、ZIP 校验与未认证 inspect 测试，确认包服务和 API 尚未实现。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_voice_packages.py backend/tests/test_voice_package_api.py -q`；退出码 1，7 failed，`app.services.voice_packages` 不存在且 inspect 路由为 404。
- GREEN/验证证据：不适用；尚未实现 Task 8 生产代码。
- 设计偏差：无。
- 遗留问题：执行 Task 8 / Step 8.5，实现 FLVOICE1、scrypt、AES-256-GCM 与安全 ZIP 校验。

### 2026-07-13 10:23（Asia/Shanghai）— Task 8 / Step 8.5 — passed

- 完成内容：实现 FLVOICE1 二进制格式、固定 scrypt 参数、AES-256-GCM、无个人信息 header、错误密码/篡改统一错误与安全 ZIP 路径/大小/哈希校验。
- 修改文件：`backend/app/services/voice_packages.py`、`backend/tests/test_voice_packages.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_voice_packages.py backend/tests/test_voice_package_api.py -q`；退出码 1，包服务不存在且 inspect API 为 404。
- GREEN/验证证据：`python -m pytest backend/tests/test_voice_packages.py -q`；退出码 0，6 passed（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 8 / Step 8.6，实现 inspect/commit 两阶段导入、显式冲突策略和临时文件清理。

### 2026-07-13 10:30（Asia/Shanghai）— Task 8 / Step 8.6 — passed

- 完成内容：实现认证 inspect/commit 两阶段 API；inspect 仅返回预览，commit 要求 merge/replace_profile_metadata/create_new 策略，导入参考 WAV 使用随机路径，解密临时 ZIP 写入 `/data/imports/voice/<uuid>.part` 并在 commit finally 清理。
- 修改文件：`backend/app/services/voice_packages.py`、`backend/app/api/voice_packages.py`、`backend/app/main.py`、`backend/tests/test_voice_packages.py`、`backend/tests/test_voice_package_api.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_voice_package_api.py -q`；退出码 1，inspect/commit 路由为 404；`python -m pytest backend/tests/test_voice_packages.py -q -k staged`；退出码 1，暂存记录缺少受控临时明文路径。
- GREEN/验证证据：`python -m pytest backend/tests/test_voice_packages.py backend/tests/test_voice_package_api.py -q`；退出码 0，11 passed（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 8 / Step 8.7，运行加密声音包的完整 GREEN 与安全回归。

### 2026-07-13 10:32（Asia/Shanghai）— Task 8 / Step 8.7 — passed

- 完成内容：完成加密声音包格式、安全校验、认证 inspect/commit 与策略导入的指定 GREEN 回归。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为 GREEN 回归验证。
- GREEN/验证证据：`python -m pytest backend/tests/test_voice_packages.py backend/tests/test_voice_package_api.py -q`；退出码 0，11 passed（另有既存第三方 `multipart` 弃用警告）。
- 设计偏差：无。
- 遗留问题：执行 Task 9 / Step 9.1，编写前端 AI 设置密钥不回显失败测试。

### 2026-07-13 10:33（Asia/Shanghai）— Task 9 / Step 9.1 — passed

- 完成内容：新增前端电子辞典 AI 设置密钥不回显失败测试。
- 修改文件：`frontend/src/features/settings/AiSettingsPanel.test.tsx`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤只创建测试，下一步骤完成后统一执行 RED 验证。
- GREEN/验证证据：不适用；尚未实现 Task 9 前端组件。
- 设计偏差：无。
- 遗留问题：执行 Task 9 / Step 9.2，编写辞典双向查询、播放与不认识标记失败测试。

### 2026-07-13 10:35（Asia/Shanghai）— Task 9 / Step 9.2 — passed

- 完成内容：新增辞典自动/手动方向、结构化结果、英文播放、不认识标记与缓存提示的失败测试。
- 修改文件：`frontend/src/features/dictionary/DictionaryPage.test.tsx`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤只创建测试，下一步骤统一执行 RED 验证。
- GREEN/验证证据：不适用；尚未实现 Task 9 前端组件。
- 设计偏差：无。
- 遗留问题：执行 Task 9 / Step 9.3，确认 AI 设置与辞典交互测试因组件缺少实现而失败。

### 2026-07-13 10:36（Asia/Shanghai）— Task 9 / Step 9.3 — passed

- 完成内容：运行 AI 设置和辞典交互测试，确认两个新组件均尚未实现。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`npm --workspace frontend test -- AiSettingsPanel.test.tsx DictionaryPage.test.tsx --run`；退出码 1，两个测试文件均无法解析缺失的 `AiSettingsPanel` 和 `DictionaryPage` 模块。
- GREEN/验证证据：不适用；尚未实现 Task 9 前端组件。
- 设计偏差：无。
- 遗留问题：执行 Task 9 / Step 9.4，实现 AI 设置和辞典查询页面。

### 2026-07-13 11:22（Asia/Shanghai）— Task 9 / Step 9.4 — passed

- 完成内容：接入电子辞典 AI 设置的读取、保存和连接测试；接入辞典查询、缓存提示、生词标记、已就绪声音选择及受认证音频播放；导航新增“辞典”，将“单词本”升级为“学习本”并保留旧路由映射。查询响应补齐 `entry_id`。音频资源现在按用户所有权隔离，跨用户生成或读取均返回 403；新增 Alembic `0008_user_owned_voice_audio`。
- 修改文件：`frontend/src/App.tsx`、`frontend/src/App.test.tsx`、`frontend/src/api/client.ts`、`frontend/src/ui/AppShell.tsx`、`frontend/src/styles.css`、`frontend/src/features/settings/SettingsPage.tsx`、`frontend/src/features/dictionary/DictionaryPage.tsx`、`frontend/src/features/dictionary/DictionaryResultCard.tsx`、`frontend/src/features/dictionary/DictionaryPage.test.tsx`、`backend/app/api/dictionary.py`、`backend/app/api/speakers.py`、`backend/app/api/tts.py`、`backend/app/api/deps.py`、`backend/app/models/dictionary.py`、`backend/app/models/speaker.py`、`backend/app/models/tts_asset.py`、`backend/app/services/dictionary.py`、`backend/app/services/speakers.py`、`backend/alembic/versions/0008_user_owned_voice_audio.py`、`backend/tests/test_dictionary_api.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`npm --workspace frontend test -- App.test.tsx --run` 退出码 1，导航中缺少“辞典”；`python -m pytest backend/tests/test_dictionary_api.py::test_dictionary_lookup_honors_auto_and_manual_direction -q` 退出码 1，响应缺少 `entry_id`；`npm --workspace frontend test -- DictionaryPage.test.tsx --run` 退出码 1，缺少“朗读声音”选择器；`python -m pytest backend/tests/test_dictionary_api.py::test_dictionary_audio_returns_authenticated_asset_for_a_ready_selected_voice -q` 退出码 1，音频端点返回 404；跨用户音频测试初始观察到生成/下载均为 200。
- GREEN/验证证据：`npm --workspace frontend test -- App.test.tsx DictionaryPage.test.tsx AiSettingsPanel.test.tsx --run`，退出码 0，3 文件 4 项通过；`npm --workspace frontend run build`，退出码 0；`python -m pytest backend/tests/test_dictionary_api.py backend/tests/test_tts_audio.py backend/tests/test_migrations.py -q`，退出码 0，9 passed（仅既有 `python_multipart` 弃用警告）。
- 设计偏差：无。声音克隆文本生成沿用现有同步适配器，真实 MiMo 调用可能占用请求至上游返回；未伪造任何音频端点。
- 遗留问题：执行 Task 9 / Step 9.5，实现生词本页面。

### 2026-07-14 07:44（Asia/Shanghai）— Task 9 / Step 9.5 — passed

- 完成内容：新增生词本页面，支持状态和类型筛选、标记已掌握、恢复不认识、多选创建草稿学习列表；从辞典页进入生词本，不增加 iPhone 底栏第六个入口。布局在 iPhone 单列中将主操作固定于安全区域上方，iPad 为两栏，桌面最多三栏。
- 修改文件：`frontend/src/features/dictionary/UnknownItemsPage.tsx`、`frontend/src/features/dictionary/UnknownItemsPage.test.tsx`、`frontend/src/features/dictionary/DictionaryPage.tsx`、`frontend/src/App.tsx`、`frontend/src/App.test.tsx`、`frontend/src/styles.css`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`npm --workspace frontend test -- UnknownItemsPage.test.tsx --run`，退出码 1，缺少 `UnknownItemsPage` 模块；`npm --workspace frontend test -- App.test.tsx --run`，退出码 1，辞典页缺少“查看生词本”入口。
- GREEN/验证证据：`npm --workspace frontend test -- UnknownItemsPage.test.tsx App.test.tsx --run`，退出码 0，2 文件 3 项通过；`npm --workspace frontend run build`，退出码 0。
- 设计偏差：无。
- 遗留问题：执行 Task 9 / Step 9.6，运行指定 GREEN、构建和四个宽度视觉检查。

### 2026-07-14 07:49（Asia/Shanghai）— Task 9 / Step 9.6 — passed

- 完成内容：完成 Task 9 指定 GREEN、生产构建与 390px、834px、1194px、1440px 视觉检查；生词本在 390px 为单列且主操作位于可视安全区域上方，在 834px/1194px 为两栏，在 1440px 为三栏。
- 修改文件：`frontend/dist/index.html`、`frontend/dist/assets/index-CqCZvwgT.css`、`frontend/dist/assets/index-MwlteFu2.js`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为 GREEN、构建与视觉验收。
- GREEN/验证证据：`npm --workspace frontend test -- AiSettingsPanel.test.tsx DictionaryPage.test.tsx --run`，退出码 0，2 文件 3 项通过；`npm --workspace frontend run build`，退出码 0。隔离临时数据库上的本地 Playwright 截图/布局检查：390px `scrollWidth=390`、单列、主操作底部 389px/视口 900px；834px `scrollWidth=834`、两栏；1194px `scrollWidth=1194`、两栏；1440px `scrollWidth=1440`、三栏。截图保存于临时目录，未写入仓库。
- 视觉工具说明：内置浏览器连接本机回环服务受 URL 策略阻断；服务健康检查正常后，使用隔离临时数据库与本地 Playwright 回退完成四宽度检查。临时注入样例的中文翻译在 PowerShell 编码下显示乱码，不属于项目数据或前端文案，未影响布局/交互验收。
- 设计偏差：无。
- 遗留问题：开始 Task 10 / Step 10.1，编写声音档案前端失败测试。

### 2026-07-14 07:51（Asia/Shanghai）— Task 10 / Step 10.1 — passed

- 完成内容：新增声音授权、录制按钮状态、ready 声音试听以及每位使用人仅一个默认声音标识的前端失败测试。
- 修改文件：`frontend/src/features/voices/SpeakerProfilesPage.test.tsx`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤仅创建测试，Step 10.4 将统一运行 RED 验证。
- GREEN/验证证据：不适用；声音档案组件尚未实现。
- 设计偏差：无。
- 遗留问题：执行 Task 10 / Step 10.2，编写加密导出导入交互失败测试。

### 2026-07-14 07:52（Asia/Shanghai）— Task 10 / Step 10.2 — passed

- 完成内容：新增加密声音包导出双密码一致性、不包含 API Key 提示、导入预览以及显式 merge 冲突策略提交的前端失败测试。
- 修改文件：`frontend/src/features/voices/VoicePackageDialog.test.tsx`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤仅创建测试，Step 10.4 将统一运行 RED 验证。
- GREEN/验证证据：不适用；声音包交互组件尚未实现。
- 设计偏差：无。
- 遗留问题：执行 Task 10 / Step 10.3，编写句子默写隐藏答案失败测试。

### 2026-07-14 07:53（Asia/Shanghai）— Task 10 / Step 10.3 — passed

- 完成内容：新增句子默写答案在 reveal 前隐藏、播放不自动前进、只在家长人工评分后前进的失败测试。
- 修改文件：`frontend/src/features/dictation/SentenceDictationPage.test.tsx`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤仅创建测试，下一步骤运行统一 RED 验证。
- GREEN/验证证据：不适用；句子默写组件尚未实现。
- 设计偏差：无。
- 遗留问题：执行 Task 10 / Step 10.4，运行声音与句子默写前端测试的 RED 验证。

### 2026-07-14 07:57（Asia/Shanghai）— Task 10 / Step 10.4 — passed

- 完成内容：运行声音档案、声音包和句子默写前端测试，确认所有测试都在实现前失败。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`npm --workspace frontend test -- SpeakerProfilesPage.test.tsx VoicePackageDialog.test.tsx SentenceDictationPage.test.tsx --run`，退出码 1，三个测试文件分别无法解析尚不存在的 `SpeakerProfilesPage`、`VoicePackageDialog` 与 `SentenceDictationPage` 模块。
- GREEN/验证证据：不适用；实现尚未开始。
- 设计偏差：无。
- 遗留问题：执行 Task 10 / Step 10.5，实现学习本类型编辑和声音管理。

### 2026-07-14 08:16（Asia/Shanghai）— Task 10 / Step 10.5 — passed

- 完成内容：学习本升级为可编辑单词/短语/句子类型和翻译；新增“我的声音”入口，支持授权后浏览器录音、8–30 秒时长校验、音量显示、重录和直接上传，均进入后端持久化的异步处理状态；ready 版本可受认证试听和设默认；声音包要求双密码、不含 API Key、先预览再显式策略导入，并使用真实加密导出端点下载。
- 修改文件：`frontend/src/features/words/WordListEditor.tsx`、`frontend/src/features/words/WordListEditor.test.tsx`、`frontend/src/features/voices/SpeakerProfilesPage.tsx`、`frontend/src/features/voices/VoiceRecorder.tsx`、`frontend/src/features/voices/VoiceRecorder.test.tsx`、`frontend/src/features/voices/VoicePackageDialog.tsx`、`frontend/src/App.tsx`、`frontend/src/App.test.tsx`、`frontend/src/api/client.ts`、`frontend/src/styles.css`、`backend/app/api/speakers.py`、`backend/app/api/voice_packages.py`、`backend/tests/test_speaker_preview_api.py`、`backend/tests/test_voice_package_api.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_speaker_preview_api.py -q` 退出码 1，试听端点返回 404；`npm --workspace frontend test -- WordListEditor.test.tsx --run` 退出码 1，缺少条目类型控件；`npm --workspace frontend test -- App.test.tsx --run` 退出码 1，先后确认缺少“我的声音”入口、声音包入口和导出 Blob 请求；`python -m pytest backend/tests/test_voice_package_api.py::test_voice_package_export_is_owner_scoped_and_contains_no_api_key -q` 退出码 1，导出端点返回 404；`npm --workspace frontend test -- VoiceRecorder.test.tsx --run` 退出码 1，录音组件缺失；`npm --workspace frontend test -- SpeakerProfilesPage.test.tsx --run` 退出码 1，上传声音样本入口缺失。
- GREEN/验证证据：`npm --workspace frontend test -- VoiceRecorder.test.tsx SpeakerProfilesPage.test.tsx VoicePackageDialog.test.tsx WordListEditor.test.tsx App.test.tsx --run`，退出码 0，5 文件 12 项通过；`python -m pytest backend/tests/test_speaker_preview_api.py backend/tests/test_voice_package_api.py backend/tests/test_voice_samples.py -q`，退出码 0，9 passed（仅既有 `python_multipart` 弃用警告）；`npm --workspace frontend run build`，退出码 0。
- 设计偏差：无。JSDOM 对浏览器下载触发 `Not implemented: navigation to another Document` 提示，实际 Blob 下载请求已由测试断言覆盖，非应用错误。
- 遗留问题：执行 Task 10 / Step 10.6，实现默写声音切换和历史快照展示。

### 2026-07-14 08:47（Asia/Shanghai）— Task 10 / Step 10.6 — passed

- 完成内容：默写开始前按使用人筛选 ready 声音版本，提交使用人与版本 ID；会话中锁定选择并显示名称快照。后端校验使用人所有权、版本归属及 ready 状态，保存/返回名称快照，并为实际选择的克隆声音生成、缓存和恢复用户隔离的音频资产。
- 修改文件：`frontend/src/App.tsx`、`frontend/src/features/dictation/DictationPage.tsx`、`frontend/src/features/dictation/DictationPage.test.tsx`、`backend/app/api/dictation.py`、`backend/app/services/dictation.py`、`backend/app/workers/voice.py`、`backend/tests/test_dictation_api.py`、`backend/tests/test_voice_samples.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_dictation_api.py::test_dictation_session_persists_and_returns_selected_voice_name_snapshots -q`，退出码 1，恢复响应缺少名称快照；`npm --workspace frontend test -- DictationPage.test.tsx --run`，新增使用人选择测试在旧扁平声音选择器下失败；`python -m pytest backend/tests/test_dictation_api.py -q`，新增专属声音资产测试失败（返回资产为空）；`python -m pytest backend/tests/test_voice_samples.py -q`，退出码 1，归一化后的 `reference_sha256` 为 `None`；临时移除版本配对/就绪守卫后，`python -m pytest backend/tests/test_dictation_api.py -k "rejects_voice_from_different_selected_speaker or rejects_non_ready_voice_for_selected_speaker" -q` 退出码 1，两个非法请求均错误返回 201。
- GREEN/验证证据：`python -m pytest backend/tests/test_dictation.py backend/tests/test_dictation_api.py backend/tests/test_voice_samples.py -q`，退出码 0，13 passed（仅既有 `python_multipart` 弃用警告）；`npm --workspace frontend test -- DictationPage.test.tsx SentenceDictationPage.test.tsx --run`，退出码 0，2 文件 3 项通过；`npm --workspace frontend run build`，退出码 0。
- 设计偏差：无。专属声音音频复用既有 `LearningItemAudio` 缓存和 MiMo 生成服务；无声音选择时继续使用既有默认 TTS。
- 遗留问题：执行 Task 10 / Step 10.7，运行全部前端测试与构建。

### 2026-07-14 08:48（Asia/Shanghai）— Task 10 / Step 10.7 — passed

- 完成内容：完成 Task 10 的全前端自动化回归与生产构建。
- 修改文件：`frontend/dist/index.html`、`frontend/dist/assets/index-TdFJ79xV.css`、`frontend/dist/assets/index-BTsC2P7T.js`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为 GREEN、全量回归与构建验收。
- GREEN/验证证据：`npm --workspace frontend test -- --run`，退出码 0，18 文件 30 项通过；`npm --workspace frontend run build`，退出码 0，TypeScript 构建和 Vite 生产构建完成。
- 设计偏差：无。JSDOM 输出的 `Not implemented: navigation to another Document` 来自 Blob 下载测试环境，未导致测试或构建失败。
- 遗留问题：开始 Task 11 / Step 11.1，编写统计分母、错误分型、所有权和敏感数据失败测试。

### 2026-07-14 08:49（Asia/Shanghai）— Task 11 / Step 11.1 — passed

- 完成内容：新增扩展统计失败测试，定义已评分条目加权准确率、单词/短语/句子分型准确率、生词本本周新增/掌握数和辞典缓存命中总数。
- 修改文件：`backend/tests/test_extended_stats.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤仅编写测试，Step 11.3 将统一运行 RED 验证。
- GREEN/验证证据：不适用；扩展统计尚未实现。
- 设计偏差：无。
- 遗留问题：执行 Task 11 / Step 11.2，编写认证、日志和文件访问安全失败测试。

### 2026-07-14 08:50（Asia/Shanghai）— Task 11 / Step 11.2 — passed

- 完成内容：新增匿名配置/参考声音/声音包访问、日志敏感数据泄漏与声音文件静态 URL 访问的安全失败测试。
- 修改文件：`backend/tests/test_voice_security.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤仅编写测试，Step 11.3 将统一运行 RED 验证。
- GREEN/验证证据：不适用；统计和管理任务状态尚未实现。
- 设计偏差：无。
- 遗留问题：执行 Task 11 / Step 11.3，运行扩展统计与安全测试的 RED 验证。

### 2026-07-14 08:51（Asia/Shanghai）— Task 11 / Step 11.3 — passed

- 完成内容：运行扩展统计与声音安全测试，确认统计字段/聚合尚未实现且参考声音可经静态 URL 读取。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_extended_stats.py backend/tests/test_voice_security.py -q`，退出码 1；3 项统计测试分别缺少 `accuracy`、`reference_date` 和 `dictionary_cache_hits`，静态 `/voice-samples/private.wav` 返回 200 而非 404。其余 4 项认证/日志安全断言已通过。
- GREEN/验证证据：不适用；实现尚未开始。
- 设计偏差：无。
- 遗留问题：执行 Task 11 / Step 11.4，实现统计、失败任务管理、备份内容与参考声音静态访问修复。

### 2026-07-14 09:18（Asia/Shanghai）— Task 11 / Step 11.4 — passed

- 完成内容：按已评分条目返回整体和三类准确率、生词本周新增/掌握及辞典缓存命中，并在统计页展示；阻止参考声音与上传目录经 SPA 静态回退读取；设置页显示可由 worker 实际重试的失败声音任务；备份 ZIP 包含 SQLite、数据库引用的参考声音和已有 AI/TTS 密钥文件，且同秒请求使用唯一文件名。
- 修改文件：`backend/app/services/dictation_stats.py`、`backend/app/api/stats.py`、`backend/app/main.py`、`backend/app/services/backups.py`、`backend/app/api/settings.py`、`frontend/src/App.tsx`、`frontend/src/features/stats/DictationStatsPage.tsx`、`frontend/src/features/stats/DictationStatsPage.test.tsx`、`frontend/src/features/settings/SettingsPage.tsx`、`frontend/src/features/settings/SettingsPage.test.tsx`、`frontend/src/App.test.tsx`、`backend/tests/test_extended_stats.py`、`backend/tests/test_voice_security.py`、`backend/tests/test_settings_api.py`、`backend/tests/test_backups.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_extended_stats.py backend/tests/test_voice_security.py -q`，退出码 1，统计字段/参数缺失且静态参考声音返回 200；后续新增复核测试在修正前确认 `ai_lookup` 被错误列为可重试、同秒备份路径相同，且统计页缺少 `80%` 展示。
- GREEN/验证证据：`python -m pytest backend/tests/test_extended_stats.py backend/tests/test_voice_security.py backend/tests/test_settings_api.py backend/tests/test_backups.py -q`，退出码 0，15 passed（仅既有 `python_multipart` 弃用警告）；`npm --workspace frontend test -- App.test.tsx DictationStatsPage.test.tsx SettingsPage.test.tsx --run`，退出码 0，3 文件 9 项通过；`npm --workspace frontend run build`，退出码 0。
- 设计偏差：无。同步 AI 查询不会伪装成可由 worker 重试的持久任务；设置页仅显示 runner 实际支持的声音任务类型。
- 遗留问题：执行 Task 11 / Step 11.5，运行完整后端测试套件。

### 2026-07-14 09:20（Asia/Shanghai）— Task 11 / Step 11.5 — failed

- 完成内容：运行完整后端测试套件。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为完整 GREEN 验收。
- GREEN/验证证据：`python -m pytest -q`，退出码 1，117 passed、5 failed；失败为 reveal 旧响应字段兼容、ready 声音列表旧响应兼容、无效 XLSX 解析错误类型，以及 `0008_user_owned_voice_audio` 对旧库缺少表的迁移回归（2 项）。
- 设计偏差：无。
- 遗留问题：修复完整后端套件的 5 个回归失败后，重新执行 Task 11 / Step 11.5。

### 2026-07-14 09:24（Asia/Shanghai）— Task 11 / Step 11.5 — passed

- 完成内容：修复旧 API 响应兼容、Office 导入异常、精简旧库迁移和声音列表元数据契约回归后，完成完整后端测试套件。
- 修改文件：`backend/app/api/dictation.py`、`backend/app/api/speakers.py`、`backend/app/services/imports.py`、`backend/alembic/versions/0008_user_owned_voice_audio.py`、`backend/tests/test_speakers_api.py`、`frontend/src/App.tsx`、`frontend/src/App.test.tsx`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：此前完整套件退出码 1，117 passed、5 failed；聚焦复现确认旧 reveal 字段、voice 列表精确响应、无效 XLSX、精简旧库迁移均失败；新增 selection metadata 契约测试在默认 ready 列表含额外字段时失败。
- GREEN/验证证据：`python -m pytest -q`，退出码 0，123 passed（仅既有 `python_multipart` 弃用警告）。
- 设计偏差：无。`include_selection_metadata=true` 是新默写选择器的显式扩展；旧 `?ready=true` 保持最小响应契约。
- 遗留问题：开始 Task 12 / Step 12.1，更新部署、iOS 验收和声音隐私备份文档。

### 2026-07-14 09:26（Asia/Shanghai）— Task 12 / Step 12.1 — passed

- 完成内容：更新 DS918+ 部署、iOS/iPad 真机验收和声音隐私/备份恢复文档，涵盖共享 `/data` 映射、迁移前备份、AI/TTS 与多声音切换、隐私授权、25/50 MB 限制、不可恢复的 `.flvoice` 密码及数据库/参考声音/密钥成套恢复。
- 修改文件：`docs/DEPLOYMENT.md`、`docs/IOS-TEST-CHECKLIST.md`、`docs/VOICE-PRIVACY-AND-BACKUP.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤仅更新文档。
- GREEN/验证证据：逐个 UTF-8 读取 3 个文档，确认均非空且包含计划要求主题，无 `TODO` 占位符。
- 设计偏差：无。文档明确当前备份仅含数据库、已登记参考声音和存在的 AI/TTS 密钥，不声称覆盖视频、上传源文件或 TTS 缓存。
- 遗留问题：执行 Task 12 / Step 12.2，在隔离副本上演练旧数据库迁移并记录迁移前后表行数。

### 2026-07-14 09:39（Asia/Shanghai）— Task 12 / Step 12.2 — blocked

- 完成内容：使用 Python SQLite backup API 从 `local-data/app.db` 创建一致性临时快照，并记录迁移前 21 张业务表的行数；原 `local-data` 未被写入。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为旧数据库迁移演练。
- GREEN/验证证据：未完成。`docker build -t family-learning:migration-rehearsal -f deploy/Dockerfile .` 退出码 1：容器内 `pip install ./backend` 无法找到 `cryptography<46,>=43`；因此未运行新镜像中的 `alembic upgrade head`，也没有迁移后表行数可记录。
- 设计偏差：无。临时演练目录为 `%TEMP%/family-learning-migration-rehearsal-20260714`，迁移前统计文件已写入其中；未以旧镜像或本机服务冒充新镜像演练。
- 遗留问题：需要使 Docker 构建环境可获得 `cryptography>=43,<46`（例如恢复可访问的 Python 包索引/镜像缓存）后，重新执行 Task 12 / Step 12.2。

### 2026-07-14 09:45（Asia/Shanghai）— Task 12 / Step 12.2 — passed

- 完成内容：网络恢复后成功构建 `family-learning:migration-rehearsal`，在 `%TEMP%/family-learning-migration-rehearsal-20260714/app.db` 的隔离一致性 SQLite 快照上运行镜像内 `alembic upgrade head`；未写入 `local-data` 原件。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为迁移演练。
- GREEN/验证证据：`docker build -t family-learning:migration-rehearsal -f deploy/Dockerfile .`，退出码 0；镜像内 `alembic upgrade head`，退出码 0；迁移前后 21 张表行数比较 `changed={}`，包括 `recordings`、`word_lists`、`dictation_sessions` 与 `tts_provider_config`。临时数据库已是最新 revision，因此本次升级无待执行 migration，未新增 `pre-0002` 备份；演练前一致性快照和前后统计均保存在临时目录。
- 设计偏差：无。
- 遗留问题：执行 Task 12 / Step 12.3，逐项运行完整自动验证和 Compose 配置检查。

### 2026-07-14 09:51（Asia/Shanghai）— Task 12 / Step 12.3 — passed

- 完成内容：完成后端、前端、生产构建和 Compose 配置的完整自动验证。
- 修改文件：`frontend/dist/index.html`、`frontend/dist/assets/index-TdFJ79xV.css`、`frontend/dist/assets/index-wwwKY0Ei.js`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为完整 GREEN 验收。
- GREEN/验证证据：`python -m pytest -q`，退出码 0，123 passed（仅既有 `python_multipart` 弃用警告）；`npm --workspace frontend test -- --run`，退出码 0，18 文件 33 项通过（JSDOM 输出既有下载导航提示）；`npm --workspace frontend run build`，退出码 0；`docker compose -f deploy/compose.yaml config --quiet`，退出码 0。
- 设计偏差：无。
- 遗留问题：执行 Task 12 / Step 12.4，使用独立 Docker 项目名、端口和数据目录进行本地 app/worker 部署验收。

### 2026-07-14 22:36（Asia/Shanghai）— Task 12 / Step 12.4 — passed

- 完成内容：使用 `family-learning-acceptance` 独立项目、端口 `18080` 和 `%TEMP%/family-learning-docker-acceptance-20260714` 临时数据目录启动 app/worker；修复空卷并发启动时的 SQLite Alembic 迁移竞争，并完成 API 验收。
- 修改文件：`deploy/entrypoint.sh`、`backend/tests/test_entrypoint_migrations.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：初次隔离启动日志显示 app/worker 同时迁移，`0001_initial` 创建 `children` 时返回 `sqlite3.OperationalError: table children already exists`；新增入口测试在未使用共享 `flock` 时失败。
- GREEN/验证证据：`python -m pytest backend/tests/test_entrypoint_migrations.py -q`，退出码 0，2 passed；`docker build -t family-learning:acceptance -f deploy/Dockerfile .`，退出码 0；空数据目录重启后两个容器均 Up，未出现迁移异常。登录后显式回送生产 Secure cookie 验证 AI 设置读取、声音上传任务 `201 processing`、学习本创建/确认、统计读取均成功；隔离环境辞典返回预期 `409 AI_NOT_CONFIGURED`。
- 设计偏差：无。生产 cookie 的 `Secure` 属性使纯 HTTP 客户端不会自动回送，验收脚本显式回送已登录 cookie；真实 DS918+ 部署仍要求 HTTPS。
- 遗留问题：执行 Task 12 / Step 12.5，构建并导出 `linux/amd64` DS918+ all-in-one 镜像、SHA-256、Compose 文件和版本说明，并验证 `docker load` 标签。

### 2026-07-14 22:41（Asia/Shanghai）— Task 12 / Step 12.5 — passed

- 完成内容：构建并导出同一镜像供 app/worker 以不同 command 启动的 DS918+ all-in-one 发布包；发布 Compose 不含 `build`，可在仅导入 tar 后使用。
- 修改文件：`dist/ds918plus-20260714/family-learning-ds918plus-amd64-20260714.tar`、`dist/ds918plus-20260714/family-learning-ds918plus-amd64-20260714.tar.sha256`、`dist/ds918plus-20260714/compose.yaml`、`dist/ds918plus-20260714/VERSION.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-implementation.md`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为构建、导出与加载验收。
- GREEN/验证证据：`docker buildx build --platform linux/amd64 --load -t family-learning:ds918plus-amd64-20260714 -f deploy/Dockerfile .`，退出码 0，镜像检查为 `linux/amd64`；导出 tar 后 SHA-256 为 `7d06064dba203b4c11e1050db8b5ecc92d71858e52f1264e16198ee87e2bd7da`；临时 Docker context 中 `docker load` 退出码 0，并检查标签 `[family-learning:ds918plus-amd64-20260714] linux/amd64`；发布 Compose 配置检查退出码 0。
- 设计偏差：无。
- 遗留问题：执行 Task 12 / Step 12.6，完成 iPhone Safari/PWA、iPad、桌面和已授权真实 MiMo 克隆的真机验收矩阵。

### 2026-07-14 22:43（Asia/Shanghai）— Task 12 / Step 12.6 — blocked

- 完成内容：完成可由本机执行的验收前置项：后端/前端自动化、生产构建、隔离 Docker app/worker、迁移演练、声音包自动化与 DS918+ all-in-one 镜像导入验证。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为跨设备与外部服务验收。
- GREEN/验证证据：本机可执行项均有前序记录：后端 123 passed、前端 33 passed、生产构建通过、隔离 app/worker 运行正常、`linux/amd64` tar 已在临时 Docker context 成功 `docker load`。真机浏览器和真实 MiMo 未在本机伪造验证。
- 设计偏差：无。
- 遗留问题：需要用户在 HTTPS 部署入口完成 `docs/IOS-TEST-CHECKLIST.md` 的 iPhone Safari/PWA 与 iPad 竖横屏项目，并使用已授权声音和真实 MiMo Key 完成克隆试听、声音切换及 `.flvoice` 导入导出验收；完成后回传结果以解除阻塞。

### 2026-07-14 23:00（Asia/Shanghai）— Task 12 / Step 12.6 — partial local API diagnosis

- 完成内容：排查本机 `127.0.0.1:8001` 的词典 AI/TTS 配置未生效问题。停止两个遗留 API 进程后重启为单一监听进程；首次重启遗漏 `APP_DATA_DIR` 与 `APP_DATABASE_URL`，进程错误连接默认空库 `/data/app.db`，已立即以 `local-data` 和 `local-data/app.db` 显式重启。保留现有 worker，不读取或输出任何 API Key、密文、密码或音频内容。
- 修改文件：`backend/app/services/openai_chat.py`、`backend/tests/test_openai_chat.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：完整 Chat Completions URL 的回归测试在修正前失败，因为客户端把已完整的 `/chat/completions` 再次追加；此前本机 API 登录返回 `LOGIN_FAILED`，根因是空默认库中没有用户，而非已配置 AI 的鉴权结果。
- GREEN/验证证据：`python -m pytest backend/tests/test_openai_chat.py -q` 退出码 0（4 passed）；`python -m pytest backend/tests/test_ai_settings.py backend/tests/test_dictionary_api.py -q` 退出码 0（9 passed）。当前 API PID `15832` 仅监听 `127.0.0.1:8001`，worker PID `27676` 存活，均使用 `local-data/app.db`。实际 OpenCode 请求已使用完整 endpoint，稳定返回 `AI_AUTH_FAILED`；实际 MiMo TTS 请求成功接收非空音频，验证 TTS endpoint、已保存 Key、模型与声音配置可用。
- 设计偏差：无。AI 完整 endpoint 支持保持 OpenAI 兼容 base URL 的既有拼接行为；未将外部服务的 `AI_AUTH_FAILED` 伪装为本地配置成功。
- 遗留问题：在 OpenCode 控制台更新或重新填入有效 AI Key 后，使用 `admin` 账户完成受认证的 `/api/settings/ai/test` 与 `/api/dictionary/lookup` 验收；还需由 `admin` 密码或用户自行在 UI 创建并确认学习本，确认 worker 消费 `generate_tts` 任务。Task 12 / Step 12.6 的真机/HTTPS/已授权声音克隆验收仍未完成。

### 2026-07-14 23:08（Asia/Shanghai）— Task 12 / Step 12.6 — local service availability follow-up

- 完成内容：确认当前 API（PID `28452`）唯一监听 `127.0.0.1:8001`，worker（PID `27676`）仍存活。`GET /api/setup/status` 返回 `needs_initial_admin=false`，并且 `local-data/app.db` 现有 1 个用户，证明 API 当前连接的是已配置本地数据库而非空默认库。
- 修改文件：`scripts/run-local-api-8001.cmd`、`scripts/run-local-worker.cmd`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为运行态复核与启动脚本准备。尝试创建持久计划任务时，Windows `schtasks` 对含空格路径的参数引用失败，因此未把该尝试误记为已创建。
- GREEN/验证证据：`Get-NetTCPConnection -LocalPort 8001 -State Listen` 返回唯一 `127.0.0.1:8001` 监听；`GET /api/setup/status` 成功；`Get-Process -Id 27676` 成功。两个脚本均显式设置 `APP_DATA_DIR`、`APP_DATABASE_URL` 和 `APP_ENVIRONMENT`，供手动/后续受控启动使用。
- 设计偏差：无。
- 遗留问题：当前 API/worker 依赖现有运行进程；若它们退出，可在两个单独终端分别运行 `scripts/run-local-api-8001.cmd` 与 `scripts/run-local-worker.cmd`。仍需更新 OpenCode AI Key 并完成受认证 API、TTS 队列、桌面与真机验收；Task 12 / Step 12.6 继续 blocked。

### 2026-07-14 23:18（Asia/Shanghai）— Task 12 / Step 12.6 — local browser entry-point diagnosis

- 完成内容：修复本机浏览器入口。根因是 8001 仅运行后端 API 且未设置 `APP_FRONTEND_DIR`，所以访问 `/` 返回 404；开发 Vite 代理也错误指向 8000，而当前 API 使用 8001。启动脚本现显式指向 `frontend/dist`，并将开发代理统一到 8001。
- 修改文件：`frontend/vite.config.ts`、`frontend/vite.config.test.ts`、`frontend/local-launcher.test.ts`、`scripts/run-local-api-8001.cmd`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：访问 `http://127.0.0.1:8001/` 和日志均复现 404；`vite.config.test.ts` 在代理仍为 8000 时失败；`local-launcher.test.ts` 在启动脚本缺少 `APP_FRONTEND_DIR` 时失败。另有一次重启失败的直接错误为 Windows 将未正确双引号包裹的含空格脚本路径拆分为 `C:\\Users\\qihq\\Documents\\home`，已在正确引用后排除。
- GREEN/验证证据：`npm --workspace frontend test -- vite.config.test.ts local-launcher.test.ts --run` 退出码 0（2 passed）；`npm --workspace frontend run build` 退出码 0。当前 API PID `28376` 监听 `127.0.0.1:8001`，`GET /` 返回 200 且包含 `id=\"root\"` 应用壳，`GET /api/setup/status` 返回 200，worker PID `27676` 存活。
- 设计偏差：无。
- 遗留问题：用户可重新打开 `http://127.0.0.1:8001/`；若 API/worker 退出，按脚本重新启动。仍需更新 OpenCode AI Key 并完成受认证 API、TTS 队列、桌面与真机验收；Task 12 / Step 12.6 继续 blocked。

### 2026-07-14 23:25（Asia/Shanghai）— Task 12 / Step 12.6 — OpenCode dictionary AI compatibility diagnosis

- 完成内容：验证已保存 OpenCode Key 的真实请求路径、模型与请求字段，未读取或输出 Key。确认 Key、完整 `/v1/chat/completions` endpoint 与 `mimo-v2.5` 模型本身有效；阻断发生在应用强制发送 JSON mode 字段时。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：使用与应用完全相同的 `Authorization: Bearer`、endpoint、模型和 `response_format: {"type":"json_object"}` 请求，稳定获得 OpenCode HTTP 403 `Forbidden`，响应为 `error code: 1010`，在客户端被映射为误导性的 `AI_AUTH_FAILED`。
- GREEN/验证证据：移除仅 `response_format` 字段后，相同已保存 Key、endpoint 和模型返回 HTTP 200，响应包含 OpenAI 兼容的 `choices`、`usage` 等字段；词典提示词本身已明确要求返回单一 JSON，且 Pydantic 校验/修复路径仍可校验响应格式。
- 设计偏差：无。当前仅完成根因诊断，未在未经确认时改变通用 OpenAI 兼容客户端的 JSON mode 行为。
- 遗留问题：如要使 OpenCode 词典功能可用，需要以 TDD 调整客户端，让 JSON mode 成为可选项并对当前 OpenCode 配置关闭；随后使用 `admin` 受认证 API 实测 `/api/settings/ai/test` 和 `/api/dictionary/lookup`。Task 12 / Step 12.6 继续 blocked。

### 2026-07-14 23:45（Asia/Shanghai）— Task 12 / Step 12.6 — local OpenCode dictionary acceptance passed

- 完成内容：完成 OpenCode 词典 AI 的本机端到端验收并修复两个根因。第一，OpenCode 的边缘防护会拒绝未带 `User-Agent` 的请求（HTTP 403 / `error code: 1010`）；客户端现统一发送非敏感 `family-learning/0.1` 标识，继续使用 JSON mode。第二，词典提示词现内含精确响应 schema；随后发现 `local-data/app.db` 停在 revision `0007_learning_item_audio`，按既有 Alembic `0008_user_owned_voice_audio` 升级补齐 `dictionary_history.owner_user_id` 等归属列。
- 修改文件：`backend/app/services/openai_chat.py`、`backend/app/services/dictionary.py`、`backend/tests/test_openai_chat.py`、`backend/tests/test_dictionary.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`；本地数据 `local-data/app.db` 由 revision `0007_learning_item_audio` 升级至 `0008_user_owned_voice_audio`。
- RED 证据：`python -m pytest backend/tests/test_openai_chat.py -q` 在客户端缺少 `User-Agent` 时失败；`python -m pytest backend/tests/test_dictionary.py::test_dictionary_prompt_declares_the_exact_response_schema -q` 在提示词未声明字段时失败。外部单变量实测中，无 `User-Agent` 的相同 Key/endpoint/model 请求为 HTTP 403 `1010`，仅增加该头后为 HTTP 200；未提供 schema 的模型响应含 `word`、`definitions` 等不兼容字段，导致 `DICTIONARY_RESPONSE_INVALID`。真实首次词典调用的 500 trace 确认为缺少 `dictionary_history.owner_user_id`，而非 AI 返回错误。
- GREEN/验证证据：`python -m pytest backend/tests/test_dictionary.py::test_dictionary_prompt_declares_the_exact_response_schema backend/tests/test_dictionary.py backend/tests/test_openai_chat.py backend/tests/test_ai_settings.py backend/tests/test_dictionary_api.py -q` 退出码 0（22 passed）。`alembic upgrade head` 退出码 0，当前 revision 为 `0008_user_owned_voice_audio`，三个归属列已存在。使用本地 `admin/admin` 会话：`POST /api/settings/ai/test` 返回 `ok=true`、模型 `mimo-v2.5`、延迟 3952 ms；`POST /api/dictionary/lookup` 查询 `apple` 返回 200，包含 entry、英→中方向、1 个词性和 3 个示例。API 重启后仍监听 `127.0.0.1:8001`，worker 保持存活。
- 设计偏差：无。JSON mode 保持通用 OpenAI 兼容行为；仅补充标准 `User-Agent`，词典 schema 与 `DictionaryResult` 保持一致。数据库升级使用既有迁移，不手改 schema。
- 遗留问题：本机 OpenCode 辞典 AI 已验证；仍需用 `admin` 会话创建并确认学习本以验证 `generate_tts` worker 队列，以及完成桌面完整人工流程、HTTPS iPhone/iPad 与已授权真实 MiMo 声音克隆验收。Task 12 / Step 12.6 继续 blocked，复选框保持未勾选。

### 2026-07-14 23:58（Asia/Shanghai）— Task 12 / Step 12.6 — local MiMo TTS queue acceptance passed

- 完成内容：使用本地 `admin/admin` 会话创建并确认一个唯一时间戳学习本，端到端验证 `generate_tts` 入队、worker 消费、TTS 资产关联和音频落盘。验收前数据库基线为 1 个旧失败 `generate_tts` job、0 个 ready TTS 资产；本次结果仅按新 confirmed item 的 ID 关联，未把旧任务或缓存命中计入。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`；本地验收数据新增学习本 `c8232c2e-0f69-425a-a6d4-0ab2f4b2a4b5`、job `e7ba6230-aa1a-4c0b-8e99-cd93069a3938` 和 TTS 资产 `bc50ae40-5d4b-4453-8c26-c7aa72099939`。
- RED 证据：不适用；本步骤为真实 provider/worker 验收。基线中的旧 job `70aa9972-1205-4802-bb7c-5db88fe11409` 已是 `failed / JOB_PROCESSING_FAILED`，明确与本次唯一新任务隔离。
- GREEN/验证证据：新学习本 `TTS acceptance 20260714155711470` 状态为 `confirmed`；新 item `codexqueue20260714155711470` 产生的唯一 `generate_tts` job 状态为 `succeeded`、`attempts=1`、无错误码；item 已关联 ready 资产，provider `mimo`、model `mimo-v2.5-tts`、voice `Chloe`。音频文件存在于 `local-data/tts/en-US/4c/4cc108fe2faaaa166b580ead0222667a0397619215f00d309504e04a6f2cc3ce.wav`，大小 860204 字节。复核时 API 监听 `127.0.0.1:8001`，worker PID `27676` 仍在运行。
- 设计偏差：无。本次使用新词避免 TTS 缓存命中，并仅记录非敏感配置与资产元数据，未输出 Key 或音频内容。
- 遗留问题：本机 OpenCode 辞典 AI 与 MiMo 基础 TTS 队列均已端到端通过；仍需完成桌面浏览器完整人工流程、HTTPS iPhone/iPad 真机，以及已授权本人声音的真实 MiMo 声音克隆、切换和 `.flvoice` 导入导出复验。Task 12 / Step 12.6 继续 blocked，复选框保持未勾选。

### 2026-07-15 08:08（Asia/Shanghai）— Task 12 / Step 12.6 — local desktop service-worker regression fixed

- 完成内容：桌面验收首次加载发现 PWA Service Worker 请求被 SPA 回退路由返回为 HTML；已确保 `/service-worker.js` 返回 JavaScript，使浏览器能够正常注册该 Worker。
- 修改文件：`backend/app/main.py`、`backend/tests/test_spa.py`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`python -m pytest backend/tests/test_spa.py::test_application_serves_service_worker_as_javascript -q`；退出码 1，断言失败显示 `content-type` 为预期缺失行为的 `text/html; charset=utf-8`。
- GREEN/验证证据：`python -m pytest backend/tests/test_spa.py -q`；退出码 0，2 passed（仅第三方 `python_multipart` PendingDeprecationWarning）。
- 设计偏差：无。
- 遗留问题：重启本地 API 后复验浏览器注册无控制台错误，再继续桌面完整流程；HTTPS iPhone/iPad 真机及已授权本人声音的真实 MiMo 克隆仍为外部验收阻塞，Task 12 / Step 12.6 保持未勾选。

### 2026-07-15 08:28（Asia/Shanghai）— Task 12 / Step 12.6 — desktop browser acceptance passed

- 完成内容：使用本地 `admin` 验收会话完成桌面浏览器流程：登录、辞典查询 `apple`、标记不认识与生词本显示、混合单词/句子学习本、答案隐藏/揭示和家长人工评分、声音授权门槛，以及重启 API 后的 PWA 登录页复验。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为已实现功能的真实浏览器验收。前一项 Service Worker 修复的 RED 证据已单独记录于 2026-07-15 08:08。
- GREEN/验证证据：在 `http://127.0.0.1:8001/` 使用独立桌面浏览器会话登录后，辞典返回 `apple -> 苹果` 且显示缓存命中；点击“标记不认识”显示“已加入生词本”，生词本列出 `apple`；混合清单识别第 2 条为 `sentence`，默写先显示“答案已隐藏”，点击后先后显示 `apple` 与 `This is a sentence.` 并提供“正确/错误”；声音页“开始录制”在未勾选授权时禁用、勾选后启用。API 重启后，`GET /service-worker.js` 为 200、`application/javascript`，全新浏览器页登录界面正常且 `error/warn` 控制台日志为空。
- 设计偏差：无。验收库没有已授权使用人/声音版本，因此未试听或导出真实声音包，也未申请麦克风权限、上传声音或导入包。
- 遗留问题：iPhone Safari/PWA 与 iPad 竖屏/横屏仍需通过 HTTPS 真机验证；真实 MiMo 克隆、试听、切换和 `.flvoice` 导入导出仍需用户提供已授权本人声音和真实 MiMo Key。Task 12 / Step 12.6 继续 blocked，复选框保持未勾选。

### 2026-07-15 08:31（Asia/Shanghai）— Task 12 / Step 12.6 — post-desktop full regression passed

- 完成内容：在桌面验收与 Service Worker 修复后重新运行完整自动化验证，确认无回归。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本步骤为既有验收后的完整回归验证。
- GREEN/验证证据：`python -m pytest -q` 在 `backend/` 退出码 0（128 passed，1 个第三方 PendingDeprecationWarning）；`npm --workspace frontend test -- --run` 退出码 0（20 files、35 tests passed；输出含 jsdom 已知的 `Not implemented: navigation to another Document` 提示但无测试失败）；`npm --workspace frontend run build` 退出码 0；`docker compose -f deploy/compose.yaml config --quiet` 退出码 0。
- 设计偏差：无。
- 遗留问题：iPhone Safari/PWA 与 iPad 竖屏/横屏仍需通过 HTTPS 真机验证；真实 MiMo 克隆、试听、切换和 `.flvoice` 导入导出仍需用户提供已授权本人声音和真实 MiMo Key。Task 12 / Step 12.6 继续 blocked，复选框保持未勾选。

### 2026-07-15 08:31（Asia/Shanghai）— Task 12 / Step 12.6 — progress state corrected

- 完成内容：将进度摘要的历史遗留总体状态从 `not_started` 更正为与 Task 12 外部验收一致的 `blocked`。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：不适用；本项为进度元数据一致性校正。
- GREEN/验证证据：进度摘要显示 Task 1–11 complete、Task 12 为 5/6 且 blocked；实施计划 `12.6` 和所有最终完成条件保持未勾选。
- 设计偏差：无。
- 遗留问题：iPhone Safari/PWA 与 iPad 竖屏/横屏仍需通过 HTTPS 真机验证；真实 MiMo 克隆、试听、切换和 `.flvoice` 导入导出仍需用户提供已授权本人声音和真实 MiMo Key。Task 12 / Step 12.6 继续 blocked，复选框保持未勾选。

### 2026-07-15 08:40（Asia/Shanghai）— Task 12 / Step 12.6 — responsive preflight and mobile navigation fix

- 完成内容：响应式预检发现移动底栏截断了“设置”，使 iPhone 无法进入 AI 设置、声音管理和声音包入口；已让移动底栏保留完整六项导航，并在 390x844、834x1194、1194x834 尺寸复验辞典、设置和声音入口。
- 修改文件：`frontend/src/ui/AppShell.tsx`、`frontend/src/App.test.tsx`、`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：`npm --workspace frontend test -- App.test.tsx --run`；退出码 1，`keeps settings reachable from the mobile navigation` 在 `.bottom-nav` 中找不到“设置”，DOM 仅有“今天、辞典、学习本、视频库、统计”。首次未限定移动导航的测试错误命中桌面侧栏，已立即收紧且未据此实现。
- GREEN/验证证据：移除 `navigation.slice(0, 5)` 后，同一测试退出码 0（8 passed）。重新构建并重启本地 API 后：390x844 手机尺寸登录、辞典查询和“设置 -> 我的声音”均可达，控制台无 error/warn；834x1194 iPad 竖屏设置表单可用；1194x834 iPad 横屏辞典双栏查询与结果均可见，控制台无 error/warn。该预检不等同于 iPhone/iPad Safari HTTPS 真机验收。
- 设计偏差：无；此修复使“所有新增 UI 适配 iPhone、iPad 和桌面”约束在移动导航层面成立。
- 遗留问题：本机只有 HTTP 本地入口，设计已明确域名、证书和反向代理由用户维护；仍需在 HTTPS 的真实 iPhone Safari/PWA 和 iPad 竖横屏完成录音、播放和声音包验收。真实 MiMo 克隆、试听、切换和 `.flvoice` 导入导出仍需用户提供已授权本人声音和真实 MiMo Key。Task 12 / Step 12.6 继续 blocked，复选框保持未勾选。

### 2026-07-15 08:41（Asia/Shanghai）— Task 12 / Step 12.6 — mobile navigation regression passed

- 完成内容：完成移动导航修复后的全前端回归和生产构建验证。
- 修改文件：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- RED 证据：已记录于同一 Task 12.6 的 2026-07-15 08:40 条目。
- GREEN/验证证据：`npm --workspace frontend test -- --run` 退出码 0（20 files、36 tests passed；输出含 jsdom 已知的 `Not implemented: navigation to another Document` 提示但无测试失败）；`npm --workspace frontend run build` 退出码 0。
- 设计偏差：无。
- 遗留问题：本机只有 HTTP 本地入口，仍需在 HTTPS 的真实 iPhone Safari/PWA 和 iPad 竖横屏完成录音、播放和声音包验收。真实 MiMo 克隆、试听、切换和 `.flvoice` 导入导出仍需用户提供已授权本人声音和真实 MiMo Key。Task 12 / Step 12.6 继续 blocked，复选框保持未勾选。

## 最终验收矩阵

| 验收项 | 状态 | 证据 |
| --- | --- | --- |
| 后端完整测试 | passed | `python -m pytest -q`: 128 passed（2026-07-15 08:31 复验） |
| 前端完整测试 | passed | Vitest: 20 文件、36 项通过（2026-07-15 08:41 复验） |
| 前端生产构建 | passed | TypeScript 与 Vite 构建通过 |
| Alembic 旧库迁移 | passed | 隔离快照由新镜像升级，21 张表行数无变化 |
| 本地 Docker app/worker | passed | `family-learning-acceptance` 在临时数据目录和端口 18080 运行通过 |
| iPhone Safari/PWA | blocked | 需要 HTTPS 真机验收 |
| iPad 竖屏/横屏 | blocked | 需要真机验收 |
| 桌面浏览器 | passed | 本地 admin 桌面会话完成登录、辞典/生词本、混合句子默写、声音授权门槛；API 重启后 PWA 登录页无应用控制台错误 |
| 真实 MiMo 声音克隆 | blocked | 需要已授权声音和真实 MiMo Key |
| 加密声音包导入导出 | passed (automated) | 声音包 API 与前端交互测试已通过；真机复验待 12.6 |
| DS918+ all-in-one 镜像 | passed | `linux/amd64` tar、SHA-256、Compose 和临时 context 加载标签验证通过 |
