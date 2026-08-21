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

const videoTrack = { stop: vi.fn(), readyState: 'live' }
const liveAudioTrack = { stop: vi.fn(), readyState: 'live', muted: false }
const stream = { getTracks: () => [videoTrack, liveAudioTrack], getVideoTracks: () => [videoTrack], getAudioTracks: () => [liveAudioTrack] } as unknown as MediaStream
const videoOnlyStream = { getTracks: () => [videoTrack], getVideoTracks: () => [videoTrack], getAudioTracks: () => [] } as unknown as MediaStream

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

it('offers to abandon a recovered recording and start fresh', async () => {
  const user = userEvent.setup()
  render(<RecordingPage language="english" onBack={vi.fn()} onHome={vi.fn()} onOpenVideos={vi.fn()} recovery={{ recordingId: 'r1', language: 'english', nextSequence: 3, ended: false }} />)

  await user.click(screen.getByRole('button', { name: '放弃并重新开始' }))

  expect(api).toHaveBeenCalledWith('/recordings/r1/abandon', { method: 'POST' })
  expect(await screen.findByRole('button', { name: '开始录制' })).toBeVisible()
  expect(screen.queryByRole('button', { name: '放弃并重新开始' })).not.toBeInTheDocument()
})

it('presents the skating recording with its own island copy and badge', async () => {
  render(<RecordingPage language="skating" onBack={() => undefined} onHome={() => undefined} onOpenVideos={() => undefined} />)

  expect(screen.getByRole('heading', { name: '花滑录制' })).toBeVisible()
  expect(screen.getByText('小岛花滑时光')).toBeVisible()
  expect(document.querySelector('.recording-language-badge img')).toHaveAttribute('src', '/animal-island/skating.svg')
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

it('refuses to start recording when the camera stream has no microphone track', async () => {
  vi.mocked(navigator.mediaDevices.getUserMedia).mockResolvedValue(videoOnlyStream)
  const user = userEvent.setup()
  render(<RecordingPage language="english" onBack={vi.fn()} onHome={vi.fn()} onOpenVideos={vi.fn()} />)

  await user.click(screen.getByRole('button', { name: '开始录制' }))

  expect(await screen.findByText('没有获取到麦克风声音，请在浏览器与系统设置中允许麦克风权限后重试。')).toBeVisible()
  expect(api).not.toHaveBeenCalledWith('/recordings', expect.anything())
})

it('re-requests camera and microphone when the previously opened stream lost its tracks after locking the screen', async () => {
  const user = userEvent.setup()
  render(<RecordingPage language="english" onBack={vi.fn()} onHome={vi.fn()} onOpenVideos={vi.fn()} />)

  // open the camera in advance, as when preparing before locking the screen
  await user.click(screen.getByRole('button', { name: '切换到后置摄像头' }))
  expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledTimes(1)

  // simulate the lock screen ending the tracks of the previously opened stream
  videoTrack.readyState = 'ended'
  liveAudioTrack.readyState = 'ended'

  const freshVideoTrack = { stop: vi.fn(), readyState: 'live' }
  const freshAudioTrack = { stop: vi.fn(), readyState: 'live', muted: false }
  const freshStream = { getTracks: () => [freshVideoTrack, freshAudioTrack], getVideoTracks: () => [freshVideoTrack], getAudioTracks: () => [freshAudioTrack] } as unknown as MediaStream
  vi.mocked(navigator.mediaDevices.getUserMedia).mockResolvedValueOnce(freshStream)

  await user.click(screen.getByRole('button', { name: '开始录制' }))

  expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledTimes(2)
  expect(await screen.findByRole('button', { name: '结束录制' })).toBeVisible()

  videoTrack.readyState = 'live'
  liveAudioTrack.readyState = 'live'
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
