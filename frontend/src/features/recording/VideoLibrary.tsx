import { useState } from 'react'

export type RecordingItem = { id: string; reading_date: string; language_type: 'chinese' | 'english'; title: string | null; status: string; is_official: boolean; duration_ms: number | null; download_ready: boolean }
const labels = { chinese: '中文阅读', english: '英文阅读' }

type Props = {
  recordings: RecordingItem[]
  workerOnline?: boolean
  onMakeOfficial?: (id: string) => void
  onDelete?: (id: string) => Promise<void>
  onRename?: (id: string, title: string) => Promise<void>
}

export function VideoLibrary({ recordings, workerOnline = true, onMakeOfficial, onDelete, onRename }: Props) {
  const [previewId, setPreviewId] = useState<string | null>(null)
  const remove = async (recording: RecordingItem) => { if (window.confirm(`确定删除 ${recording.reading_date} 的${labels[recording.language_type]}视频吗？此操作无法撤销。`)) await onDelete?.(recording.id) }
  const rename = async (recording: RecordingItem) => { const title = window.prompt('视频名称', recording.title ?? `${recording.reading_date} ${labels[recording.language_type]}`); if (title?.trim()) await onRename?.(recording.id, title.trim()) }
  const hasPendingWork = recordings.some(item => ['assembling', 'transcoding'].includes(item.status))

  return <section className="video-library">
    <header><p className="date">视频库</p><h1>阅读记录</h1></header>
    {!workerOnline && hasPendingWork && <p role="alert">后台处理服务离线，视频处理已暂停。重启最新容器后会继续。</p>}
    <div className="recording-list">{recordings.map(recording => <article key={recording.id}>
      <div><strong>{recording.title || `${recording.reading_date} · ${labels[recording.language_type]}`}</strong><p>{recording.status === 'ready' ? '已完成' : ['assembling', 'transcoding'].includes(recording.status) ? '处理中' : recording.status}</p></div>
      <div className="recording-actions">
        {recording.is_official ? <span>正式打卡</span> : <button onClick={() => onMakeOfficial?.(recording.id)}>设为正式</button>}
        {recording.download_ready && <><button onClick={() => setPreviewId(previewId === recording.id ? null : recording.id)}>{previewId === recording.id ? '关闭预览' : '预览'}</button><a href={`/api/recordings/${recording.id}/download/720p`} download aria-label="下载到设备">保存到手机</a></>}
        <button onClick={() => void rename(recording)}>重命名</button>
        <button className="delete-recording" onClick={() => void remove(recording)}>删除</button>
        {previewId === recording.id && <video className="library-video-preview" controls playsInline preload="metadata" src={`/api/recordings/${recording.id}/preview`} />}
      </div>
    </article>)}</div>
  </section>
}
