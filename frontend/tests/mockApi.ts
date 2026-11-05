import { vi } from 'vitest'

// Stand in for `fetch` with canned answers keyed by "METHOD /path". A path with no answer
// resolves to 404, so a screen that calls something unexpected fails visibly.
export function mockApi(answers: Record<string, unknown>): void {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path =
        typeof input === 'string' ? input : input instanceof URL ? input.pathname : input.url
      const key = `${init?.method ?? 'GET'} ${path}`
      if (!(key in answers)) {
        return Promise.resolve(new Response(null, { status: 404 }))
      }
      return Promise.resolve(
        new Response(JSON.stringify(answers[key]), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      )
    }),
  )
}

export function failApi(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
  )
}
