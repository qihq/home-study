import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { WordListEditor } from './WordListEditor'

vi.mock('../../api/client', () => ({ api: vi.fn() }))
import { api } from '../../api/client'

beforeEach(() => { vi.mocked(api).mockResolvedValue([]) })

async function openCreateLearningBook(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('tab', { name: '创建学习本' }))
}

it('separates saved learning books from the create flow with tabs', async () => {
  vi.mocked(api).mockImplementation(async (path: string) => {
    if (path === '/health') return { worker: true }
    if (path === '/word-lists') return [{
      id: 'list-1', title: 'Unit 1', status: 'confirmed', source_type: 'paste', word_list_version_id: 'version-1', items: ['apple'], tts_progress: null,
    }]
    throw new Error(`Unexpected API call: ${path}`)
  })
  const user = userEvent.setup()
  render(<WordListEditor onConfirm={vi.fn()} />)

  expect(await screen.findByText('Unit 1')).toBeVisible()
  expect(screen.queryByLabelText('粘贴单词')).not.toBeInTheDocument()
  await openCreateLearningBook(user)
  expect(screen.getByLabelText('粘贴单词')).toBeVisible()
  expect(screen.getByRole('tab', { name: '图片识别' })).toBeVisible()
})

it('shows parsed words for parent confirmation before creating a list', async () => {
  const user = userEvent.setup()
  render(<WordListEditor onConfirm={vi.fn()} />)
  await openCreateLearningBook(user)
  await user.type(screen.getByLabelText('粘贴单词'), 'Apple\napple\nbanana')
  await user.click(screen.getByRole('button', { name: '整理内容' }))
  expect(screen.getByDisplayValue('Apple')).toBeVisible()
  expect(screen.getByDisplayValue('banana')).toBeVisible()
})

it('only shows the active create source controls', async () => {
  const user = userEvent.setup()
  render(<WordListEditor onConfirm={vi.fn()} />)
  await openCreateLearningBook(user)
  expect(screen.queryByLabelText('上传单词表')).not.toBeInTheDocument()
  await user.click(screen.getByRole('tab', { name: '文件导入' }))
  expect(screen.getByLabelText('上传单词表')).toHaveAttribute('accept', '.txt,.csv,.xlsx,.docx,.pdf')
  expect(screen.queryByLabelText('粘贴单词')).not.toBeInTheDocument()
})

it('lets a parent edit an item type and translation before confirming a learning list', async () => {
  const user = userEvent.setup()
  render(<WordListEditor onConfirm={vi.fn()} />)
  await openCreateLearningBook(user)
  await user.type(screen.getByLabelText('粘贴单词'), 'I like apples.')
  await user.click(screen.getByRole('button', { name: '整理内容' }))
  await user.selectOptions(screen.getByLabelText('条目类型 1'), 'sentence')
  await user.type(screen.getByLabelText('翻译 1'), '我喜欢苹果。')
  expect(screen.getByLabelText('条目类型 1')).toHaveValue('sentence')
  expect(screen.getByLabelText('翻译 1')).toHaveValue('我喜欢苹果。')
})

it('shows saved-list TTS progress and warns when background processing is offline', async () => {
  vi.mocked(api).mockImplementation(async (path: string) => {
    if (path === '/health') return { worker: false }
    if (path === '/word-lists') return [{
      id: 'list-1', title: 'Unit 1', status: 'confirmed', source_type: 'paste', word_list_version_id: 'version-1',
      items: ['apple', 'banana'], tts_progress: { total: 2, ready: 0, queued: 2, running: 0, failed: 0, progress: 5 },
    }]
    throw new Error(`Unexpected API call: ${path}`)
  })

  render(<WordListEditor onConfirm={vi.fn()} />)

  expect(await screen.findByLabelText('Unit 1 本地发音进度')).toHaveValue(5)
  expect(screen.getByRole('alert')).toHaveTextContent('后台处理服务离线')
})

it('removes a saved learning-list card immediately after delete succeeds', async () => {
  const user = userEvent.setup()
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  vi.mocked(api).mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === '/health') return { worker: true }
    if (path === '/word-lists' && !init) return [{ id: 'list-1', title: '错误单词本', status: 'confirmed', source_type: 'paste', word_list_version_id: 'version-1', items: ['wrong'], tts_progress: null }]
    if (path === '/word-lists/list-1' && init?.method === 'DELETE') return undefined
    throw new Error(`Unexpected API call: ${path}`)
  })
  render(<WordListEditor onConfirm={vi.fn()} />)

  await user.click(await screen.findByRole('button', { name: '删除' }))

  expect(screen.queryByText('错误单词本')).not.toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent('已删除')
})

it('offers separate camera and photo-library inputs on mobile', async () => {
  const user = userEvent.setup()
  render(<WordListEditor onConfirm={vi.fn()} />)
  await openCreateLearningBook(user)
  await user.click(screen.getByRole('tab', { name: '图片识别' }))

  expect(screen.getByLabelText('拍照识别拼写测试')).toHaveAttribute('capture', 'environment')
  expect(screen.getByLabelText('从照片库选择拼写测试')).not.toHaveAttribute('capture')
})

it('shows a prominent save confirmation after OCR succeeds', async () => {
  const user = userEvent.setup()
  vi.mocked(api).mockImplementation(async (path: string) => {
    if (path === '/health') return { worker: true }
    if (path === '/word-lists') return []
    if (path === '/word-lists/recognize-image') return { words: ['apple', 'banana'] }
    throw new Error(`Unexpected API call: ${path}`)
  })
  render(<WordListEditor onConfirm={vi.fn()} />)
  await openCreateLearningBook(user)
  await user.click(screen.getByRole('tab', { name: '图片识别' }))

  await user.upload(screen.getByLabelText('从照片库选择拼写测试'), new File(['image'], 'spelling.jpg', { type: 'image/jpeg' }))

  expect(await screen.findByRole('button', { name: '保存为学习本' })).toBeVisible()
  expect(screen.getByText('识别结果：2 个单词。请检查后保存。')).toBeVisible()
})

it('lets a parent force one saved word to use native pronunciation', async () => {
  const user = userEvent.setup()
  vi.mocked(api).mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === '/health') return { worker: true }
    if (path === '/word-lists') return [{
      id: 'list-1', title: 'Unit 1', status: 'confirmed', source_type: 'paste', word_list_version_id: 'version-1', items: ['use'], tts_progress: null,
      item_details: [{ id: 'item-1', display_text: 'use', pronunciation_source: 'default', audio_ready: true }],
    }]
    if (path === '/word-items/item-1/pronunciation' && init?.method === 'PATCH') return { id: 'item-1', pronunciation_source: 'configured', audio_ready: false }
    throw new Error(`Unexpected API call: ${path}`)
  })
  render(<WordListEditor onConfirm={vi.fn()} />)

  await user.selectOptions(await screen.findByLabelText('use 发音来源'), 'configured')

  expect(api).toHaveBeenCalledWith('/word-items/item-1/pronunciation', expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ pronunciation_source: 'configured' }) }))
})
