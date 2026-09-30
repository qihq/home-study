import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { ApiError } from '../../api/client'
import { DictionaryPage } from './DictionaryPage'

const WORD_RESULT = {
  source_language: 'en', target_language: 'zh', item_type: 'word', source_text: 'apple',
  primary_translation: '苹果', phonetic: null, parts_of_speech: [], alternatives: [], examples: [],
  usage_note: null, cache_hit: false, entry_id: 'entry-apple',
} as const

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
  expect(screen.queryByRole('group', { name: '发音口音' })).not.toBeInTheDocument()
  await user.selectOptions(screen.getByLabelText('朗读声音'), 'custom')
  await user.selectOptions(screen.getByLabelText('克隆声音'), 'voice-1')
  await user.click(screen.getByRole('button', { name: '播放发音' }))
  await user.click(screen.getByRole('button', { name: '标记不认识' }))
  expect(onPlay).toHaveBeenCalledWith('entry-1', { source: 'custom', voice_version_id: 'voice-1', regenerate: false, accent: 'us' })
  expect(onMarkUnknown).toHaveBeenCalledWith('entry-1')

  await user.selectOptions(screen.getByLabelText('翻译方向'), 'zh')
  await user.click(screen.getByRole('button', { name: '查询' }))
  expect(onLookup).toHaveBeenLastCalledWith({ text: '我喜欢苹果。', source_language: 'zh' })
})

it('limits input to 2,000 characters and plays English with the selected ready voice', async () => {
  const user = userEvent.setup()
  const onLookup = vi.fn().mockResolvedValue(WORD_RESULT)
  const onPlay = vi.fn().mockResolvedValue('voice_clone')
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
  await user.selectOptions(screen.getByLabelText('朗读声音'), 'custom')
  await user.selectOptions(screen.getByLabelText('克隆声音'), 'voice-1')
  await user.click(screen.getByRole('button', { name: '播放发音' }))

  expect(onPlay).toHaveBeenCalledWith('entry-apple', { source: 'custom', voice_version_id: 'voice-1', regenerate: false, accent: 'us' })
  expect(screen.getByRole('status')).toHaveTextContent('正在播放克隆声音发音')
})

it('switches between American and British accent for English words', async () => {  const user = userEvent.setup()
  const onPlay = vi.fn().mockResolvedValue('standard_audio')
  render(<DictionaryPage onLookup={vi.fn().mockResolvedValue(WORD_RESULT)} onPlay={onPlay} onMarkUnknown={vi.fn()} />)

  await user.type(screen.getByLabelText('查询内容'), 'apple')
  await user.click(screen.getByRole('button', { name: '查询' }))
  await screen.findByText('苹果')

  expect(screen.getByRole('button', { name: '美音' })).toHaveAttribute('aria-pressed', 'true')
  await user.click(screen.getByRole('button', { name: '英音' }))
  await user.click(screen.getByRole('button', { name: '播放发音' }))

  expect(screen.getByRole('button', { name: '英音' })).toHaveAttribute('aria-pressed', 'true')
  expect(onPlay).toHaveBeenCalledWith('entry-apple', { source: 'standard', voice_version_id: undefined, regenerate: false, accent: 'uk' })
})

it('defaults to standard pronunciation and offers human recording separately', async () => {
  const user = userEvent.setup()
  const onPlay = vi.fn().mockResolvedValue('standard_audio')
  render(<DictionaryPage onLookup={vi.fn().mockResolvedValue(WORD_RESULT)} onPlay={onPlay} onMarkUnknown={vi.fn()} />)

  await user.type(screen.getByLabelText('查询内容'), 'apple')
  await user.click(screen.getByRole('button', { name: '查询' }))
  await screen.findByText('苹果')

  expect(screen.getByLabelText('朗读声音')).toHaveValue('standard')
  expect(screen.getByRole('option', { name: '标准发音（默认）' })).toBeEnabled()
  await user.click(screen.getByRole('button', { name: '播放发音' }))
  expect(onPlay).toHaveBeenCalledWith('entry-apple', { source: 'standard', voice_version_id: undefined, regenerate: false, accent: 'us' })
  expect(screen.getByRole('status')).toHaveTextContent('正在播放标准发音')

  onPlay.mockResolvedValue('human_recording')
  await user.selectOptions(screen.getByLabelText('朗读声音'), 'human')
  await user.click(screen.getByRole('button', { name: '播放发音' }))
  expect(onPlay).toHaveBeenLastCalledWith('entry-apple', { source: 'human', voice_version_id: undefined, regenerate: false, accent: 'us' })
  expect(screen.getByRole('status')).toHaveTextContent('正在播放真人录音')

  onPlay.mockResolvedValue('configured_tts')
  await user.selectOptions(screen.getByLabelText('朗读声音'), 'configured')
  await user.click(screen.getByRole('button', { name: '播放发音' }))
  expect(onPlay).toHaveBeenLastCalledWith('entry-apple', { source: 'configured', voice_version_id: undefined, regenerate: false, accent: 'us' })
  expect(screen.getByRole('status')).toHaveTextContent('正在播放AI 生成发音')
})

it.each([
  {
    name: 'sentences',
    result: {
      source_language: 'en' as const, target_language: 'zh' as const, item_type: 'sentence' as const,
      source_text: 'I like apples.', primary_translation: '我喜欢苹果。', phonetic: null,
      parts_of_speech: [], alternatives: [], examples: [], usage_note: null, cache_hit: false, entry_id: 'entry-1',
    },
  },
  {
    name: 'Chinese words',
    result: {
      ...WORD_RESULT,
      entry_id: 'entry-chinese', source_language: 'zh' as const, target_language: 'en' as const,
      source_text: '苹果', primary_translation: 'apple',
    },
  },
])('disables human recordings for $name', async ({ result }) => {
  const user = userEvent.setup()
  render(<DictionaryPage onLookup={vi.fn().mockResolvedValue(result)} onMarkUnknown={vi.fn()} />)

  await user.type(screen.getByLabelText('查询内容'), result.source_text)
  await user.click(screen.getByRole('button', { name: '查询' }))
  await screen.findByText(result.primary_translation)

  expect(screen.getByRole('option', { name: '真人录音' })).toBeDisabled()
})

it('shows the backend message when playback fails', async () => {
  const user = userEvent.setup()
  const onPlay = vi.fn().mockRejectedValue(new ApiError('DICTIONARY_HUMAN_UNAVAILABLE', '该条目没有真人录音，请改用标准发音。', 422))
  render(<DictionaryPage onLookup={vi.fn().mockResolvedValue(WORD_RESULT)} onPlay={onPlay} onMarkUnknown={vi.fn()} />)

  await user.type(screen.getByLabelText('查询内容'), 'apple')
  await user.click(screen.getByRole('button', { name: '查询' }))
  await screen.findByText('苹果')
  await user.selectOptions(screen.getByLabelText('朗读声音'), 'human')
  await user.click(screen.getByRole('button', { name: '播放发音' }))

  expect(await screen.findByRole('status')).toHaveTextContent('该条目没有真人录音，请改用标准发音。')
})


it('shows source-specific loading text while audio is being prepared', async () => {
  const user = userEvent.setup()
  let resolvePlay: ((outcome: 'human_recording') => void) | undefined
  const onPlay = vi.fn().mockImplementation(() => new Promise<'human_recording'>(resolve => { resolvePlay = resolve }))
  render(<DictionaryPage onLookup={vi.fn().mockResolvedValue(WORD_RESULT)} onPlay={onPlay} onMarkUnknown={vi.fn()} />)

  await user.type(screen.getByLabelText('查询内容'), 'apple')
  await user.click(screen.getByRole('button', { name: '查询' }))
  await user.selectOptions(screen.getByLabelText('朗读声音'), 'human')
  await user.click(screen.getByRole('button', { name: '播放发音' }))

  expect(screen.getByRole('button', { name: '真人录音加载中' })).toBeDisabled()
  resolvePlay?.('human_recording')
  expect(await screen.findByRole('status')).toHaveTextContent('正在播放真人录音')
})

it('can force pronunciation regeneration while preserving the selected voice', async () => {
  const user = userEvent.setup()
  const onPlay = vi.fn().mockResolvedValue('voice_clone')
  render(<DictionaryPage onLookup={vi.fn().mockResolvedValue(WORD_RESULT)} onPlay={onPlay} onMarkUnknown={vi.fn()} voices={[{ id: 'voice-1', display_name: '妈妈 / 清晰美音' }]} />)

  await user.type(screen.getByLabelText('查询内容'), 'apple')
  await user.click(screen.getByRole('button', { name: '查询' }))
  await user.selectOptions(screen.getByLabelText('朗读声音'), 'custom')
  await user.selectOptions(screen.getByLabelText('克隆声音'), 'voice-1')
  await user.click(screen.getByRole('button', { name: '重新生成发音' }))

  expect(onPlay).toHaveBeenCalledWith('entry-apple', { source: 'custom', voice_version_id: 'voice-1', regenerate: true, accent: 'us' })
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

it('renders additional meanings, usage notes, and bilingual examples', async () => {
  const user = userEvent.setup()
  render(<DictionaryPage onLookup={vi.fn().mockResolvedValue({
    entry_id: 'rich-apple', source_language: 'en', target_language: 'zh', item_type: 'word', source_text: 'apple',
    primary_translation: '苹果', phonetic: "'æpl'", parts_of_speech: [{ part: 'n.', meaning: '苹果；苹果树' }],
    alternatives: ['苹果公司', '苹果味'], examples: [{ source: 'She ate an apple.', translation: '她吃了一个苹果。' }],
    usage_note: 'a round fruit\nthe fruit of an apple tree', cache_hit: false, result_source: 'ecdict',
  })} onMarkUnknown={vi.fn()} />)

  await user.type(screen.getByLabelText('查询内容'), 'apple')
  await user.click(screen.getByRole('button', { name: '查询' }))

  expect(await screen.findByRole('heading', { name: '其他释义' })).toBeVisible()
  expect(screen.getByText('苹果公司')).toBeVisible()
  expect(screen.getByRole('heading', { name: '英文释义 / 用法提示' })).toBeVisible()
  expect(screen.getByText('the fruit of an apple tree')).toBeVisible()
  expect(screen.getByRole('heading', { name: '双语例句' })).toBeVisible()
  expect(screen.getByText('她吃了一个苹果。')).toBeVisible()
})

it('streams sentence playback without generating an audio asset', async () => {
  const user = userEvent.setup()
  const onPlay = vi.fn()
  const onStreamPlay = vi.fn().mockResolvedValue(undefined)
  render(<DictionaryPage onLookup={vi.fn().mockResolvedValue({
    entry_id: 'entry-1', source_language: 'zh', target_language: 'en', item_type: 'sentence', source_text: '我喜欢苹果。',
    primary_translation: 'I like apples.', phonetic: null, parts_of_speech: [], alternatives: [], examples: [],
    usage_note: null, cache_hit: false,
  })} onPlay={onPlay} onStreamPlay={onStreamPlay} onMarkUnknown={vi.fn()} />)

  await user.type(screen.getByLabelText('查询内容'), '我喜欢苹果。')
  await user.click(screen.getByRole('button', { name: '查询' }))
  await screen.findByText('I like apples.')
  await user.click(screen.getByRole('button', { name: '播放发音' }))

  expect(onStreamPlay).toHaveBeenCalledWith('I like apples.')
  expect(onPlay).not.toHaveBeenCalled()
})

it('renders dual phonetics, word tags, and online dictionary provenance', async () => {
  const user = userEvent.setup()
  render(<DictionaryPage onLookup={vi.fn().mockResolvedValue({
    entry_id: 'online-apple', source_language: 'en', target_language: 'zh', item_type: 'word', source_text: 'apple',
    primary_translation: '苹果', phonetic: '/ˈæp.əl/', phonetic_uk: '/ˈæp.əl/', phonetic_us: '/ˈæp.əl/',
    word_tags: ['中考', '柯林斯3星'], parts_of_speech: [{ part: 'n.', meaning: '苹果' }],
    alternatives: [], examples: [{ source: 'She ate an apple.', translation: '她吃了一个苹果。' }],
    usage_note: null, cache_hit: false, result_source: 'youdao', source_attribution: '在线词典 · 有道（公开接口）',
  })} onMarkUnknown={vi.fn()} />)

  await user.type(screen.getByLabelText('查询内容'), 'apple')
  await user.click(screen.getByRole('button', { name: '查询' }))

  expect(await screen.findByText('在线词典 · 有道')).toBeVisible()
  expect(screen.getByText('英 /ˈæp.əl/')).toBeVisible()
  expect(screen.getByText('美 /ˈæp.əl/')).toBeVisible()
  expect(screen.getByText('中考')).toBeVisible()
  expect(screen.getByText('柯林斯3星')).toBeVisible()
})
