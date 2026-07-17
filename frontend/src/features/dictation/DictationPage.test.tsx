import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DictationPage } from './DictationPage'

it('hides spelling until parent reveals the answer and then records an incorrect score', async () => {
  const user = userEvent.setup()
  const saveResult = vi.fn()
  render(<DictationPage words={['apple']} onScore={saveResult} />)
  expect(screen.queryByText('apple')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '显示答案' }))
  expect(screen.getByText('apple')).toBeVisible()
  await user.click(screen.getByRole('button', { name: '错误' }))
  expect(saveResult).toHaveBeenCalledWith('incorrect')
})

it('selects a speaker then its ready version, submits both IDs, and locks returned snapshot names', async () => {
  const user = userEvent.setup()
  const onCreateSession = vi.fn().mockResolvedValue({
    id: 'session-1',
    results: [],
    speaker_profile_name_snapshot: '妈妈',
    voice_version_name_snapshot: '清晰美音',
  })
  render(<DictationPage
    words={['apple']}
    wordListVersionId="version-1"
    onScore={vi.fn()}
    speakers={[{ id: 'speaker-1', display_name: '妈妈' }]}
    voices={[
      { id: 'voice-1', speaker_profile_id: 'speaker-1', display_name: '清晰美音', status: 'ready' },
      { id: 'voice-2', speaker_profile_id: 'speaker-1', display_name: '处理中', status: 'processing' },
    ]}
    onCreateSession={onCreateSession}
  />)

  await user.selectOptions(screen.getByLabelText('朗读使用人'), 'speaker-1')
  expect(screen.getByRole('option', { name: '清晰美音' })).toBeVisible()
  expect(screen.queryByRole('option', { name: '处理中' })).not.toBeInTheDocument()
  await user.selectOptions(screen.getByLabelText('声音版本'), 'voice-1')
  await user.click(screen.getByRole('button', { name: '开始默写' }))
  expect(onCreateSession).toHaveBeenCalledWith({ word_list_version_id: 'version-1', mode: 'ordered', speaker_profile_id: 'speaker-1', voice_version_id: 'voice-1' })
  expect(screen.getByLabelText('朗读使用人')).toBeDisabled()
  expect(screen.getByLabelText('声音版本')).toBeDisabled()
  expect(screen.getByText('妈妈 / 清晰美音')).toBeVisible()
})

it('navigates by previous, next, and number without revealing option words', async () => {
  const user = userEvent.setup()
  render(<DictationPage words={['apple', 'banana', 'cat']} onScore={vi.fn()} />)

  expect(screen.getByRole('button', { name: '上一个' })).toBeDisabled()
  expect(screen.getByRole('option', { name: '第 2 个' })).toBeVisible()
  expect(screen.queryByRole('option', { name: /banana/ })).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '下一个' }))
  expect(screen.getByText('第 2 / 3 个')).toBeVisible()
  await user.selectOptions(screen.getByLabelText('跳转到题目'), '2')
  expect(screen.getByRole('button', { name: '下一个' })).toBeDisabled()
})

it('preserves each completed answer while navigating without showing words in the jump menu', async () => {
  const user = userEvent.setup()
  render(<DictationPage words={['apple', 'banana']} onScore={vi.fn()} />)

  await user.click(screen.getByRole('button', { name: '显示答案' }))
  await user.click(screen.getByRole('button', { name: '正确' }))
  expect(screen.getByRole('option', { name: '第 1 个（已完成）' })).toBeVisible()
  expect(screen.queryByText('apple')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '上一个' }))
  expect(screen.getByText('apple')).toBeVisible()
})

it('offers regeneration for configured native pronunciation', async () => {
  const user = userEvent.setup()
  const createSession = vi.fn().mockResolvedValue({
    id: 'session-native', speaker_profile_name_snapshot: null, voice_version_name_snapshot: null,
    results: [{ id: 'result-native', word_item_id: 'item-native', audio_asset_id: 'asset-native', pronunciation_source: 'configured', result: 'unscored' }],
  })
  render(<DictationPage words={['apple']} wordListVersionId="version-native" onScore={vi.fn()} onCreateSession={createSession} />)
  await user.click(screen.getByRole('button', { name: '开始默写' }))
  expect(screen.getByRole('button', { name: '重新生成原生发音' })).toBeVisible()
})
