export type ReadingStats = {
  combined_rate: number
  current_dual_streak: number
  chinese: { duration_ms: number }
  english: { duration_ms: number }
  calendar: Array<{ date: string; chinese: boolean; english: boolean }>
}

function minutes(milliseconds: number) { return Math.round(milliseconds / 60_000) }

export function ReadingStatsPage({ stats }: { stats: ReadingStats }) {
  return <section className="stats-page"><header><p className="date">阅读统计</p><h1>看见每天的积累</h1></header><div className="stats-grid"><article><p>综合完成率</p><strong>{Math.round(stats.combined_rate * 100)}%</strong></article><article><p>当前连续打卡</p><strong>{stats.current_dual_streak} 天</strong></article><article><p>中文阅读</p><strong>{minutes(stats.chinese.duration_ms)} 分钟</strong></article><article><p>英文阅读</p><strong>{minutes(stats.english.duration_ms)} 分钟</strong></article></div><div className="calendar" aria-label="阅读日历">{stats.calendar.map(day => <div key={day.date} className={day.chinese && day.english ? 'calendar-day complete' : 'calendar-day'}><span>{day.date.slice(-2)}</span><small>{day.chinese ? '中' : '·'} {day.english ? '英' : '·'}</small></div>)}</div></section>
}
