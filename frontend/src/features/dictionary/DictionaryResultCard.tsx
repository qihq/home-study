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
  result_source?: 'ecdict' | 'cc-cedict' | 'ai'
  source_attribution?: string | null
}

export function DictionaryResultCard({ result, onPlay, onRegenerate, audioBusy = false, onMarkUnknown }: { result: DictionaryResult; onPlay?: (text: string) => void; onRegenerate?: () => void; audioBusy?: boolean; onMarkUnknown: (entryId: string) => void }) {
  const english = result.source_language === 'en' ? result.source_text : result.primary_translation
  const sourceLabel = result.result_source === 'ecdict' ? '本地词典 · ECDICT' : result.result_source === 'cc-cedict' ? '本地词典 · CC-CEDICT' : 'AI 生成，请家长核对'
  return <article className="dictionary-result"><p className={result.result_source === 'ecdict' || result.result_source === 'cc-cedict' ? 'dictionary-source' : 'ai-disclaimer'} title={result.source_attribution ?? undefined}>{sourceLabel}</p>{result.cache_hit && <p className="cache-hit">已命中缓存</p>}<p className="dictionary-query">{result.source_text}</p><h2>{result.primary_translation}</h2>{result.phonetic && <p className="dictionary-phonetic">{result.phonetic}</p>}<p>类型：{result.item_type}</p>{result.parts_of_speech.length > 0 && <section className="dictionary-detail-section"><h3>词性与释义</h3>{result.parts_of_speech.map(item => <p key={`${item.part}-${item.meaning}`}><strong>{item.part}</strong> {item.meaning}</p>)}</section>}{result.alternatives.length > 0 && <section className="dictionary-detail-section"><h3>其他释义</h3><ul>{result.alternatives.map(item => <li key={item}>{item}</li>)}</ul></section>}{result.usage_note && <section className="dictionary-detail-section"><h3>英文释义 / 用法提示</h3>{result.usage_note.split('\n').filter(Boolean).map(line => <p key={line}>{line}</p>)}</section>}{result.examples.length > 0 && <section className="dictionary-detail-section"><h3>双语例句</h3>{result.examples.map(example => <blockquote key={`${example.source}-${example.translation}`}><p>{example.source}</p><footer>{example.translation}</footer></blockquote>)}</section>}<div className="result-actions"><button disabled={!onPlay || audioBusy} title={onPlay ? undefined : '音频生成尚未可用'} onClick={() => onPlay?.(english)}>{audioBusy ? '发音处理中' : onPlay ? '播放发音' : '音频尚未可用'}</button>{onRegenerate && <button disabled={audioBusy} onClick={onRegenerate}>重新生成发音</button>}<button onClick={() => onMarkUnknown(result.entry_id)}>标记不认识</button></div></article>
}
