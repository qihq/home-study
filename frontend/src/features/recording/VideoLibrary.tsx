import { useEffect, useMemo, useState } from 'react'
import { RecordingCalendar } from './RecordingCalendar'

export type RecordingItem = {
  id: string
  reading_date: string
  language_type: 'chinese' | 'english'
  title?: string | null
  status: string
  is_official: boolean
  duration_ms: number | null
  download_ready: boolean
}

const labels = { chinese: '中文阅读', english: '英文阅读' }
const asset = (name: string) => `/animal-island/${name}`

const formatDuration = (durationMs: number | null) => {
  if (!durationMs) return '时长计算中'
  const totalSeconds = Math.floor(durationMs / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

const formatDate = (value: string) => {
  const [year, month, day] = value.split('-').map(Number)
  if (!year || !month || !day) return value
  return `${year}年${month}月${day}日`
}

const statusLabel = (status: string) => {
  if (status === 'ready') return '已完成'
  if (['assembling', 'transcoding'].includes(status)) return '处理中'
  if (['assemble_failed', 'transcode_failed'].includes(status)) return '处理失败'
  return status
}

type Props = {
  recordings: RecordingItem[]
  loading?: boolean
  loadError?: string | null
  onRetry?: () => void
  workerOnline?: boolean
  onMakeOfficial?: (id: string) => void
  onDelete?: (id: string) => Promise<void>
  onRename?: (id: string, title: string) => Promise<void>
  onRetryProcessing?: (id: string) => Promise<void>
}

export function VideoLibrary({ recordings, loading = false, loadError = null, onRetry, workerOnline = true, onMakeOfficial, onDelete, onRename, onRetryProcessing }: Props) {
  const [previewId, setPreviewId] = useState<string | null>(null)
  const [selectedDate, setSelectedDate] = useState<string | null>(() => recordings.map(item => item.reading_date).sort().at(-1) ?? null)
  const visibleRecordings = useMemo(() => selectedDate ? recordings.filter(item => item.reading_date === selectedDate) : recordings, [recordings, selectedDate])
  useEffect(() => {
    if (previewId && !visibleRecordings.some(item => item.id === previewId)) setPreviewId(null)
  }, [previewId, visibleRecordings])
  const remove = async (recording: RecordingItem) => {
    if (window.confirm(`确定删除 ${recording.reading_date} 的${labels[recording.language_type]}视频吗？此操作无法撤销。`)) {
      await onDelete?.(recording.id)
    }
  }
  const rename = async (recording: RecordingItem) => {
    const title = window.prompt('视频名称', recording.title ?? `${recording.reading_date} ${labels[recording.language_type]}`)
    if (title?.trim()) await onRename?.(recording.id, title.trim())
  }
  const hasPendingWork = recordings.some(item => ['assembling', 'transcoding'].includes(item.status))

  return <section className="video-library">
    <header className="video-library-hero">
      <div>
        <p className="date">小岛影像馆</p>
        <h1>阅读回忆册</h1>
        <p>把每一次认真阅读，都收藏成成长的回忆。</p>
      </div>
      <img src={asset('camera.svg')} alt="" />
    </header>
    {!workerOnline && hasPendingWork && <p role="alert">后台处理服务离线，视频处理已暂停。重启最新容器后会继续。</p>}
    {loadError && <section className="video-library-load-error" role="alert">
      <img src={asset('critterpedia.svg')} alt="" />
      <div><strong>暂时没能打开影像馆</strong><p>{loadError}</p></div>
      <button onClick={onRetry}>重新加载</button>
    </section>}
    {recordings.length > 0 && <RecordingCalendar recordings={recordings} selectedDate={selectedDate} onSelectDate={setSelectedDate} onShowAll={() => setSelectedDate(null)} />}
    {loading && recordings.length === 0 ? <p className="video-library-loading" role="status"><img src={asset('leaf.png')} alt="" />正在整理岛上的阅读回忆…</p> : !loadError && recordings.length === 0 ? <section className="video-library-empty">
      <img src={asset('animal-icon.png')} alt="两位小岛伙伴" />
      <h2>影像馆还空空的</h2>
      <p>完成一次阅读打卡后，视频会出现在这里。</p>
    </section> : <div className="recording-list">
      {visibleRecordings.map(recording => {
        const isPreviewing = previewId === recording.id
        const title = recording.title || `${labels[recording.language_type]} · ${recording.reading_date}`
        const downloadName = `${recording.reading_date}-${recording.language_type}-reading.mp4`
        return <article className={isPreviewing ? 'recording-card is-previewing' : 'recording-card'} key={recording.id}>
          <div className="recording-card-heading">
            <span className={`recording-type-icon ${recording.language_type}`}><img src={asset(recording.language_type === 'chinese' ? 'camera.svg' : 'chat.svg')} alt="" /></span>
            <div>
              <div className="recording-badges">
                <span>{labels[recording.language_type]}</span>
                {recording.is_official && <span className="official-badge"><img src={asset('leaf.png')} alt="" />正式打卡</span>}
              </div>
              <h2>{title}</h2>
            </div>
          </div>

          <dl className="recording-meta">
            <div><dt>日期</dt><dd>{formatDate(recording.reading_date)}</dd></div>
            <div><dt>时长</dt><dd>{formatDuration(recording.duration_ms)}</dd></div>
            <div><dt>状态</dt><dd className={`recording-status ${recording.status}`}>{statusLabel(recording.status)}</dd></div>
          </dl>

          {isPreviewing && <section className="island-video-player" aria-label={`${title}视频预览`}>
            <div className="island-video-screen">
              <video className="library-video-preview" controls playsInline preload="metadata" src={`/api/recordings/${recording.id}/preview`} />
            </div>
            <div className="island-video-caption"><img src={asset('leaf.png')} alt="" /><span>正在播放这一天的阅读回忆</span></div>
          </section>}

          <div className="recording-primary-actions">
            {recording.download_ready && <>
              <button className="recording-preview-button" aria-expanded={isPreviewing} onClick={() => setPreviewId(isPreviewing ? null : recording.id)}>
                <img src={asset('camera.svg')} alt="" />{isPreviewing ? '收起预览' : '播放回忆'}
              </button>
              <a className="recording-download-button" href={`/api/recordings/${recording.id}/download/720p`} download={downloadName} aria-label="下载 MP4 到设备">
                <img src={asset('shopping.svg')} alt="" />保存 MP4
              </a>
            </>}
            {['assemble_failed', 'transcode_failed'].includes(recording.status) && <button className="recording-retry-button" onClick={() => void onRetryProcessing?.(recording.id)}>重新处理</button>}
          </div>

          <div className="recording-secondary-actions">
            {!recording.is_official && <button onClick={() => onMakeOfficial?.(recording.id)}>设为正式</button>}
            <button onClick={() => void rename(recording)}>重命名</button>
            <button className="delete-recording" onClick={() => void remove(recording)}>删除</button>
          </div>
        </article>
      })}
    </div>}
  </section>
}
