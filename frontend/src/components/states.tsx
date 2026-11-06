// The three states every screen can be in besides showing its data: loading, empty, and
// failed. One look for each, so a person always knows which one they are seeing.
import type { ReactNode } from 'react'

import { ApiError } from '../api'

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <p role="status" aria-live="polite" className="py-10 text-center text-sm text-slate-500">
      {label}
    </p>
  )
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-slate-300 bg-white px-6 py-10 text-center">
      <p className="text-sm font-medium text-slate-800">{title}</p>
      {children !== undefined && <div className="mt-2 text-sm text-slate-600">{children}</div>}
    </div>
  )
}

/**
 * A failed load, in the backend's own words where it gave any. The reference line names
 * the request and its status, which is what a person reports when asking for help.
 */
export function ErrorState({
  title = 'This could not be loaded',
  error,
  onRetry,
}: {
  title?: string
  error: Error
  onRetry?: () => void
}) {
  const api = error instanceof ApiError ? error : null
  return (
    <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-5 py-4">
      <p className="text-sm font-semibold text-red-900">{title}</p>
      <p className="mt-1 text-sm text-red-800">{error.message}</p>
      {api !== null && !api.unreachable && (
        <p className="mt-2 text-xs text-red-700">
          {api.path} answered {api.status}
          {api.pendingDecision !== null && ` · pending decision ${api.pendingDecision}`}
        </p>
      )}
      {onRetry !== undefined && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-900 hover:bg-red-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-700"
        >
          Try again
        </button>
      )}
    </div>
  )
}

type Tone = 'neutral' | 'good' | 'attention'

const TONES: Record<Tone, string> = {
  neutral: 'border-slate-300 bg-slate-50 text-slate-700',
  good: 'border-emerald-300 bg-emerald-50 text-emerald-800',
  attention: 'border-amber-300 bg-amber-50 text-amber-900',
}

/** A short status in words. The colour supports the words and never replaces them. */
export function Pill({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-block rounded border px-2 py-0.5 text-xs font-medium whitespace-nowrap ${TONES[tone]}`}
    >
      {children}
    </span>
  )
}
