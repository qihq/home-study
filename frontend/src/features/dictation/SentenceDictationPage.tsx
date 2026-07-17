import { useState } from 'react'

export function SentenceDictationPage({ items, onPlay, onScore }: {
  items: string[]
  onPlay: (text: string) => void
  onScore: (result: 'correct' | 'incorrect') => void
}) {
  const [position, setPosition] = useState(0)
  const [revealed, setRevealed] = useState(false)
  const item = items[position]
  const score = (result: 'correct' | 'incorrect') => {
    onScore(result); setRevealed(false); setPosition(current => Math.min(current + 1, items.length - 1))
  }
  return <section className="dictation-page"><p className="date">第 {position + 1} / {items.length} 个</p><h1>句子默写</h1><p className="listen-prompt">请先听发音，再手写句子。</p><div className="answer-area">{revealed ? <strong>{item}</strong> : <span>答案已隐藏</span>}</div><div className="dictation-actions"><button onClick={() => onPlay(item)}>播放发音</button><button onClick={() => setRevealed(true)}>显示答案</button>{revealed && <><button onClick={() => score('correct')}>正确</button><button onClick={() => score('incorrect')}>错误</button></>}</div></section>
}
