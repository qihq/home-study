import { FormEvent, useState } from 'react'
import { ApiError } from '../../api/client'
import { DictionaryResult, DictionaryResultCard } from './DictionaryResultCard'

export type PlaybackSource = 'standard' | 'human' | 'configured' | 'custom'
export type PlaybackOutcome = 'standard_audio' | 'human_recording' | 'configured_tts' | 'voice_clone'
export type PlayOptions = {
  source: PlaybackSource
  voice_version_id?: string
  regenerate: boolean
  accent: 'uk' | 'us'
}

const OUTCOME_LABELS: Record<PlaybackOutcome, string> = {
  standard_audio: '标准发音',
  human_recording: '真人录音',
  configured_tts: 'AI 生成发音',
  voice_clone: '克隆声音发音',
}

const BUSY_LABELS: Record<PlaybackSource, string> = {
  standard: '标准发音加载中',
  human: '真人录音加载中',
  configured: 'AI 发音生成中',
  custom: '克隆声音生成中',
}

type DictionaryPageProps = {
  onLookup: (request: { text: string; source_language: 'auto' | 'en' | 'zh' }) => Promise<DictionaryResult>
  onPlay?: (entryId: string, options: PlayOptions) => Promise<PlaybackOutcome> | void
  onStreamPlay?: (text: string) => Promise<void> | void
  onMarkUnknown: (entryId: string) => Promise<void> | void
  onOpenUnknownItems?: () => void
  voices?: Array<{ id: string; display_name: string }>
}

export function DictionaryPage({
  onLookup,
  onPlay,
  onStreamPlay,
  onMarkUnknown,
  onOpenUnknownItems,
  voices = [],
}: DictionaryPageProps) {
  const [text, setText] = useState('')
  const [direction, setDirection] = useState<'auto' | 'en' | 'zh'>('auto')
  const [result, setResult] = useState<DictionaryResult | null>(null)
  const [message, setMessage] = useState('')
  const [playbackSource, setPlaybackSource] = useState<PlaybackSource>('standard')
  const [voiceVersionId, setVoiceVersionId] = useState('')
  const [audioBusySource, setAudioBusySource] = useState<PlaybackSource | null>(null)
  const [accent, setAccent] = useState<'uk' | 'us'>('us')

  const lookup = async (event: FormEvent) => {
    event.preventDefault()
    if (!text.trim()) return
    try {
      setResult(await onLookup({ text: text.trim(), source_language: direction }))
      setMessage('')
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : '查询失败，请稍后重试。')
    }
  }

  const canUseHuman = result?.source_language === 'en' && result.item_type === 'word'
  // Keep the user's human-recording preference for the next eligible English
  // word, while presenting and using standard audio for ineligible results.
  const selectedPlaybackSource: PlaybackSource = playbackSource === 'human' && !canUseHuman
    ? 'standard'
    : playbackSource

  const play = async (regenerate = false) => {
    if (!result || audioBusySource) return
    const spokenText = result.source_language === 'en' ? result.source_text : result.primary_translation
    const isWord = result.item_type === 'word'
    const source = selectedPlaybackSource
    const voiceId = source === 'custom' ? voiceVersionId || undefined : undefined
    if (!regenerate && source !== 'custom' && !isWord && onStreamPlay) {
      setAudioBusySource(source)
      try {
        await onStreamPlay(spokenText)
        setMessage('正在播放发音。')
      } catch {
        setMessage('播放失败，请检查英语发音服务配置。')
      } finally {
        setAudioBusySource(null)
      }
      return
    }
    if (!onPlay) return
    setAudioBusySource(source)
    try {
      const outcome = await onPlay(result.entry_id, {
        source,
        voice_version_id: voiceId,
        regenerate,
        accent,
      })
      if (regenerate) setMessage('新发音已生成并播放。')
      else if (outcome) setMessage(`正在播放${OUTCOME_LABELS[outcome]}。`)
      else setMessage('正在播放发音。')
    } catch (error) {
      setMessage(
        regenerate
          ? error instanceof ApiError ? error.message : '重新生成失败，原发音仍可继续使用。'
          : error instanceof ApiError ? error.message : '播放失败，请检查英语发音服务配置。',
      )
    } finally {
      setAudioBusySource(null)
    }
  }

  return <section className="dictionary-page">
    <header>
      <h1>辞典</h1>
      <p>支持单词、短语和完整句子。</p>
      {onOpenUnknownItems && <button className="dictionary-unknown-link" onClick={onOpenUnknownItems}>查看生词本</button>}
    </header>
    <form onSubmit={event => void lookup(event)}>
      <label>翻译方向
        <select aria-label="翻译方向" value={direction} onChange={event => setDirection(event.target.value as typeof direction)}>
          <option value="auto">自动</option>
          <option value="en">英译中</option>
          <option value="zh">中译英</option>
        </select>
      </label>
      <label>查询内容
        <textarea value={text} maxLength={2000} onChange={event => setText(event.target.value)} placeholder="输入单词、短语或句子" />
      </label>
      <button type="submit">查询</button>
    </form>
    {result && <div className="dictionary-voice">
      <label>朗读声音
        <select
          aria-label="朗读声音"
          value={selectedPlaybackSource}
          onChange={event => setPlaybackSource(event.target.value as PlaybackSource)}
        >
          <option value="standard">标准发音（默认）</option>
          <option value="human" disabled={!canUseHuman}>真人录音</option>
          <option value="configured">AI 生成（接口音色）</option>
          <option value="custom" disabled={voices.length === 0}>我的克隆声音</option>
        </select>
      </label>
      {selectedPlaybackSource === 'custom' && <label>克隆声音
        <select aria-label="克隆声音" value={voiceVersionId} onChange={event => setVoiceVersionId(event.target.value)}>
          <option value="">请选择已就绪声音</option>
          {voices.map(voice => <option key={voice.id} value={voice.id}>{voice.display_name}</option>)}
        </select>
      </label>}
    </div>}
    {message && <p role="status">{message}</p>}
    {result && <DictionaryResultCard
      result={result}
      accent={accent}
      onAccentChange={setAccent}
      audioBusy={audioBusySource !== null}
      audioBusyLabel={audioBusySource ? BUSY_LABELS[audioBusySource] : undefined}
      onPlay={onPlay ? () => void play() : undefined}
      onRegenerate={onPlay ? () => void play(true) : undefined}
      onMarkUnknown={entryId => void onMarkUnknown(entryId)}
    />}
  </section>
}
