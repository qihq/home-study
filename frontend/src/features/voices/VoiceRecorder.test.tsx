import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { VoiceRecorder } from './VoiceRecorder'

it('requires consent, records a browser audio sample, and enables upload only after eight seconds', async () => {
  const user = userEvent.setup()
  const onRecorded = vi.fn()
  render(<VoiceRecorder onRecorded={onRecorded} />)

  expect(screen.getByRole('button', { name: '开始录制' })).toBeDisabled()
  await user.click(screen.getByLabelText('我已确认拥有该声音的授权'))
  expect(screen.getByRole('button', { name: '开始录制' })).toBeEnabled()
  expect(screen.getByText('录制时长：0 秒（需要 8–30 秒）')).toBeVisible()
})
