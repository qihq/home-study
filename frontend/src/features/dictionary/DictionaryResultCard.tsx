export type DictionaryResult = {
  source_language: 'en' | 'zh'
  target_language: 'en' | 'zh'
  item_type: 'word' | 'phrase' | 'sentence'
  source_text: string
  primary_translation: string
  phonetic: string | null
  phonetic_uk?: string | null
  phonetic_us?: string | null
  word_tags?: string[]
  parts_of_speech: Array<{ part: string; meaning: string }>
  alternatives: string[]
  examples: Array<{ source: string; translation: string }>
  usage_note: string | null
  cache_hit: boolean
  entry_id: string
  result_source?: 'ecdict' | 'cc-cedict' | 'dictionaryapi' | 'youdao' | 'ai'
  source_attribution?: string | null
}

const SOURCE_LABELS = {
  ecdict: '本地词典 · ECDICT',
  'cc-cedict': '本地词典 · CC-CEDICT',
  dictionaryapi: '在线词典 · Free Dictionary',
  youdao: '在线词典 · 有道',
  ai: 'AI 生成，请家长核对',
} as const

export function DictionaryResultCard({ result, accent, onAccentChange, onPlay, onRegenerate, audioBusy = false, audioBusyLabel = '发音处理中', onMarkUnknown }: { result: DictionaryResult; accent?: 'uk' | 'us'; onAccentChange?: (accent: 'uk' | 'us') => void; onPlay?: (text: string) => void; onRegenerate?: () => void; audioBusy?: boolean; audioBusyLabel?: string; onMarkUnknown: (entryId: string) => void }) {
  const english = result.source_language === 'en' ? result.source_text : result.primary_translation
  const sourceLabel = SOURCE_LABELS[result.result_source ?? 'ai']
  const accentControl = result.source_language === 'en' && result.item_type === 'word' && onAccentChange
  const showDualPhonetics = Boolean(result.phonetic_uk || result.phonetic_us)
  return <article className="dictionary-result"><p className={result.result_source === 'ecdict' || result.result_source === 'cc-cedict' ? 'dictionary-source' : 'ai-disclaimer'} title={result.source_attribution ?? undefined}>{sourceLabel}</p>{result.cache_hit && <p className="cache-hit">已命中缓存</p>}{result.word_tags && result.word_tags.length > 0 && <div className="word-tags">{result.word_tags.map(tag => <span key={tag} className="word-tag">{tag}</span>)}</div>}<p className="dictionary-query">{result.source_text}</p><h2>{result.primary_translation}</h2>{showDualPhonetics ? <p className="dictionary-phonetic">{result.phonetic_uk && <span className="phonetic-variant">英 {result.phonetic_uk}</span>}{result.phonetic_us && <span className="phonetic-variant">美 {result.phonetic_us}</span>}</p> : result.phonetic && <p className="dictionary-phonetic">{result.phonetic}</p>}<p>类型：{result.item_type}</p>{result.parts_of_speech.length > 0 && <section className="dictionary-detail-section"><h3>词性与释义</h3>{result.parts_of_speech.map(item => <p key={`${item.part}-${item.meaning}`}><strong>{item.part}</strong> {item.meaning}</p>)}</section>}{result.alternatives.length > 0 && <section className="dictionary-detail-section"><h3>其他释义</h3><ul>{result.alternatives.map(item => <li key={item}>{item}</li>)}</ul></section>}{result.usage_note && <section className="dictionary-detail-section"><h3>英文释义 / 用法提示</h3>{result.usage_note.split('\n').filter(Boolean).map(line => <p key={line}>{line}</p>)}</section>}{result.examples.length > 0 && <section className="dictionary-detail-section"><h3>双语例句</h3>{result.examples.map(example => <blockquote key={`${example.source}-${example.translation}`}><p>{example.source}</p>{example.translation && <footer>{example.translation}</footer>}</blockquote>)}</section>}<div className="result-actions">{accentControl && <div className="accent-toggle" role="group" aria-label="发音口音"><button type="button" aria-pressed={accent === 'us'} className={accent === 'us' ? 'active' : undefined} onClick={() => onAccentChange('us')}>美音</button><button type="button" aria-pressed={accent === 'uk'} className={accent === 'uk' ? 'active' : undefined} onClick={() => onAccentChange('uk')}>英音</button></div>}<button disabled={!onPlay || audioBusy} title={onPlay ? undefined : '音频生成尚未可用'} onClick={() => onPlay?.(english)}>{onPlay && <img src="/animal-island/chat.svg" alt="" />}{audioBusy ? audioBusyLabel : onPlay ? '播放发音' : '音频尚未可用'}</button>{onRegenerate && <button disabled={audioBusy} onClick={onRegenerate}>重新生成发音</button>}<button onClick={() => onMarkUnknown(result.entry_id)}>标记不认识</button></div></article>
}
