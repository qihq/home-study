import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { VoicePackageDialog } from './VoicePackageDialog'

it('requires matching export passwords and previews an import before a conflict strategy is committed', async () => {
  const user = userEvent.setup()
  const onExport = vi.fn()
  const onInspect = vi.fn().mockResolvedValue({ import_id: 'import-1', conflicts: [{ speaker_profile_id: 'speaker-1' }] })
  const onCommit = vi.fn()
  render(<VoicePackageDialog onExport={onExport} onInspect={onInspect} onCommit={onCommit} />)

  expect(screen.getByText('不包含 API Key')).toBeVisible()
  await user.type(screen.getByLabelText('导出密码'), 'first')
  await user.type(screen.getByLabelText('再次输入密码'), 'second')
  expect(screen.getByRole('button', { name: '导出声音包' })).toBeDisabled()
  await user.clear(screen.getByLabelText('再次输入密码'))
  await user.type(screen.getByLabelText('再次输入密码'), 'first')
  await user.click(screen.getByRole('button', { name: '导出声音包' }))
  expect(onExport).toHaveBeenCalledWith('first')

  await user.upload(screen.getByLabelText('导入声音包'), new File(['voice'], 'voices.flvoice', { type: 'application/octet-stream' }))
  await user.type(screen.getByLabelText('导入密码'), 'import-password')
  await user.click(screen.getByRole('button', { name: '预览导入' }))
  expect(await screen.findByText('发现 1 个冲突')).toBeVisible()
  expect(screen.queryByRole('button', { name: '完成导入' })).not.toBeInTheDocument()
  await user.selectOptions(screen.getByLabelText('冲突处理方式'), 'merge')
  await user.click(screen.getByRole('button', { name: '完成导入' }))
  expect(onCommit).toHaveBeenCalledWith({ import_id: 'import-1', strategy: 'merge' })
})
