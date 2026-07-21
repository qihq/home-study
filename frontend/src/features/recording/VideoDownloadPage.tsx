import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Button } from '../../ui/Button'

export type VideoDownloadItem = {
  id: string
  title: string
  readingDate: string
  languageType: 'chinese' | 'english'
  fileName: string
}

type DownloadState = 'downloading' | 'ready' | 'sharing' | 'cancelled' | 'error'
type Fetcher = typeof fetch

export async function downloadVideo(
  item: VideoDownloadItem,
  signal: AbortSignal,
  onProgress: (loaded: number, total: number | null) => void,
  fetcher: Fetcher = fetch,
): Promise<File> {
  const response = await fetcher(`/api/recordings/${item.id}/download/720p`, {
    credentials: 'include',
    signal,
  })
  if (!response.ok) throw new Error('VIDEO_DOWNLOAD_FAILED')
  const totalHeader = Number(response.headers.get('Content-Length'))
  const total = Number.isFinite(totalHeader) && totalHeader > 0 ? totalHeader : null
  onProgress(0, total)

  if (!response.body) {
    const blob = await response.blob()
    onProgress(blob.size, total ?? blob.size)
    return new File([blob], item.fileName, { type: 'video/mp4' })
  }

  const reader = response.body.getReader()
  const chunks: ArrayBuffer[] = []
  let loaded = 0
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    if (value) {
      const chunk = new Uint8Array(value.byteLength)
      chunk.set(value)
      chunks.push(chunk.buffer)
      loaded += value.byteLength
      onProgress(loaded, total)
    }
  }
  return new File(chunks, item.fileName, { type: 'video/mp4' })
}

const formatBytes = (bytes: number) => {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(bytes < 1024 ? 1 : 0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function VideoDownloadPage({ item, onHome, onBackToVideos }: {
  item: VideoDownloadItem
  onHome: () => void
  onBackToVideos: () => void
}) {
  const controller = useRef<AbortController | null>(null)
  const onHomeRef = useRef(onHome)
  onHomeRef.current = onHome
  const [state, setState] = useState<DownloadState>('downloading')
  const [loaded, setLoaded] = useState(0)
  const [total, setTotal] = useState<number | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [message, setMessage] = useState('正在从小岛影像馆取回视频，请保持应用在前台。')
  const [attempt, setAttempt] = useState(0)

  const shareFile = useCallback(async (video: File) => {
    if (!navigator.share || !navigator.canShare?.({ files: [video] })) {
      setState('ready')
      setMessage('当前设备不能直接打开照片存储面板，请使用下方的 MP4 保存按钮。')
      return
    }
    setState('sharing')
    setMessage('请在系统面板中选择“存储视频”。')
    try {
      await navigator.share({ files: [video], title: item.title })
      setMessage('视频已保存，正在返回主页。')
      onHomeRef.current()
    } catch {
      setState('ready')
      setMessage('尚未存入照片。可以再次点击“保存到照片”。')
    }
  }, [item.title])

  useEffect(() => {
    const current = new AbortController()
    controller.current = current
    setState('downloading')
    setLoaded(0)
    setTotal(null)
    setFile(null)
    setMessage('正在从小岛影像馆取回视频，请保持应用在前台。')
    void downloadVideo(item, current.signal, (nextLoaded, nextTotal) => {
      setLoaded(nextLoaded)
      setTotal(nextTotal)
    }).then(video => {
      if (current.signal.aborted) return
      setFile(video)
      setState('ready')
      setMessage('下载完成，正在打开系统照片存储面板。')
      void shareFile(video)
    }).catch(error => {
      if (current.signal.aborted) return
      setState('error')
      setMessage(error instanceof Error && error.message === 'VIDEO_DOWNLOAD_FAILED'
        ? '视频下载失败，请检查网络后重试。'
        : '没有足够空间完成下载，请释放设备空间后重试。')
    })
    return () => current.abort()
  }, [attempt, item, shareFile])

  const cancel = () => {
    controller.current?.abort()
    setState('cancelled')
    setMessage('下载已取消，视频仍安全保存在影像馆。')
  }
  const percent = total ? Math.min(100, Math.round((loaded / total) * 100)) : null
  const fallbackUrl = useMemo(() => file ? URL.createObjectURL(file) : null, [file])
  useEffect(() => () => { if (fallbackUrl) URL.revokeObjectURL(fallbackUrl) }, [fallbackUrl])

  return <section className="video-download-page">
    <header className="video-download-hero">
      <div><p className="date">小岛快递站</p><h1>正在保存阅读回忆</h1><p>{item.title}</p></div>
      <img src="/animal-island/shopping.svg" alt="" />
    </header>
    <article className="video-download-card">
      <img className="video-download-companion" src="/animal-island/animal-icon.png" alt="小岛伙伴正在打包视频" />
      <div className="video-download-details">
        <p className="video-download-language">{item.languageType === 'chinese' ? '中文阅读' : '英文阅读'} · {item.readingDate}</p>
        <h2>{state === 'ready' ? '视频已经准备好' : state === 'sharing' ? '等待存入照片' : state === 'error' ? '这次快递没送到' : state === 'cancelled' ? '下载已取消' : '正在打包视频'}</h2>
        <div className={`video-download-progress ${total ? '' : 'is-indeterminate'}`} role="progressbar" aria-label="视频下载进度" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent ?? undefined}>
          <span style={percent === null ? undefined : { width: `${percent}%` }} />
        </div>
        <p className="video-download-size">{percent === null ? `${formatBytes(loaded)} 已下载` : `${percent}% · ${formatBytes(loaded)} / ${formatBytes(total!)}`}</p>
        <p role="status" className="video-download-message">{message}</p>
        <div className="video-download-primary-actions">
          {state === 'downloading' && <Button variant="secondary" onClick={cancel}>取消下载</Button>}
          {(state === 'error' || state === 'cancelled') && <Button onClick={() => setAttempt(value => value + 1)}>重新下载</Button>}
          {file && state === 'ready' && navigator.canShare?.({ files: [file] }) && <Button onClick={() => void shareFile(file)}>保存到照片</Button>}
          {file && state === 'ready' && !navigator.canShare?.({ files: [file] }) && fallbackUrl && <a className="button button--primary" href={fallbackUrl} download={item.fileName} target="_blank" rel="noreferrer">保存 MP4</a>}
        </div>
      </div>
    </article>
    <div className="video-download-navigation">
      <Button variant="secondary" onClick={onBackToVideos}>返回视频库</Button>
      <Button variant="secondary" onClick={onHome}>返回主页</Button>
    </div>
  </section>
}
