import { ChangeEvent, useEffect, useState } from 'react'
import { VoiceRecorder } from './VoiceRecorder'

export type VoiceVersionView = { id: string; display_name: string; status: 'processing' | 'ready' | 'failed'; is_default: boolean; progress?: number; failure_code?: string | null }
export type SpeakerProfileView = { id: string; display_name: string; default_voice_version_id: string | null; versions: VoiceVersionView[] }
const statusLabels = { processing: '处理中', ready: '已就绪', failed: '处理失败' }

type Props = {
  profiles: SpeakerProfileView[]
  workerOnline?: boolean
  onPreview: (voiceId: string) => void
  onMakeDefault: (voiceId: string) => Promise<void>
  onOpenPackage?: (speakerId: string) => void
  onRecorded?: (speakerId: string, audio: Blob) => Promise<void>
  onRenameVoice?: (voiceId: string, name: string) => Promise<void>
  onDeleteVoice?: (voiceId: string) => Promise<void>
  onDeleteSpeaker?: (speakerId: string) => Promise<void>
}

export function SpeakerProfilesPage({ profiles, workerOnline = true, onPreview, onMakeDefault, onOpenPackage, onRecorded, onRenameVoice, onDeleteVoice, onDeleteSpeaker }: Props) {
  const [defaults, setDefaults] = useState(() => new Map(profiles.map(profile => [profile.id, profile.default_voice_version_id])))
  const [message, setMessage] = useState('')
  useEffect(() => setDefaults(new Map(profiles.map(profile => [profile.id, profile.default_voice_version_id]))), [profiles])
  const makeDefault = async (profileId: string, voiceId: string) => { await onMakeDefault(voiceId); setDefaults(current => new Map(current).set(profileId, voiceId)) }
  const upload = async (event: ChangeEvent<HTMLInputElement>) => { const file = event.target.files?.[0]; if (!file || !profiles[0] || !onRecorded) return; try { setMessage('声音样本已提交，正在处理…'); await onRecorded(profiles[0].id, file); setMessage('已提交。列表会自动显示处理进度。') } catch { setMessage('上传失败，请检查网络后重试。') } }
  const rename = async (version: VoiceVersionView) => { const name = window.prompt('声音名称', version.display_name); if (name?.trim()) await onRenameVoice?.(version.id, name.trim()) }
  const removeVoice = async (version: VoiceVersionView) => { if (window.confirm(`删除声音“${version.display_name}”吗？`)) await onDeleteVoice?.(version.id) }
  const removeSpeaker = async (profile: SpeakerProfileView) => { if (window.confirm(`删除声音档案“${profile.display_name}”及其全部声音吗？`)) await onDeleteSpeaker?.(profile.id) }
  const hasPendingWork = profiles.some(profile => profile.versions.some(version => version.status === 'processing'))

  return <section className="speaker-profiles-page">
    <header><h1>我的声音</h1><p>录制或上传已获授权的声音样本，用于朗读和默写。</p></header>
    {!workerOnline && hasPendingWork && <p role="alert">后台处理服务离线，克隆声音进度已暂停。重启最新容器后会继续。</p>}
    <VoiceRecorder onRecorded={audio => profiles[0] && onRecorded ? onRecorded(profiles[0].id, audio) : undefined} />
    <label>上传声音样本<input aria-label="上传声音样本" type="file" accept="audio/*" onChange={event => void upload(event)} /></label>
    {message && <p role="status">{message}</p>}
    <div className="speaker-profile-grid">{profiles.map(profile => <article key={profile.id}>
      <h2>{profile.display_name}</h2>
      <div className="list-actions">{onOpenPackage && <button onClick={() => onOpenPackage(profile.id)}>导入或导出声音包 {profile.display_name}</button>}<button onClick={() => void removeSpeaker(profile)}>删除档案</button></div>
      {profile.versions.length === 0 && <p>暂无声音版本。录制或上传后会显示在这里。</p>}
      {profile.versions.map(version => <div className="voice-version" key={version.id}>
        <strong>{version.display_name}</strong>
        <span>{statusLabels[version.status]}{version.status === 'processing' ? `：${version.progress ?? 0}%` : ''}{version.failure_code ? `（${version.failure_code}）` : ''}</span>
        {version.status === 'processing' && <progress max="100" value={version.progress ?? 0} aria-label={`${version.display_name} 处理进度`} />}
        {defaults.get(profile.id) === version.id && <em>默认声音</em>}
        <div className="list-actions"><button onClick={() => void rename(version)}>重命名</button><button onClick={() => void removeVoice(version)}>删除</button>{version.status === 'ready' && <><button onClick={() => onPreview(version.id)}>试听 {version.display_name}</button>{defaults.get(profile.id) !== version.id && <button onClick={() => void makeDefault(profile.id, version.id)}>设为默认 {version.display_name}</button>}</>}</div>
      </div>)}
    </article>)}</div>
  </section>
}
