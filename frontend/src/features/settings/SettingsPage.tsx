import { FormEvent, useEffect, useState } from "react";
import { Button } from "../../ui/Button";
import { AiConfig, AiSettingsPanel } from "./AiSettingsPanel";
import {
  SpellingOcrConfig,
  SpellingOcrSettingsPanel,
} from "./SpellingOcrSettingsPanel";

export type TtsConfig = {
  protocol: "mimo" | "openai_compatible";
  base_url: string;
  model: string;
  voice: string;
  speed: number;
  pronunciation_source?: "configured" | "custom";
  voice_version_id?: string | null;
  api_key_configured: boolean;
  api_key_mask: string | null;
};
export type ReadyVoice = { id: string; display_name: string };
export type FailedTask = {
  id: string;
  type: string;
  entity_id: string;
  error_code: string | null;
};
type Props = {
  config: TtsConfig;
  readyVoices?: ReadyVoice[];
  onBackup: () => void;
  onSave: (value: TtsConfig & { api_key?: string }) => Promise<void>;
  aiConfig?: AiConfig;
  onSaveAi?: (value: AiConfig & { api_key?: string }) => Promise<void>;
  onTestAi?: () => Promise<{
    ok: boolean;
    display_name: string;
    model: string;
    latency_ms: number;
  }>;
  spellingOcrConfig?: SpellingOcrConfig;
  onSaveSpellingOcr?: (
    value: SpellingOcrConfig & { api_key?: string },
  ) => Promise<void>;
  onTestSpellingOcr?: () => Promise<{
    ok: boolean;
    model: string;
    latency_ms: number;
  }>;
  onOpenVoices?: () => void;
  failedTasks?: FailedTask[];
  onRetryTask?: (id: string) => Promise<void>;
};

export function SettingsPage({
  config,
  readyVoices = [],
  onBackup,
  onSave,
  aiConfig,
  onSaveAi,
  onTestAi,
  spellingOcrConfig,
  onSaveSpellingOcr,
  onTestSpellingOcr,
  onOpenVoices,
  failedTasks = [],
  onRetryTask,
}: Props) {
  const [form, setForm] = useState<TtsConfig & { api_key: string }>({
    ...config,
    api_key: "",
  });
  const [message, setMessage] = useState("");
  useEffect(() => setForm({ ...config, api_key: "" }), [config]);
  const update = (key: keyof typeof form, value: string | number) =>
    setForm((current) => ({ ...current, [key]: value }));
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await onSave(form);
      setForm((current) => ({ ...current, api_key: "" }));
      setMessage("语音配置已保存。");
    } catch {
      setMessage("保存失败，请检查接口地址和网络。");
    }
  };
  return (
    <section className="settings-page">
      <header>
        <p className="date">管理</p>
        <h1>家庭学习助手设置</h1>
      </header>
      <article>
        <h2>英语发音服务</h2>
        <p
          className={config.api_key_configured ? "configured" : "unconfigured"}
        >
          {config.api_key_configured ? "已配置" : "尚未配置"}
        </p>
        <p>API Key 加密保存在 NAS，保存后不会再次显示。</p>
        <form
          className="tts-settings-form"
          onSubmit={(event) => void submit(event)}
        >
          <label>
            默认发音来源
            <select
              aria-label="默认发音来源"
              value={form.pronunciation_source ?? "configured"}
              onChange={(event) =>
                update("pronunciation_source", event.target.value)
              }
            >
              <option value="configured">接口配置音色</option>
              <option value="custom" disabled={readyVoices.length === 0}>
                我的克隆声音
              </option>
            </select>
          </label>
          {form.pronunciation_source === "custom" && (
            <label>
              默认克隆声音
              <select
                aria-label="默认克隆声音"
                value={form.voice_version_id ?? ""}
                required
                onChange={(event) =>
                  update("voice_version_id", event.target.value)
                }
              >
                <option value="">请选择已就绪声音</option>
                {readyVoices.map((voice) => (
                  <option key={voice.id} value={voice.id}>
                    {voice.display_name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <p>
            该选择用于辞典和学习本默认发音；开始默写时仍可单独选择其他声音。
          </p>
          <label>
            接口协议
            <select
              aria-label="接口协议"
              value={form.protocol}
              onChange={(event) => update("protocol", event.target.value)}
            >
              <option value="mimo">MiMo TTS</option>
              <option value="openai_compatible">OpenAI 兼容 TTS</option>
            </select>
          </label>
          <label>
            接口地址
            <input
              value={form.base_url}
              type="url"
              required
              onChange={(event) => update("base_url", event.target.value)}
            />
          </label>
          <label>
            模型名称
            <input
              value={form.model}
              required
              onChange={(event) => update("model", event.target.value)}
            />
          </label>
          <label>
            音色
            <input
              value={form.voice}
              required
              onChange={(event) => update("voice", event.target.value)}
            />
          </label>
          <label>
            语速
            <input
              value={form.speed}
              type="number"
              min="0.5"
              max="2"
              step="0.1"
              required
              onChange={(event) => update("speed", Number(event.target.value))}
            />
          </label>
          <label>
            API Key
            <input
              aria-label="API Key"
              value={form.api_key}
              type="password"
              placeholder={config.api_key_mask ?? "输入新的 API Key"}
              onChange={(event) => update("api_key", event.target.value)}
            />
          </label>
          {config.api_key_mask && (
            <small>当前密钥：{config.api_key_mask}</small>
          )}
          <Button type="submit">保存语音配置</Button>
        </form>
        {message && <p role="status">{message}</p>}
      </article>
      {aiConfig && onSaveAi && onTestAi && (
        <AiSettingsPanel
          config={aiConfig}
          onSave={onSaveAi}
          onTest={onTestAi}
        />
      )}
      {spellingOcrConfig && onSaveSpellingOcr && onTestSpellingOcr && (
        <SpellingOcrSettingsPanel
          config={spellingOcrConfig}
          onSave={onSaveSpellingOcr}
          onTest={onTestSpellingOcr}
        />
      )}
      {onOpenVoices && (
        <article>
          <h2>我的声音</h2>
          <Button aria-label="打开我的声音管理" onClick={onOpenVoices}>
            管理我的声音
          </Button>
        </article>
      )}
      {failedTasks.length > 0 && (
        <article>
          <h2>失败任务</h2>
          {failedTasks.map((task) => (
            <p key={task.id}>
              {task.type}：{task.error_code ?? "REQUEST_FAILED"}{" "}
              {onRetryTask && (
                <Button onClick={() => void onRetryTask(task.id)}>重试</Button>
              )}
            </p>
          ))}
        </article>
      )}
      <article>
        <h2>数据备份</h2>
        <p>立即创建包含数据库、参考声音和密钥文件的备份。</p>
        <Button onClick={onBackup}>创建备份</Button>
      </article>
    </section>
  );
}
