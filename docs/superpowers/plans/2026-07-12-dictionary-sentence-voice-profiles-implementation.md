# 电子辞典、句子默写与多人声音档案实施计划

> **给开发模型：** 必须按任务顺序执行，并遵守本文“强制进度追踪协议”。每一个步骤完成后立即将 `[ ]` 改为 `[x]`，同时更新进度日志。不得仅在对话中声称完成。

**目标：** 在不破坏现有视频、单词本、默写历史和 TTS 的前提下，交付统一学习条目、句子默写、双向电子辞典、生词本、OpenCode Go 独立 AI 配置、多人 MiMo 声音克隆档案及密码加密导入导出。

**架构：** 保留现有 SQLite 物理表并通过 Alembic 增量迁移；业务层把单词升级为统一学习条目。辞典 AI、TTS 和声音档案使用独立配置与适配器，后台 worker 处理音频归一化、克隆试听和音频生成。

**技术栈：** Python 3.12、FastAPI、SQLAlchemy 2、Alembic、SQLite、Pydantic、FFmpeg/ffprobe、MiMo V2.5 TTS、OpenAI-compatible Chat API、React、TypeScript、Vite、Vitest、Docker Compose。

## 强制进度追踪协议

- 进度日志：`docs/superpowers/plans/2026-07-12-dictionary-sentence-voice-profiles-progress.md`。
- 执行任何代码操作前，先读取设计、本文和进度日志。
- 每完成一个步骤，立即把本文件对应 `[ ]` 改为 `[x]`，然后追加进度日志；不能批量补记。
- RED 测试步骤只有在测试因预期的缺失行为失败后才能勾选。
- GREEN 步骤只有在指定测试刚刚通过后才能勾选。
- 失败步骤保持 `[ ]`，进度日志写 `failed` 或 `blocked`、命令和错误摘要。
- 若实际实现必须偏离设计，先更新设计与本文并记录原因，再修改代码。
- 不得覆盖用户已有数据；迁移或部署前必须先创建并验证备份。
- 本工作区当前没有 Git，禁止伪造 commit；若之后初始化 Git，进度日志可附 commit hash。

## 全局约束

- UI 必须适配 iPhone、iPad 竖屏/横屏和桌面，触控目标至少 44px。
- 句子默写仍由家长揭示答案并人工判定，不做 OCR 自动评分。
- API Key、声音 Base64、导出密码不得出现在 GET 响应、日志或错误详情。
- AI 配置与 TTS 配置完全分离；模型名、接口地址和供应商显示名均可自定义。
- MiMo 克隆模型固定协议为 `mimo-v2.5-tts-voiceclone`，参考音频 Base64 后不超过 10 MB。
- 一个使用人可以有多个声音版本，但最多一个默认版本。
- 声音导出包必须使用 scrypt + AES-256-GCM；不得使用自制加密算法。
- 旧 `/api/word-lists` 和历史数据必须继续可用。
- 所有数据库变更必须通过 Alembic migration，不得依赖 `create_all()` 替代升级。

---

## Task 1：建立迁移安全网与统一学习条目

**文件：**

- 新建：`backend/alembic/versions/0002_learning_dictionary_voice_profiles.py`
- 新建：`backend/app/models/learning_item.py`
- 修改：`backend/app/models/word_list.py`
- 修改：`backend/app/models/dictation.py`
- 修改：`backend/app/models/__init__.py`
- 修改：`deploy/entrypoint.sh`
- 测试：`backend/tests/test_learning_item_migration.py`

**产出接口：**

```python
class LearningItem(Base):
    __tablename__ = "word_items"

def normalize_learning_text(text: str, source_language: str) -> str: ...
def infer_item_type(text: str, source_language: str) -> Literal["word", "phrase", "sentence"]: ...
```

- [x] **1.1 写迁移前后兼容失败测试**

```python
def test_existing_word_item_is_migrated_as_english_word(migrated_legacy_database):
    row = migrated_legacy_database.execute(
        text("select item_type, source_language, target_language from word_items limit 1")
    ).mappings().one()
    assert row == {"item_type": "word", "source_language": "en", "target_language": "zh"}

def test_sentence_normalization_preserves_punctuation():
    assert normalize_learning_text("  I   like apples.  ", "en") == "i like apples."
    assert infer_item_type("I like apples.", "en") == "sentence"
```

- [x] **1.2 运行 RED 验证**

运行：`python -m pytest backend/tests/test_learning_item_migration.py -q`

预期：因 migration、新字段或函数不存在而失败；在进度日志记录实际失败摘要。

- [x] **1.3 实现 SQLite batch migration**

Migration 必须：创建迁移前 SQLite 备份；给 `word_items` 增加 `item_type`、`source_language`、`target_language`、`translation_text`、`dictionary_entry_id`；给 `dictation_sessions` 增加声音选择与快照字段；给 `dictation_results` 增加 `item_type_snapshot`。旧记录回填为 `word/en/zh`，所有回填完成后再设置非空约束。

- [x] **1.4 实现统一领域模型与旧名兼容别名**

`LearningList`、`LearningListVersion`、`LearningItem` 映射现有物理表；旧模块导出 `WordList = LearningList` 等兼容别名。`display_text` 和 `normalized_text` 改为 `Text` 或至少支持 2,000 字符。

- [x] **1.5 修改容器入口执行真实迁移**

`entrypoint.sh` 在 app 和 worker 启动前运行 `alembic upgrade head`；失败时进程退出，不启动服务。不得用 `Base.metadata.create_all()` 冒充升级。

- [x] **1.6 运行 GREEN 与旧数据回归**

运行：

```text
python -m pytest backend/tests/test_learning_item_migration.py backend/tests/test_words.py backend/tests/test_dictation.py -q
```

预期：全部通过，并在进度日志记录通过数量。

---

## Task 2：学习列表 API 与句子默写

**文件：**

- 新建：`backend/app/api/learning_lists.py`
- 新建：`backend/app/services/learning_items.py`
- 修改：`backend/app/api/dictation.py`
- 修改：`backend/app/services/dictation.py`
- 修改：`backend/app/services/dictation_stats.py`
- 修改：`backend/app/main.py`
- 测试：`backend/tests/test_learning_lists.py`
- 测试：`backend/tests/test_sentence_dictation.py`

**产出接口：**

```python
def create_learning_list(session, child_id, title, items) -> LearningList: ...
def confirm_learning_list(session, list_id) -> LearningListVersion: ...
def start_dictation(session, child_id, learning_list_version_id, mode,
                    random_source, speaker_profile_id=None,
                    voice_version_id=None) -> DictationSession: ...
```

- [x] **2.1 写单词句子混排失败测试**

```python
def test_confirmed_list_preserves_word_and_sentence_types(session):
    draft = create_learning_list(session, child_id, "Week 1", [
        {"display_text": "apple", "item_type": "word", "source_language": "en", "target_language": "zh"},
        {"display_text": "I like apples.", "item_type": "sentence", "source_language": "en", "target_language": "zh"},
    ])
    version = confirm_learning_list(session, draft.id)
    assert [item.item_type for item in version.items] == ["word", "sentence"]
```

- [x] **2.2 写句子答案隐藏和人工评分失败测试**

```python
def test_sentence_answer_is_hidden_until_reveal(client, authenticated_parent, sentence_list_version):
    started = client.post("/api/dictation-sessions", json={
        "word_list_version_id": sentence_list_version.id,
        "mode": "ordered"
    }).json()
    assert "I like apples." not in str(started)
    revealed = client.post(
        f"/api/dictation-sessions/{started['id']}/results/{started['results'][0]['id']}/reveal"
    ).json()
    assert revealed["answer"] == "I like apples."
```

- [x] **2.3 运行 RED 验证**

运行：`python -m pytest backend/tests/test_learning_lists.py backend/tests/test_sentence_dictation.py -q`

- [x] **2.4 实现学习列表新 API 与旧 API 兼容**

新 API 使用 `/api/learning-lists`；旧 `/api/word-lists` 路由继续工作并委托同一 service。确认后的版本不可变，修改产生新版本。

- [x] **2.5 扩展默写会话和统计**

会话保存声音 ID 和名称快照；结果保存条目类型快照。统计返回总准确率以及 `word_accuracy`、`phrase_accuracy`、`sentence_accuracy`，分母只计算已评分结果。

- [x] **2.6 运行 GREEN 和完整默写回归**

运行：

```text
python -m pytest backend/tests/test_learning_lists.py backend/tests/test_sentence_dictation.py backend/tests/test_dictation_api.py backend/tests/test_dictation_stats.py -q
```

---

## Task 3：独立电子辞典 AI 配置

**文件：**

- 新建：`backend/app/models/ai_provider_config.py`
- 新建：`backend/app/services/ai_config.py`
- 新建：`backend/app/services/openai_chat.py`
- 修改：`backend/app/api/settings.py`
- 修改：`backend/app/models/__init__.py`
- 测试：`backend/tests/test_ai_settings.py`
- 测试：`backend/tests/test_openai_chat.py`

**配置响应：**

```json
{
  "protocol": "openai_chat_compatible",
  "display_name": "OpenCode Go",
  "base_url": "https://provider.example/v1",
  "model": "custom-model",
  "temperature": 0.1,
  "timeout_seconds": 45,
  "enabled": true,
  "api_key_configured": true,
  "api_key_mask": "********abcd"
}
```

- [x] **3.1 写密钥隔离和掩码失败测试**

```python
def test_ai_key_is_separate_from_tts_and_never_returned(client, auth):
    client.patch("/api/settings/ai", json={
        "protocol": "openai_chat_compatible", "display_name": "OpenCode Go",
        "base_url": "https://provider.example/v1", "api_key": "ai-secret-abcd",
        "model": "custom-model", "temperature": 0.1,
        "timeout_seconds": 45, "enabled": True
    })
    response = client.get("/api/settings/ai")
    assert "ai-secret-abcd" not in response.text
    assert response.json()["api_key_mask"] == "********abcd"
```

- [x] **3.2 写 OpenAI-compatible 请求失败测试**

断言 URL 为 `{base_url}/chat/completions`，Header 为 Bearer Key，请求启用 JSON 输出约束，且日志不包含 Key。

- [x] **3.3 运行 RED 验证**

运行：`python -m pytest backend/tests/test_ai_settings.py backend/tests/test_openai_chat.py -q`

- [x] **3.4 实现 AI 配置和密钥加密**

使用成熟加密库和 `/data` 中服务器密钥；若当前依赖缺失，先在 `pyproject.toml` 固定依赖并更新 Docker 构建，不得实现自制加密。空 API Key 表示保留旧密钥。

- [x] **3.5 实现连接测试**

`POST /api/settings/ai/test` 固定查询 `apple`，返回 `{ok, display_name, model, latency_ms}`。401/403 映射 `AI_AUTH_FAILED`，超时映射 `AI_TIMEOUT`，不得透传上游敏感响应。

- [x] **3.6 运行 GREEN**

运行：`python -m pytest backend/tests/test_ai_settings.py backend/tests/test_openai_chat.py -q`

---

## Task 4：双向电子辞典、结构化缓存与查询历史

**文件：**

- 新建：`backend/app/models/dictionary.py`
- 新建：`backend/app/schemas/dictionary.py`
- 新建：`backend/app/services/dictionary.py`
- 新建：`backend/app/api/dictionary.py`
- 修改：`backend/app/main.py`
- 测试：`backend/tests/test_dictionary.py`
- 测试：`backend/tests/test_dictionary_api.py`

**结构化类型：**

```python
class DictionaryResult(BaseModel):
    source_language: Literal["en", "zh"]
    target_language: Literal["en", "zh"]
    item_type: Literal["word", "phrase", "sentence"]
    source_text: str
    primary_translation: str
    phonetic: str | None
    parts_of_speech: list[PartOfSpeech]
    alternatives: list[str] = Field(max_length=3)
    examples: list[DictionaryExample] = Field(max_length=3)
    usage_note: str | None
```

- [x] **4.1 写语言方向和 schema 失败测试**

```python
@pytest.mark.parametrize(("text", "source", "target"), [
    ("apple", "en", "zh"),
    ("我喜欢苹果。", "zh", "en"),
])
def test_auto_detects_dictionary_direction(text, source, target):
    assert detect_direction(text) == (source, target)
```

- [x] **4.2 写缓存失败测试**

同一规范化输入、方向、provider fingerprint 和 prompt version 查询两次，fake AI 只能调用一次；模型变化后必须再次调用。

- [x] **4.3 运行 RED 验证**

运行：`python -m pytest backend/tests/test_dictionary.py backend/tests/test_dictionary_api.py -q`

- [x] **4.4 实现安全提示词和一次格式修复重试**

用户文本作为 JSON 数据字段放入 user message；system message 明确忽略查询文本中的指令并只返回 schema。第一次 Pydantic 校验失败后允许一次只修 JSON 的重试；再失败返回 `DICTIONARY_RESPONSE_INVALID`。

- [x] **4.5 实现缓存、历史与删除语义**

缓存按孩子隔离查询历史，但同一家庭可复用无个人信息的结构化结果；删除历史不删除生词记录。游标分页稳定按 `created_at,id` 排序。

- [x] **4.6 运行 GREEN**

运行：`python -m pytest backend/tests/test_dictionary.py backend/tests/test_dictionary_api.py -q`

---

## Task 5：生词本与复习列表

**文件：**

- 新建：`backend/app/models/unknown_item.py`
- 新建：`backend/app/services/unknown_items.py`
- 新建：`backend/app/api/unknown_items.py`
- 修改：`backend/app/main.py`
- 测试：`backend/tests/test_unknown_items.py`

- [x] **5.1 写幂等标记和掌握状态失败测试**

```python
def test_marking_same_dictionary_entry_unknown_twice_is_idempotent(session, entry):
    first = mark_unknown(session, child_id, entry.id)
    second = mark_unknown(session, child_id, entry.id)
    assert first.id == second.id
    assert count_active_unknown(session, child_id, "apple") == 1
```

- [x] **5.2 写生词生成混合学习列表失败测试**

选择一个单词和一个句子生成草稿列表，断言类型、翻译快照和顺序保留，原生词状态不被改变。

- [x] **5.3 运行 RED 验证**

运行：`python -m pytest backend/tests/test_unknown_items.py -q`

- [x] **5.4 实现生词 API 与唯一约束**

同一孩子、方向和规范化文本只有一条活跃记录；支持 `unknown/mastered`、类型筛选、时间/错误次数排序。

- [x] **5.5 实现复习列表创建**

`POST /api/learning-lists/from-unknown-items` 创建新草稿，不修改辞典缓存、历史列表版本或生词状态。

- [x] **5.6 运行 GREEN 与旧错词回归**

运行：`python -m pytest backend/tests/test_unknown_items.py backend/tests/test_dictation_stats.py -q`

---

## Task 6：使用人与多声音版本领域模型

**文件：**

- 新建：`backend/app/models/speaker.py`
- 新建：`backend/app/services/speakers.py`
- 新建：`backend/app/api/speakers.py`
- 修改：`backend/app/models/tts_asset.py`
- 修改：`backend/app/models/__init__.py`
- 修改：`backend/app/main.py`
- 测试：`backend/tests/test_speakers.py`

- [x] **6.1 写“每人一个默认声音”失败测试**

```python
def test_making_voice_default_unsets_previous_default(session, speaker, two_ready_voices):
    make_default(session, speaker.id, two_ready_voices[0].id)
    make_default(session, speaker.id, two_ready_voices[1].id)
    assert get_speaker(session, speaker.id).default_voice_version_id == two_ready_voices[1].id
```

- [x] **6.2 写历史引用软删除失败测试**

被默写会话引用的声音版本只能标记 `disabled`，不能物理删除；历史名称快照保持不变。

- [x] **6.3 运行 RED 验证**

运行：`python -m pytest backend/tests/test_speakers.py -q`

- [x] **6.4 实现使用人和声音版本 API**

UUID、名称、备注、颜色、active、默认声音；声音版本含 provider/model/reference metadata/style/status/failure code。所有资源必须认证并按家庭作用域访问。

- [x] **6.5 实现多声音音频缓存关系**

创建 `learning_item_audio`，fingerprint 包含参考 WAV SHA-256，确保更换参考声音后不会复用旧音频。

- [x] **6.6 运行 GREEN**

运行：`python -m pytest backend/tests/test_speakers.py backend/tests/test_tts.py -q`

---

## Task 7：MiMo 声音录制、归一化、克隆试听和任意文本发音

**文件：**

- 新建：`backend/app/services/voice_samples.py`
- 新建：`backend/app/services/mimo_voice_clone.py`
- 新建：`backend/app/workers/voice.py`
- 修改：`backend/app/workers/runner.py`
- 修改：`backend/app/workers/tts.py`
- 修改：`backend/app/api/speakers.py`
- 修改：`backend/app/api/dictionary.py`
- 测试：`backend/tests/test_voice_samples.py`
- 测试：`backend/tests/test_mimo_voice_clone.py`

- [x] **7.1 写音频验证失败测试**

覆盖 WAV/MP3 成功、视频容器去视频轨、短于 3 秒、长于 30 秒、无音频流和 Base64 超过 10 MB。

- [x] **7.2 写 MiMo 官方 payload 失败测试**

```python
def test_voice_clone_sends_reference_audio_as_data_uri(fake_urlopen, wav_sample):
    client = MimoVoiceCloneClient(...)
    client.synthesize("apple", wav_sample, "Read clearly")
    payload = fake_urlopen.json_body
    assert payload["model"] == "mimo-v2.5-tts-voiceclone"
    assert payload["audio"]["voice"].startswith("data:audio/wav;base64,")
```

- [x] **7.3 运行 RED 验证**

运行：`python -m pytest backend/tests/test_voice_samples.py backend/tests/test_mimo_voice_clone.py -q`

- [x] **7.4 实现 multipart 上传、授权同意和后台归一化**

请求必须含 `consent_confirmed=true`；否则 `VOICE_CONSENT_REQUIRED`。随机文件名保存，Worker 用 FFmpeg 生成 24 kHz mono PCM WAV，ffprobe 验证后原子提升。

- [x] **7.5 实现克隆试听和任意文本 TTS**

归一化成功后用固定英文测试句生成试听。辞典和默写选择声音版本时，通过相同适配器生成 WAV；429/5xx/超时退避重试，401/403 和非法样本不重试。

- [x] **7.6 运行 GREEN 与真实 Key 手工验收记录**

自动测试：`python -m pytest backend/tests/test_voice_samples.py backend/tests/test_mimo_voice_clone.py backend/tests/test_tts.py -q`

若环境配置了真实 MiMo Key，再在进度日志记录人工试听结果；没有 Key 时明确标记该手工项为待 NAS 验收，不能伪造通过。

---

## Task 8：密码加密的声音档案导入导出

**文件：**

- 新建：`backend/app/services/voice_packages.py`
- 新建：`backend/app/api/voice_packages.py`
- 修改：`backend/app/main.py`
- 修改：`backend/pyproject.toml`
- 测试：`backend/tests/test_voice_packages.py`
- 测试：`backend/tests/test_voice_package_api.py`

**加密接口：**

```python
def export_voice_package(session, speaker_id: str, voice_version_ids: list[str], password: str) -> Path: ...
def inspect_voice_package(upload: BinaryIO, password: str) -> VoicePackagePreview: ...
def import_voice_package(session, import_id: str,
                         strategy: Literal["merge", "replace_profile_metadata", "create_new"]): ...
```

- [x] **8.1 添加并固定成熟密码学依赖**

使用支持 scrypt 和 AESGCM 的成熟库；更新 lock/build 文件。禁止标准库 XOR、自制 stream cipher 或 OpenSSL shell 拼接密码。

- [x] **8.2 写加密、错误密码和篡改失败测试**

正确密码往返后 manifest/audio 完全一致；错误密码和修改任意 ciphertext 字节都返回 `VOICE_PACKAGE_PASSWORD_INVALID`，且不产生数据库记录。

- [x] **8.3 写 ZIP 路径穿越和冲突策略失败测试**

拒绝 `../escape.wav`、绝对路径、超量文件、SHA 不符；验证 merge 幂等、同 ID 不同哈希冲突、create_new 重映射全部 ID。

- [x] **8.4 运行 RED 验证**

运行：`python -m pytest backend/tests/test_voice_packages.py backend/tests/test_voice_package_api.py -q`

- [x] **8.5 实现 FLVOICE1 格式与临时文件清理**

scrypt 参数严格为 `N=2^15,r=8,p=1`，AES-256-GCM nonce 12 bytes；header 不含个人信息；finally 清除临时明文。导出包不得包含 API Key 或 TTS 缓存。

- [x] **8.6 实现 inspect/commit 两阶段导入**

inspect 只返回预览和冲突，不写业务表；commit 必须显式策略。临时导入记录设过期时间，worker 定期清理。

- [x] **8.7 运行 GREEN 与安全回归**

运行：`python -m pytest backend/tests/test_voice_packages.py backend/tests/test_voice_package_api.py -q`

---

## Task 9：前端 AI 设置、辞典和生词本（三端）

**文件：**

- 新建：`frontend/src/features/settings/AiSettingsPanel.tsx`
- 新建：`frontend/src/features/dictionary/DictionaryPage.tsx`
- 新建：`frontend/src/features/dictionary/DictionaryResultCard.tsx`
- 新建：`frontend/src/features/dictionary/UnknownItemsPage.tsx`
- 修改：`frontend/src/features/settings/SettingsPage.tsx`
- 修改：`frontend/src/App.tsx`
- 修改：`frontend/src/ui/AppShell.tsx`
- 修改：`frontend/src/styles.css`
- 测试：`frontend/src/features/settings/AiSettingsPanel.test.tsx`
- 测试：`frontend/src/features/dictionary/DictionaryPage.test.tsx`

- [x] **9.1 写 AI 设置密钥不回显失败测试**

```tsx
it('never fills the saved AI key back into the password input', () => {
  render(<AiSettingsPanel config={configuredAi} />)
  expect(screen.getByLabelText('AI API Key')).toHaveValue('')
  expect(screen.getByText('********abcd')).toBeVisible()
})
```

- [x] **9.2 写双向查询、播放和标记失败测试**

测试自动方向、手动中译英、结果结构、播放按钮、标记不认识以及缓存结果标识；不测试 CSS 实现细节。

- [x] **9.3 运行 RED 验证**

运行：`npm --workspace frontend test -- AiSettingsPanel.test.tsx DictionaryPage.test.tsx --run`

- [x] **9.4 实现 AI 设置和辞典页面**

Key 输入为空表示保留；测试连接显示稳定状态。辞典输入最大 2,000 字符，结果标注“AI 生成，请家长核对”，英文文本可选择声音并播放。

- [x] **9.5 实现生词本页面**

支持类型/状态筛选、标记掌握、恢复不认识、多选创建学习列表。iPhone 单列且主操作在 safe-area 上方；iPad 双栏；桌面最多三栏。

- [x] **9.6 运行 GREEN、构建和三宽度视觉检查**

运行：

```text
npm --workspace frontend test -- AiSettingsPanel.test.tsx DictionaryPage.test.tsx --run
npm --workspace frontend run build
```

记录 390px、834px、1194px、1440px 四个宽度的截图或浏览器检查结果。

---

## Task 10：前端学习本、句子默写和声音管理（三端）

**文件：**

- 新建：`frontend/src/features/voices/SpeakerProfilesPage.tsx`
- 新建：`frontend/src/features/voices/VoiceRecorder.tsx`
- 新建：`frontend/src/features/voices/VoicePackageDialog.tsx`
- 修改：`frontend/src/features/words/WordListEditor.tsx`
- 修改：`frontend/src/features/dictation/DictationPage.tsx`
- 修改：`frontend/src/features/settings/SettingsPage.tsx`
- 修改：`frontend/src/App.tsx`
- 修改：`frontend/src/styles.css`
- 测试：`frontend/src/features/voices/SpeakerProfilesPage.test.tsx`
- 测试：`frontend/src/features/voices/VoicePackageDialog.test.tsx`
- 测试：`frontend/src/features/dictation/SentenceDictationPage.test.tsx`

- [x] **10.1 写声音授权、录制和默认版本失败测试**

未勾选授权时提交按钮禁用；ready 声音可试听和设默认；每人只有一个默认标识。

- [x] **10.2 写加密导出导入交互失败测试**

导出要求两次密码一致；明确显示“不包含 API Key”；导入先预览后选择 merge/replace/create_new，不允许直接覆盖。

- [x] **10.3 写句子默写隐藏答案失败测试**

句子在 reveal 前不出现；播放后不自动前进；人工评分后才允许下一项。

- [x] **10.4 运行 RED 验证**

运行：`npm --workspace frontend test -- SpeakerProfilesPage.test.tsx VoicePackageDialog.test.tsx SentenceDictationPage.test.tsx --run`

- [x] **10.5 实现学习本类型编辑和声音管理**

“单词本”升级文案为“学习本”；允许条目类型和翻译编辑。声音录制 8–30 秒，显示计时/音量/重录；上传离开页面后可恢复任务状态。

- [x] **10.6 实现默写声音切换和历史快照展示**

开始前选择使用人/版本；会话中可播放但不允许无提示切换已保存的会话声音；历史显示当时名称快照。

- [x] **10.7 运行 GREEN、全前端测试与构建**

运行：

```text
npm --workspace frontend test -- --run
npm --workspace frontend run build
```

---

## Task 11：统计、管理、备份与安全收尾

**文件：**

- 修改：`backend/app/services/dictation_stats.py`
- 修改：`backend/app/api/stats.py`
- 修改：`backend/app/services/backups.py`
- 修改：`frontend/src/features/stats/DictationStatsPage.tsx`
- 修改：`frontend/src/features/settings/SettingsPage.tsx`
- 测试：`backend/tests/test_extended_stats.py`
- 测试：`backend/tests/test_voice_security.py`

- [x] **11.1 写扩展统计失败测试**

准确率按已评分条目聚合，不平均会话百分比；返回三类准确率、生词本周新增/掌握和辞典缓存命中数。

- [x] **11.2 写认证、日志和文件访问安全失败测试**

未登录访问配置、参考音频、导出包均 401；日志捕获中不能出现 Key、密码和 Base64 前缀；声音文件不能通过静态 URL 访问。

- [x] **11.3 运行 RED 验证**

运行：`python -m pytest backend/tests/test_extended_stats.py backend/tests/test_voice_security.py -q`

- [x] **11.4 实现统计和管理任务状态**

设置页显示声音/AI 失败任务和重试入口；备份包含数据库、参考声音和加密密钥文件，恢复文档说明三者必须成套恢复。

- [x] **11.5 运行 GREEN 和完整后端套件**

运行：`python -m pytest -q`

---

## Task 12：文档、迁移演练、群晖部署和 all-in-one 镜像

**文件：**

- 修改：`docs/DEPLOYMENT.md`
- 修改：`docs/IOS-TEST-CHECKLIST.md`
- 新建：`docs/VOICE-PRIVACY-AND-BACKUP.md`
- 修改：`deploy/Dockerfile`
- 修改：`deploy/compose.yaml`
- 修改：`deploy/entrypoint.sh`

- [x] **12.1 更新部署和隐私文档**

写明 DS918+ `/data` 映射、迁移前备份、AI/TTS 配置、声音隐私、25/50 MB 反代限制、`.flvoice` 密码不可恢复、多人声音切换和恢复步骤。

- [x] **12.2 执行旧数据库迁移演练**

复制本地现有 `/data/app.db` 到临时目录，运行新镜像升级；验证旧视频、单词本、默写历史、TTS 配置数量不变；记录迁移前后表行数。

- [x] **12.3 运行全部自动验证**

```text
python -m pytest -q
npm --workspace frontend test -- --run
npm --workspace frontend run build
docker compose -f deploy/compose.yaml config --quiet
```

每条命令必须单独记录退出码和通过数量。

- [x] **12.4 本地 Docker 部署验收**

使用独立 `family-learning` 项目名和未占用端口启动 app/worker；验证 `/api/setup/status`、登录、AI 设置、辞典查询、声音上传任务、学习本和统计。不得用其他项目容器冒充本项目。

- [x] **12.5 构建并导出 DS918+ all-in-one 镜像**

镜像必须是 `linux/amd64`。群晖单容器发布变体在一个容器内启动 app/worker；开发部署可保留同一镜像通过不同 command 拆分启动的模式。输出 tar、SHA-256、Compose 文件和版本说明。使用临时 Docker context 执行一次 `docker load` 验证标签。

- [ ] **12.6 完成真机验收矩阵**

iPhone Safari/PWA、iPad 竖/横屏、桌面分别验证辞典、播放、标记、句子默写、录音、声音试听、加密导入导出；真实 MiMo 克隆必须由已授权的本人声音完成。

---

## 最终完成条件

以下全部成立才能在进度日志将项目标记为 `complete`：

- [ ] 所有 Task 1–12 步骤均已逐项勾选并附证据。
- [ ] 后端完整测试刚刚通过。
- [ ] 前端完整测试与生产构建刚刚通过。
- [ ] Alembic 旧数据库迁移演练通过且备份可读。
- [ ] 本地 app/worker 容器运行正常。
- [ ] iPhone、iPad、桌面验收矩阵完成。
- [ ] 真实 MiMo 声音克隆试听完成，或明确记录为唯一外部 Key 阻塞项。
- [ ] DS918+ all-in-one tar 与 SHA-256 已生成并验证可导入。
