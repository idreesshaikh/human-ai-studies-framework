import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, onUnauthorized } from '../src/lib/api'

function stubFetch(status: number, body: unknown = {}): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: status >= 200 && status < 300,
      status,
      statusText: String(status),
      json: async () => body,
    })),
  )
  vi.stubGlobal('localStorage', {
    getItem: () => null,
    setItem: () => undefined,
    removeItem: () => undefined,
  })
}

afterEach(() => {
  onUnauthorized(null)
  vi.unstubAllGlobals()
})

describe('the sign-in hook', () => {
  it('fires the listener on a 401 and still rejects', async () => {
    stubFetch(401)
    const listener = vi.fn()
    onUnauthorized(listener)
    await expect(api.health()).rejects.toThrow('401')
    expect(listener).toHaveBeenCalledOnce()
  })

  it('stays quiet on success and on non-auth failures', async () => {
    const listener = vi.fn()
    onUnauthorized(listener)
    stubFetch(200, { status: 'ok', studyId: null, protocolLoaded: false })
    await api.health()
    stubFetch(500)
    await expect(api.health()).rejects.toThrow('500')
    expect(listener).not.toHaveBeenCalled()
  })

  it('exposes the middleware sign-in mode', async () => {
    stubFetch(200, { mode: 'token' })
    await expect(api.authConfig()).resolves.toEqual({ mode: 'token' })
  })
})
