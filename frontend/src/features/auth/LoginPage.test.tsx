import { render, screen } from '@testing-library/react'
import { LoginPage } from './LoginPage'

it('shows a first-run setup action when no administrator exists', () => {
  render(<LoginPage firstRun onLoggedIn={vi.fn()} />)
  expect(screen.getByRole('button', { name: '创建管理员' })).toBeVisible()
})
