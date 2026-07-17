import { FormEvent, useState } from 'react'
import { api } from '../../api/client'
import { Button } from '../../ui/Button'

export function LoginPage({ firstRun = false, onLoggedIn }: { firstRun?: boolean; onLoggedIn: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  async function submit(event: FormEvent) {
    event.preventDefault(); setError('')
    try {
      if (firstRun) await api('/setup/initial-admin', { method: 'POST', body: JSON.stringify({ username, password }) })
      await api('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) })
      onLoggedIn()
    } catch { setError('无法登录，请检查用户名和密码。') }
  }
  return <main className="login-page"><form onSubmit={submit}><p className="date">家庭学习助手</p><h1>{firstRun ? '创建管理员' : '欢迎回来'}</h1><p>{firstRun ? '首次使用，请创建只属于家庭的管理员账号。' : '登录后继续今天的学习。'}</p><label>用户名<input value={username} onChange={event => setUsername(event.target.value)} required /></label><label>密码<input type="password" value={password} onChange={event => setPassword(event.target.value)} required /></label>{error && <p role="alert">{error}</p>}<Button type="submit">{firstRun ? '创建管理员' : '登录'}</Button></form></main>
}
