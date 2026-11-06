// What the forms share: one look for a field, a button and the outcome of a write. A form
// collects what a person declares and sends it; the backend validates it and decides.
import type { ReactNode } from 'react'

const BUTTON =
  'rounded border px-3 py-1.5 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700 disabled:cursor-default disabled:opacity-60'
export const SECONDARY = `${BUTTON} border-slate-300 bg-white text-slate-800 hover:bg-slate-100 disabled:hover:bg-white`
export const PRIMARY = `${BUTTON} border-slate-800 bg-slate-800 text-white hover:bg-slate-700 disabled:hover:bg-slate-800`
export const LINK_BUTTON = `${BUTTON} inline-block border-slate-300 bg-white text-slate-800 hover:bg-slate-100`

export const INPUT =
  'mt-1 block w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700 disabled:bg-slate-100'

/** A labelled field. `hint` says what is expected; it is tied to the control for a reader. */
export function Field({
  id,
  label,
  required = false,
  hint,
  children,
}: {
  id: string
  label: string
  required?: boolean
  hint?: string
  children: ReactNode
}) {
  return (
    <div>
      <label htmlFor={id} className="text-sm font-medium text-slate-800">
        {label}{' '}
        <span className="font-normal text-slate-600">{required ? '(required)' : '(optional)'}</span>
      </label>
      {children}
      {hint !== undefined && (
        <p id={`${id}-hint`} className="mt-1 text-xs text-slate-600">
          {hint}
        </p>
      )}
    </div>
  )
}

/** A write the backend accepted. */
export function Recorded({ children }: { children: ReactNode }) {
  return (
    <p
      role="status"
      aria-live="polite"
      className="rounded border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-900"
    >
      {children}
    </p>
  )
}

/** An exact amount as a person types it: digits, and at most two decimals. */
export function isAmount(value: string): boolean {
  return /^\d{1,13}(\.\d{1,2})?$/.test(value.trim())
}

/** An exact amount that may be negative: an effect, signed as the schedule signs it. */
export function isSignedAmount(value: string): boolean {
  return /^-?\d{1,13}(\.\d{1,2})?$/.test(value.trim())
}
