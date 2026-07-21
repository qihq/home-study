import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { downloadVideo, VideoDownloadPage, VideoDownloadItem } from './VideoDownloadPage'

const item: VideoDownloadItem = {
  id: 'recording-1',
  title: '周一英文阅读',
  readingDate: '2026-07-21',
  languageType: 'english',
  fileName: '2026-07-21-english-reading.mp4',
}

function streamedResponse(chunks: Uint8Array[], total = chunks.reduce((sum, chunk) => sum + chunk.length, 0)) {
  let position = 0
  return {
    ok: true,
    status: 200,
    headers: new Headers({ 'Content-Length': String(total), 'Content-Type': 'video/mp4' }),
    body: {
      getReader: () => ({
        read: vi.fn(async () => position < chunks.length
          ? { done: false, value: chunks[position++] }
          : { done: true, value: undefined }),
      }),
    },
  } as unknown as Response
}

it('reports real byte progress while streaming the authenticated video', async () => {
  const progress: Array<[number, number | null]> = []
  const fetcher = vi.fn().mockResolvedValue(streamedResponse([
    new Uint8Array([1, 2]),
    new Uint8Array([3, 4]),
  ]))

  const file = await downloadVideo(item, new AbortController().signal, (loaded, total) => progress.push([loaded, total]), fetcher)

  expect(fetcher).toHaveBeenCalledWith('/api/recordings/recording-1/download/720p', expect.objectContaining({ credentials: 'include' }))
  expect(progress).toEqual([[0, 4], [2, 4], [4, 4]])
  expect(file).toMatchObject({ name: item.fileName, type: 'video/mp4', size: 4 })
})

it('shares the completed video and returns home after the system sheet succeeds', async () => {
  const share = vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'canShare', { configurable: true, value: vi.fn(() => true) })
  Object.defineProperty(navigator, 'share', { configurable: true, value: share })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamedResponse([new Uint8Array([1, 2, 3])])))
  const onHome = vi.fn()

  render(<VideoDownloadPage item={item} onHome={onHome} onBackToVideos={vi.fn()} />)

  expect(await screen.findByRole('heading', { name: '正在保存阅读回忆' })).toBeVisible()
  await waitFor(() => expect(share).toHaveBeenCalledWith(expect.objectContaining({ files: [expect.any(File)] })))
  await waitFor(() => expect(onHome).toHaveBeenCalledOnce())
})

it('stays on the page when sharing is cancelled and allows another save attempt', async () => {
  const share = vi.fn()
    .mockRejectedValueOnce(new DOMException('cancelled', 'AbortError'))
    .mockResolvedValueOnce(undefined)
  Object.defineProperty(navigator, 'canShare', { configurable: true, value: vi.fn(() => true) })
  Object.defineProperty(navigator, 'share', { configurable: true, value: share })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamedResponse([new Uint8Array([1, 2, 3])])))
  const onHome = vi.fn()
  const user = userEvent.setup()

  render(<VideoDownloadPage item={item} onHome={onHome} onBackToVideos={vi.fn()} />)

  const saveAgain = await screen.findByRole('button', { name: '保存到照片' })
  expect(onHome).not.toHaveBeenCalled()
  await user.click(saveAgain)
  await waitFor(() => expect(onHome).toHaveBeenCalledOnce())
})
