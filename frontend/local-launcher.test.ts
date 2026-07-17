import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

describe('local API launcher', () => {
  it('serves the built frontend from port 8001', () => {
    const script = readFileSync(resolve(import.meta.dirname, '../scripts/run-local-api-8001.cmd'), 'utf8')

    expect(script).toContain('APP_FRONTEND_DIR=%~dp0..\\frontend\\dist')
  })
})
