import { FormEvent, useEffect, useState } from 'react'
import { Button } from '../../ui/Button'

export type AiConfig = {
  protocol: 'openai_chat_compatible'
  display_name: string
  base_url: string | null
  model: string | null
  temperature: number
  timeout_seconds: number
  enabled: boolean
  api_key_configured: boolean
  api_key_mask: string | null
}

export function AiSettingsPanel({ config, onSave, onTest }: {
  config: AiConfig
  onSave: (value: AiConfig & { api_key?: string }) => Promise<void>
  onTest: () => Promise<{ ok: boolean; display_name: string; model: string; latency_ms: number }>
}) {
  const [form, setForm] = useState<AiConfig & { api_key: string }>({ ...config, api_key: '' })
  const [message, setMessage] = useState('')
  useEffect(() => setForm({ ...config, api_key: '' }), [config])
  const update = (key: keyof typeof form, value: string | number | boolean) => setForm(current => ({ ...current, [key]: value }))
  const save = async (event: FormEvent) => {
    event.preventDefault()
    try { await onSave(form); setForm(current => ({ ...current, api_key: '' })); setMessage('电子辞典 AI 配置已保存。') }
    catch { setMessage('保存失败，请检查接口地址和网络。') }
  }
  const test = async () => {
    try { const result = await onTest(); setMessage(`${result.display_name} / ${result.model} 连接成功（${result.latency_ms} ms）。`) }
    catch { setMessage('连接测试失败，请检查配置。') }
  }
  return <article className="ai-settings-panel"><h2>电子辞典 AI</h2><p>密钥加密保存于 NAS，保存后不会再次显示。</p><form onSubmit={event => void save(event)}><label>服务名称<input value={form.display_name} onChange={event => update('display_name', event.target.value)} required /></label><label>接口地址<input type="url" value={form.base_url ?? ''} onChange={event => update('base_url', event.target.value)} required /></label><label>模型名称<input value={form.model ?? ''} onChange={event => update('model', event.target.value)} required /></label><label>AI API Key<input aria-label="AI API Key" type="password" value={form.api_key} placeholder={config.api_key_mask ?? '输入新的 AI API Key'} autoComplete="new-password" onChange={event => update('api_key', event.target.value)} /></label>{config.api_key_mask && <small>{config.api_key_mask}</small>}<label>温度<input type="number" min="0" max="1" step="0.1" value={form.temperature} onChange={event => update('temperature', Number(event.target.value))} /></label><label>超时（秒）<input type="number" min="10" max="120" value={form.timeout_seconds} onChange={event => update('timeout_seconds', Number(event.target.value))} /></label><label><input type="checkbox" checked={form.enabled} onChange={event => update('enabled', event.target.checked)} /> 启用电子辞典 AI</label><div className="form-actions"><Button type="submit">保存 AI 配置</Button><Button type="button" onClick={() => void test()}>测试连接</Button></div></form>{message && <p role="status">{message}</p>}</article>
}
