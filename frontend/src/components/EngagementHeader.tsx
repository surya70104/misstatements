// The top of every screen that belongs to one engagement: where it is, what it is called,
// and the tabs that lead to the engagement's other screens.
import type { ReactNode } from 'react'

import { href } from '../router'
import { EngagementNav } from './EngagementNav'

const LINK = 'underline decoration-slate-300 underline-offset-2 hover:decoration-slate-700'

export function Breadcrumb({
  id,
  label,
  here,
}: {
  id: string
  label: string | null
  here: string
}) {
  return (
    <nav aria-label="Breadcrumb" className="mb-3 text-sm text-slate-600">
      <a href={href({ name: 'engagements' })} className={LINK}>
        Engagements
      </a>
      <span aria-hidden="true"> / </span>
      <a href={href({ name: 'schedule', id })} className={LINK}>
        {label ?? 'Engagement'}
      </a>
      <span aria-hidden="true"> / </span>
      <span>{here}</span>
    </nav>
  )
}

export function EngagementHeader({
  id,
  label,
  headingId,
  screen,
  tab,
  children,
}: {
  id: string
  label: string
  headingId: string
  screen: string
  tab: 'schedule' | 'evaluation' | 'thresholds' | 'spine' | 'events'
  children?: ReactNode
}) {
  return (
    <header>
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <h1 id={headingId} className="text-xl font-semibold">
            {label}
          </h1>
          <p className="mt-1 text-sm text-slate-600">{screen}</p>
        </div>
        {children}
      </div>
      <EngagementNav id={id} current={tab} />
    </header>
  )
}
