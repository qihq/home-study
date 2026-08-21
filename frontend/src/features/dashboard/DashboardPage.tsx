import { Button } from '../../ui/Button'

export type DashboardSummary = {
  chinese: 'pending' | 'complete' | 'processing'
  english: 'pending' | 'complete' | 'processing'
  skating: 'pending' | 'complete' | 'processing'
  streak: number
  weeklyRate: number
}

const readingCopy = { chinese: '中文阅读', english: '英文阅读', skating: '花滑录制' } as const
const cardStateCopy = { pending: '等待开始', complete: '已完成', processing: '正在处理' } as const

export function DashboardPage({ summary, onRecord, onDictation, onOpenVideos, recoveryLanguage }: { summary: DashboardSummary; onRecord?: (language: keyof typeof readingCopy) => void; onDictation?: () => void; onOpenVideos?: () => void; recoveryLanguage?: keyof typeof readingCopy }) {
  return <section className="dashboard">
    <header className="page-header island-hero"><div><p className="date">今天的学习岛</p><h1>陪孩子，慢慢积累</h1><p>阅读一点，记住一点，每天都在长大。</p></div><img src="/animal-island/animal-icon.png" alt="两只欢迎学习的小岛伙伴" /></header>
    <div className="reading-grid">
      {(Object.keys(readingCopy) as Array<keyof typeof readingCopy>).map((language) => {
        const state = summary[language]
        return <article className={`task-card ${language}`} key={language}>
          <div><p className="task-label">{readingCopy[language]}</p><h2>{cardStateCopy[state]}</h2></div>
          {state === 'pending' ? <Button onClick={() => onRecord?.(language)}>开始{readingCopy[language]}</Button> : <Button variant="secondary" onClick={onOpenVideos}>查看视频</Button>}
        </article>
      })}
    </div>
    {recoveryLanguage && <section className="recovery-card"><p>检测到未完成的{readingCopy[recoveryLanguage]}录像。</p><Button variant="secondary" onClick={() => onRecord?.(recoveryLanguage)}>恢复{readingCopy[recoveryLanguage]}录制</Button></section>}
    <section className="overview"><article><p>连续打卡</p><strong>{summary.streak}<small> 天</small></strong></article><article><p>本周完成率</p><strong>{summary.weeklyRate}<small>%</small></strong></article><article className="dictation-card"><div><p>单词默写</p><h2>准备好开始了吗？</h2></div><Button onClick={onDictation}>开始默写</Button></article></section>
  </section>
}
