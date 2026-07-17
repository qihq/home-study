import { ChangeEvent, useState } from 'react'

export function VoicePackageDialog({ onExport, onInspect, onCommit }: {
  onExport: (password: string) => void
  onInspect: (file: File, password: string) => Promise<{ import_id: string; conflicts: Array<{ speaker_profile_id: string }> }>
  onCommit: (value: { import_id: string; strategy: 'merge' | 'replace_profile_metadata' | 'create_new' }) => void
}) {
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [importPassword, setImportPassword] = useState('')
  const [preview, setPreview] = useState<{ import_id: string; conflicts: Array<{ speaker_profile_id: string }> } | null>(null)
  const [strategy, setStrategy] = useState<'merge' | 'replace_profile_metadata' | 'create_new' | ''>('')
  const inspect = async () => { if (file) setPreview(await onInspect(file, importPassword)) }
  return <section className="voice-package-dialog"><h2>导入和导出声音包</h2><p>不包含 API Key</p><label>导出密码<input aria-label="导出密码" type="password" value={password} onChange={event => setPassword(event.target.value)} /></label><label>再次输入密码<input aria-label="再次输入密码" type="password" value={confirmation} onChange={event => setConfirmation(event.target.value)} /></label><button disabled={!password || password !== confirmation} onClick={() => onExport(password)}>导出声音包</button><hr /><label>导入声音包<input aria-label="导入声音包" type="file" accept=".flvoice" onChange={(event: ChangeEvent<HTMLInputElement>) => setFile(event.target.files?.[0] ?? null)} /></label><label>导入密码<input aria-label="导入密码" type="password" value={importPassword} onChange={event => setImportPassword(event.target.value)} /></label><button disabled={!file || !importPassword} onClick={() => void inspect()}>预览导入</button>{preview && <div><p>发现 {preview.conflicts.length} 个冲突</p><label>冲突处理方式<select aria-label="冲突处理方式" value={strategy} onChange={event => setStrategy(event.target.value as typeof strategy)}><option value="">选择处理方式</option><option value="merge">合并</option><option value="replace_profile_metadata">更新资料并合并</option><option value="create_new">新建使用人</option></select></label>{strategy && <button onClick={() => onCommit({ import_id: preview.import_id, strategy })}>完成导入</button>}</div>}</section>
}
