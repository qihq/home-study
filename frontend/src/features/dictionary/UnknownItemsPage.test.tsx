import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { UnknownItemsPage } from './UnknownItemsPage'

const unknownItems = [
  { id: 'unknown-1', item_type: 'word' as const, source_text: 'apple', translation_text: '苹果', status: 'unknown' as const },
  { id: 'unknown-2', item_type: 'sentence' as const, source_text: 'I like apples.', translation_text: '我喜欢苹果。', status: 'mastered' as const },
]

it('filters unknown items, changes mastery, and creates a learning list from selected items', async () => {
  const user = userEvent.setup()
  const onLoad = vi.fn().mockResolvedValue(unknownItems)
  const onUpdateStatus = vi.fn().mockResolvedValue(undefined)
  const onCreateLearningList = vi.fn().mockResolvedValue({ id: 'list-1', status: 'draft' })
  render(<UnknownItemsPage onLoad={onLoad} onUpdateStatus={onUpdateStatus} onCreateLearningList={onCreateLearningList} />)

  expect(await screen.findByText('apple')).toBeVisible()
  await user.selectOptions(screen.getByLabelText('类型筛选'), 'word')
  expect(onLoad).toHaveBeenLastCalledWith({ status: 'unknown', item_type: 'word' })
  await user.click(screen.getByRole('button', { name: '标记已掌握' }))
  expect(onUpdateStatus).toHaveBeenCalledWith('unknown-1', 'mastered')

  await user.selectOptions(screen.getByLabelText('状态筛选'), 'mastered')
  expect(onLoad).toHaveBeenLastCalledWith({ status: 'mastered', item_type: 'word' })
  await user.selectOptions(screen.getByLabelText('类型筛选'), 'all')
  expect(await screen.findByText('I like apples.')).toBeVisible()
  await user.click(screen.getByRole('button', { name: '恢复不认识' }))
  expect(onUpdateStatus).toHaveBeenCalledWith('unknown-2', 'unknown')

  await user.click(screen.getByLabelText('选择 apple'))
  await user.click(screen.getByRole('button', { name: '创建学习列表（1）' }))
  expect(onCreateLearningList).toHaveBeenCalledWith(['unknown-1'])
})

it('deletes an unknown item after confirmation and refreshes the list', async () => {
  const user = userEvent.setup()
  const onLoad = vi.fn().mockResolvedValueOnce([unknownItems[0]]).mockResolvedValueOnce([])
  const onDelete = vi.fn().mockResolvedValue(undefined)
  vi.spyOn(window, 'confirm').mockReturnValue(true)

  render(<UnknownItemsPage onLoad={onLoad} onUpdateStatus={vi.fn()} onCreateLearningList={vi.fn()} onDelete={onDelete} />)
  await user.click(await screen.findByRole('button', { name: '删除 apple' }))

  expect(onDelete).toHaveBeenCalledWith('unknown-1')
  expect(onLoad).toHaveBeenCalledTimes(1)
  expect(screen.queryByText('apple')).not.toBeInTheDocument()
})
