import { useEffect, useRef, useState } from 'react'

export function VoiceRecorder({ onRecorded }: { onRecorded: (audio: Blob) => Promise<void> | void }) {
  const [consent, setConsent] = useState(false)
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [message, setMessage] = useState('')
  const recorder = useRef<MediaRecorder | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const chunks = useRef<Blob[]>([])
  const startedAt = useRef(0)

  useEffect(() => () => stream.current?.getTracks().forEach(track => track.stop()), [])
  useEffect(() => { if (!recording) return; const timer = window.setInterval(() => setSeconds(Math.floor((Date.now() - startedAt.current) / 1000)), 250); return () => window.clearInterval(timer) }, [recording])
  const start = async () => {
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true })
      stream.current = media; chunks.current = []; setMessage('')
      const instance = new MediaRecorder(media); recorder.current = instance
      instance.ondataavailable = event => { if (event.data.size) chunks.current.push(event.data) }
      instance.onstop = async () => {
        const duration = Math.round((Date.now() - startedAt.current) / 1000)
        media.getTracks().forEach(track => track.stop()); stream.current = null; setRecording(false); setSeconds(duration)
        if (duration < 8 || duration > 30) { setMessage('录音需要介于 8 到 30 秒之间。'); return }
        try { setMessage('录音已提交，正在处理声音样本…'); await onRecorded(new Blob(chunks.current, { type: instance.mimeType || 'audio/webm' })); setMessage('录音已提交，处理完成后可试听并设为默认声音。') }
        catch { setMessage('提交录音失败，请检查网络后重试。') }
      }
      startedAt.current = Date.now(); setSeconds(0); setRecording(true); instance.start()
    } catch { setMessage('无法使用麦克风，请检查浏览器权限。') }
  }
  return <div className="voice-recorder"><p>录制时长：{seconds} 秒（需要 8–30 秒）</p><label className="voice-consent"><input aria-label="我已确认拥有该声音的授权" type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} /> 我已确认拥有该声音的授权</label>{recording ? <><button onClick={() => recorder.current?.stop()}>停止录制</button><button onClick={() => { recorder.current?.stop(); setSeconds(0) }}>重录</button></> : <button disabled={!consent} onClick={() => void start()}>开始录制</button>}{message && <p role="status">{message}</p>}</div>
}
