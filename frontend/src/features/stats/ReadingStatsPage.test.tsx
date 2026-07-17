import { render, screen } from '@testing-library/react'
import { ReadingStatsPage } from './ReadingStatsPage'

it('shows reading rate and dual-language streak', () => {
  render(<ReadingStatsPage stats={{ combined_rate: 0.75, current_dual_streak: 4, chinese: { duration_ms: 60000 }, english: { duration_ms: 120000 }, calendar: [] }} />)
  expect(screen.getByText('75%')).toBeVisible()
  expect(screen.getByText('4 天')).toBeVisible()
})
