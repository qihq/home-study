import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import { createIndexedDbRecordingStore, RecordingSession } from '../../lib/recordingStore'
import { Button } from '../../ui/Button'

type RecordingState = 'idle' | 'recording' | 'uploading' | 'complete' | 'error'
const store = createIndexedDbRecordingStore()

function preferredMime() {
  return ['video/mp4;codecs=avc1,mp4a.40.2', 'video/mp4', 'video/webm;codecs=vp8,opus'].find(type => MediaRecorder.isTypeSupported(type))
}

async function digest(blob: Blob) {
  const bytes = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())
  return [...new Uint8Array(bytes)].map(byte => byte.toString(16).padStart(2, '0')).join('')
}

type RecordingPageProps = {
  language: 'chinese' | 'english'
  onBack: () => void
  onHome: () => void
  onOpenVideos: () => void
  recovery?: RecordingSession
}

function formatElapsed(elapsedMs: number) {
  const totalSeconds = Math.floor(elapsedMs / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  const clock = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
  return hours ? `${hours.toString().padStart(2, '0')}:${clock}` : clock
}

export function RecordingPage({ language, onBack, onHome, onOpenVideos, recovery }: RecordingPageProps) {
  const video = useRef<HTMLVideoElement>(null)
  const recorder = useRef<MediaRecorder | null>(null)
  const recordingId = useRef<string | null>(null)
  const sequence = useRef(0)
  const pendingUploads = useRef(new Set<Promise<void>>())
  const startedAt = useRef<number | null>(null)
  const [state, setState] = useState<RecordingState>(recovery ? 'error' : 'idle')
  const [camera, setCamera] = useState<'user' | 'environment'>('user')
  const [message, setMessage] = useState('请保持页面在前台，录制片段会自动上传到 NAS。')
  const [elapsedMs, setElapsedMs] = useState(0)

  useEffect(() => () => recorder.current?.stream.getTracks().forEach(track => track.stop()), [])
  useEffect(() => {
    if (state !== 'recording' || startedAt.current === null) return
    const update = () => setElapsedMs(performance.now() - startedAt.current!)
    update()
    const timer = window.setInterval(update, 250)
    return () => window.clearInterval(timer)
  }, [state])

  async function upload(sequenceNumber: number, blob: Blob) {
    const id = recordingId.current
    if (!id) return
    await store.put(id, sequenceNumber, blob)
    const hash = await digest(blob)
    const response = await fetch(`/api/recordings/${id}/chunks/${sequenceNumber}`, { method: 'PUT', body: blob, credentials: 'include', headers: { 'X-Chunk-Sha256': hash, 'Content-Type': blob.type || 'video/mp4' } })
    if (!response.ok) throw new Error('UPLOAD_FAILED')
    await store.acknowledge(id, sequenceNumber)
  }

  async function resumePending() {
    const id = recordingId.current
    if (!id) return
    const known = await api<{ received_sequences: number[] }>(`/recordings/${id}/chunks`)
    const received = new Set(known.received_sequences)
    for (const item of await store.list(id)) {
      if (!received.has(item.sequence)) await upload(item.sequence, item.blob)
      else await store.acknowledge(id, item.sequence)
    }
  }

  async function openCamera(facingMode: 'user' | 'environment') {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode }, audio: true })
    const previous = video.current?.srcObject as MediaStream | null
    if (video.current) { video.current.srcObject = stream; await video.current.play() }
    previous?.getTracks().forEach(track => track.stop())
    setCamera(facingMode)
    return stream
  }

  async function switchCamera() {
    if (state !== 'idle' && state !== 'recording') return
    try {
      const next = camera === 'user' ? 'environment' : 'user'
      if (state === 'recording' && recorder.current) {
        const oldRecorder = recorder.current
        const oldStream = oldRecorder.stream
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: next }, audio: true })
        await new Promise<void>(resolve => { oldRecorder.addEventListener('stop', () => resolve(), { once: true }); oldRecorder.stop() })
        oldStream.getTracks().forEach(track => track.stop())
        if (video.current) { video.current.srcObject = stream; await video.current.play() }
        const instance = new MediaRecorder(stream, preferredMime() ? { mimeType: preferredMime() } : undefined)
        configureRecorder(instance); instance.start(4000); recorder.current = instance; setCamera(next)
      } else await openCamera(next)
    }
    catch { setMessage('无法切换摄像头，请检查后置摄像头权限。') }
  }

  function configureRecorder(instance: MediaRecorder) {
    instance.ondataavailable = event => {
      if (!event.data.size) return
      const sequenceNumber = sequence.current++
      const id = recordingId.current
      const task = (async () => {
        if (id) await store.putSession({ recordingId: id, language, nextSequence: sequence.current, ended: false })
        await upload(sequenceNumber, event.data)
      })().catch(() => { setState('error'); setMessage('片段上传失败，已保留在本机缓存，请恢复网络后重试。') }).finally(() => pendingUploads.current.delete(task))
      pendingUploads.current.add(task)
    }
  }

  async function start() {
    try {
      const stream = (video.current?.srcObject as MediaStream | null) ?? await openCamera(camera)
      if (recovery) { recordingId.current = recovery.recordingId; sequence.current = recovery.nextSequence; await resumePending() }
      else {
        const created = await api<{ id: string }>('/recordings', { method: 'POST', body: JSON.stringify({ language_type: language }) })
        recordingId.current = created.id; sequence.current = 0
        await store.putSession({ recordingId: created.id, language, nextSequence: 0, ended: false })
      }
      const instance = new MediaRecorder(stream, preferredMime() ? { mimeType: preferredMime() } : undefined)
      configureRecorder(instance)
      instance.start(4000); recorder.current = instance; startedAt.current = performance.now(); setElapsedMs(0); setState('recording'); setMessage('录制中，片段正在保存到 NAS。')
    } catch { setState('error'); setMessage('无法打开摄像头或麦克风，请检查浏览器权限和 HTTPS。') }
  }

  async function stop() {
    if (!recorder.current || !recordingId.current) return
    if (startedAt.current !== null) setElapsedMs(performance.now() - startedAt.current)
    startedAt.current = null
    setState('uploading')
    await new Promise<void>(resolve => { recorder.current!.addEventListener('stop', () => resolve(), { once: true }); recorder.current!.stop() })
    recorder.current.stream.getTracks().forEach(track => track.stop())
    await Promise.all([...pendingUploads.current])
    await store.putSession({ recordingId: recordingId.current, language, nextSequence: sequence.current, ended: true })
    await resumePending()
    const completed = await api<{ missing_sequences: number[] }>(`/recordings/${recordingId.current}/complete`, { method: 'POST', body: JSON.stringify({ final_chunk_count: sequence.current }) })
    if (completed.missing_sequences.length) { setState('error'); setMessage('仍有片段等待上传，请保持页面打开后重试。'); return }
    await store.removeSession(recordingId.current)
    setState('complete'); setMessage('源视频已提交 NAS，正在自动生成可保存到手机的 720p 版本。')
  }

  async function submitRecoveredRecording() {
    if (!recovery) return
    setState('uploading')
    try {
      recordingId.current = recovery.recordingId; sequence.current = recovery.nextSequence
      await resumePending()
      const completed = await api<{ missing_sequences: number[] }>(`/recordings/${recovery.recordingId}/complete`, { method: 'POST', body: JSON.stringify({ final_chunk_count: recovery.nextSequence }) })
      if (completed.missing_sequences.length) throw new Error('MISSING_CHUNKS')
      await store.removeSession(recovery.recordingId)
      setState('complete'); setMessage('源视频已提交 NAS，正在自动生成 720p 版本。')
    } catch { setState('error'); setMessage('仍有片段等待上传，请恢复网络后重试。') }
  }

  const title = language === 'chinese' ? '中文阅读' : '英文阅读'
  return <section className="recording-page">
    <header className="recording-header">
      <Button variant="secondary" onClick={onBack}>返回</Button>
      <div><p className="date">小岛阅读打卡</p><h1>{title}</h1></div>
      <img src="/animal-island/camera.svg" alt="" />
    </header>
    {state === 'complete' ? <section className="recording-complete-card">
      <img src="/animal-island/animal-icon.png" alt="小岛伙伴" />
      <p className="date">本次录制 {formatElapsed(elapsedMs)}</p>
      <h2>阅读视频保存成功</h2>
      <p>{message}</p>
      <div className="recording-complete-actions">
        <Button onClick={onHome}>返回主页</Button>
        <Button variant="secondary" onClick={onOpenVideos}>去视频库查看</Button>
      </div>
    </section> : <>
      <div className="recording-stage">
        <video ref={video} muted playsInline className="preview" />
        <div className={`recording-timer ${state === 'recording' ? 'is-recording' : ''}`}>
          {state === 'recording' && <span aria-hidden="true" />}{formatElapsed(elapsedMs)}
        </div>
        <div className="recording-language-badge"><img src="/animal-island/leaf.png" alt="" />{title}</div>
      </div>
      <div className="recording-primary-control">
        {state === 'idle' || state === 'error' ? recovery?.ended ? <Button onClick={() => void submitRecoveredRecording()}>补传并提交</Button> : <Button onClick={() => void start()}>{recovery ? '继续录制' : '开始录制'}</Button> : state === 'recording' ? <Button variant="danger" onClick={() => void stop()}>结束录制</Button> : <Button disabled>正在提交视频…</Button>}
      </div>
      <div className="recording-controls"><Button variant="secondary" disabled={state === 'uploading'} onClick={() => void switchCamera()}>切换到{camera === 'user' ? '后置' : '前置'}摄像头</Button></div>
      <div className={`recording-status-card ${state}`}><img src="/animal-island/map.svg" alt="" /><p className={`recording-message ${state}`}>{message}</p></div>
    </>}
  </section>
}
