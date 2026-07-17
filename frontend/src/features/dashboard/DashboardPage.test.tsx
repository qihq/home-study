import { render, screen } from '@testing-library/react'
import { DashboardPage } from './DashboardPage'

it('renders today reading actions when both tasks are incomplete', () => {
  render(<DashboardPage summary={{ chinese: 'pending', english: 'pending', streak: 3, weeklyRate: 75 }} />)
  expect(screen.getByRole('button', { name: '开始中文阅读' })).toBeVisible()
  expect(screen.getByRole('button', { name: '开始英文阅读' })).toBeVisible()
})

it('shows a recoverable recording action', () => {
  render(<DashboardPage summary={{ chinese: 'pending', english: 'pending', streak: 0, weeklyRate: 0 }} recoveryLanguage="english" />)
  expect(screen.getByRole('button', { name: '恢复英文阅读录制' })).toBeVisible()
})
