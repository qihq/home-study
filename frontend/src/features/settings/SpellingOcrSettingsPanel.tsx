import { FormEvent, useEffect, useState } from 'react'
import { Button } from '../../ui/Button'

export type SpellingOcrConfig = { source: 'dictionary' | 'separate'; protocol: 'openai_chat_compatible'; display_name: string; base_url: string | null; model: string | null; temperature: number; timeout_seconds: number; enabled: boolean; api_key_configured: boolean; api_key_mask: string | null }

export function SpellingOcrSettingsPanel({ config, onSave, onTest }: { config: SpellingOcrConfig; onSave: (value: SpellingOcrConfig & { api_key?: string }) => Promise<void>; onTest: () => Promise<{ ok: boolean; model: string; latency_ms: number }> }) {
  const [form, setForm] = useState<SpellingOcrConfig & { api_key: string }>({ ...config, api_key: '' })
  const [message, setMessage] = useState('')
  useEffect(() => setForm({ ...config, api_key: '' }), [config])
  const update = (key: keyof typeof form, value: string | boolean) => setForm(current => ({ ...current, [key]: value }))
  const save = async (event: FormEvent) => { event.preventDefault(); try { await onSave(form); setMessage('拼写图片识别 AI 配置已保存。') } catch { setMessage('保存失败，请检查配置。') } }
  const test = async () => { try { const result = await onTest(); setMessage(`${result.model} 连接成功（${result.latency_ms} ms）。`) } catch { setMessage('连接测试失败，请确认模型支持图片识别。') } }
  return <article className="ai-settings-panel"><h2>拼写图片识别 AI</h2><p>图片会发送给这里选择的云端 AI；模型必须支持图片输入。</p><form onSubmit={event => void save(event)}><label>配置来源<select aria-label="OCR 配置来源" value={form.source} onChange={event => update('source', event.target.value)}><option value="dictionary">使用已配置的电子词典 AI</option><option value="separate">使用单独的识别 AI</option></select></label>{form.source === 'separate' && <><label>服务名称<input value={form.display_name} onChange={event => update('display_name', event.target.value)} required /></label><label>接口地址<input type="url" value={form.base_url ?? ''} onChange={event => update('base_url', event.target.value)} required /></label><label>视觉模型名称<input value={form.model ?? ''} onChange={event => update('model', event.target.value)} required /></label><label>识别 AI API Key<input aria-label="识别 AI API Key" type="password" value={form.api_key} placeholder={config.api_key_mask ?? '输入新的 API Key'} onChange={event => update('api_key', event.target.value)} /></label><label><input type="checkbox" checked={form.enabled} onChange={event => update('enabled', event.target.checked)} /> 启用单独的识别 AI</label></>}<div className="form-actions"><Button type="submit">保存识别 AI 配置</Button><Button type="button" onClick={() => void test()}>测试连接</Button></div></form>{message && <p role="status">{message}</p>}</article>
}
