import config from './vite.config'

describe('development API proxy', () => {
  it('forwards API requests to the local backend on port 8001', () => {
    expect(config.server?.proxy?.['/api']).toBe('http://127.0.0.1:8001')
  })
})
