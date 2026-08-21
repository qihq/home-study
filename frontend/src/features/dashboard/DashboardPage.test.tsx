import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DashboardPage } from './DashboardPage'

it('renders today reading actions when both tasks are incomplete', () => {
  render(<DashboardPage summary={{ chinese: 'pending', english: 'pending', skating: 'pending', streak: 3, weeklyRate: 75 }} />)
  expect(screen.getByRole('button', { name: '开始中文阅读' })).toBeVisible()
  expect(screen.getByRole('button', { name: '开始英文阅读' })).toBeVisible()
  expect(screen.getByRole('button', { name: '开始花滑录制' })).toBeVisible()
})

it('shows a recoverable recording action', () => {
  render(<DashboardPage summary={{ chinese: 'pending', english: 'pending', skating: 'pending', streak: 0, weeklyRate: 0 }} recoveryLanguage="english" />)
  expect(screen.getByRole('button', { name: '恢复英文阅读录制' })).toBeVisible()
})

it('shows a completed skating card without a record action', () => {
  render(<DashboardPage summary={{ chinese: 'pending', english: 'pending', skating: 'complete', streak: 0, weeklyRate: 0 }} />)
  expect(screen.getByText('花滑录制')).toBeVisible()
  expect(screen.queryByRole('button', { name: '开始花滑录制' })).not.toBeInTheDocument()
})

it('opens the video library from a completed card', async () => {
  const user = userEvent.setup()
  const onOpenVideos = vi.fn()
  render(<DashboardPage summary={{ chinese: 'complete', english: 'pending', skating: 'pending', streak: 1, weeklyRate: 50 }} onOpenVideos={onOpenVideos} />)
  await user.click(screen.getByRole('button', { name: '查看视频' }))
  expect(onOpenVideos).toHaveBeenCalledOnce()
})
