// The Dr/Cr lines (spec section 3.1): a misstatement is double-entry, and the amounts live
// in the Financial Spine. Each line is shown with its ledger, the group it sits under, and
// its financial classification: the Schedule III head, the statement and the section the
// effects are computed on. Nothing is added up here.
import type { Misstatement, SpineLine } from '../../api'
import { dateTime, isZero, NOT_AVAILABLE, rupees } from '../../format'
import { natureLabel, sectionLabel } from '../../labels'
import { Fact, Panel, Unavailable } from '../panels'

const HEAD = 'px-3 py-2 font-semibold'

// Below the `lg` width a cell is a labelled line: its column's name, then its value.
const CELL =
  'px-3 py-2 max-lg:flex max-lg:gap-3 max-lg:px-0 max-lg:py-1 max-lg:before:w-32 max-lg:before:shrink-0 max-lg:before:pt-0.5 max-lg:before:text-xs max-lg:before:tracking-wide max-lg:before:text-slate-500 max-lg:before:uppercase max-lg:before:content-[attr(data-label)]'

function Amount({ value }: { value: string }) {
  // The side a line does not carry is left empty rather than shown as a nil amount.
  return isZero(value) ? (
    <span className="text-slate-500">{NOT_AVAILABLE}</span>
  ) : (
    <span className="tabular-nums">{rupees(value)}</span>
  )
}

function Line({ line }: { line: SpineLine }) {
  return (
    <tr className="border-t border-slate-200 align-top max-lg:block max-lg:py-3">
      <th
        scope="row"
        className="px-3 py-2 text-left font-medium max-lg:block max-lg:px-0 max-lg:pt-0 max-lg:pb-1"
      >
        {line.ledger_name}
      </th>
      <td data-label="Group" className={`${CELL} text-slate-700`}>
        {line.parent_chain.length > 0 ? line.parent_chain.join(' › ') : NOT_AVAILABLE}
      </td>
      <td data-label="Schedule III head" className={CELL}>
        <span className="min-w-0 break-all">{line.head_id ?? 'Not mapped'}</span>
      </td>
      <td data-label="Statement" className={CELL}>
        {natureLabel(line.nature) ?? NOT_AVAILABLE}
      </td>
      <td data-label="Section" className={CELL}>
        {sectionLabel(line.section) ?? NOT_AVAILABLE}
      </td>
      <td data-label="Debit" className={`${CELL} lg:text-right lg:whitespace-nowrap`}>
        <Amount value={line.dr} />
      </td>
      <td data-label="Credit" className={`${CELL} lg:text-right lg:whitespace-nowrap`}>
        <Amount value={line.cr} />
      </td>
    </tr>
  )
}

function When({ value }: { value: string | null }) {
  if (value === null) return <>{NOT_AVAILABLE}</>
  return <time dateTime={value}>{dateTime(value)}</time>
}

function SpineAdjustment({ misstatement }: { misstatement: Misstatement }) {
  const { spine } = misstatement
  return (
    <div className="mt-5 border-t border-slate-200 pt-4">
      <h3 className="text-xs font-semibold tracking-wide text-slate-600 uppercase">
        Adjustment in the Financial Spine
      </h3>
      <dl className="mt-3 grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
        <Fact label="Status">{spine.adjustment_status ?? NOT_AVAILABLE}</Fact>
        <Fact label="Kind">{spine.kind ?? NOT_AVAILABLE}</Fact>
        <Fact label="Reference in the Spine">{spine.finding_ref ?? NOT_AVAILABLE}</Fact>
        <Fact label="Gross size">
          <span className="tabular-nums">{rupees(spine.measure)}</span>
        </Fact>
        <Fact label="Proposed by">{spine.proposed_by ?? NOT_AVAILABLE}</Fact>
        <Fact label="Proposed">
          <When value={spine.proposed_at} />
        </Fact>
        <Fact label="Decided by">{spine.decided_by ?? NOT_AVAILABLE}</Fact>
        <Fact label="Decided">
          <When value={spine.decided_at} />
        </Fact>
        {spine.decision_note !== null && (
          <Fact label="Decision note" wide>
            {spine.decision_note}
          </Fact>
        )}
      </dl>
    </div>
  )
}

export function AccountingLines({ misstatement }: { misstatement: Misstatement }) {
  const { lines, detail } = misstatement.spine

  return (
    <Panel id="lines" title="Dr/Cr lines">
      {lines.length === 0 ? (
        <Unavailable what="The Dr/Cr lines are not available." why={detail} />
      ) : (
        <>
          <table className="w-full border-collapse text-sm max-lg:block">
            <caption className="sr-only">Dr/Cr lines with their financial classification</caption>
            <thead className="bg-slate-100 text-left text-xs tracking-wide text-slate-600 uppercase max-lg:sr-only">
              <tr>
                <th scope="col" className={HEAD}>
                  Ledger
                </th>
                <th scope="col" className={HEAD}>
                  Group
                </th>
                <th scope="col" className={HEAD}>
                  Schedule III head
                </th>
                <th scope="col" className={HEAD}>
                  Statement
                </th>
                <th scope="col" className={HEAD}>
                  Section
                </th>
                <th scope="col" className={`${HEAD} text-right`}>
                  Debit
                </th>
                <th scope="col" className={`${HEAD} text-right`}>
                  Credit
                </th>
              </tr>
            </thead>
            <tbody className="max-lg:block max-lg:[&>tr:first-child]:border-t-0 max-lg:[&>tr:first-child]:pt-0">
              {lines.map((line, index) => (
                <Line key={`${line.ledger_key}-${String(index)}`} line={line} />
              ))}
            </tbody>
          </table>
          <SpineAdjustment misstatement={misstatement} />
        </>
      )}
    </Panel>
  )
}
