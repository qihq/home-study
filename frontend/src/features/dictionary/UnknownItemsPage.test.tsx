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
  expect(onLoad).toHaveBeenLastCalledWith({ status: 'unknown', item_type: 'word', sort: 'recent' })
  await user.click(screen.getByRole('button', { name: '标记已掌握' }))
  expect(onUpdateStatus).toHaveBeenCalledWith('unknown-1', 'mastered')

  await user.selectOptions(screen.getByLabelText('状态筛选'), 'mastered')
  expect(onLoad).toHaveBeenLastCalledWith({ status: 'mastered', item_type: 'word', sort: 'recent' })
  await user.selectOptions(screen.getByLabelText('类型筛选'), 'all')
  expect(await screen.findByText('I like apples.')).toBeVisible()
  await user.click(screen.getByRole('button', { name: '恢复不认识' }))
  expect(onUpdateStatus).toHaveBeenCalledWith('unknown-2', 'unknown')

  await user.click(screen.getByLabelText('选择 apple'))
  await user.click(screen.getByRole('button', { name: '生成学习本（1）' }))
  expect(onCreateLearningList).toHaveBeenCalledWith(['unknown-1'], expect.stringMatching(/^生词复习/))
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

it('sorts by word frequency and renders dictionary tags', async () => {
  const user = userEvent.setup()
  const onLoad = vi.fn().mockResolvedValue([{ ...unknownItems[0], word_tags: ['中考', '柯林斯3星'] }])
  render(<UnknownItemsPage onLoad={onLoad} onUpdateStatus={vi.fn()} onCreateLearningList={vi.fn()} />)

  expect(await screen.findByText('中考')).toBeVisible()
  expect(screen.getByText('柯林斯3星')).toBeVisible()
  await user.selectOptions(screen.getByLabelText('排序'), 'importance')
  expect(onLoad).toHaveBeenLastCalledWith({ status: 'unknown', item_type: 'all', sort: 'importance' })
})

it('opens the generated learning-book tab after creating a list from unknown items', async () => {
  const user = userEvent.setup()
  const onLoadLearningLists = vi.fn().mockResolvedValue([
    { id: 'list-1', title: '七月生词', status: 'draft', created_at: '2026-07-21T09:00:00Z', items: [{ display_text: 'apple', item_type: 'word', translation_text: '苹果' }] },
  ])
  const onCreateLearningList = vi.fn().mockResolvedValue({ id: 'list-1', status: 'draft' })
  render(<UnknownItemsPage onLoad={vi.fn().mockResolvedValue([unknownItems[0]])} onUpdateStatus={vi.fn()} onCreateLearningList={onCreateLearningList} onLoadLearningLists={onLoadLearningLists} />)

  await user.click(await screen.findByLabelText('选择 apple'))
  await user.clear(screen.getByLabelText('学习本名称'))
  await user.type(screen.getByLabelText('学习本名称'), '七月生词')
  await user.click(screen.getByRole('button', { name: '生成学习本（1）' }))

  expect(onCreateLearningList).toHaveBeenCalledWith(['unknown-1'], '七月生词')
  expect(await screen.findByRole('tab', { name: '生成的学习本' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByRole('tab', { name: /七月生词/ })).toBeVisible()
  expect(screen.getByText('苹果')).toBeVisible()
})
