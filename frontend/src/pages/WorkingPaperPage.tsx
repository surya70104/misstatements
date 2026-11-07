// The generated working paper (SA 230; SA 450 paragraph 15; spec section 6 item 5; backend
// D66): the engagement's whole record as one structured paper, and its export, which
// freezes the paper against the current evaluation run and registers it with a hash.
//
// Display only, apart from the export. Every figure, status and reason is the backend's,
// read from `GET /api/engagements/{id}/working-paper`. The export sends nothing but the
// request: the backend freezes what it generates itself and answers with the registration.
//
// The Working Paper Binder has a generated-paper intake, but its contract names no source
// for this module, so the export registers the snapshot here and shows the delivery it would
// make; nothing is sent to the Binder.
import { useState, type ReactNode } from 'react'

import {
  exportWorkingPaper,
  getWorkingPaper,
  listWorkingPaperExports,
  type WorkingPaper,
  type WorkingPaperExport,
  type WorkingPaperSummary,
} from '../api'
import {
  Explained,
  FigureHeads,
  Figures,
  HEAD,
  LEFT,
  NUMBER,
  PriorPeriodSection,
  ROW,
  TABLE,
  THEAD,
} from '../components/documentParts'
import { EngagementNav } from '../components/EngagementNav'
import { PRIMARY, SECONDARY } from '../components/forms'
import { Panel } from '../components/panels'
import { ErrorState, Loading, Pill } from '../components/states'
import { count, dateTime, rupees } from '../format'
import {
  BAND_LABEL,
  determinationLabel,
  NOT_BANDED,
  raisedFromLabel,
  recordStatus,
  STATE_LABEL,
  TYPE_LABEL,
} from '../labels'
import { href } from '../router'
import { usePageTitle } from '../usePageTitle'
import { useResource } from '../useResource'
import { useSubmit } from '../useSubmit'

const LINK = 'underline decoration-slate-300 underline-offset-2 hover:decoration-slate-700'

type Loaded = { paper: WorkingPaper; exports: WorkingPaperSummary[] }

async function load(id: string): Promise<Loaded> {
  const [paper, exports] = await Promise.all([getWorkingPaper(id), listWorkingPaperExports(id)])
  return { paper, exports }
}

function Term({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs tracking-wide text-slate-500 uppercase">{label}</dt>
      <dd className="mt-1 text-sm break-words text-slate-900">{children}</dd>
    </div>
  )
}

function Documented({ documented }: { documented: boolean }) {
  return documented ? (
    <Pill tone="good">Documented</Pill>
  ) : (
    <Pill tone="attention">Not documented</Pill>
  )
}

function Documentation({ paper }: { paper: WorkingPaper }) {
  const { documentation: doc } = paper
  const trivial = doc.clearly_trivial_amount
  const accumulated = doc.misstatements_accumulated_and_whether_corrected
  const concluded = doc.conclusion_and_basis
  return (
    <Panel id="wp-documentation" title="What SA 450 paragraph 15 requires to be documented">
      <p className="flex flex-wrap items-center gap-2 text-sm text-slate-700">
        {doc.complete ? (
          <Pill tone="good">Complete</Pill>
        ) : (
          <Pill tone="attention">Not yet complete</Pill>
        )}
        <span>Each requirement is a field of this paper, checked as present or not.</span>
      </p>
      <dl className="mt-4 space-y-4 text-sm">
        <div className="rounded border border-slate-200 px-4 py-3">
          <dt className="flex flex-wrap items-center gap-2 font-medium text-slate-900">
            The amount below which misstatements are clearly trivial
            <Documented documented={trivial.documented} />
          </dt>
          <dd className="mt-1 text-slate-800">
            {trivial.documented ? (
              <>
                <span className="tabular-nums">{rupees(trivial.amount)}</span>, the fraction{' '}
                {trivial.fraction_of_pm} of performance materiality, thresholds version{' '}
                {String(trivial.threshold_version_no)}; basis: {trivial.basis}
              </>
            ) : (
              'No thresholds have been set.'
            )}
          </dd>
        </div>
        <div className="rounded border border-slate-200 px-4 py-3">
          <dt className="flex flex-wrap items-center gap-2 font-medium text-slate-900">
            All misstatements accumulated, and whether they have been corrected
            <Documented documented={accumulated.documented} />
          </dt>
          <dd className="mt-1 text-slate-800">
            {count(accumulated.count, 'misstatement')} recorded. Uncorrected:{' '}
            {accumulated.uncorrected.length === 0 ? 'none' : accumulated.uncorrected.join(', ')}.
            Corrected:{' '}
            {accumulated.corrected.length === 0 ? 'none' : accumulated.corrected.join(', ')}.
            Withdrawn:{' '}
            {accumulated.withdrawn.length === 0 ? 'none' : accumulated.withdrawn.join(', ')}.
          </dd>
        </div>
        <div className="rounded border border-slate-200 px-4 py-3">
          <dt className="flex flex-wrap items-center gap-2 font-medium text-slate-900">
            The conclusion as to whether uncorrected misstatements are material, and its basis
            <Documented documented={concluded.documented} />
          </dt>
          <dd className="mt-1 text-slate-800">
            {concluded.documented ? (
              <>
                <p>
                  <span className="font-medium">
                    {determinationLabel(concluded.determination) ?? ''}
                  </span>
                  , by {concluded.concluded_by} on run {String(concluded.run_no)} (
                  {recordStatus(concluded.status ?? 'none').text.toLowerCase()}).
                </p>
                <p className="mt-1">Conclusion: {concluded.conclusion}</p>
                <p className="mt-1">Basis: {concluded.basis}</p>
              </>
            ) : (
              'No conclusion has been recorded by a partner.'
            )}
          </dd>
        </div>
      </dl>
    </Panel>
  )
}

function Misstatements({ paper }: { paper: WorkingPaper }) {
  return (
    <Panel id="wp-misstatements" title="Misstatements accumulated">
      {paper.misstatements.length === 0 ? (
        <p className="text-sm text-slate-700">No misstatement has been recorded.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className={TABLE}>
            <caption className="sr-only">
              Every misstatement, with its type, state, band, effects, source and what is recorded
              against it
            </caption>
            <thead className={THEAD}>
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
                <th scope="col" className={LEFT}>
                  Band
                </th>
                <th scope="col" className={HEAD}>
                  Profit before tax
                </th>
                <th scope="col" className={HEAD}>
                  Net assets
                </th>
                <th scope="col" className={LEFT}>
                  Source
                </th>
                <th scope="col" className={LEFT}>
                  Recorded with it
                </th>
              </tr>
            </thead>
            <tbody>
              {paper.misstatements.map((item) => (
                <tr key={item.ref} className={ROW}>
                  <th scope="row" className="px-3 py-2 text-left font-medium whitespace-nowrap">
                    <a href={href({ name: 'misstatement', id: item.id })} className={LINK}>
                      {item.ref}
                    </a>
                  </th>
                  <td className="px-3 py-2">{TYPE_LABEL[item.current.type]}</td>
                  <td className="px-3 py-2 break-words">{item.current.description}</td>
                  <td className="px-3 py-2">{STATE_LABEL[item.current.state]}</td>
                  <td className="px-3 py-2">
                    {item.band === null ? NOT_BANDED : BAND_LABEL[item.band]}
                  </td>
                  <td className={NUMBER}>
                    {item.effects === null || item.effects.profit_before_tax === null
                      ? 'Not determined'
                      : rupees(item.effects.profit_before_tax)}
                  </td>
                  <td className={NUMBER}>
                    {item.effects === null || item.effects.net_assets === null
                      ? 'Not determined'
                      : rupees(item.effects.net_assets)}
                  </td>
                  <td className="px-3 py-2">
                    {item.current.source_ref}
                    <span className="block text-xs text-slate-500">
                      {raisedFromLabel(item.current.raised_from)}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-700">
                    <ul className="space-y-0.5">
                      <li>{count(item.spine.lines.length, 'Dr/Cr line')}</li>
                      <li>{count(item.versions?.length ?? 1, 'version')}</li>
                      {item.qualitative.escalated && (
                        <li>
                          Escalated: {count(item.qualitative.factors.length, 'qualitative factor')}
                        </li>
                      )}
                      {item.current.sampling !== null && (
                        <li>Projected from sample {item.current.sample_ref ?? ''}</li>
                      )}
                      {item.current.refusal_reason !== null && (
                        <li>Refused: {item.current.refusal_reason}</li>
                      )}
                    </ul>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  )
}

function Evaluation({ paper }: { paper: WorkingPaper }) {
  const { evaluation, thresholds, runs, conclusions, events } = paper
  const aggregate = evaluation.aggregate
  const current = thresholds.current
  const answered = events.filter((event) => event.kind === 'strategy_trigger_response')
  const acknowledged = events.filter((event) => event.kind === 'soft_gate_acknowledged')
  return (
    <Panel id="wp-evaluation" title="Thresholds, evaluation and conclusions">
      <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-4">
        <Term label="Thresholds">
          {current === null ? (
            'Not set'
          ) : (
            <span className="tabular-nums">
              OM {rupees(current.om)} · PM {rupees(current.pm)} · CTT {rupees(current.ctt)} (version{' '}
              {current.version_no})
            </span>
          )}
        </Term>
        <Term label="Materiality reassessed">
          {paper.materiality_reassessment.runs.length === 0
            ? 'Not yet: no evaluation run'
            : `At ${count(paper.materiality_reassessment.runs.length, 'run')}: ${paper.materiality_reassessment.runs.map(String).join(', ')}`}
        </Term>
        <Term label="Hard gate (OM)">{evaluation.gates.hard.status}</Term>
        <Term label="Soft gate (PM)">
          {evaluation.gates.soft.status}; acknowledgement{' '}
          {evaluation.gates.soft.acknowledgement.status}
        </Term>
      </dl>

      <div className="mt-4 overflow-x-auto">
        <table className={TABLE}>
          <caption className="sr-only">
            The aggregate of uncorrected misstatements, gross and net, on profit before tax and net
            assets
          </caption>
          <thead className={THEAD}>
            <tr>
              <th scope="col" className={LEFT}>
                Aggregate
              </th>
              <FigureHeads />
            </tr>
          </thead>
          <tbody>
            <tr className={ROW}>
              <th scope="row" className="px-3 py-2 text-left font-medium">
                Uncorrected misstatements ({count(aggregate.counted.length, 'item')})
              </th>
              <Figures sums={aggregate} />
            </tr>
          </tbody>
        </table>
      </div>

      <h3 className="mt-5 text-sm font-semibold text-slate-900">Evaluation runs</h3>
      {runs.length === 0 ? (
        <p className="mt-1 text-sm text-slate-700">No evaluation run has been recorded.</p>
      ) : (
        <ul aria-label="Evaluation runs" className="mt-1 space-y-1 text-sm text-slate-800">
          {runs.map((run) => (
            <li key={run.id}>
              Run {run.run_no} by {run.evaluated_by},{' '}
              <time dateTime={run.at}>{dateTime(run.at)}</time>: profit before tax gross{' '}
              <span className="tabular-nums">{rupees(run.agg_gross_pbt)}</span>, net assets gross{' '}
              <span className="tabular-nums">{rupees(run.agg_gross_na)}</span>
              {run.concluded && ` · concluded ${determinationLabel(run.determination) ?? ''}`}
            </li>
          ))}
        </ul>
      )}

      <h3 className="mt-5 text-sm font-semibold text-slate-900">Partner's conclusions</h3>
      {conclusions.length === 0 ? (
        <p className="mt-1 text-sm text-slate-700">No conclusion has been recorded.</p>
      ) : (
        <ul aria-label="Conclusions" className="mt-1 space-y-2 text-sm text-slate-800">
          {conclusions.map((run) => (
            <li key={run.id}>
              <span className="font-medium">{determinationLabel(run.determination) ?? ''}</span>,
              run {run.run_no} by {run.concluded_by}: {run.conclusion}
              <span className="block text-xs text-slate-600">Basis: {run.basis}</span>
            </li>
          ))}
        </ul>
      )}

      <h3 className="mt-5 text-sm font-semibold text-slate-900">
        Strategy prompt answers and partner acknowledgements
      </h3>
      {answered.length === 0 && acknowledged.length === 0 ? (
        <p className="mt-1 text-sm text-slate-700">None recorded.</p>
      ) : (
        <ul aria-label="Strategy answers and acknowledgements" className="mt-1 space-y-1 text-sm">
          {[...answered, ...acknowledged].map((event) => (
            <li key={event.id}>
              {event.kind === 'strategy_trigger_response'
                ? 'Strategy prompt answered'
                : 'Soft gate acknowledged'}{' '}
              by {event.actor}, <time dateTime={event.at}>{dateTime(event.at)}</time>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

function Export({
  engagementId,
  paper,
  exports,
  onExported,
}: {
  engagementId: string
  paper: WorkingPaper
  exports: WorkingPaperSummary[]
  onExported: () => void
}) {
  const [done, setDone] = useState<WorkingPaperExport | null>(null)
  const { submitting, error, submit } = useSubmit()
  const status = recordStatus(paper.export.status)

  async function send() {
    const sent = await submit(() => exportWorkingPaper(engagementId))
    if (!sent.ok) return
    setDone(sent.value)
    onExported()
  }

  return (
    <Panel id="wp-export" title="Export to the binder">
      {done !== null && (
        <div
          role="status"
          aria-live="polite"
          className="mb-3 rounded border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900"
        >
          <p className="font-medium">
            Registered as paper {done.paper.paper_no}, on evaluation run {String(done.paper.run_no)}
            .
          </p>
          <p className="mt-1 font-mono text-xs break-all">{done.paper.content_hash}</p>
          <p className="mt-1">{done.binder_delivery.not_deliverable_because}</p>
        </div>
      )}
      <p className="flex flex-wrap items-center gap-2 text-sm text-slate-700">
        <span>Latest export:</span>
        <Pill tone={status.tone}>{status.text}</Pill>
        {paper.export.latest !== null && (
          <span>
            paper {paper.export.latest.paper_no} on run {String(paper.export.latest.run_no)},{' '}
            <time dateTime={paper.export.latest.at}>{dateTime(paper.export.latest.at)}</time>
          </span>
        )}
      </p>
      <p className="mt-2 max-w-3xl text-sm text-slate-700">
        An export freezes this paper as it stands, tied to the current evaluation run, with a
        SHA-256 of its content. Content hash now:{' '}
        <span className="font-mono text-xs break-all">{paper.content_hash}</span>
      </p>
      {!paper.exportable.allowed && (
        <ul
          aria-label="Why the paper cannot be exported"
          className="mt-2 list-disc pl-5 text-sm text-amber-900"
        >
          {paper.exportable.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
      {error !== null && (
        <div className="mt-3">
          <ErrorState title="The paper was not exported" error={error} />
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-2 print:hidden">
        <button
          type="button"
          disabled={submitting || !paper.exportable.allowed}
          onClick={() => {
            void send()
          }}
          className={PRIMARY}
        >
          {submitting ? 'Exporting…' : 'Export to the binder'}
        </button>
        <button
          type="button"
          onClick={() => {
            window.print()
          }}
          className={SECONDARY}
        >
          Print or save as PDF
        </button>
      </div>

      <h3 className="mt-5 text-sm font-semibold text-slate-900">Registered papers</h3>
      {exports.length === 0 ? (
        <p className="mt-1 text-sm text-slate-700">None yet.</p>
      ) : (
        <div className="mt-1 overflow-x-auto">
          <table className={TABLE}>
            <caption className="sr-only">Registered working papers, newest first</caption>
            <thead className={THEAD}>
              <tr>
                <th scope="col" className={LEFT}>
                  Paper
                </th>
                <th scope="col" className={LEFT}>
                  Run
                </th>
                <th scope="col" className={LEFT}>
                  Exported by
                </th>
                <th scope="col" className={LEFT}>
                  When
                </th>
                <th scope="col" className={LEFT}>
                  Content hash
                </th>
              </tr>
            </thead>
            <tbody>
              {exports.map((entry) => (
                <tr key={entry.id} className={ROW}>
                  <th scope="row" className="px-3 py-2 text-left font-medium">
                    {entry.paper_no}
                  </th>
                  <td className="px-3 py-2">{String(entry.run_no)}</td>
                  <td className="px-3 py-2">{entry.generated_by}</td>
                  <td className="px-3 py-2">
                    <time dateTime={entry.at}>{dateTime(entry.at)}</time>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs break-all">{entry.content_hash}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Explained summary="How this paper is generated">{paper.basis}</Explained>
    </Panel>
  )
}

export function WorkingPaperPage({ id }: { id: string }) {
  const { resource, reload, refresh } = useResource(() => load(id), `working-paper:${id}`)
  const label = resource.state === 'ready' ? resource.data.paper.engagement.label : null
  usePageTitle(label === null ? 'Working paper' : `Working paper · ${label}`)

  return (
    <section aria-labelledby="wp-heading">
      <nav aria-label="Breadcrumb" className="mb-3 text-sm text-slate-600 print:hidden">
        <a href={href({ name: 'engagements' })} className={LINK}>
          Engagements
        </a>
        <span aria-hidden="true"> / </span>
        <a href={href({ name: 'schedule', id })} className={LINK}>
          {label ?? 'Engagement'}
        </a>
        <span aria-hidden="true"> / </span>
        <span>Working paper</span>
      </nav>

      {resource.state === 'loading' && <Loading label="Loading the working paper…" />}

      {resource.state === 'error' && (
        <ErrorState
          title="This working paper could not be loaded"
          error={resource.error}
          onRetry={reload}
        />
      )}

      {resource.state === 'ready' && (
        <>
          <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <h1 id="wp-heading" className="text-xl font-semibold">
                  {resource.data.paper.engagement.label}
                </h1>
                <span className="print:hidden">
                  {resource.data.paper.documentation.complete ? (
                    <Pill tone="good">Documentation complete</Pill>
                  ) : (
                    <Pill tone="attention">Documentation incomplete</Pill>
                  )}
                </span>
              </div>
              <p className="mt-1 text-sm text-slate-600">
                {resource.data.paper.paper.title} · {resource.data.paper.paper.standards.join(', ')}{' '}
                · generated by {resource.data.paper.paper.module}{' '}
                {resource.data.paper.paper.module_version}
              </p>
            </div>
          </header>
          <div className="print:hidden">
            <EngagementNav id={id} current="working-paper" />
          </div>

          <div className="mt-5 space-y-5">
            <Export
              key={`export:${id}`}
              engagementId={id}
              paper={resource.data.paper}
              exports={resource.data.exports}
              onExported={refresh}
            />
            <Documentation paper={resource.data.paper} />
            <Misstatements paper={resource.data.paper} />
            <PriorPeriodSection id="wp-prior" prior={resource.data.paper.evaluation.prior_period} />
            <Evaluation paper={resource.data.paper} />
          </div>
        </>
      )}
    </section>
  )
}
