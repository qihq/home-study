import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { SpeakerProfilesPage } from './SpeakerProfilesPage'

it('requires voice consent before recording and lets a ready version be previewed and become the only default', async () => {
  const user = userEvent.setup()
  const onPreview = vi.fn()
  const onMakeDefault = vi.fn().mockResolvedValue(undefined)
  render(<SpeakerProfilesPage profiles={[{
    id: 'speaker-1', display_name: '妈妈', default_voice_version_id: 'voice-1',
    versions: [
      { id: 'voice-1', display_name: '清晰美音', status: 'ready', is_default: true },
      { id: 'voice-2', display_name: '慢速美音', status: 'ready', is_default: false },
    ],
  }]} onPreview={onPreview} onMakeDefault={onMakeDefault} />)

  expect(screen.getByRole('button', { name: '开始录制' })).toBeDisabled()
  await user.click(screen.getByLabelText('我已确认拥有该声音的授权'))
  expect(screen.getByRole('button', { name: '开始录制' })).toBeEnabled()
  await user.click(screen.getByRole('button', { name: '试听 清晰美音' }))
  expect(onPreview).toHaveBeenCalledWith('voice-1')
  await user.click(screen.getByRole('button', { name: '设为默认 慢速美音' }))
  expect(onMakeDefault).toHaveBeenCalledWith('voice-2')
  expect(screen.getAllByText('默认声音')).toHaveLength(1)
})

it('accepts an uploaded authorized audio sample so processing survives leaving the page', async () => {
  const user = userEvent.setup()
  const onRecorded = vi.fn().mockResolvedValue(undefined)
  render(<SpeakerProfilesPage profiles={[{ id: 'speaker-1', display_name: '妈妈', default_voice_version_id: null, versions: [] }]} onPreview={vi.fn()} onMakeDefault={vi.fn()} onRecorded={onRecorded} />)

  await user.upload(screen.getByLabelText('上传声音样本'), new File(['audio'], 'sample.wav', { type: 'audio/wav' }))

  expect(onRecorded).toHaveBeenCalledWith('speaker-1', expect.any(Blob))
})

it('shows that clone progress is paused when the worker is offline', () => {
  render(<SpeakerProfilesPage workerOnline={false} profiles={[{
    id: 'speaker-1', display_name: '妈妈', default_voice_version_id: null,
    versions: [{ id: 'voice-1', display_name: '待处理声音', status: 'processing', is_default: false, progress: 5 }],
  }]} onPreview={vi.fn()} onMakeDefault={vi.fn()} />)

  expect(screen.getByRole('alert')).toHaveTextContent('后台处理服务离线')
  expect(screen.getByLabelText('待处理声音 处理进度')).toHaveValue(5)
})
