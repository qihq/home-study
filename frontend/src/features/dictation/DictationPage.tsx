import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { Button } from '../../ui/Button'

type DictationResult = {
  id: string
  audio_asset_id: string | null
  result?: 'correct' | 'incorrect' | 'unscored'
  revealed?: boolean
  word_item_id?: string
  pronunciation_source?: 'default' | 'configured' | 'custom'
}

type DictationSession = {
  id: string
  results: DictationResult[]
  speaker_profile_name_snapshot?: string | null
  voice_version_name_snapshot?: string | null
}

type Speaker = { id: string; display_name: string }
type Voice = { id: string; speaker_profile_id: string; display_name: string; status: string }
type StartPayload = { word_list_version_id: string; mode: 'ordered'; speaker_profile_id?: string; voice_version_id?: string }

type Props = {
  words: string[]
  wordListVersionId?: string
  resumeSessionId?: string
  onScore: (result: 'correct' | 'incorrect') => void
  speakers?: Speaker[]
  voices?: Voice[]
  onCreateSession?: (payload: StartPayload) => Promise<DictationSession>
}

export function DictationPage({ words, wordListVersionId, resumeSessionId, onScore, speakers = [], voices = [], onCreateSession }: Props) {
  const [position, setPosition] = useState(0)
  const [selectedSpeakerId, setSelectedSpeakerId] = useState('')
  const [selectedVoiceId, setSelectedVoiceId] = useState('')
  const [snapshotNames, setSnapshotNames] = useState<{ speaker?: string | null; voice?: string | null }>({})
  const [started, setStarted] = useState(!wordListVersionId || Boolean(resumeSessionId))
  const [sessionId, setSessionId] = useState<string | undefined>(resumeSessionId)
  const [results, setResults] = useState<DictationResult[]>(() => words.map((_, index) => ({ id: String(index), audio_asset_id: null, result: 'unscored', revealed: false })))
  const [audioRevision, setAudioRevision] = useState(0)
  const [pronunciationBusy, setPronunciationBusy] = useState(false)
  const word = words[position]
  const current = results[position]
  const selectedVoices = voices.filter(voice => voice.speaker_profile_id === selectedSpeakerId && voice.status === 'ready')

  const applySession = (value: DictationSession) => {
    setSessionId(value.id)
    setResults(value.results)
    setSnapshotNames({ speaker: value.speaker_profile_name_snapshot, voice: value.voice_version_name_snapshot })
  }

  const start = async () => {
    if (!wordListVersionId) { setStarted(true); return }
    const payload: StartPayload = { word_list_version_id: wordListVersionId, mode: 'ordered' }
    if (selectedSpeakerId && selectedVoiceId) {
      payload.speaker_profile_id = selectedSpeakerId
      payload.voice_version_id = selectedVoiceId
    }
    const value = onCreateSession ? await onCreateSession(payload) : await api<DictationSession>('/dictation-sessions', { method: 'POST', body: JSON.stringify(payload) })
    applySession(value)
    setStarted(true)
  }

  useEffect(() => {
    if (!resumeSessionId) return
    void api<DictationSession>(`/dictation-sessions/${resumeSessionId}`).then(value => {
      applySession(value)
      const next = value.results.findIndex(result => result.result === 'unscored')
      setPosition(next < 0 ? Math.max(value.results.length - 1, 0) : next)
    })
  }, [resumeSessionId])

  useEffect(() => {
    if (!sessionId || results.every(result => Boolean(result.audio_asset_id))) return
    const timer = window.setInterval(() => {
      void api<DictationSession>(`/dictation-sessions/${sessionId}`).then(applySession)
    }, 3000)
    return () => window.clearInterval(timer)
  }, [sessionId, results])

  async function score(result: 'correct' | 'incorrect') {
    onScore(result)
    if (sessionId && current?.id) {
      await api(`/dictation-sessions/${sessionId}/results/${current.id}`, { method: 'PATCH', body: JSON.stringify({ result }) })
    }
    setResults(value => value.map((item, index) => index === position ? { ...item, result, revealed: true } : item))
    setPosition(value => Math.min(value + 1, words.length - 1))
  }

  async function reveal() {
    if (sessionId && current?.id) await api(`/dictation-sessions/${sessionId}/results/${current.id}/reveal`, { method: 'POST' })
    setResults(value => value.map((item, index) => index === position ? { ...item, revealed: true } : item))
  }

  function play() {
    const id = current?.audio_asset_id
    if (id) void new Audio(`/api/tts-assets/${id}/audio?v=${audioRevision}`).play()
  }

  async function changePronunciation(source: 'configured' | 'custom', regenerate = false) {
    if (!sessionId || !current?.id) return
    setPronunciationBusy(true)
    try {
      const updated = await api<{ pronunciation_source: 'configured' | 'custom'; audio_asset_id: string | null }>(
        `/dictation-sessions/${sessionId}/results/${current.id}/pronunciation`,
        { method: 'PATCH', body: JSON.stringify({ pronunciation_source: source, regenerate }) },
      )
      setResults(value => value.map((item, index) => index === position ? { ...item, pronunciation_source: updated.pronunciation_source, audio_asset_id: updated.audio_asset_id } : item))
      setAudioRevision(value => value + 1)
    } finally {
      setPronunciationBusy(false)
    }
  }

  if (!started) return <section className="dictation-page"><h1>开始默写</h1><VoiceSelection speakers={speakers} voices={selectedVoices} selectedSpeakerId={selectedSpeakerId} selectedVoiceId={selectedVoiceId} onSpeakerChange={id => { setSelectedSpeakerId(id); setSelectedVoiceId('') }} onVoiceChange={setSelectedVoiceId} /><Button disabled={Boolean(selectedSpeakerId && !selectedVoiceId)} onClick={() => void start()}>开始默写</Button></section>

  const revealed = Boolean(current?.revealed)
  const completed = current?.result && current.result !== 'unscored'
  const audioReady = !wordListVersionId || Boolean(current?.audio_asset_id)
  const lockedLabel = snapshotNames.speaker && snapshotNames.voice ? `${snapshotNames.speaker} / ${snapshotNames.voice}` : '会话声音已锁定'
  const pronunciationValue = current?.pronunciation_source === 'configured' || !snapshotNames.voice ? 'configured' : 'custom'
  return <section className="dictation-page">
    <header className="dictation-exercise-header"><div><p className="date">第 {position + 1} / {words.length} 个</p><h1>单词默写</h1></div><img src="/animal-island/chat.svg" alt="" /></header>
    <section className="dictation-focus-card">
      <p className="listen-prompt">请先听发音，再写下单词。</p>
      <Button className="dictation-play-button" disabled={!audioReady} onClick={play}>{audioReady ? '播放发音' : '发音生成中'}</Button>
      {revealed ? <div className="answer-area is-revealed"><strong>{word}</strong></div> : <button className="answer-area is-hidden" aria-label="显示答案" onClick={() => void reveal()}><span>答案已隐藏</span><small>点击这里显示单词</small></button>}
      {revealed && <div className="dictation-actions"><Button disabled={completed} onClick={() => void score('correct')}>正确</Button><Button variant="danger" disabled={completed} onClick={() => void score('incorrect')}>错误</Button></div>}
    </section>
    <div className="dictation-navigation">
      <Button variant="secondary" disabled={position === 0} onClick={() => setPosition(value => value - 1)}>上一个</Button>
      <label>跳转到<select aria-label="跳转到题目" value={position} onChange={event => setPosition(Number(event.target.value))}>{words.map((_, index) => <option key={index} value={index}>第 {index + 1} 个{results[index]?.result && results[index].result !== 'unscored' ? '（已完成）' : ''}</option>)}</select></label>
      <Button variant="secondary" disabled={position === words.length - 1} onClick={() => setPosition(value => value + 1)}>下一个</Button>
    </div>
    {wordListVersionId && <details className="pronunciation-settings"><summary>发音设置</summary><div className="pronunciation-settings-content">
      <p>{lockedLabel}</p>
      <label>朗读使用人<select aria-label="朗读使用人" value={selectedSpeakerId} disabled><option value={selectedSpeakerId}>{snapshotNames.speaker ?? '会话声音已锁定'}</option></select></label>
      <label>声音版本<select aria-label="声音版本" value={selectedVoiceId} disabled><option value={selectedVoiceId}>{snapshotNames.voice ?? '会话声音已锁定'}</option></select></label>
      {sessionId && current?.word_item_id && <div className="pronunciation-controls"><label>当前单词发音<select aria-label="当前单词发音" disabled={pronunciationBusy} value={pronunciationValue} onChange={event => void changePronunciation(event.target.value as 'configured' | 'custom')}><option value="configured">原生发音</option>{snapshotNames.voice && <option value="custom">自定义声音</option>}</select></label><Button variant="secondary" disabled={pronunciationBusy} onClick={() => void changePronunciation(pronunciationValue, true)}>{pronunciationBusy ? '重新生成中' : pronunciationValue === 'custom' ? '重新生成自定义发音' : '重新生成原生发音'}</Button></div>}
    </div></details>}
  </section>
}

function VoiceSelection({ speakers, voices, selectedSpeakerId, selectedVoiceId, onSpeakerChange, onVoiceChange }: { speakers: Speaker[]; voices: Voice[]; selectedSpeakerId: string; selectedVoiceId: string; onSpeakerChange: (id: string) => void; onVoiceChange: (id: string) => void }) {
  return <><label>朗读使用人<select aria-label="朗读使用人" value={selectedSpeakerId} onChange={event => onSpeakerChange(event.target.value)}><option value="">使用默认声音</option>{speakers.map(speaker => <option key={speaker.id} value={speaker.id}>{speaker.display_name}</option>)}</select></label>{selectedSpeakerId && <label>声音版本<select aria-label="声音版本" value={selectedVoiceId} onChange={event => onVoiceChange(event.target.value)}><option value="">选择就绪版本</option>{voices.map(voice => <option key={voice.id} value={voice.id}>{voice.display_name}</option>)}</select></label>}</>
}
