import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { SentenceDictationPage } from './SentenceDictationPage'

it('keeps a sentence hidden until reveal and advances only after parent scoring', async () => {
  const user = userEvent.setup()
  const onPlay = vi.fn()
  const onScore = vi.fn()
  render(<SentenceDictationPage items={['I like apples.', 'I eat pears.']} onPlay={onPlay} onScore={onScore} />)

  expect(screen.queryByText('I like apples.')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '播放发音' }))
  expect(onPlay).toHaveBeenCalledWith('I like apples.')
  expect(screen.getByText('第 1 / 2 个')).toBeVisible()
  await user.click(screen.getByRole('button', { name: '显示答案' }))
  expect(screen.getByText('I like apples.')).toBeVisible()
  expect(screen.queryByRole('button', { name: '下一项' })).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '正确' }))
  expect(onScore).toHaveBeenCalledWith('correct')
  expect(screen.getByText('第 2 / 2 个')).toBeVisible()
})
