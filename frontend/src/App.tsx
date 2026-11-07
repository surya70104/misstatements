import { useEffect, useRef, useState } from 'react'

import { getHealth, type Health } from './api'
import { EngagementsPage } from './pages/EngagementsPage'
import { EvaluationPage } from './pages/EvaluationPage'
import { EventsPage } from './pages/EventsPage'
import { MisstatementPage } from './pages/MisstatementPage'
import { NewEngagementPage } from './pages/NewEngagementPage'
import { RaiseMisstatementPage } from './pages/RaiseMisstatementPage'
import { RepLetterAttachmentPage } from './pages/RepLetterAttachmentPage'
import { SchedulePage } from './pages/SchedulePage'
import { SpinePage } from './pages/SpinePage'
import { TcwgExtractPage } from './pages/TcwgExtractPage'
import { ThresholdsPage } from './pages/ThresholdsPage'
import { WorkingPaperPage } from './pages/WorkingPaperPage'
import { href, useRoute, type Route } from './router'

type Backend = { state: 'checking' } | { state: 'up'; health: Health } | { state: 'down' }

function useBackend(): Backend {
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
  return backend
}

function Screen({ route }: { route: Route }) {
  switch (route.name) {
    case 'engagements':
      return <EngagementsPage />
    case 'new-engagement':
      return <NewEngagementPage />
    case 'schedule':
      return <SchedulePage id={route.id} />
    case 'evaluation':
      return <EvaluationPage id={route.id} />
    case 'tcwg-extract':
      return <TcwgExtractPage id={route.id} />
    case 'rep-letter-attachment':
      return <RepLetterAttachmentPage id={route.id} />
    case 'working-paper':
      return <WorkingPaperPage id={route.id} />
    case 'thresholds':
      return <ThresholdsPage id={route.id} />
    case 'spine':
      return <SpinePage id={route.id} />
    case 'events':
      return <EventsPage id={route.id} />
    case 'raise':
      return <RaiseMisstatementPage id={route.id} />
    case 'misstatement':
      return <MisstatementPage id={route.id} />
  }
}

export function App() {
  const route = useRoute()
  const backend = useBackend()
  const main = useRef<HTMLElement>(null)
  const address = href(route)
  const opened = useRef(address)

  // When the screen changes, keyboard focus moves to the new screen's content, so a person
  // using a keyboard or a screen reader starts at what they asked for and not at a link
  // that is no longer there. Not on the first load: focus stays where the browser put it.
  useEffect(() => {
    if (opened.current === address) return
    opened.current = address
    main.current?.focus()
  }, [address])

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 font-sans text-slate-900">
      <button
        type="button"
        onClick={() => {
          main.current?.focus()
        }}
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-20 focus:rounded focus:border focus:border-slate-800 focus:bg-white focus:px-3 focus:py-1.5 focus:text-sm focus:font-medium"
      >
        Skip to the content
      </button>
      <header className="border-b border-slate-200 bg-white print:hidden">
        <div className="mx-auto flex max-w-7xl flex-wrap items-baseline gap-x-6 gap-y-1 px-4 py-3 sm:px-6">
          <div className="flex items-baseline gap-3">
            <a
              href={href({ name: 'engagements' })}
              className="text-lg font-semibold hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
            >
              Misstatements Rollup
            </a>
            <span className="text-sm text-slate-500">SA 450 · OAK Audit</span>
          </div>
          <nav aria-label="Main" className="text-sm">
            <a
              href={href({ name: 'engagements' })}
              aria-current={route.name === 'engagements' ? 'page' : undefined}
              className="rounded px-1 py-0.5 text-slate-700 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700 aria-[current=page]:font-semibold aria-[current=page]:text-slate-900"
            >
              Engagements
            </a>
          </nav>
        </div>
      </header>

      <main
        ref={main}
        tabIndex={-1}
        className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 focus:outline-none sm:px-6"
      >
        <Screen route={route} />
      </main>

      <footer className="border-t border-slate-200 bg-white print:hidden">
        <p role="status" className="mx-auto max-w-7xl px-4 py-2 text-xs text-slate-500 sm:px-6">
          {backend.state === 'checking' && 'Checking the backend…'}
          {backend.state === 'up' &&
            `Backend ${backend.health.module} ${backend.health.version} is ${backend.health.status}.`}
          {backend.state === 'down' && 'Backend unreachable: start it on port 8003.'}
        </p>
      </footer>
    </div>
  )
}
