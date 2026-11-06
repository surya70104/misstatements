// Evaluation runs (spec section 9, `evaluation`: append-only, one row per run). A run is
// the evaluation as it stood when it was recorded: the threshold version and the four
// aggregates. Rows are never changed, so an older run is read exactly as it was written,
// and whether the latest one still describes the evaluation is the backend's to say.
//
// Recording a run sends nothing but the statement that materiality was reassessed first
// (SA 450 paragraph 10). The figures are computed and stored by the backend.
import { Fragment, useState, type SyntheticEvent } from 'react'

import { recordEvaluationRun, type Evaluation, type EvaluationRun } from '../../api'
import { dateTime, NOT_AVAILABLE, rupees } from '../../format'
import {
  BAND_LABEL,
  NOT_BANDED,
  STATE_LABEL,
  TYPE_LABEL,
  determinationLabel,
  gateStatus,
  recordStatus,
  responseStatus,
} from '../../labels'
import { useSubmit } from '../../useSubmit'
import { Fact, Panel } from '../panels'
import { ErrorState, Pill } from '../states'

const HEAD = 'px-3 py-2 font-semibold'

// Below the `lg` width a cell is a labelled line: its column's name, then its value.
const CELL =
  'px-3 py-2 max-lg:flex max-lg:gap-3 max-lg:px-0 max-lg:py-0.5 max-lg:before:w-28 max-lg:before:shrink-0 max-lg:before:text-xs max-lg:before:tracking-wide max-lg:before:text-slate-500 max-lg:before:uppercase max-lg:before:content-[attr(data-label)]'
const MONEY = `${CELL} tabular-nums lg:text-right lg:whitespace-nowrap`

const BUTTON =
  'rounded border px-3 py-1.5 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700 disabled:cursor-default disabled:opacity-60'
const SECONDARY = `${BUTTON} border-slate-300 bg-white text-slate-800 hover:bg-slate-100 disabled:hover:bg-white`
const PRIMARY = `${BUTTON} border-slate-800 bg-slate-800 text-white hover:bg-slate-700 disabled:hover:bg-slate-800`

function kind(run: EvaluationRun): string {
  return run.concluded ? `Conclusion: ${determinationLabel(run.determination) ?? ''}` : 'Run'
}

/** What a recorded row holds beyond its four aggregates, exactly as it was written. */
function Inspection({ run }: { run: EvaluationRun }) {
  const { detail } = run
  const hard = detail.gates?.hard
  const soft = detail.gates?.soft
  return (
    <div className="space-y-4 rounded border border-slate-200 bg-slate-50 px-4 py-4">
      <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
        <Fact label="Recorded by">{run.evaluated_by}</Fact>
        <Fact label="Recorded">
          <time dateTime={run.at}>{dateTime(run.at)}</time>
        </Fact>
        <Fact label="Materiality reassessed">{run.materiality_reassessed ? 'Yes' : 'No'}</Fact>
        <Fact label="Thresholds">
          {detail.threshold === undefined ? (
            NOT_AVAILABLE
          ) : (
            <span className="tabular-nums">
              Version {detail.threshold.version_no}: CTT {rupees(detail.threshold.ctt)} · PM{' '}
              {rupees(detail.threshold.pm)} · OM {rupees(detail.threshold.om)}
            </span>
          )}
        </Fact>
        {detail.figures !== undefined && (
          <>
            <Fact label="PBT without projected">
              <span className="tabular-nums">
                {rupees(detail.figures.profit_before_tax.gross_without_projected)} gross,{' '}
                {rupees(detail.figures.profit_before_tax.net_without_projected)} net
              </span>
            </Fact>
            <Fact label="Net assets without projected">
              <span className="tabular-nums">
                {rupees(detail.figures.net_assets.gross_without_projected)} gross,{' '}
                {rupees(detail.figures.net_assets.net_without_projected)} net
              </span>
            </Fact>
          </>
        )}
        {detail.not_accumulated !== undefined && detail.not_accumulated.length > 0 && (
          <Fact label="Clearly trivial, not accumulated">{detail.not_accumulated.join(', ')}</Fact>
        )}
        {hard !== undefined && <Fact label="Hard gate then">{gateStatus(hard.status).text}</Fact>}
        {soft !== undefined && (
          <Fact label="Soft gate then">
            {gateStatus(soft.status).text}; acknowledgement{' '}
            {responseStatus(soft.acknowledgement).text.toLowerCase()}
          </Fact>
        )}
        {detail.sign_off !== undefined && (
          <Fact label="Sign-off then" wide>
            {detail.sign_off.blocked ? 'Blocked' : 'Not blocked'}
            {detail.sign_off.reasons.length > 0 && `: ${detail.sign_off.reasons.join('; ')}`}
          </Fact>
        )}
        {run.concluded && (
          <>
            <Fact label="Concluded by">{run.concluded_by ?? NOT_AVAILABLE}</Fact>
            <Fact label="Run reviewed">
              {detail.reviewed_run === undefined
                ? NOT_AVAILABLE
                : `Run ${String(detail.reviewed_run.run_no)}`}
            </Fact>
            <Fact label="Conclusion" wide>
              {run.conclusion}
            </Fact>
            <Fact label="Basis" wide>
              {run.basis}
            </Fact>
          </>
        )}
      </dl>

      {detail.items !== undefined && detail.items.length > 0 && (
        <div className="max-w-3xl overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <caption className="pb-1 text-left text-xs font-semibold tracking-wide text-slate-600 uppercase">
              Misstatements as they stood in run {run.run_no}
            </caption>
            <thead className="bg-slate-100 text-left text-xs text-slate-600">
              <tr>
                <th scope="col" className="px-3 py-1.5 font-semibold">
                  Ref
                </th>
                <th scope="col" className="px-3 py-1.5 font-semibold">
                  Type
                </th>
                <th scope="col" className="px-3 py-1.5 font-semibold">
                  State
                </th>
                <th scope="col" className="px-3 py-1.5 font-semibold">
                  Band
                </th>
                <th scope="col" className="px-3 py-1.5 font-semibold">
                  Counted
                </th>
              </tr>
            </thead>
            <tbody>
              {detail.items.map((item) => (
                <tr key={item.ref} className="border-t border-slate-200">
                  <th scope="row" className="px-3 py-1.5 text-left font-medium whitespace-nowrap">
                    {item.ref}
                  </th>
                  <td className="px-3 py-1.5">{TYPE_LABEL[item.type]}</td>
                  <td className="px-3 py-1.5">{STATE_LABEL[item.state]}</td>
                  <td className="px-3 py-1.5">
                    {item.band === null ? NOT_BANDED : BAND_LABEL[item.band]}
                    {item.classification_only && ' (classification only)'}
                  </td>
                  <td className="px-3 py-1.5">{countedIn(detail, item.ref, item.uncorrected)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/**
 * Whether the run summed an item, in the run's own words: its `counted` list, and what it
 * left out as clearly trivial. A run recorded without those lists falls back to whether the
 * item was uncorrected, which is all such a run says.
 */
function countedIn(detail: EvaluationRun['detail'], ref: string, uncorrected: boolean): string {
  if (detail.not_accumulated?.includes(ref) === true) return 'No: clearly trivial'
  if (detail.counted !== undefined) return detail.counted.includes(ref) ? 'Yes' : 'No'
  return uncorrected ? 'Yes' : 'No'
}

function History({ runs, evaluation }: { runs: EvaluationRun[]; evaluation: Evaluation }) {
  const [inspected, setInspected] = useState<string | null>(null)
  const latest = evaluation.latest_run

  return (
    <table className="mt-4 w-full border-collapse text-sm max-lg:block">
      <caption className="sr-only">Evaluation runs, newest first</caption>
      <thead className="bg-slate-100 text-left text-xs tracking-wide text-slate-600 uppercase max-lg:sr-only">
        <tr>
          <th scope="col" className={HEAD}>
            Run
          </th>
          <th scope="col" className={HEAD}>
            Recorded
          </th>
          <th scope="col" className={HEAD}>
            Thresholds
          </th>
          <th scope="col" className={`${HEAD} text-right`}>
            PBT gross
          </th>
          <th scope="col" className={`${HEAD} text-right`}>
            PBT net
          </th>
          <th scope="col" className={`${HEAD} text-right`}>
            Net assets gross
          </th>
          <th scope="col" className={`${HEAD} text-right`}>
            Net assets net
          </th>
          <th scope="col" className={HEAD}>
            Status
          </th>
          <th scope="col" className={HEAD}>
            <span className="sr-only">Inspect</span>
          </th>
        </tr>
      </thead>
      <tbody className="max-lg:block">
        {runs.map((run) => {
          const open = inspected === run.id
          // Only the latest row can still describe the evaluation: the backend says whether
          // it does. An earlier row is a record of its own moment and nothing more.
          const status =
            latest.run?.id === run.id
              ? recordStatus(latest.status)
              : { text: 'Earlier', tone: 'neutral' as const }
          return (
            <Fragment key={run.id}>
              <tr className="border-t border-slate-200 align-top max-lg:block max-lg:py-3">
                <th
                  scope="row"
                  className="px-3 py-2 text-left font-medium max-lg:block max-lg:px-0 max-lg:pt-0"
                >
                  Run {run.run_no}
                  <span className="block text-xs font-normal text-slate-600">{kind(run)}</span>
                </th>
                <td data-label="Recorded" className={CELL}>
                  <span>
                    <time dateTime={run.at}>{dateTime(run.at)}</time>
                    <span className="block text-xs text-slate-600">by {run.evaluated_by}</span>
                  </span>
                </td>
                <td data-label="Thresholds" className={CELL}>
                  {run.threshold_version_no === null
                    ? NOT_AVAILABLE
                    : `Version ${String(run.threshold_version_no)}`}
                </td>
                <td data-label="PBT gross" className={MONEY}>
                  {rupees(run.agg_gross_pbt)}
                </td>
                <td data-label="PBT net" className={MONEY}>
                  {rupees(run.agg_net_pbt)}
                </td>
                <td data-label="Net assets gross" className={MONEY}>
                  {rupees(run.agg_gross_na)}
                </td>
                <td data-label="Net assets net" className={MONEY}>
                  {rupees(run.agg_net_na)}
                </td>
                <td data-label="Status" className={CELL}>
                  <span>
                    <Pill tone={status.tone}>{status.text}</Pill>
                  </span>
                </td>
                <td className="px-3 py-2 max-lg:block max-lg:px-0 max-lg:pt-2">
                  <button
                    type="button"
                    aria-label={`${open ? 'Close' : 'Inspect'} run ${String(run.run_no)}`}
                    aria-expanded={open}
                    aria-controls={`run-${run.id}`}
                    onClick={() => {
                      setInspected(open ? null : run.id)
                    }}
                    className={SECONDARY}
                  >
                    {open ? 'Close' : 'Inspect'}
                  </button>
                </td>
              </tr>
              {open && (
                <tr id={`run-${run.id}`} className="max-lg:block">
                  <td colSpan={9} className="px-3 pb-4 max-lg:block max-lg:px-0">
                    <Inspection run={run} />
                  </td>
                </tr>
              )}
            </Fragment>
          )
        })}
      </tbody>
    </table>
  )
}

export function RunsPanel({
  engagementId,
  evaluation,
  runs,
  onRecorded,
}: {
  engagementId: string
  evaluation: Evaluation
  runs: EvaluationRun[]
  onRecorded: () => void
}) {
  const [reassessed, setReassessed] = useState(false)
  const [recorded, setRecorded] = useState<number | null>(null)
  const { submitting, error, submit } = useSubmit()
  const latest = recordStatus(evaluation.latest_run.status)

  async function record(event: SyntheticEvent) {
    event.preventDefault()
    if (!reassessed) return
    setRecorded(null)
    const sent = await submit(() => recordEvaluationRun(engagementId))
    if (!sent.ok) return
    setRecorded(sent.value.run_no)
    setReassessed(false)
    onRecorded()
  }

  return (
    <Panel id="runs" title="Evaluation runs">
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <span>Latest run:</span>
        <Pill tone={latest.tone}>{latest.text}</Pill>
        <span className="text-slate-700">{evaluation.latest_run.detail}</span>
      </p>

      <form
        aria-label="Record an evaluation run"
        onSubmit={(event) => {
          void record(event)
        }}
        className="mt-4 rounded border border-slate-300 bg-slate-50 px-4 py-4"
      >
        <p className="text-sm text-slate-800">
          A run records the threshold version and the four aggregates as they stand now. It is added
          to the history and is never changed. A gate that fires does not stop a run.
        </p>
        <label className="mt-3 flex items-start gap-2 text-sm text-slate-900">
          <input
            type="checkbox"
            checked={reassessed}
            disabled={submitting}
            onChange={(event) => {
              setReassessed(event.target.checked)
            }}
            className="mt-0.5 h-4 w-4"
          />
          <span>
            Materiality has been reassessed before this evaluation (SA 450 paragraph 10). If it
            needs revising, a new threshold version is set first.
          </span>
        </label>

        {error !== null && (
          <div className="mt-3">
            <ErrorState title="The run was not recorded" error={error} />
          </div>
        )}
        {recorded !== null && (
          <p
            role="status"
            aria-live="polite"
            className="mt-3 rounded border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-900"
          >
            Recorded: run {recorded}.
          </p>
        )}

        <div className="mt-4">
          <button type="submit" disabled={submitting || !reassessed} className={PRIMARY}>
            {submitting ? 'Recording…' : 'Record evaluation run'}
          </button>
        </div>
      </form>

      {runs.length === 0 ? (
        <p className="mt-4 text-sm text-slate-600">No evaluation run has been recorded yet.</p>
      ) : (
        <History runs={runs} evaluation={evaluation} />
      )}
    </Panel>
  )
}
