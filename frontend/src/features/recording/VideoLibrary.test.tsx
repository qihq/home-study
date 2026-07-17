import { render, screen } from '@testing-library/react'
import { VideoLibrary } from './VideoLibrary'

it('shows a download action only for ready compressed videos', () => {
  render(<VideoLibrary recordings={[{ id: '1', reading_date: '2026-07-12', language_type: 'chinese', status: 'ready', is_official: true, duration_ms: 60000, download_ready: true }, { id: '2', reading_date: '2026-07-12', language_type: 'english', status: 'transcoding', is_official: false, duration_ms: null, download_ready: false }]} />)
  expect(screen.getByRole('link', { name: '下载到设备' })).toBeVisible()
  expect(screen.getByText('处理中')).toBeVisible()
})

it('explains why queued video processing cannot advance while the worker is offline', () => {
  render(<VideoLibrary workerOnline={false} recordings={[{ id: '2', reading_date: '2026-07-12', language_type: 'english', title: null, status: 'assembling', is_official: false, duration_ms: null, download_ready: false }]} />)
  expect(screen.getByRole('alert')).toHaveTextContent('后台处理服务离线')
})
