export type DictionaryResult = {
  source_language: 'en' | 'zh'
  target_language: 'en' | 'zh'
  item_type: 'word' | 'phrase' | 'sentence'
  source_text: string
  primary_translation: string
  phonetic: string | null
  parts_of_speech: Array<{ part: string; meaning: string }>
  alternatives: string[]
  examples: Array<{ source: string; translation: string }>
  usage_note: string | null
  cache_hit: boolean
  entry_id: string
}

export function DictionaryResultCard({ result, onPlay, onMarkUnknown }: { result: DictionaryResult; onPlay?: (text: string) => void; onMarkUnknown: (entryId: string) => void }) {
  const english = result.source_language === 'en' ? result.source_text : result.primary_translation
  return <article className="dictionary-result"><p className="ai-disclaimer">AI 生成，请家长核对</p>{result.cache_hit && <p className="cache-hit">已命中缓存</p>}<h2>{result.primary_translation}</h2>{result.phonetic && <p>{result.phonetic}</p>}<p>类型：{result.item_type}</p>{result.parts_of_speech.map(item => <p key={`${item.part}-${item.meaning}`}><strong>{item.part}</strong> {item.meaning}</p>)}<div className="result-actions"><button disabled={!onPlay} title={onPlay ? undefined : '音频生成尚未可用'} onClick={() => onPlay?.(english)}>{onPlay ? '播放英文' : '音频尚未可用'}</button><button onClick={() => onMarkUnknown(result.entry_id)}>标记不认识</button></div></article>
}
