// The Summary of Audit Differences (spec section 6.1): every misstatement with its
// reference, type, description, Dr/Cr lines, effect on profit, effect on net assets, band,
// state, its source (the working paper, the agent run or the review note) and who raised
// it. Display only: the lines are the
// Financial Spine's, the effects and the band are computed by the backend. A misstatement
// with a qualitative factor recorded is marked Escalated beside its band, whatever its
// amount (spec section 5; acceptance 8).
//
// On a wide screen this is a table. Below that width each misstatement becomes a block with
// its values labelled, so the page never scrolls sideways.
import type { ReactNode } from 'react'

import type { Misstatement } from '../api'
import { count, isZero, rupees } from '../format'
import {
  BAND_LABEL,
  BAND_TONE,
  NOT_BANDED,
  raisedFromLabel,
  STATE_LABEL,
  STATE_TONE,
  TYPE_LABEL,
} from '../labels'
import { href } from '../router'
import { Pill } from './states'

const HEAD = 'px-3 py-2 font-semibold'

// Below the `xl` width a cell is a labelled line: its column's name, then its value.
const CELL =
  'px-3 py-3 max-xl:flex max-xl:gap-3 max-xl:px-0 max-xl:py-1 max-xl:before:w-28 max-xl:before:shrink-0 max-xl:before:pt-0.5 max-xl:before:text-xs max-xl:before:tracking-wide max-xl:before:text-slate-500 max-xl:before:uppercase max-xl:before:content-[attr(data-label)]'

function Cell({
  label,
  className = '',
  children,
}: {
  label: string
  className?: string
  children: ReactNode
}) {
  return (
    <td data-label={label} className={`${CELL} ${className}`}>
      {children}
    </td>
  )
}

function Unavailable({ why }: { why: string | null }) {
  return (
    <span className="text-slate-500">
      Not available{why !== null && <span className="block text-xs">{why}</span>}
    </span>
  )
}

function Lines({ misstatement }: { misstatement: Misstatement }) {
  const { lines, detail } = misstatement.spine
  if (lines.length === 0) return <Unavailable why={detail} />
  return (
    <ul className="max-w-md min-w-0 flex-1 space-y-0.5">
      {lines.map((line, index) => {
        const debit = !isZero(line.dr) // a line carries exactly one side above zero
        return (
          <li
            key={`${line.ledger_key}-${String(index)}`}
            className="grid grid-cols-[1.75rem_minmax(0,1fr)_auto] gap-x-2"
          >
            <span className="text-slate-500">{debit ? 'Dr' : 'Cr'}</span>
            <span className={`min-w-0 [overflow-wrap:anywhere] ${debit ? '' : 'pl-3'}`}>
              {line.ledger_name}
            </span>
            <span className="text-right tabular-nums">{rupees(debit ? line.dr : line.cr)}</span>
          </li>
        )
      })}
    </ul>
  )
}

function Effect({
  value,
  misstatement,
}: {
  value: string | null | undefined
  misstatement: Misstatement
}) {
  if (value === null || value === undefined) {
    // Null effects are never shown as zero: the backend could not determine them.
    const effects = misstatement.effects
    const why =
      effects === null
        ? null // the Dr/Cr lines cell already carries the Spine's reason
        : effects.unresolved.length > 0
          ? `Cannot be classified: ${effects.unresolved.join(', ')}`
          : null
    return <Unavailable why={why} />
  }
  return <span className="tabular-nums">{rupees(value)}</span>
}

function BandCell({ misstatement }: { misstatement: Misstatement }) {
  const { band, band_basis: basis, banding, qualitative } = misstatement
  return (
    <div>
      {band === null ? (
        <>
          <Pill tone="attention">{NOT_BANDED}</Pill>
          {basis !== null && <p className="mt-1 max-w-56 text-xs text-slate-500">{basis}</p>}
        </>
      ) : (
        <Pill tone={BAND_TONE[band]}>{BAND_LABEL[band]}</Pill>
      )}
      {banding.classification_only && (
        <p className="mt-1 text-xs text-slate-500">Classification only</p>
      )}
      {banding.range_crosses_pm === true && (
        <p className="mt-1 text-xs text-amber-800">Range crosses PM</p>
      )}
      {qualitative.escalated && (
        <div className="mt-1.5">
          <Pill tone="attention">Escalated</Pill>
          <p className="mt-1 max-w-56 text-xs text-amber-800">
            Listed individually whatever its amount:{' '}
            {count(qualitative.factors.length, 'qualitative factor')} recorded
          </p>
        </div>
      )}
    </div>
  )
}

function Row({ misstatement }: { misstatement: Misstatement }) {
  const { current, effects, state_consistency: consistency } = misstatement
  return (
    <tr className="border-t border-slate-200 align-top max-xl:block max-xl:px-4 max-xl:py-3 xl:hover:bg-slate-50">
      <th
        scope="row"
        className="px-3 py-3 text-left font-medium whitespace-nowrap max-xl:block max-xl:px-0 max-xl:pt-0 max-xl:pb-1 max-xl:text-base"
      >
        <a
          href={href({ name: 'misstatement', id: misstatement.id })}
          className="text-slate-900 underline decoration-slate-300 underline-offset-2 hover:decoration-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
        >
          {misstatement.ref}
        </a>
      </th>
      <Cell label="Type">
        <div>
          {TYPE_LABEL[current.type]}
          {current.type === 'projected' && (
            <p className="mt-1 text-xs text-amber-800">
              From sample {current.sample_ref ?? 'not recorded'}
            </p>
          )}
        </div>
      </Cell>
      <Cell label="Description" className="xl:max-w-64">
        <span className="min-w-0 break-words">{current.description}</span>
      </Cell>
      <Cell label="Dr/Cr lines" className="xl:min-w-64">
        <Lines misstatement={misstatement} />
      </Cell>
      <Cell label="PBT effect" className="xl:text-right xl:whitespace-nowrap">
        <Effect value={effects?.profit_before_tax} misstatement={misstatement} />
      </Cell>
      <Cell label="Net assets effect" className="xl:text-right xl:whitespace-nowrap">
        <Effect value={effects?.net_assets} misstatement={misstatement} />
      </Cell>
      <Cell label="Band">
        <BandCell misstatement={misstatement} />
      </Cell>
      <Cell label="State">
        <div>
          <Pill tone={STATE_TONE[current.state]}>{STATE_LABEL[current.state]}</Pill>
          {consistency.consistent === false && (
            <p className="mt-1 max-w-56 text-xs text-amber-800">
              Differs from the Financial Spine
              {consistency.detail !== null && `: ${consistency.detail}`}
            </p>
          )}
        </div>
      </Cell>
      <Cell label="Source" className="xl:whitespace-nowrap">
        <div>
          {current.source_ref}
          {current.raised_from !== 'wp' && (
            <p className="text-xs text-slate-500">{raisedFromLabel(current.raised_from)}</p>
          )}
        </div>
      </Cell>
      <Cell label="Raised by" className="text-slate-700">
        <span className="min-w-0 break-words">{current.raised_by}</span>
      </Cell>
    </tr>
  )
}

export function ScheduleTable({ misstatements }: { misstatements: Misstatement[] }) {
  return (
    <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
      <table className="w-full border-collapse text-sm max-xl:block">
        <caption className="sr-only">Schedule of misstatements</caption>
        <thead className="bg-slate-100 text-left text-xs tracking-wide text-slate-600 uppercase max-xl:sr-only">
          <tr>
            <th scope="col" className={HEAD}>
              Ref
            </th>
            <th scope="col" className={HEAD}>
              Type
            </th>
            <th scope="col" className={HEAD}>
              Description
            </th>
            <th scope="col" className={HEAD}>
              Dr/Cr lines
            </th>
            <th scope="col" className={`${HEAD} text-right`}>
              PBT effect
            </th>
            <th scope="col" className={`${HEAD} text-right`}>
              Net assets effect
            </th>
            <th scope="col" className={HEAD}>
              Band
            </th>
            <th scope="col" className={HEAD}>
              State
            </th>
            <th scope="col" className={HEAD}>
              Source
            </th>
            <th scope="col" className={HEAD}>
              Raised by
            </th>
          </tr>
        </thead>
        <tbody className="max-xl:block [&>tr:first-child]:border-t-0 xl:[&>tr:first-child]:border-t">
          {misstatements.map((misstatement) => (
            <Row key={misstatement.id} misstatement={misstatement} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
