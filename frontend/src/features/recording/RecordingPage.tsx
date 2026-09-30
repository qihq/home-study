import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import { createIndexedDbRecordingStore, RecordingLanguage, RecordingSession } from '../../lib/recordingStore'
import { Button } from '../../ui/Button'

type RecordingState = 'idle' | 'recording' | 'uploading' | 'complete' | 'error'
const store = createIndexedDbRecordingStore()

function preferredMime() {
  return ['video/mp4;codecs=avc1,mp4a.40.2', 'video/mp4', 'video/webm;codecs=vp8,opus'].find(type => MediaRecorder.isTypeSupported(type))
}

const NO_MIC_MESSAGE = '没有获取到麦克风声音，请在浏览器与系统设置中允许麦克风权限后重试。'
const NO_RECORDING_MESSAGE = '这次没有录到任何画面：录制过程中锁屏或切到别的应用会让摄像头中断。请保持页面在前台重新录制。'
const RECORDING_STALLED_MESSAGE = '录制似乎已经中断（超过 20 秒没有新片段），可能是锁屏或切到了其他应用。建议结束录制后重新开始。'
const SUBMIT_FAILED_MESSAGE = '提交失败，视频片段仍保存在本机。可以点「补传并提交」重试，或「放弃并重新开始」。'

// 分片每 4 秒产生一个；这么久没有新片段就说明录制已经断了。
const RECORDING_STALL_MS = 20_000
// 锁屏/切后台会让音视频轨失效，此时 MediaRecorder.stop() 可能永远不派发 stop 事件。
const RECORDER_STOP_TIMEOUT_MS = 10_000

function stopRecorder(instance: MediaRecorder, timeoutMs = RECORDER_STOP_TIMEOUT_MS) {
  return new Promise<void>(resolve => {
    let settled = false
    const finish = () => {
      if (settled) return
      settled = true
      window.clearTimeout(timer)
      resolve()
    }
    const timer = window.setTimeout(finish, timeoutMs)
    instance.addEventListener('stop', finish, { once: true })
    try { instance.stop() } catch { finish() }
  })
}

function hasLiveAudio(stream: MediaStream) {
  const audioTracks = stream.getAudioTracks()
  return audioTracks.length > 0 && audioTracks.some(track => track.readyState === 'live' && !track.muted)
}

function hasLiveVideo(stream: MediaStream) {
  return stream.getVideoTracks().some(track => track.readyState === 'live')
}

function stopStream(stream: MediaStream) {
  stream.getTracks().forEach(track => track.stop())
}

// 锁屏/切后台后摄像头流可能只剩失效的音视频轨（表现为无声视频）。
// 复用挂在预览上的旧流前必须确认轨道仍然可用，否则重新向系统申请。
function usableAfterLock(stream: MediaStream) {
  return hasLiveAudio(stream) && hasLiveVideo(stream)
}

async function digest(blob: Blob) {
  const bytes = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())
  return [...new Uint8Array(bytes)].map(byte => byte.toString(16).padStart(2, '0')).join('')
}

// 录制每 4 秒产出一个分片。上传必须限流：每个在飞的分片都会占用服务端一条数据库连接，
// 不限并发时网络一变慢就会堆到连接池耗尽（QueuePool timeout → 500），整段录制报废。
const MAX_CONCURRENT_UPLOADS = 2
const UPLOAD_RETRY_DELAYS_MS = [1000, 3000, 8000]

class UploadError extends Error {
  constructor(readonly status: number) { super(`UPLOAD_FAILED_${status}`) }
}

// 4xx（除 429）是确定性失败：录制已被删除、分片冲突、哈希不符，重试没有意义。
function isRetryableUploadError(error: unknown) {
  return error instanceof UploadError && (error.status === 0 || error.status === 429 || error.status >= 500)
}

function createUploadLimiter(limit: number) {
  const waiting: Array<() => void> = []
  let active = 0
  return async function withSlot<T>(task: () => Promise<T>): Promise<T> {
    if (active >= limit) await new Promise<void>(resolve => waiting.push(resolve))
    active += 1
    try { return await task() }
    finally {
      active -= 1
      waiting.shift()?.()
    }
  }
}

type RecordingPageProps = {
  language: RecordingLanguage
  onBack: () => void
  onHome: () => void
  onOpenVideos: () => void
  recovery?: RecordingSession
}

const recordingCopy = {
  chinese: { title: '中文阅读', date: '小岛阅读打卡', saved: '阅读视频保存成功', badge: '/animal-island/leaf.png' },
  english: { title: '英文阅读', date: '小岛阅读打卡', saved: '阅读视频保存成功', badge: '/animal-island/leaf.png' },
  skating: { title: '花滑录制', date: '小岛花滑时光', saved: '花滑视频保存成功', badge: '/animal-island/skating.svg' },
} as const

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
  const withUploadSlot = useRef<ReturnType<typeof createUploadLimiter> | null>(null)
  withUploadSlot.current ??= createUploadLimiter(MAX_CONCURRENT_UPLOADS)
  const startedAt = useRef<number | null>(null)
  const lastChunkAt = useRef<number | null>(null)
  const [abandonedRecoveryId, setAbandonedRecoveryId] = useState<string | null>(null)
  const [localRecovery, setLocalRecovery] = useState<RecordingSession | null>(null)
  // 刚录完但提交失败的会话只存在于本机，优先于登录时读到的 recovery，
  // 否则用户会看到「开始录制」又开一段新的，把上一段变成永远清理不掉的残留。
  const candidateRecovery = localRecovery ?? recovery ?? undefined
  const effectiveRecovery = candidateRecovery?.recordingId === abandonedRecoveryId ? undefined : candidateRecovery
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
  useEffect(() => {
    // 锁屏/切后台后 MediaRecorder 会静默停摆：不报错，也不再产生片段。
    // 这里主动发现「录了半天其实什么都没录到」，而不是等用户点完提交才发现。
    if (state !== 'recording') return
    const timer = window.setInterval(() => {
      const last = lastChunkAt.current
      if (last !== null && performance.now() - last > RECORDING_STALL_MS) setMessage(RECORDING_STALLED_MESSAGE)
    }, 5_000)
    return () => window.clearInterval(timer)
  }, [state])

  async function upload(sequenceNumber: number, blob: Blob) {
    const id = recordingId.current
    if (!id) return
    await store.put(id, sequenceNumber, blob)
    const hash = await digest(blob)
    let response: Response
    try {
      response = await fetch(`/api/recordings/${id}/chunks/${sequenceNumber}`, { method: 'PUT', body: blob, credentials: 'include', headers: { 'X-Chunk-Sha256': hash, 'Content-Type': blob.type || 'video/mp4' } })
    } catch { throw new UploadError(0) }
    if (!response.ok) throw new UploadError(response.status)
    await store.acknowledge(id, sequenceNumber)
  }

  async function uploadWithRetry(sequenceNumber: number, blob: Blob) {
    for (let attempt = 0; ; attempt += 1) {
      try { await upload(sequenceNumber, blob); return }
      catch (error) {
        const delay = UPLOAD_RETRY_DELAYS_MS[attempt]
        if (delay === undefined || !isRetryableUploadError(error)) throw error
        await new Promise(resolve => window.setTimeout(resolve, delay))
      }
    }
  }

  function enqueueUpload(sequenceNumber: number, blob: Blob) {
    return withUploadSlot.current!(() => uploadWithRetry(sequenceNumber, blob))
  }

  async function drainPendingUploads() {
    while (pendingUploads.current.size > 0) {
      setMessage(`正在上传剩余片段（还有 ${pendingUploads.current.size} 个）…`)
      await Promise.all([...pendingUploads.current])
    }
  }

  async function resumePending() {
    const id = recordingId.current
    if (!id) return
    const known = await api<{ received_sequences: number[] }>(`/recordings/${id}/chunks`)
    const received = new Set(known.received_sequences)
    for (const item of await store.list(id)) {
      if (!received.has(item.sequence)) await enqueueUpload(item.sequence, item.blob)
      else await store.acknowledge(id, item.sequence)
    }
  }

  async function openCamera(facingMode: 'user' | 'environment') {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode }, audio: true })
    if (!hasLiveAudio(stream)) {
      stopStream(stream)
      throw new Error('NO_AUDIO_TRACK')
    }
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
        if (!hasLiveAudio(stream)) {
          stopStream(stream)
          throw new Error('NO_AUDIO_TRACK')
        }
        await stopRecorder(oldRecorder)
        oldStream.getTracks().forEach(track => track.stop())
        if (video.current) { video.current.srcObject = stream; await video.current.play() }
        const instance = new MediaRecorder(stream, preferredMime() ? { mimeType: preferredMime() } : undefined)
        configureRecorder(instance); instance.start(4000); recorder.current = instance; setCamera(next)
      } else await openCamera(next)
    }
    catch { setMessage('无法切换摄像头或麦克风，请检查相机与麦克风权限。') }
  }

  function configureRecorder(instance: MediaRecorder) {
    instance.ondataavailable = event => {
      if (!event.data.size) return
      const sequenceNumber = sequence.current++
      const id = recordingId.current
      const task = (async () => {
        if (id) await store.putSession({ recordingId: id, language, nextSequence: sequence.current, ended: false })
        lastChunkAt.current = performance.now()
        await enqueueUpload(sequenceNumber, event.data)
      })().catch(() => { setState('error'); setMessage('片段上传失败，已保留在本机缓存，请恢复网络后重试。') }).finally(() => pendingUploads.current.delete(task))
      pendingUploads.current.add(task)
    }
  }

  async function start() {
    try {
      let stream = video.current?.srcObject as MediaStream | null
      if (stream && !usableAfterLock(stream)) {
        // 锁屏或切后台后旧流可能只剩失效轨道：停掉并重新申请摄像头与麦克风
        stopStream(stream)
        if (video.current) video.current.srcObject = null
        stream = null
      }
      stream = stream ?? await openCamera(camera)
      if (!hasLiveAudio(stream)) {
        stopStream(stream)
        if (video.current) video.current.srcObject = null
        setState('error')
        setMessage(NO_MIC_MESSAGE)
        return
      }
      if (effectiveRecovery) { recordingId.current = effectiveRecovery.recordingId; sequence.current = effectiveRecovery.nextSequence; await resumePending() }
      else {
        const created = await api<{ id: string }>('/recordings', { method: 'POST', body: JSON.stringify({ language_type: language }) })
        recordingId.current = created.id; sequence.current = 0
        await store.putSession({ recordingId: created.id, language, nextSequence: 0, ended: false })
      }
      const instance = new MediaRecorder(stream, preferredMime() ? { mimeType: preferredMime() } : undefined)
      configureRecorder(instance)
      instance.start(4000); recorder.current = instance; startedAt.current = performance.now(); lastChunkAt.current = performance.now(); setElapsedMs(0); setLocalRecovery(null); setState('recording'); setMessage('录制中，片段正在保存到 NAS。')
    } catch (error) { setState('error'); setMessage(error instanceof Error && error.message === 'NO_AUDIO_TRACK' ? NO_MIC_MESSAGE : '无法打开摄像头或麦克风，请检查浏览器权限和 HTTPS。') }
  }

  async function stop() {
    const instance = recorder.current
    const id = recordingId.current
    if (!instance || !id) {
      // 以前这里直接 return，按钮点了毫无反应。现在明确告诉用户发生了什么。
      setState('error')
      setMessage('录制已经中断，请重新开始录制。')
      return
    }
    if (startedAt.current !== null) setElapsedMs(performance.now() - startedAt.current)
    startedAt.current = null
    setState('uploading')
    setMessage('正在提交视频…')
    try {
      await stopRecorder(instance)
      instance.stream.getTracks().forEach(track => track.stop())
      recorder.current = null
      if (sequence.current === 0) {
        // 一个片段都没有：录制中途被打断了。服务端那条空录制没有保留价值，直接放弃。
        try { await api(`/recordings/${id}/abandon`, { method: 'POST' }) } catch { /* 服务端可能已无此录制 */ }
        await store.removeSession(id)
        setState('error')
        setMessage(NO_RECORDING_MESSAGE)
        return
      }
      await drainPendingUploads()
      await store.putSession({ recordingId: id, language, nextSequence: sequence.current, ended: true })
      await resumePending()
      const completed = await api<{ missing_sequences: number[] }>(`/recordings/${id}/complete`, { method: 'POST', body: JSON.stringify({ final_chunk_count: sequence.current }) })
      if (completed.missing_sequences.length) {
        setLocalRecovery({ recordingId: id, language, nextSequence: sequence.current, ended: true })
        setState('error')
        setMessage('仍有片段等待上传，请保持页面打开后重试。')
        return
      }
      await store.removeSession(id)
      setState('complete'); setMessage('源视频已提交 NAS，正在自动生成可保存到手机的 720p 版本。')
    } catch {
      // 以前没有 try/catch：任何一步抛错都会把界面永远留在「正在提交视频…」。
      setLocalRecovery({ recordingId: id, language, nextSequence: sequence.current, ended: true })
      setState('error')
      setMessage(SUBMIT_FAILED_MESSAGE)
    }
  }

  async function submitRecoveredRecording() {
    if (!effectiveRecovery) return
    setState('uploading')
    try {
      recordingId.current = effectiveRecovery.recordingId; sequence.current = effectiveRecovery.nextSequence
      await resumePending()
      const completed = await api<{ missing_sequences: number[] }>(`/recordings/${effectiveRecovery.recordingId}/complete`, { method: 'POST', body: JSON.stringify({ final_chunk_count: effectiveRecovery.nextSequence }) })
      if (completed.missing_sequences.length) throw new Error('MISSING_CHUNKS')
      await store.removeSession(effectiveRecovery.recordingId)
      setLocalRecovery(null)
      setState('complete'); setMessage('源视频已提交 NAS，正在自动生成 720p 版本。')
    } catch { setState('error'); setMessage('仍有片段等待上传，请恢复网络后重试。') }
  }

  async function abandonRecovery() {
    if (!effectiveRecovery) return
    try { await api(`/recordings/${effectiveRecovery.recordingId}/abandon`, { method: 'POST' }) } catch { /* 服务端可能已无此录制 */ }
    await store.removeSession(effectiveRecovery.recordingId)
    setAbandonedRecoveryId(effectiveRecovery.recordingId)
    setLocalRecovery(null)
    recordingId.current = null; sequence.current = 0
    setState('idle')
    setMessage('已放弃之前的录制，现在可以开始新的录制。')
  }

  const copy = recordingCopy[language]
  return <section className={`recording-page ${language}`}>
    <header className="recording-header">
      <Button variant="secondary" onClick={onBack}>返回</Button>
      <div><p className="date">{copy.date}</p><h1>{copy.title}</h1></div>
      <img src="/animal-island/camera.svg" alt="" />
    </header>
    {state === 'complete' ? <section className="recording-complete-card">
      <img src="/animal-island/animal-icon.png" alt="小岛伙伴" />
      <p className="date">本次录制 {formatElapsed(elapsedMs)}</p>
      <h2>{copy.saved}</h2>
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
        <div className="recording-language-badge"><img src={copy.badge} alt="" />{copy.title}</div>
      </div>
      <div className="recording-primary-control">
        {state === 'idle' || state === 'error' ? effectiveRecovery?.ended ? <Button onClick={() => void submitRecoveredRecording()}>补传并提交</Button> : <Button onClick={() => void start()}>{effectiveRecovery ? '继续录制' : '开始录制'}</Button> : state === 'recording' ? <Button variant="danger" onClick={() => void stop()}>结束录制</Button> : <Button disabled>正在提交视频…</Button>}
      </div>
      <div className="recording-controls">{effectiveRecovery && <Button variant="secondary" disabled={state === 'uploading'} onClick={() => void abandonRecovery()}>放弃并重新开始</Button>}<Button variant="secondary" disabled={state === 'uploading'} onClick={() => void switchCamera()}>切换到{camera === 'user' ? '后置' : '前置'}摄像头</Button></div>
      <div className={`recording-status-card ${state}`}><img src="/animal-island/map.svg" alt="" /><p className={`recording-message ${state}`}>{message}</p></div>
    </>}
  </section>
}
