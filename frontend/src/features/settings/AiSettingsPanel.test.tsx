import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'
import { AiSettingsPanel } from './AiSettingsPanel'

it('never fills the saved AI key back into the password input', () => {
  render(<AiSettingsPanel config={{
    protocol: 'openai_chat_compatible', display_name: 'OpenCode Go', base_url: 'https://provider.example/v1',
    model: 'custom-model', temperature: 0.1, timeout_seconds: 45, enabled: true,
    api_key_configured: true, api_key_mask: '********abcd',
  }} onSave={vi.fn()} onTest={vi.fn()} />)

  expect(screen.getByLabelText('AI API Key')).toHaveValue('')
  expect(screen.getByText('********abcd')).toBeVisible()
})
