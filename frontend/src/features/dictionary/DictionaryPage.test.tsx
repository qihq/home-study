import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { DictionaryPage } from './DictionaryPage'

it('supports automatic and manual directions, playback, unknown marking, and cache feedback', async () => {
  const user = userEvent.setup()
  const onLookup = vi.fn().mockResolvedValue({
    source_language: 'zh', target_language: 'en', item_type: 'sentence', source_text: '我喜欢苹果。',
    primary_translation: 'I like apples.', phonetic: null, parts_of_speech: [], alternatives: [], examples: [],
    usage_note: null, cache_hit: true, entry_id: 'entry-1',
  })
  const onPlay = vi.fn()
  const onMarkUnknown = vi.fn()
  render(<DictionaryPage onLookup={onLookup} onPlay={onPlay} onMarkUnknown={onMarkUnknown} voices={[{ id: 'voice-1', display_name: '妈妈 / 清晰美音' }]} />)

  await user.type(screen.getByLabelText('查询内容'), '我喜欢苹果。')
  await user.click(screen.getByRole('button', { name: '查询' }))

  expect(onLookup).toHaveBeenCalledWith({ text: '我喜欢苹果。', source_language: 'auto' })
  expect(await screen.findByText('I like apples.')).toBeVisible()
  expect(screen.getByText('已命中缓存')).toBeVisible()
  await user.selectOptions(screen.getByLabelText('朗读声音'), 'voice-1')
  await user.click(screen.getByRole('button', { name: '播放发音' }))
  await user.click(screen.getByRole('button', { name: '标记不认识' }))
  expect(onPlay).toHaveBeenCalledWith('entry-1', 'voice-1')
  expect(onMarkUnknown).toHaveBeenCalledWith('entry-1')

  await user.selectOptions(screen.getByLabelText('翻译方向'), 'zh')
  await user.click(screen.getByRole('button', { name: '查询' }))
  expect(onLookup).toHaveBeenLastCalledWith({ text: '我喜欢苹果。', source_language: 'zh' })
})

it('limits input to 2,000 characters and plays English with the selected ready voice', async () => {
  const user = userEvent.setup()
  const onLookup = vi.fn().mockResolvedValue({
    source_language: 'en', target_language: 'zh', item_type: 'word', source_text: 'apple',
    primary_translation: '苹果', phonetic: null, parts_of_speech: [], alternatives: [], examples: [],
    usage_note: null, cache_hit: false, entry_id: 'entry-1',
  })
  const onPlay = vi.fn().mockResolvedValue(undefined)
  render(<DictionaryPage
    onLookup={onLookup}
    onPlay={onPlay}
    onMarkUnknown={vi.fn()}
    voices={[{ id: 'voice-1', display_name: '妈妈 / 清晰美音' }]}
  />)

  await user.click(screen.getByLabelText('查询内容'))
  await user.paste('a'.repeat(2_001))
  expect(screen.getByLabelText('查询内容')).toHaveValue('a'.repeat(2_000))
  await user.click(screen.getByRole('button', { name: '查询' }))
  await screen.findByText('苹果')
  await user.selectOptions(screen.getByLabelText('朗读声音'), 'voice-1')
  await user.click(screen.getByRole('button', { name: '播放发音' }))

  expect(onPlay).toHaveBeenCalledWith('entry-1', 'voice-1')
})

it('can force pronunciation regeneration while preserving the selected voice', async () => {
  const user = userEvent.setup()
  const onPlay = vi.fn().mockResolvedValue(undefined)
  render(<DictionaryPage onLookup={vi.fn().mockResolvedValue({
    entry_id: 'entry-apple', source_language: 'en', target_language: 'zh', item_type: 'word', source_text: 'apple',
    primary_translation: '苹果', phonetic: null, parts_of_speech: [], alternatives: [], examples: [], usage_note: null, cache_hit: false,
  })} onPlay={onPlay} onMarkUnknown={vi.fn()} voices={[{ id: 'voice-1', display_name: '妈妈 / 清晰美音' }]} />)

  await user.type(screen.getByLabelText('查询内容'), 'apple')
  await user.click(screen.getByRole('button', { name: '查询' }))
  await user.selectOptions(screen.getByLabelText('朗读声音'), 'voice-1')
  await user.click(screen.getByRole('button', { name: '重新生成发音' }))

  expect(onPlay).toHaveBeenCalledWith('entry-apple', 'voice-1', true)
  expect(screen.getByRole('status')).toHaveTextContent('新发音已生成并播放')
})

it('shows local dictionary provenance instead of an AI disclaimer', async () => {
  const user = userEvent.setup()
  render(<DictionaryPage onLookup={vi.fn().mockResolvedValue({
    entry_id: 'local-apple', source_language: 'en', target_language: 'zh', item_type: 'word', source_text: 'apple',
    primary_translation: '苹果', phonetic: "'æpl'", parts_of_speech: [], alternatives: [], examples: [], usage_note: null,
    cache_hit: false, result_source: 'ecdict', source_attribution: 'ECDICT (MIT)',
  })} onMarkUnknown={vi.fn()} />)

  await user.type(screen.getByLabelText('查询内容'), 'apple')
  await user.click(screen.getByRole('button', { name: '查询' }))

  expect(screen.getByText('本地词典 · ECDICT')).toBeVisible()
  expect(screen.queryByText('AI 生成，请家长核对')).not.toBeInTheDocument()
})
