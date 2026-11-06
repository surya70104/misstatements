// One engagement's evaluation (spec sections 4.1, 6.4, 7 and 10.3): the aggregate view, the
// gate status, the evaluation runs and the conclusion.
//
// Every figure, status and reason is the backend's. Six writes can be sent from here. Four
// the backend opens to any signed-in identity: recording an evaluation run, answering the
// strategy prompt, recording a prior-period item and ceasing to carry one. Two it reserves
// to the engagement partner: the soft-gate acknowledgement and the conclusion. Their forms
// are offered only where the backend says a partner can be named, and the backend refuses
// anyone the proxy's role claim does not name a partner.
//
// The prior-period carry-forward (spec section 10.3: "current and cumulative with
// prior-period items") is shown after the aggregate, apart from it.
import {
  getEngagement,
  getEvaluation,
  getOpinionGate,
  getSignOffGate,
  listConclusions,
  listEvaluationRuns,
  type Engagement,
  type Evaluation,
  type EvaluationRun,
  type GateExposure,
} from '../api'
import { AggregatePanel } from '../components/evaluation/AggregatePanel'
import { ConclusionPanel } from '../components/evaluation/ConclusionPanel'
import { EngagementNav } from '../components/EngagementNav'
import { GatesPanel } from '../components/evaluation/GatesPanel'
import { PriorPeriodPanel } from '../components/evaluation/PriorPeriodPanel'
import { RunsPanel } from '../components/evaluation/RunsPanel'
import { StrategyPanel } from '../components/evaluation/StrategyPanel'
import { ErrorState, Loading } from '../components/states'
import { href } from '../router'
import { usePageTitle } from '../usePageTitle'
import { useResource } from '../useResource'

const LINK = 'underline decoration-slate-300 underline-offset-2 hover:decoration-slate-700'

type Loaded = {
  engagement: Engagement
  evaluation: Evaluation
  runs: EvaluationRun[]
  conclusions: EvaluationRun[]
  opinionGate: GateExposure
  signOffGate: GateExposure
}

/**
 * The six reads the evaluation needs, asked for together. If any fails nothing partial is
 * shown: a gate without its figures, or figures without their gates, would mislead. The
 * engagement's failure is reported first, so an engagement that does not exist says so.
 */
async function loadEvaluation(id: string): Promise<Loaded> {
  const [engagement, evaluation, runs, conclusions, opinionGate, signOffGate] =
    await Promise.allSettled([
      getEngagement(id),
      getEvaluation(id),
      listEvaluationRuns(id),
      listConclusions(id),
      getOpinionGate(id),
      getSignOffGate(id),
    ])
  if (engagement.status === 'rejected') throw engagement.reason
  if (evaluation.status === 'rejected') throw evaluation.reason
  if (runs.status === 'rejected') throw runs.reason
  if (conclusions.status === 'rejected') throw conclusions.reason
  if (opinionGate.status === 'rejected') throw opinionGate.reason
  if (signOffGate.status === 'rejected') throw signOffGate.reason
  return {
    engagement: engagement.value,
    evaluation: evaluation.value,
    runs: runs.value,
    conclusions: conclusions.value,
    opinionGate: opinionGate.value,
    signOffGate: signOffGate.value,
  }
}

export function EvaluationPage({ id }: { id: string }) {
  const { resource, reload, refresh } = useResource(() => loadEvaluation(id), `evaluation:${id}`)
  const label = resource.state === 'ready' ? resource.data.engagement.label : null
  usePageTitle(label === null ? 'Evaluation' : `Evaluation · ${label}`)

  return (
    <section aria-labelledby="evaluation-heading">
      <nav aria-label="Breadcrumb" className="mb-3 text-sm text-slate-600">
        <a href={href({ name: 'engagements' })} className={LINK}>
          Engagements
        </a>
        <span aria-hidden="true"> / </span>
        <a href={href({ name: 'schedule', id })} className={LINK}>
          {resource.state === 'ready' ? resource.data.engagement.label : 'Engagement'}
        </a>
        <span aria-hidden="true"> / </span>
        <span>Evaluation</span>
      </nav>

      {resource.state === 'loading' && <Loading label="Loading the evaluation…" />}

      {resource.state === 'error' && (
        <ErrorState
          title="This evaluation could not be loaded"
          error={resource.error}
          onRetry={reload}
        />
      )}

      {resource.state === 'ready' && (
        <>
          <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
            <div className="min-w-0">
              <h1 id="evaluation-heading" className="text-xl font-semibold">
                {resource.data.engagement.label}
              </h1>
              <p className="mt-1 text-sm text-slate-600">Evaluation of uncorrected misstatements</p>
            </div>
            <a
              href={href({ name: 'schedule', id })}
              className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
            >
              Back to the schedule
            </a>
          </header>
          <EngagementNav id={id} current="evaluation" />

          <div className="mt-5 space-y-5">
            <AggregatePanel evaluation={resource.data.evaluation} />
            <PriorPeriodPanel
              key={`prior-period:${id}`}
              engagementId={id}
              evaluation={resource.data.evaluation}
              onRecorded={refresh}
            />
            <GatesPanel
              key={`gates:${id}`}
              engagementId={id}
              evaluation={resource.data.evaluation}
              opinionGate={resource.data.opinionGate}
              signOffGate={resource.data.signOffGate}
              onRecorded={refresh}
            />
            {/* Keyed by engagement so one engagement's half-made entry never reaches another. */}
            <RunsPanel
              key={`runs:${id}`}
              engagementId={id}
              evaluation={resource.data.evaluation}
              runs={resource.data.runs}
              onRecorded={refresh}
            />
            <StrategyPanel
              key={`strategy:${id}`}
              engagementId={id}
              evaluation={resource.data.evaluation}
              onAnswered={refresh}
            />
            <ConclusionPanel
              key={`conclusion:${id}`}
              engagementId={id}
              evaluation={resource.data.evaluation}
              conclusions={resource.data.conclusions}
              onRecorded={refresh}
            />
          </div>
        </>
      )}
    </section>
  )
}
