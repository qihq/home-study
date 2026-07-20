import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, vi } from 'vitest'
import { RecordingPage } from './RecordingPage'
import { api } from '../../api/client'

const recordingStore = vi.hoisted(() => ({
  put: vi.fn().mockResolvedValue(undefined),
  get: vi.fn().mockResolvedValue(undefined),
  acknowledge: vi.fn().mockResolvedValue(undefined),
  list: vi.fn().mockResolvedValue([]),
  putSession: vi.fn().mockResolvedValue(undefined),
  getSession: vi.fn().mockResolvedValue(undefined),
  listSessions: vi.fn().mockResolvedValue([]),
  removeSession: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('../../api/client', () => ({ api: vi.fn() }))
vi.mock('../../lib/recordingStore', async importOriginal => {
  const original = await importOriginal<typeof import('../../lib/recordingStore')>()
  return { ...original, createIndexedDbRecordingStore: () => recordingStore }
})

class FakeMediaRecorder extends EventTarget {
  static isTypeSupported() { return true }
  stream: MediaStream
  ondataavailable: ((event: BlobEvent) => void) | null = null
  constructor(stream: MediaStream) { super(); this.stream = stream }
  start() {}
  stop() { this.dispatchEvent(new Event('stop')) }
}

const track = { stop: vi.fn() }
const stream = { getTracks: () => [track] } as unknown as MediaStream

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api).mockImplementation(async path => {
    if (path === '/recordings') return { id: 'recording-1' } as never
    if (path.endsWith('/complete')) return { missing_sequences: [] } as never
    if (path.endsWith('/chunks')) return { received_sequences: [] } as never
    return {} as never
  })
  vi.stubGlobal('MediaRecorder', FakeMediaRecorder)
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn().mockResolvedValue(stream) } })
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue()
})

it('offers to continue a recovered recording instead of creating a new session', async () => {
  render(<RecordingPage language="english" onBack={() => undefined} onHome={() => undefined} onOpenVideos={() => undefined} recovery={{ recordingId: 'r1', language: 'english', nextSequence: 3, ended: false }} />)

  expect(await screen.findByRole('button', { name: '继续录制' })).toBeVisible()
})

it('offers to resume upload for an ended recording', async () => {
  render(<RecordingPage language="english" onBack={() => undefined} onHome={() => undefined} onOpenVideos={() => undefined} recovery={{ recordingId: 'r1', language: 'english', nextSequence: 3, ended: true }} />)

  expect(await screen.findByRole('button', { name: '补传并提交' })).toBeVisible()
})

it('shows elapsed time while recording and does not reset it when switching cameras', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
  render(<RecordingPage language="chinese" onBack={vi.fn()} onHome={vi.fn()} onOpenVideos={vi.fn()} />)

  expect(screen.getByText('00:00')).toBeVisible()
  await user.click(screen.getByRole('button', { name: '开始录制' }))
  await vi.advanceTimersByTimeAsync(3100)
  expect(screen.getByText('00:03')).toBeVisible()
  await user.click(screen.getByRole('button', { name: '切换到后置摄像头' }))
  await vi.advanceTimersByTimeAsync(2000)
  expect(screen.getByText('00:05')).toBeVisible()
  vi.useRealTimers()
})

it('freezes duration and offers explicit home and video-library destinations after submission', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
  const onHome = vi.fn()
  const onOpenVideos = vi.fn()
  render(<RecordingPage language="english" onBack={vi.fn()} onHome={onHome} onOpenVideos={onOpenVideos} />)

  await user.click(screen.getByRole('button', { name: '开始录制' }))
  await vi.advanceTimersByTimeAsync(2200)
  await user.click(screen.getByRole('button', { name: '结束录制' }))
  const homeButton = await screen.findByRole('button', { name: '返回主页' })
  const completion = homeButton.closest('.recording-complete-card') as HTMLElement
  expect(within(completion).getByText('本次录制 00:02')).toBeVisible()
  await vi.advanceTimersByTimeAsync(3000)
  expect(within(completion).getByText('本次录制 00:02')).toBeVisible()
  await user.click(homeButton)
  await user.click(screen.getByRole('button', { name: '去视频库查看' }))
  expect(onHome).toHaveBeenCalledOnce()
  expect(onOpenVideos).toHaveBeenCalledOnce()
  vi.useRealTimers()
})
