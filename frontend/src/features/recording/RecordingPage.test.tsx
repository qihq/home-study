import { render, screen } from '@testing-library/react'
import { RecordingPage } from './RecordingPage'

it('offers to continue a recovered recording instead of creating a new session', async () => {
  render(<RecordingPage language="english" onBack={() => undefined} recovery={{ recordingId: 'r1', language: 'english', nextSequence: 3, ended: false }} />)

  expect(await screen.findByRole('button', { name: '继续录制' })).toBeVisible()
})

it('offers to resume upload for an ended recording', async () => {
  render(<RecordingPage language="english" onBack={() => undefined} recovery={{ recordingId: 'r1', language: 'english', nextSequence: 3, ended: true }} />)

  expect(await screen.findByRole('button', { name: '补传并提交' })).toBeVisible()
})
