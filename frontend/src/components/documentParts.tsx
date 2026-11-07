// The pieces the generated documents share: the TCWG extract and the attachment to the
// written representation. Display only: every figure shown is the backend's.
import type { ReactNode } from 'react'

import type { BothWays, Evaluation, GrossNet, TcwgRow } from '../api'
import { rupees } from '../format'
import { STATE_LABEL, TYPE_LABEL } from '../labels'
import { href } from '../router'
import { Panel } from './panels'

const LINK = 'underline decoration-slate-300 underline-offset-2 hover:decoration-slate-700'
export const HEAD = 'px-3 py-2 text-right font-semibold'
export const LEFT = 'px-3 py-2 text-left font-semibold'
export const NUMBER = 'px-3 py-2 text-right tabular-nums'
export const TABLE = 'w-full border-collapse text-sm'
export const THEAD = 'bg-slate-100 text-xs text-slate-600 print:bg-transparent'
export const ROW = 'border-t border-slate-200 align-top'

export function Explained({ summary, children }: { summary: string; children: ReactNode }) {
  return (
    <details className="mt-3 text-xs text-slate-600 print:hidden">
      <summary className="cursor-pointer text-slate-700 underline decoration-slate-300 underline-offset-2">
        {summary}
      </summary>
      <p className="mt-1 max-w-4xl">{children}</p>
    </details>
  )
}

/** An effect the backend could not determine is said to be so, never shown as nil. */
export function Effect({ value }: { value: string | null }) {
  return value === null ? (
    <span className="text-slate-500">Not determined</span>
  ) : (
    <span className="tabular-nums">{rupees(value)}</span>
  )
}

export function Figures({ sums }: { sums: BothWays }) {
  const cell = (pair: GrossNet, way: keyof GrossNet) => (
    <td className={NUMBER}>{rupees(pair[way])}</td>
  )
  return (
    <>
      {cell(sums.profit_before_tax, 'gross')}
      {cell(sums.profit_before_tax, 'net')}
      {cell(sums.net_assets, 'gross')}
      {cell(sums.net_assets, 'net')}
    </>
  )
}

export function FigureHeads() {
  return (
    <>
      <th scope="col" className={HEAD}>
        Profit before tax, gross
      </th>
      <th scope="col" className={HEAD}>
        Profit before tax, net
      </th>
      <th scope="col" className={HEAD}>
        Net assets, gross
      </th>
      <th scope="col" className={HEAD}>
        Net assets, net
      </th>
    </>
  )
}

export function ItemRows({ items }: { items: TcwgRow[] }) {
  return (
    <>
      {items.map((item) => (
        <tr key={item.ref} className={ROW}>
          <th scope="row" className="px-3 py-2 text-left font-medium whitespace-nowrap">
            <a href={href({ name: 'misstatement', id: item.id })} className={LINK}>
              {item.ref}
            </a>
          </th>
          <td className="px-3 py-2">{TYPE_LABEL[item.type]}</td>
          <td className="px-3 py-2 break-words">
            {item.description}
            {item.classification_only && (
              <span className="block text-xs text-slate-500">Classification only</span>
            )}
            {item.refusal_reason !== null && (
              <span className="block text-xs text-slate-600">
                Management's reason for not correcting: {item.refusal_reason}
              </span>
            )}
          </td>
          <td className="px-3 py-2">{STATE_LABEL[item.state]}</td>
          <td className={NUMBER}>
            <Effect value={item.profit_before_tax} />
          </td>
          <td className={NUMBER}>
            <Effect value={item.net_assets} />
          </td>
        </tr>
      ))}
    </>
  )
}

export function ItemHeads() {
  return (
    <tr>
      <th scope="col" className={LEFT}>
        Ref
      </th>
      <th scope="col" className={LEFT}>
        Type
      </th>
      <th scope="col" className={LEFT}>
        Description
      </th>
      <th scope="col" className={LEFT}>
        State
      </th>
      <th scope="col" className={HEAD}>
        Effect on profit before tax
      </th>
      <th scope="col" className={HEAD}>
        Effect on net assets
      </th>
    </tr>
  )
}

export function PriorPeriodSection({
  id,
  prior,
}: {
  id: string
  prior: Evaluation['prior_period']
}) {
  if (prior.items.length === 0) return null
  return (
    <Panel id={id} title="Prior-period uncorrected misstatements">
      <p className="max-w-3xl text-sm text-slate-700">
        Misstatements left uncorrected in prior periods and carried forward, each with its
        current-period effect and its cumulative effect. They are not in the totals above.
      </p>
      <div className="mt-3 overflow-x-auto">
        <table className={TABLE}>
          <caption className="sr-only">
            Prior-period items, each with its current-period and cumulative effect
          </caption>
          <thead className={THEAD}>
            <tr>
              <th scope="col" className={LEFT}>
                Ref
              </th>
              <th scope="col" className={LEFT}>
                Prior-period item
              </th>
              <th scope="col" className={HEAD}>
                Current period: profit before tax
              </th>
              <th scope="col" className={HEAD}>
                Current period: net assets
              </th>
              <th scope="col" className={HEAD}>
                Cumulative: profit before tax
              </th>
              <th scope="col" className={HEAD}>
                Cumulative: net assets
              </th>
            </tr>
          </thead>
          <tbody>
            {prior.items.map((item) => (
              <tr key={item.ref} className={ROW}>
                <th scope="row" className="px-3 py-2 text-left font-medium whitespace-nowrap">
                  {item.ref}
                </th>
                <td className="px-3 py-2 break-words">
                  {item.description}
                  <span className="block text-xs text-slate-600">
                    {item.prior_period} · {item.source_ref}
                  </span>
                </td>
                <td className={NUMBER}>{rupees(item.current_period.profit_before_tax)}</td>
                <td className={NUMBER}>{rupees(item.current_period.net_assets)}</td>
                <td className={NUMBER}>{rupees(item.cumulative.profit_before_tax)}</td>
                <td className={NUMBER}>{rupees(item.cumulative.net_assets)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-5 overflow-x-auto">
        <table className={TABLE}>
          <caption className="sr-only">
            The current year's uncorrected misstatements together with the prior-period items, on
            each basis
          </caption>
          <thead className={THEAD}>
            <tr>
              <th scope="col" className={LEFT}>
                Current year with prior-period items
              </th>
              <FigureHeads />
            </tr>
          </thead>
          <tbody>
            <tr className={ROW}>
              <th scope="row" className="px-3 py-2 text-left font-medium">
                Current-period basis
              </th>
              <Figures sums={prior.with_prior_period.current_period} />
            </tr>
            <tr className={ROW}>
              <th scope="row" className="px-3 py-2 text-left font-medium">
                Cumulative basis
              </th>
              <Figures sums={prior.with_prior_period.cumulative} />
            </tr>
          </tbody>
        </table>
      </div>
    </Panel>
  )
}
