import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { VideoLibrary } from './VideoLibrary'

it('shows a download action only for ready compressed videos', () => {
  render(<VideoLibrary recordings={[{ id: '1', reading_date: '2026-07-12', language_type: 'chinese', status: 'ready', is_official: true, duration_ms: 60000, download_ready: true }, { id: '2', reading_date: '2026-07-12', language_type: 'english', status: 'transcoding', is_official: false, duration_ms: null, download_ready: false }]} />)
  const download = screen.getByRole('link', { name: '下载 MP4 到设备' })
  expect(download).toBeVisible()
  expect(download).toHaveAttribute('download', '2026-07-12-chinese-reading.mp4')
  expect(screen.getByText('处理中')).toBeVisible()
})

it('opens only the selected themed video preview and can close it', async () => {
  const user = userEvent.setup()
  render(<VideoLibrary recordings={[{ id: '1', reading_date: '2026-07-12', language_type: 'chinese', status: 'ready', is_official: true, duration_ms: 60100, download_ready: true }]} />)

  expect(screen.getByText('1:00')).toBeVisible()
  expect(screen.queryByLabelText(/视频预览/)).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: '播放回忆' }))
  expect(screen.getByLabelText(/视频预览/)).toBeVisible()
  expect(screen.getByText('收起预览')).toBeVisible()

  await user.click(screen.getByRole('button', { name: '收起预览' }))
  expect(screen.queryByLabelText(/视频预览/)).not.toBeInTheDocument()
})

it('shows an Animal Island empty state when there are no videos', () => {
  render(<VideoLibrary recordings={[]} />)
  expect(screen.getByRole('heading', { name: '影像馆还空空的' })).toBeVisible()
  expect(screen.getByAltText('两位小岛伙伴')).toHaveAttribute('src', '/animal-island/animal-icon.png')
})

it('distinguishes a loading failure from a genuinely empty library', async () => {
  const user = userEvent.setup()
  const retry = vi.fn()
  render(<VideoLibrary recordings={[]} loadError="请检查网络后重试。" onRetry={retry} />)

  expect(screen.getByRole('alert')).toHaveTextContent('暂时没能打开影像馆')
  expect(screen.queryByText('影像馆还空空的')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '重新加载' }))
  expect(retry).toHaveBeenCalledOnce()
})

it('explains why queued video processing cannot advance while the worker is offline', () => {
  render(<VideoLibrary workerOnline={false} recordings={[{ id: '2', reading_date: '2026-07-12', language_type: 'english', title: null, status: 'assembling', is_official: false, duration_ms: null, download_ready: false }]} />)
  expect(screen.getByRole('alert')).toHaveTextContent('后台处理服务离线')
})

it('filters the library to a selected calendar date and can show all again', async () => {
  const user = userEvent.setup()
  render(<VideoLibrary recordings={[
    { id: '1', reading_date: '2026-07-12', language_type: 'chinese', title: '周日中文', status: 'ready', is_official: true, duration_ms: 60000, download_ready: true },
    { id: '2', reading_date: '2026-07-13', language_type: 'english', title: '周一英文', status: 'ready', is_official: true, duration_ms: 60000, download_ready: true },
  ]} />)

  expect(screen.getByText('周一英文')).toBeVisible()
  expect(screen.queryByText('周日中文')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '2026年7月12日，中文1个' }))
  expect(screen.getByText('周日中文')).toBeVisible()
  expect(screen.queryByText('周一英文')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '显示全部' }))
  expect(screen.getByText('周日中文')).toBeVisible()
  expect(screen.getByText('周一英文')).toBeVisible()
})

it('offers manual processing retry only for exhausted video failures', async () => {
  const user = userEvent.setup()
  const retry = vi.fn().mockResolvedValue(undefined)
  render(<VideoLibrary onRetryProcessing={retry} recordings={[
    { id: 'failed', reading_date: '2026-07-12', language_type: 'english', status: 'transcode_failed', is_official: false, duration_ms: 60000, download_ready: false },
  ]} />)

  expect(screen.getByText('处理失败')).toBeVisible()
  await user.click(screen.getByRole('button', { name: '重新处理' }))
  expect(retry).toHaveBeenCalledWith('failed')
})
