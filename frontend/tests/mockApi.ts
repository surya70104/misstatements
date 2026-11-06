import { vi } from 'vitest'

const REFUSAL = Symbol('refusal')

type Refusal = { [REFUSAL]: true; status: number; body: unknown }

function isRefusal(value: unknown): value is Refusal {
  return typeof value === 'object' && value !== null && REFUSAL in value
}

/**
 * An answer with a status other than 200 and, optionally, a body: what the backend sends
 * when it refuses. `refusal(404, { detail: '...' })`.
 */
export function refusal(status: number, body?: unknown): Refusal {
  return { [REFUSAL]: true, status, body }
}

/** An answer with a given status that is not a refusal: `answered(201, created)`. */
export function answered(status: number, body: unknown): Refusal {
  return refusal(status, body)
}

/** An answer that arrives only when the test says so: for what a screen does meanwhile. */
export function deferred(): { answer: Promise<unknown>; arrive: (value: unknown) => void } {
  let arrive: (value: unknown) => void = () => undefined
  const answer = new Promise<unknown>((resolve) => {
    arrive = resolve
  })
  return { answer, arrive }
}

/**
 * Answers given one after another, the last one repeating: what the backend says before a
 * write and what it says after. `inTurn(before, after)`.
 */
export function inTurn(...answers: unknown[]): () => unknown {
  let asked = 0
  return () => {
    const answer = answers[Math.min(asked, answers.length - 1)]
    asked += 1
    return answer
  }
}

function pathOf(input: RequestInfo | URL): string {
  return typeof input === 'string' ? input : input instanceof URL ? input.pathname : input.url
}

function respond(answer: unknown): Response {
  if (isRefusal(answer)) {
    const body = answer.body === undefined ? null : JSON.stringify(answer.body)
    return new Response(body, {
      status: answer.status,
      headers: { 'content-type': 'application/json' },
    })
  }
  return new Response(JSON.stringify(answer), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  })
}

// Stand in for `fetch` with canned answers keyed by "METHOD /path". A path with no answer
// resolves to 404, so a screen that calls something unexpected fails visibly. An answer may
// be a promise (see `deferred`), in which case the request stays open until it settles.
export function mockApi(answers: Record<string, unknown>): void {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const key = `${init?.method ?? 'GET'} ${pathOf(input)}`
      if (!(key in answers)) {
        return Promise.resolve(new Response(null, { status: 404 }))
      }
      const answer: unknown = answers[key]
      // An answer may be a function, asked afresh on every request (see `inTurn`).
      const now: unknown = typeof answer === 'function' ? (answer as () => unknown)() : answer
      return Promise.resolve(now).then(respond)
    }),
  )
}

export function failApi(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
  )
}

/** Every path `fetch` was asked for, in order, as "METHOD /path". */
export function requested(): string[] {
  return vi.mocked(fetch).mock.calls.map(([input, init]) => {
    return `${init?.method ?? 'GET'} ${pathOf(input)}`
  })
}

/** Every request that carried a body, in order, with the body as it was sent. */
export function sent(): { request: string; body: unknown; contentType: string | null }[] {
  return vi
    .mocked(fetch)
    .mock.calls.filter(([, init]) => typeof init?.body === 'string')
    .map(([input, init]) => ({
      request: `${init?.method ?? 'GET'} ${pathOf(input)}`,
      body: JSON.parse(init?.body as string) as unknown,
      contentType: new Headers(init?.headers).get('content-type'),
    }))
}
