// The running totals at the top of the schedule (spec sections 4.1 and 10.1): the aggregate
// of the uncorrected misstatements, gross and net, on profit before tax and on net assets,
// in rupees and as a percentage of each of the three lines.
//
// Every amount here is the backend's, read from the evaluation. The screen adds nothing up.
// The only arithmetic is the percentage, which is presentation (architecture D16) and is
// computed exactly, with integers, in `format.ts`.
//
// "Always visible" (spec section 10.1) is taken at its word: the totals stay in view while
// the schedule scrolls beneath them at every width, a phone included, where the table is set
// smaller so that it fits and leaves room for the schedule.
import type { Evaluation, Measure } from '../api'
import { count, NOT_AVAILABLE, percentOf, rupees } from '../format'
import { STATE_LABEL } from '../labels'
import { NotAccumulated } from './NotAccumulated'

type Line = { name: string; amount: string | null }

const HEAD = 'px-1.5 py-1 text-right font-semibold sm:px-3 sm:py-1.5'
const CELL = 'px-1.5 py-1 text-right tabular-nums whitespace-nowrap sm:px-3 sm:py-1.5'

function Row({
  label,
  short,
  way,
  figure,
  lines,
}: {
  label: string
  short: string
  way: string
  figure: string
  lines: Line[]
}) {
  return (
    <tr className="border-t border-slate-200">
      <th scope="row" className="px-1.5 py-1 text-left font-medium sm:px-3 sm:py-1.5">
        {/* On a phone the short name is shown; a screen reader is given the full one. */}
        <span className="max-sm:sr-only">{label}</span>
        <span aria-hidden="true" className="sm:hidden">
          {short}
        </span>{' '}
        <span className="font-normal text-slate-500">{way}</span>
      </th>
      <td className={`${CELL} font-medium`}>{rupees(figure)}</td>
      {lines.map((line) => (
        <td key={line.name} className={CELL}>
          {percentOf(figure, line.amount) ?? NOT_AVAILABLE}
        </td>
      ))}
    </tr>
  )
}

function refs(list: string[]): string {
  return list.join(', ')
}

function WithoutProjected({ name, measure }: { name: string; measure: Measure }) {
  return (
    <>
      {name} {rupees(measure.gross_without_projected)} gross and{' '}
      {rupees(measure.net_without_projected)} net
    </>
  )
}

export function RunningTotals({ evaluation }: { evaluation: Evaluation }) {
  const { aggregate, threshold } = evaluation
  const lines: Line[] = [
    { name: 'CTT', amount: threshold?.ctt ?? null },
    { name: 'PM', amount: threshold?.pm ?? null },
    { name: 'OM', amount: threshold?.om ?? null },
  ]
  const pbt = aggregate.profit_before_tax
  const na = aggregate.net_assets

  return (
    <>
      {/* A direct child of the page, so it stays in view while the schedule scrolls
          beneath it (spec section 10.1: "always visible"). */}
      <section
        aria-labelledby="totals-heading"
        className="sticky top-0 z-10 mt-5 rounded-md border border-slate-300 bg-white shadow-sm"
      >
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 px-3 pt-2 pb-1.5 sm:px-4 sm:pt-3 sm:pb-2">
          <h2 id="totals-heading" className="text-sm font-semibold">
            Running totals: uncorrected misstatements
          </h2>
          <p className="text-xs text-slate-600">
            {threshold === null
              ? 'Thresholds are not set, so there are no lines to compare with.'
              : `Against thresholds version ${String(threshold.version_no)}`}
          </p>
        </div>

        {!aggregate.complete && (
          <p className="border-t border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-900 sm:px-4 sm:py-2 sm:text-sm">
            These totals are incomplete: {count(aggregate.unresolved.length, 'misstatement')} could
            not be aggregated ({refs(aggregate.unresolved)}). The figures cover the others only.
          </p>
        )}

        {/* An amount too long for a narrow screen scrolls inside this box, never the page. */}
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-xs sm:text-sm">
            <caption className="sr-only">
              Aggregate uncorrected misstatements in rupees and as a percentage of the
              clearly-trivial threshold, performance materiality and overall materiality
            </caption>
            <thead className="bg-slate-100 text-xs text-slate-600">
              <tr>
                <th scope="col" className="px-1.5 py-1 text-left font-semibold sm:px-3 sm:py-1.5">
                  Effect
                </th>
                <th scope="col" className={HEAD}>
                  Amount
                </th>
                {lines.map((line) => (
                  <th key={line.name} scope="col" className={HEAD}>
                    % of {line.name}
                    <span className="block font-normal tabular-nums max-sm:hidden">
                      {line.amount === null ? 'not set' : rupees(line.amount)}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <Row
                label="Profit before tax"
                short="PBT"
                way="gross"
                figure={pbt.gross}
                lines={lines}
              />
              <Row label="Profit before tax" short="PBT" way="net" figure={pbt.net} lines={lines} />
              <Row
                label="Net assets"
                short="Net assets"
                way="gross"
                figure={na.gross}
                lines={lines}
              />
              <Row label="Net assets" short="Net assets" way="net" figure={na.net} lines={lines} />
            </tbody>
          </table>
        </div>

        {threshold !== null && (
          <p className="border-t border-slate-200 px-3 py-1 text-xs text-slate-600 tabular-nums sm:hidden">
            CTT {rupees(threshold.ctt)} · PM {rupees(threshold.pm)} · OM {rupees(threshold.om)}
          </p>
        )}
      </section>

      <div className="mt-2 space-y-1 px-1 text-xs text-slate-600">
        <p>
          {count(aggregate.counted.length, 'misstatement')} accumulated
          {aggregate.not_accumulated.length > 0 && (
            <>; clearly trivial, not accumulated: {refs(aggregate.not_accumulated)}</>
          )}
          {aggregate.excluded.length > 0 && (
            <>
              ; not counted:{' '}
              {aggregate.excluded
                .map((entry) => `${entry.ref} (${STATE_LABEL[entry.state].toLowerCase()})`)
                .join(', ')}
            </>
          )}
          . The filters below do not change these totals.
        </p>
        {aggregate.not_accumulated.length > 0 && (
          <p>
            A misstatement below the clearly-trivial threshold stays in the schedule and is in none
            of these totals.
          </p>
        )}
        {(aggregate.not_accumulated.length > 0 ||
          aggregate.not_accumulated_total.accumulated_together.length > 0) && (
          <NotAccumulated total={aggregate.not_accumulated_total} />
        )}
        {aggregate.classification_only.length > 0 && (
          <p>Classification only, contributing nil: {refs(aggregate.classification_only)}.</p>
        )}
        {aggregate.projected.length > 0 && (
          <p>
            Includes projected misstatements ({refs(aggregate.projected)}). Without them:{' '}
            <WithoutProjected name="profit before tax" measure={pbt} />;{' '}
            <WithoutProjected name="net assets" measure={na} />.
          </p>
        )}
        <details>
          <summary className="cursor-pointer text-slate-700 underline decoration-slate-300 underline-offset-2">
            How these totals are computed
          </summary>
          <p className="mt-1 max-w-4xl">{aggregate.basis}</p>
          <p className="mt-1 max-w-4xl">
            Each percentage compares the size of the figure with the line, to one decimal place.
          </p>
        </details>
      </div>
    </>
  )
}
