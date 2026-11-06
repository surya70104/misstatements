// The conclusion (spec section 6.4): whether uncorrected misstatements are material
// individually or in aggregate, and the basis, saved with its figures. A conclusion is a
// row of the evaluation history and is never edited; when the evaluation moves it goes
// stale and a new one is needed.
//
// This screen shows the conclusion, its history, and what the backend says about recording
// one now. Recording one is reserved to the engagement partner: the form is offered where
// the backend says a partner can be named, and the backend refuses everyone else.
import type { ConclusionAllowed, Evaluation, EvaluationRun } from '../../api'
import { dateTime, NOT_AVAILABLE, rupees } from '../../format'
import { determinationLabel, recordStatus } from '../../labels'
import { Basis, Fact, Panel } from '../panels'
import { Pill } from '../states'
import { ConclusionForm, PartnerOnly } from './PartnerForms'

function Recorded({ run }: { run: EvaluationRun }) {
  return (
    <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
      <Fact label="Determination">{determinationLabel(run.determination) ?? NOT_AVAILABLE}</Fact>
      <Fact label="Concluded by">{run.concluded_by ?? NOT_AVAILABLE}</Fact>
      <Fact label="Recorded">
        <time dateTime={run.at}>{dateTime(run.at)}</time>
      </Fact>
      <Fact label="Row">
        Run {run.run_no}
        {run.detail.reviewed_run !== undefined &&
          `, on review of run ${String(run.detail.reviewed_run.run_no)}`}
      </Fact>
      <Fact label="Conclusion" wide>
        {run.conclusion}
      </Fact>
      <Fact label="Basis" wide>
        {run.basis}
      </Fact>
      <Fact label="Profit before tax">
        <span className="tabular-nums">
          {rupees(run.agg_gross_pbt)} gross, {rupees(run.agg_net_pbt)} net
        </span>
      </Fact>
      <Fact label="Net assets">
        <span className="tabular-nums">
          {rupees(run.agg_gross_na)} gross, {rupees(run.agg_net_na)} net
        </span>
      </Fact>
      <Fact label="Thresholds">
        {run.threshold_version_no === null
          ? NOT_AVAILABLE
          : `Version ${String(run.threshold_version_no)}`}
      </Fact>
    </dl>
  )
}

function Allowed({ what, allowed }: { what: string; allowed: ConclusionAllowed }) {
  return (
    <li>
      <p className="flex flex-wrap items-center gap-2">
        <span>{what}:</span>
        {allowed.allowed ? (
          <Pill tone="good">Not blocked</Pill>
        ) : (
          <Pill tone="attention">Blocked</Pill>
        )}
      </p>
      {allowed.reasons.length > 0 && (
        <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-800">
          {allowed.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
    </li>
  )
}

export function ConclusionPanel({
  engagementId,
  evaluation,
  conclusions,
  onRecorded,
}: {
  engagementId: string
  evaluation: Evaluation
  conclusions: EvaluationRun[]
  onRecorded: () => void
}) {
  const { conclusion } = evaluation
  const status = recordStatus(conclusion.status)
  // The latest conclusion is shown in full above; the history lists the ones before it.
  const earlier = conclusions.filter((entry) => entry.id !== conclusion.run?.id)

  return (
    <Panel id="conclusion" title="Conclusion">
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <span>Latest conclusion:</span>
        <Pill tone={status.tone}>{status.text}</Pill>
        <span className="text-slate-700">{conclusion.detail}</span>
      </p>

      {conclusion.run !== null && (
        <div className="mt-4 rounded border border-slate-200 px-4 py-4">
          <Recorded run={conclusion.run} />
        </div>
      )}

      <div className="mt-5 border-t border-slate-200 pt-4">
        <h3 className="text-xs font-semibold tracking-wide text-slate-600 uppercase">
          Recording a conclusion now
        </h3>
        <ul className="mt-2 space-y-3 text-sm">
          <Allowed
            what="That the misstatements are not material"
            allowed={conclusion.allowed.not_material}
          />
          <Allowed
            what="That the misstatements are material"
            allowed={conclusion.allowed.material}
          />
        </ul>
        <Basis>A conclusion also requires: {conclusion.requires}.</Basis>
        <div className="mt-3">
          <PartnerOnly what="Record a conclusion" authorisation={evaluation.authorisation}>
            <ConclusionForm
              engagementId={engagementId}
              evaluation={evaluation}
              onRecorded={onRecorded}
            />
          </PartnerOnly>
        </div>
      </div>

      <div className="mt-5 border-t border-slate-200 pt-4">
        <h3 className="text-xs font-semibold tracking-wide text-slate-600 uppercase">
          Earlier conclusions
        </h3>
        {earlier.length === 0 ? (
          <p className="mt-2 text-sm text-slate-600">
            {conclusions.length === 0
              ? 'No conclusion has been recorded.'
              : 'There is no earlier conclusion.'}
          </p>
        ) : (
          <ol aria-label="Earlier conclusions" className="mt-2 space-y-3">
            {earlier.map((entry) => (
              <li key={entry.id} className="rounded border border-slate-200 px-4 py-4">
                <Recorded run={entry} />
              </li>
            ))}
          </ol>
        )}
      </div>
    </Panel>
  )
}
