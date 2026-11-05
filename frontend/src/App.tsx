import { useEffect, useState } from 'react'

import { getHealth, type Health } from './api'

type Backend = { state: 'checking' } | { state: 'up'; health: Health } | { state: 'down' }

export function App() {
  const [backend, setBackend] = useState<Backend>({ state: 'checking' })

  useEffect(() => {
    let cancelled = false
    getHealth()
      .then((health) => {
        if (!cancelled) setBackend({ state: 'up', health })
      })
      .catch(() => {
        if (!cancelled) setBackend({ state: 'down' })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-baseline gap-3 px-6 py-3">
          <a href="#/" className="text-lg font-semibold hover:underline">
            Misstatements Rollup
          </a>
          <span className="text-sm text-slate-500">SA 450 · OAK Audit</span>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-6">
        <p className="text-slate-700">
          Stage 0: project foundation. The schedule, misstatement detail and evaluation screens
          arrive with Stage 6.
        </p>
        <p className="mt-4 text-sm text-slate-500" role="status">
          {backend.state === 'checking' && 'Checking the backend…'}
          {backend.state === 'up' &&
            `Backend ${backend.health.module} ${backend.health.version} is ${backend.health.status}.`}
          {backend.state === 'down' && 'Backend unreachable: start it on port 8003.'}
        </p>
      </main>
    </div>
  )
}
