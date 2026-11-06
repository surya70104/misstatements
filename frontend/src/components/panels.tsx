// Small pieces the sections of the detail and evaluation screens share.
import type { ReactNode } from 'react'

/** One section of the detail page: a titled panel. */
export function Panel({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section
      aria-labelledby={`${id}-heading`}
      className="rounded-md border border-slate-200 bg-white"
    >
      <h2
        id={`${id}-heading`}
        className="border-b border-slate-200 px-5 py-3 text-sm font-semibold text-slate-900"
      >
        {title}
      </h2>
      <div className="px-5 py-4">{children}</div>
    </section>
  )
}

/** A labelled value in a definition list. */
export function Fact({
  label,
  wide = false,
  children,
}: {
  label: string
  wide?: boolean
  children: ReactNode
}) {
  return (
    <div className={wide ? 'sm:col-span-2 lg:col-span-4' : ''}>
      <dt className="text-xs tracking-wide text-slate-500 uppercase">{label}</dt>
      <dd className="mt-1 text-sm break-words text-slate-900">{children}</dd>
    </div>
  )
}

/**
 * Something the backend could not give, with its reason. Never a zero, never a blank: a
 * person must be able to tell "nil" from "not known".
 */
export function Unavailable({ what, why }: { what: string; why: string | null }) {
  return (
    <p className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      {what}
      {why !== null && <span className="mt-1 block text-amber-800">{why}</span>}
    </p>
  )
}

/** The backend's own explanation of a figure, shown as it was sent. */
export function Basis({ children }: { children: ReactNode }) {
  return <p className="mt-1 max-w-3xl text-xs text-slate-600">{children}</p>
}
