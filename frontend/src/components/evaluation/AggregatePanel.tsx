// The aggregate view (spec sections 4.1 and 10.3): gross and net, profit before tax and net
// assets, with and without the projected items, against CTT, PM and OM, and the gross
// contribution of each type.
//
// Every amount is the backend's, read from the evaluation. Whether a figure is at or above
// a line is the backend's too: the gates name the measures that reach performance
// materiality and overall materiality, and this table marks exactly those. The only
// arithmetic here is the percentage, which is presentation (architecture D16), exact, and
// done with integers in `format.ts`.
import type { Evaluation, Measure } from '../../api'
import { count, NOT_AVAILABLE, percentOf, rupees } from '../../format'
import { STATE_LABEL } from '../../labels'
import { NotAccumulated } from '../NotAccumulated'
import { Basis, Panel } from '../panels'
import { Pill } from '../states'

const HEAD = 'px-3 py-2 text-right font-semibold'

// Below the `md` width a cell is a labelled value: its column's name, then the figure.
const CELL =
  'px-3 py-2 text-right tabular-nums max-md:flex max-md:justify-between max-md:gap-3 max-md:px-0 max-md:py-0.5 max-md:text-left max-md:before:text-xs max-md:before:text-slate-500 max-md:before:content-[attr(data-label)]'

type Way = 'gross' | 'net'

function Reached({ line }: { line: string }) {
  return (
    <span className="ml-2 inline-block align-middle">
      <Pill tone="attention">At or above {line}</Pill>
    </span>
  )
}

function Row({
  label,
  measureKey,
  way,
  measure,
  evaluation,
}: {
  label: string
  measureKey: 'profit' | 'net_assets'
  way: Way
  measure: Measure
  evaluation: Evaluation
}) {
  const { threshold, gates } = evaluation
  const figure = way === 'gross' ? measure.gross : measure.net
  const without = way === 'gross' ? measure.gross_without_projected : measure.net_without_projected
  // The name the gates use for this measure in `fires_on`.
  const name = `${measureKey}.${way}`
  return (
    <tr className="border-t border-slate-200 max-md:block max-md:py-2">
      <th scope="row" className="px-3 py-2 text-left font-medium max-md:block max-md:px-0">
        {label} <span className="font-normal text-slate-500">{way}</span>
      </th>
      <td data-label="With projected" className={`${CELL} font-medium`}>
        {rupees(figure)}
      </td>
      <td data-label="Without projected" className={CELL}>
        {rupees(without)}
      </td>
      <td data-label="% of CTT" className={CELL}>
        {percentOf(figure, threshold?.ctt) ?? NOT_AVAILABLE}
      </td>
      <td data-label="% of PM" className={CELL}>
        <span>
          {percentOf(figure, threshold?.pm) ?? NOT_AVAILABLE}
          {gates.soft.fires_on.includes(name) && <Reached line="PM" />}
        </span>
      </td>
      <td data-label="% of OM" className={CELL}>
        <span>
          {percentOf(figure, threshold?.om) ?? NOT_AVAILABLE}
          {gates.hard.fires_on.includes(name) && <Reached line="OM" />}
        </span>
      </td>
    </tr>
  )
}

function ByType({ label, measure }: { label: string; measure: Measure }) {
  return (
    <tr className="border-t border-slate-200 max-md:block max-md:py-2">
      <th scope="row" className="px-3 py-2 text-left font-medium max-md:block max-md:px-0">
        {label} <span className="font-normal text-slate-500">gross</span>
      </th>
      <td data-label="Factual" className={CELL}>
        {rupees(measure.factual_gross)}
      </td>
      <td data-label="Judgemental" className={CELL}>
        {rupees(measure.judgemental_gross)}
      </td>
      <td data-label="Projected" className={CELL}>
        {rupees(measure.projected_gross)}
      </td>
    </tr>
  )
}

function Line({ name, amount }: { name: string; amount: string | null }) {
  return (
    <th scope="col" className={HEAD}>
      % of {name}
      <span className="block font-normal tabular-nums">
        {amount === null ? 'not set' : rupees(amount)}
      </span>
    </th>
  )
}

export function AggregatePanel({ evaluation }: { evaluation: Evaluation }) {
  const { aggregate, threshold } = evaluation
  const pbt = aggregate.profit_before_tax
  const na = aggregate.net_assets

  return (
    <Panel id="aggregate" title="Aggregate of uncorrected misstatements">
      <p className="text-sm text-slate-700">
        {threshold === null ? (
          'Thresholds are not set, so there are no lines to compare the aggregate with.'
        ) : (
          <>
            Against thresholds version {threshold.version_no}:{' '}
            <span className="tabular-nums">
              CTT {rupees(threshold.ctt)} · PM {rupees(threshold.pm)} · OM {rupees(threshold.om)}
            </span>
          </>
        )}
      </p>

      {!aggregate.complete && (
        <p className="mt-3 rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          This aggregate is incomplete: {count(aggregate.unresolved.length, 'misstatement')} could
          not be aggregated ({aggregate.unresolved.join(', ')}). The figures cover the others only.
        </p>
      )}

      <table className="mt-4 w-full border-collapse text-sm max-md:block">
        <caption className="sr-only">
          Aggregate uncorrected misstatements, with and without the projected items, against the
          three lines
        </caption>
        <thead className="bg-slate-100 text-xs text-slate-600 max-md:sr-only">
          <tr>
            <th scope="col" className="px-3 py-2 text-left font-semibold">
              Effect
            </th>
            <th scope="col" className={HEAD}>
              With projected
            </th>
            <th scope="col" className={HEAD}>
              Without projected
            </th>
            <Line name="CTT" amount={threshold?.ctt ?? null} />
            <Line name="PM" amount={threshold?.pm ?? null} />
            <Line name="OM" amount={threshold?.om ?? null} />
          </tr>
        </thead>
        <tbody className="max-md:block">
          <Row
            label="Profit before tax"
            measureKey="profit"
            way="gross"
            measure={pbt}
            evaluation={evaluation}
          />
          <Row
            label="Profit before tax"
            measureKey="profit"
            way="net"
            measure={pbt}
            evaluation={evaluation}
          />
          <Row
            label="Net assets"
            measureKey="net_assets"
            way="gross"
            measure={na}
            evaluation={evaluation}
          />
          <Row
            label="Net assets"
            measureKey="net_assets"
            way="net"
            measure={na}
            evaluation={evaluation}
          />
        </tbody>
      </table>
      <Basis>
        Each percentage compares the size of the figure that includes the projected items with the
        line, to one decimal place. A figure is marked at or above a line where the gate at that
        line names it.
      </Basis>

      <h3 className="mt-5 text-xs font-semibold tracking-wide text-slate-600 uppercase">
        Contribution by type
      </h3>
      <table className="mt-2 w-full max-w-3xl border-collapse text-sm max-md:block">
        <caption className="sr-only">
          Gross contribution of factual, judgemental and projected misstatements
        </caption>
        <thead className="bg-slate-100 text-xs text-slate-600 max-md:sr-only">
          <tr>
            <th scope="col" className="px-3 py-2 text-left font-semibold">
              Effect
            </th>
            <th scope="col" className={HEAD}>
              Factual
            </th>
            <th scope="col" className={HEAD}>
              Judgemental
            </th>
            <th scope="col" className={HEAD}>
              Projected
            </th>
          </tr>
        </thead>
        <tbody className="max-md:block">
          <ByType label="Profit before tax" measure={pbt} />
          <ByType label="Net assets" measure={na} />
        </tbody>
      </table>

      <div className="mt-4 space-y-1 text-xs text-slate-600">
        <p>
          {count(aggregate.counted.length, 'misstatement')} accumulated
          {aggregate.counted.length > 0 && ` (${aggregate.counted.join(', ')})`}
          {aggregate.not_accumulated.length > 0 && (
            <>; clearly trivial, not accumulated: {aggregate.not_accumulated.join(', ')}</>
          )}
          {aggregate.excluded.length > 0 && (
            <>
              ; not counted:{' '}
              {aggregate.excluded
                .map((entry) => `${entry.ref} (${STATE_LABEL[entry.state].toLowerCase()})`)
                .join(', ')}
            </>
          )}
          .
        </p>
        {aggregate.not_accumulated.length > 0 && (
          <p>
            A misstatement below the clearly-trivial threshold stays in the schedule and is in no
            aggregate figure and no gate.
          </p>
        )}
        {(aggregate.not_accumulated.length > 0 ||
          aggregate.not_accumulated_total.accumulated_together.length > 0) && (
          <NotAccumulated total={aggregate.not_accumulated_total} />
        )}
        {aggregate.projected.length > 0 && (
          <p>Projected misstatements counted: {aggregate.projected.join(', ')}.</p>
        )}
        {aggregate.classification_only.length > 0 && (
          <p>Classification only, contributing nil: {aggregate.classification_only.join(', ')}.</p>
        )}
        <details>
          <summary className="cursor-pointer text-slate-700 underline decoration-slate-300 underline-offset-2">
            How the aggregate is computed
          </summary>
          <p className="mt-1 max-w-4xl">{aggregate.basis}</p>
        </details>
      </div>
    </Panel>
  )
}
