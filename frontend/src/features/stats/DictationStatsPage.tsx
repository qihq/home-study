export type DailyDictation = { date: string; correct: number; incorrect: number; accuracy: number }
export type Mistake = { word: string; normalized_text: string; incorrect_count: number; correct_count: number }
export type DictationStats = {
  daily: DailyDictation[]
  accuracy: number | null
  word_accuracy: number | null
  phrase_accuracy: number | null
  sentence_accuracy: number | null
  unknown_items: { added_this_week: number; mastered_this_week: number }
  dictionary_cache_hits: number
}

function percent(value: number | null) {
  return value === null ? '—' : `${Math.round(value * 100)}%`
}

export function DictationStatsPage({ stats, mistakes, onReview }: { stats: DictationStats; mistakes: Mistake[]; onReview?: (words: string[]) => void }) {
  const { daily } = stats
  const latest = daily.at(-1)
  return <section className="dictation-stats"><header><p className="date">单词统计</p><h1>错词，都是下一次的重点</h1></header><div className="stats-grid"><article><p>最近正确率</p><strong>{latest ? percent(latest.accuracy) : '—'}</strong></article><article><p>累计错词</p><strong>{mistakes.length}</strong></article><article><p>总正确率</p><strong>{percent(stats.accuracy)}</strong></article><article><p>单词正确率</p><strong>{percent(stats.word_accuracy)}</strong></article><article><p>短语正确率</p><strong>{percent(stats.phrase_accuracy)}</strong></article><article><p>句子正确率</p><strong>{percent(stats.sentence_accuracy)}</strong></article><article><p>本周新增生词</p><strong>{stats.unknown_items.added_this_week}</strong></article><article><p>本周掌握生词</p><strong>{stats.unknown_items.mastered_this_week}</strong></article><article><p>词典缓存命中</p><strong>{stats.dictionary_cache_hits}</strong></article></div><h2>错词本</h2><div className="mistake-list">{mistakes.map(item => <label key={item.normalized_text}><input type="checkbox" value={item.normalized_text} /> <strong>{item.word}</strong><span>错 {item.incorrect_count} 次</span></label>)}</div>{mistakes.length > 0 && <button onClick={() => onReview?.(mistakes.map(item => item.normalized_text))}>生成复习列表</button>}</section>
}
