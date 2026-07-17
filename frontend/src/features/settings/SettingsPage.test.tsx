import { render, screen } from '@testing-library/react'
import { SettingsPage } from './SettingsPage'

it('offers a custom protocol and leaves the API key field empty', () => {
  render(<SettingsPage config={{ protocol: 'mimo', base_url: 'https://api.xiaomimimo.com/v1', model: 'mimo-v2.5-tts', voice: 'Chloe', speed: 1, api_key_configured: true, api_key_mask: '********-key' }} onBackup={vi.fn()} onSave={vi.fn()} />)
  expect(screen.getByLabelText('接口协议')).toBeVisible()
  expect(screen.getByLabelText('API Key')).toHaveValue('')
  expect(screen.getByText(/当前密钥：\*{8}-key/)).toBeVisible()
})

it('shows failed task retries when supplied by settings', () => {
  render(<SettingsPage config={{ protocol: 'mimo', base_url: 'https://api.xiaomimimo.com/v1', model: 'mimo-v2.5-tts', voice: 'Chloe', speed: 1, api_key_configured: true, api_key_mask: '********-key' }} onBackup={vi.fn()} onSave={vi.fn()} failedTasks={[{ id: 'job-1', type: 'voice_preview', entity_id: 'voice-1', error_code: 'VOICE_CLONE_FAILED' }]} onRetryTask={vi.fn()} />)
  expect(screen.getByText('失败任务')).toBeVisible()
  expect(screen.getByText((_, element) => element?.tagName === 'P' && element.textContent?.includes('VOICE_CLONE_FAILED') === true)).toBeVisible()
  expect(screen.getByRole('button', { name: '重试' })).toBeVisible()
})

it('lets a parent choose a ready cloned voice as the system pronunciation', () => {
  render(<SettingsPage
    config={{ protocol: 'mimo', base_url: 'https://api.xiaomimimo.com/v1', model: 'mimo-v2.5-tts', voice: 'Chloe', speed: 1, api_key_configured: true, api_key_mask: '********-key', pronunciation_source: 'custom', voice_version_id: 'voice-1' }}
    readyVoices={[{ id: 'voice-1', display_name: '妈妈 / 清晰美音' }]}
    onBackup={vi.fn()} onSave={vi.fn()}
  />)

  expect(screen.getByLabelText('默认发音来源')).toHaveValue('custom')
  expect(screen.getByLabelText('默认克隆声音')).toHaveValue('voice-1')
  expect(screen.getByRole('option', { name: '妈妈 / 清晰美音' })).toBeVisible()
})
