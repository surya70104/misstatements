// One misstatement's detail (spec sections 6.1 and 10.2): what it is, its Dr/Cr lines with
// their classification, its computed effects, its state trail, and the moves it can make.
//
// Display only, apart from the moves and the qualitative checklist. Every figure and every
// explanation is the backend's, read from `GET /api/misstatements/{id}`. A move is sent to
// the backend, which decides it; the answer is the record as it now stands and replaces what
// is shown. The schedule reads the backend afresh each time it is opened, so it shows the
// move as well.
//
// The qualitative checklist (spec sections 5 and 10.2) comes with the misstatement. A write
// on it answers with the checklist as it now stands, which replaces the one shown.
import { getMisstatement } from '../api'
import { AccountingLines } from '../components/misstatement/AccountingLines'
import { FinancialEffects } from '../components/misstatement/FinancialEffects'
import { Identification } from '../components/misstatement/Identification'
import { QualitativeFactors } from '../components/misstatement/QualitativeFactors'
import { StateHistory } from '../components/misstatement/StateHistory'
import { WorkflowActions } from '../components/misstatement/WorkflowActions'
import { ErrorState, Loading, Pill } from '../components/states'
import { BAND_LABEL, BAND_TONE, NOT_BANDED, STATE_LABEL, STATE_TONE, TYPE_LABEL } from '../labels'
import { href } from '../router'
import { usePageTitle } from '../usePageTitle'
import { useResource } from '../useResource'

const LINK = 'underline decoration-slate-300 underline-offset-2 hover:decoration-slate-700'

export function MisstatementPage({ id }: { id: string }) {
  const { resource, reload, replace } = useResource(() => getMisstatement(id), `misstatement:${id}`)
  usePageTitle(resource.state === 'ready' ? `Misstatement ${resource.data.ref}` : 'Misstatement')

  return (
    <section aria-labelledby="misstatement-heading">
      <nav aria-label="Breadcrumb" className="mb-3 text-sm text-slate-600">
        <a href={href({ name: 'engagements' })} className={LINK}>
          Engagements
        </a>
        <span aria-hidden="true"> / </span>
        {resource.state === 'ready' ? (
          <>
            <a href={href({ name: 'schedule', id: resource.data.engagement_id })} className={LINK}>
              Schedule
            </a>
            <span aria-hidden="true"> / </span>
            <span>{resource.data.ref}</span>
          </>
        ) : (
          <span>Misstatement</span>
        )}
      </nav>

      {resource.state === 'loading' && <Loading label="Loading the misstatement…" />}

      {resource.state === 'error' && (
        <ErrorState
          title="This misstatement could not be loaded"
          error={resource.error}
          onRetry={reload}
        />
      )}

      {resource.state === 'ready' && (
        <>
          <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <h1 id="misstatement-heading" className="text-xl font-semibold">
                  {resource.data.ref}
                </h1>
                <Pill>{TYPE_LABEL[resource.data.current.type]}</Pill>
                <Pill tone={STATE_TONE[resource.data.current.state]}>
                  {STATE_LABEL[resource.data.current.state]}
                </Pill>
                {resource.data.band === null ? (
                  <Pill tone="attention">{NOT_BANDED}</Pill>
                ) : (
                  <Pill tone={BAND_TONE[resource.data.band]}>{BAND_LABEL[resource.data.band]}</Pill>
                )}
                {resource.data.qualitative.escalated && <Pill tone="attention">Escalated</Pill>}
              </div>
              <p className="mt-1 max-w-3xl text-sm text-slate-700">
                {resource.data.current.description}
              </p>
            </div>
            <a
              href={href({ name: 'schedule', id: resource.data.engagement_id })}
              className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
            >
              Back to the schedule
            </a>
          </header>

          <div className="mt-5 space-y-5">
            <Identification misstatement={resource.data} />
            <AccountingLines misstatement={resource.data} />
            <FinancialEffects misstatement={resource.data} />
            {/* Keyed by misstatement so one record's half-typed reason never reaches another. */}
            <QualitativeFactors
              key={`qualitative:${id}`}
              misstatement={resource.data}
              onChanged={(checklist) => {
                replace({
                  ...resource.data,
                  qualitative: {
                    escalated: checklist.escalated,
                    factors: checklist.factors,
                    escalation_basis: checklist.escalation_basis,
                    checklist: checklist.checklist,
                    history: checklist.history,
                  },
                })
              }}
            />
            <div className="grid items-start gap-5 lg:grid-cols-2">
              <StateHistory misstatement={resource.data} />
              {/* Keyed by misstatement so one record's half-typed reason never reaches another. */}
              <WorkflowActions key={id} misstatement={resource.data} onMoved={replace} />
            </div>
          </div>
        </>
      )}
    </section>
  )
}
