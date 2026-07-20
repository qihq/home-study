import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RecordingCalendar } from './RecordingCalendar'

const recordings = [
  { id: '1', reading_date: '2026-07-12', language_type: 'chinese' as const, status: 'ready', is_official: true, duration_ms: 1000, download_ready: true },
  { id: '2', reading_date: '2026-07-12', language_type: 'english' as const, status: 'ready', is_official: false, duration_ms: 1000, download_ready: true },
  { id: '3', reading_date: '2026-08-03', language_type: 'english' as const, status: 'ready', is_official: true, duration_ms: 1000, download_ready: true },
]

it('marks Chinese and English recordings and navigates between months', async () => {
  const user = userEvent.setup()
  render(<RecordingCalendar recordings={recordings} selectedDate="2026-07-12" onSelectDate={() => undefined} onShowAll={() => undefined} />)

  expect(screen.getByRole('button', { name: '2026年7月12日，中文1个，英文1个' })).toBeVisible()
  await user.click(screen.getByRole('button', { name: '下个月' }))
  expect(screen.getByText('2026年8月')).toBeVisible()
  expect(screen.getByRole('button', { name: '2026年8月3日，英文1个' })).toBeVisible()
})

it('selects a marked date and can clear the date filter', async () => {
  const user = userEvent.setup()
  const onSelectDate = vi.fn()
  const onShowAll = vi.fn()
  render(<RecordingCalendar recordings={recordings} selectedDate="2026-07-12" onSelectDate={onSelectDate} onShowAll={onShowAll} />)

  await user.click(screen.getByRole('button', { name: '2026年7月12日，中文1个，英文1个' }))
  await user.click(screen.getByRole('button', { name: '显示全部' }))
  expect(onSelectDate).toHaveBeenCalledWith('2026-07-12')
  expect(onShowAll).toHaveBeenCalledOnce()
})
