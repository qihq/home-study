import { useEffect, useMemo, useState } from 'react'
import type { RecordingItem } from './VideoLibrary'

type Props = {
  recordings: RecordingItem[]
  selectedDate: string | null
  onSelectDate: (date: string) => void
  onShowAll: () => void
}

const dateKey = (year: number, month: number, day: number) => `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`

export function RecordingCalendar({ recordings, selectedDate, onSelectDate, onShowAll }: Props) {
  const initial = selectedDate ?? recordings.map(item => item.reading_date).sort().at(-1) ?? dateKey(new Date().getFullYear(), new Date().getMonth(), new Date().getDate())
  const [year, initialMonth] = initial.split('-').map(Number)
  const [visibleMonth, setVisibleMonth] = useState(() => new Date(year, initialMonth - 1, 1))
  const counts = useMemo(() => recordings.reduce<Record<string, { chinese: number; english: number }>>((result, item) => {
    const day = result[item.reading_date] ?? { chinese: 0, english: 0 }
    day[item.language_type] += 1
    result[item.reading_date] = day
    return result
  }, {}), [recordings])

  useEffect(() => {
    if (!selectedDate) return
    const [selectedYear, selectedMonth] = selectedDate.split('-').map(Number)
    setVisibleMonth(new Date(selectedYear, selectedMonth - 1, 1))
  }, [selectedDate])

  const currentYear = visibleMonth.getFullYear()
  const currentMonth = visibleMonth.getMonth()
  const leadingCells = new Date(currentYear, currentMonth, 1).getDay()
  const days = new Date(currentYear, currentMonth + 1, 0).getDate()
  const today = new Date()
  const todayKey = dateKey(today.getFullYear(), today.getMonth(), today.getDate())
  const moveMonth = (amount: number) => setVisibleMonth(value => new Date(value.getFullYear(), value.getMonth() + amount, 1))

  return <section className="recording-calendar" aria-label="视频打卡日历">
    <header><button aria-label="上个月" onClick={() => moveMonth(-1)}>‹</button><h2>{currentYear}年{currentMonth + 1}月</h2><button aria-label="下个月" onClick={() => moveMonth(1)}>›</button></header>
    <div className="recording-calendar-weekdays" aria-hidden="true">{['日', '一', '二', '三', '四', '五', '六'].map(day => <span key={day}>{day}</span>)}</div>
    <div className="recording-calendar-grid">
      {Array.from({ length: leadingCells }, (_, index) => <span className="calendar-spacer" key={`spacer-${index}`} />)}
      {Array.from({ length: days }, (_, index) => {
        const day = index + 1
        const key = dateKey(currentYear, currentMonth, day)
        const count = counts[key]
        const details = [count?.chinese ? `中文${count.chinese}个` : '', count?.english ? `英文${count.english}个` : ''].filter(Boolean).join('，')
        const label = `${currentYear}年${currentMonth + 1}月${day}日${details ? `，${details}` : '，没有视频'}`
        return <button key={key} aria-label={label} aria-pressed={selectedDate === key} className={`${count ? 'has-recording' : ''} ${selectedDate === key ? 'is-selected' : ''} ${todayKey === key ? 'is-today' : ''}`} onClick={() => onSelectDate(key)}>
          <span>{day}</span><small>{count?.chinese ? <i className="calendar-dot chinese">中</i> : null}{count?.english ? <i className="calendar-dot english">英</i> : null}</small>
        </button>
      })}
    </div>
    <button className="calendar-show-all" onClick={onShowAll}>显示全部</button>
  </section>
}
