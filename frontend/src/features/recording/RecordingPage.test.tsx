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
  static instances: FakeMediaRecorder[] = []
  static silentStop = false
  stream: MediaStream
  ondataavailable: ((event: BlobEvent) => void) | null = null
  constructor(stream: MediaStream) { super(); this.stream = stream; FakeMediaRecorder.instances.push(this) }
  start() {}
  stop() {
    // 锁屏/切后台后 iOS 的 MediaRecorder 可能永远不派发 stop 事件
    if (FakeMediaRecorder.silentStop) return
    this.dispatchEvent(new Event('stop'))
  }
}

const fakeChunk = { size: 1, type: 'video/mp4', arrayBuffer: async () => new ArrayBuffer(8) } as unknown as Blob

function emitChunk(recorder: FakeMediaRecorder, count = 1) {
  for (let index = 0; index < count; index += 1) recorder.ondataavailable?.({ data: fakeChunk } as BlobEvent)
}

const videoTrack = { stop: vi.fn(), readyState: 'live' }
const liveAudioTrack = { stop: vi.fn(), readyState: 'live', muted: false }
const stream = { getTracks: () => [videoTrack, liveAudioTrack], getVideoTracks: () => [videoTrack], getAudioTracks: () => [liveAudioTrack] } as unknown as MediaStream
const videoOnlyStream = { getTracks: () => [videoTrack], getVideoTracks: () => [videoTrack], getAudioTracks: () => [] } as unknown as MediaStream

beforeEach(() => {
  vi.clearAllMocks()
  vi.unstubAllGlobals()
  FakeMediaRecorder.instances = []
  FakeMediaRecorder.silentStop = false
  vi.mocked(api).mockImplementation(async path => {
    if (path === '/recordings') return { id: 'recording-1' } as never
    if (path.endsWith('/complete')) return { missing_sequences: [] } as never
    if (path.endsWith('/chunks')) return { received_sequences: [] } as never
    return {} as never
  })
  vi.stubGlobal('MediaRecorder', FakeMediaRecorder)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200 }))
  vi.stubGlobal('crypto', { subtle: { digest: vi.fn().mockResolvedValue(new Uint8Array(32).buffer) } })
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

it('caps parallel chunk uploads so a slow network cannot exhaust the server connection pool', async () => {
  let inFlight = 0
  let peak = 0
  const release: Array<() => void> = []
  const fetchMock = vi.fn(() => {
    inFlight += 1
    peak = Math.max(peak, inFlight)
    return new Promise<Response>(resolve => {
      release.push(() => { inFlight -= 1; resolve({ ok: true, status: 200 } as Response) })
    })
  })
  vi.stubGlobal('fetch', fetchMock)

  const user = userEvent.setup()
  render(<RecordingPage language="english" onBack={vi.fn()} onHome={vi.fn()} onOpenVideos={vi.fn()} />)
  await user.click(screen.getByRole('button', { name: '开始录制' }))

  const recorder = FakeMediaRecorder.instances.at(-1)!
  const chunk = { size: 1, type: 'video/mp4', arrayBuffer: async () => new ArrayBuffer(8) } as unknown as Blob
  for (let index = 0; index < 6; index += 1) recorder.ondataavailable?.({ data: chunk } as BlobEvent)

  await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  expect(peak).toBe(2)
  for (let guard = 0; guard < 200; guard += 1) {
    if (!release.length && fetchMock.mock.calls.length === 6 && inFlight === 0) break
    while (release.length) release.shift()!()
    await new Promise(resolve => setTimeout(resolve, 0))
  }

  expect(fetchMock).toHaveBeenCalledTimes(6)
  expect(peak).toBe(2)
  expect(inFlight).toBe(0)
})

it('finishes submission instead of hanging when the recorder never fires stop', async () => {
  // 回归：锁屏/切后台后 iOS 的 MediaRecorder.stop() 不派发 stop 事件，
  // 旧代码会永远 await 在那个 Promise 上，「结束录制」按钮永久停在提交中。
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
  FakeMediaRecorder.silentStop = true
  render(<RecordingPage language="english" onBack={vi.fn()} onHome={vi.fn()} onOpenVideos={vi.fn()} />)

  await user.click(screen.getByRole('button', { name: '开始录制' }))
  await vi.advanceTimersByTimeAsync(4_000)
  await user.click(screen.getByRole('button', { name: '结束录制' }))
  await vi.advanceTimersByTimeAsync(11_000)

  expect(await screen.findByText(/没有录到任何画面/)).toBeVisible()
  expect(screen.queryByRole('button', { name: '正在提交视频…' })).not.toBeInTheDocument()
  vi.useRealTimers()
})

it('abandons the server recording and explains itself when nothing was captured', async () => {
  const user = userEvent.setup()
  render(<RecordingPage language="english" onBack={vi.fn()} onHome={vi.fn()} onOpenVideos={vi.fn()} />)

  await user.click(screen.getByRole('button', { name: '开始录制' }))
  await user.click(screen.getByRole('button', { name: '结束录制' }))

  expect(await screen.findByText(/没有录到任何画面/)).toBeVisible()
  expect(api).toHaveBeenCalledWith('/recordings/recording-1/abandon', { method: 'POST' })
  expect(api).not.toHaveBeenCalledWith('/recordings/recording-1/complete', expect.anything())
})

it('keeps a failed submission recoverable instead of leaving the page stuck', async () => {
  vi.mocked(api).mockImplementation(async path => {
    if (path === '/recordings') return { id: 'recording-1' } as never
    if (path.endsWith('/chunks')) return { received_sequences: [] } as never
    if (path.endsWith('/complete')) throw new Error('network down')
    return {} as never
  })
  const user = userEvent.setup()
  render(<RecordingPage language="english" onBack={vi.fn()} onHome={vi.fn()} onOpenVideos={vi.fn()} />)

  await user.click(screen.getByRole('button', { name: '开始录制' }))
  emitChunk(FakeMediaRecorder.instances.at(-1)!)
  await user.click(screen.getByRole('button', { name: '结束录制' }))

  expect(await screen.findByText(/提交失败/)).toBeVisible()
  expect(screen.getByRole('button', { name: '补传并提交' })).toBeVisible()
  expect(screen.getByRole('button', { name: '放弃并重新开始' })).toBeVisible()
})

it('freezes duration and offers explicit home and video-library destinations after submission', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
  const onHome = vi.fn()
  const onOpenVideos = vi.fn()
  render(<RecordingPage language="english" onBack={vi.fn()} onHome={onHome} onOpenVideos={onOpenVideos} />)

  await user.click(screen.getByRole('button', { name: '开始录制' }))
  await vi.advanceTimersByTimeAsync(2200)
  emitChunk(FakeMediaRecorder.instances.at(-1)!)
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
