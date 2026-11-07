// The attachment to the written representation (SA 450 paragraph 14; spec section 2 row 14,
// section 6 item 3; backend D63): the summary of uncorrected misstatements in the form that
// attaches to the representation letter, with the statement management is asked to make.
//
// Display only, and read-only at the backend. Which misstatements are in the summary, every
// figure, the words of the statement and every caution are the backend's, read from
// `GET /api/engagements/{id}/rep-letter-attachment`. Nothing is computed here.
//
// The statement is management's belief, not the auditor's conclusion. Where the evaluation
// does not sit with it, the backend raises a caution. The cautions, and what is left out of
// the summary, are shown to the auditor on screen and are not printed: the printed page is
// the attachment alone.
import { getRepLetterAttachment, type RepLetterAttachment, type TcwgRow } from '../api'
import {
  Explained,
  FigureHeads,
  Figures,
  HEAD,
  ItemHeads,
  ItemRows,
  LEFT,
  NUMBER,
  PriorPeriodSection,
  ROW,
  TABLE,
  THEAD,
} from '../components/documentParts'
import { EngagementNav } from '../components/EngagementNav'
import { SECONDARY } from '../components/forms'
import { Panel } from '../components/panels'
import { ErrorState, Loading, Pill } from '../components/states'
import { count, rupees } from '../format'
import { determinationLabel, recordStatus, STATE_LABEL, TYPE_LABEL } from '../labels'
import { href } from '../router'
import { usePageTitle } from '../usePageTitle'
import { useResource } from '../useResource'

const LINK = 'underline decoration-slate-300 underline-offset-2 hover:decoration-slate-700'

function ForTheAuditor({ attachment }: { attachment: RepLetterAttachment }) {
  const { cautions, evaluation, not_included: outside } = attachment
  const run = recordStatus(evaluation.run.status)
  const conclusion = recordStatus(evaluation.conclusion.status)
  const trivial = outside.clearly_trivial
  return (
    <div className="print:hidden">
      <Panel id="rep-auditor" title="For the auditor: not part of the attachment">
        {cautions.length === 0 ? (
          <p className="text-sm text-slate-700">
            No caution: nothing in the evaluation as it stands is at odds with the statement.
          </p>
        ) : (
          <>
            <p className="text-sm font-medium text-amber-900">
              {count(cautions.length, 'caution')} before this attachment is sent:
            </p>
            <ul aria-label="Cautions" className="mt-2 list-disc space-y-1 pl-5 text-sm">
              {cautions.map((caution) => (
                <li key={caution.code} className="text-amber-900">
                  {caution.text}
                </li>
              ))}
            </ul>
          </>
        )}

        <dl className="mt-4 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs tracking-wide text-slate-500 uppercase">Evaluation run</dt>
            <dd className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1">
              <Pill tone={run.tone}>{run.text}</Pill>
              <span>
                {evaluation.run.run_no === null
                  ? evaluation.run.detail
                  : `run ${String(evaluation.run.run_no)}: ${evaluation.run.detail}`}
              </span>
            </dd>
          </div>
          <div>
            <dt className="text-xs tracking-wide text-slate-500 uppercase">Partner's conclusion</dt>
            <dd className="mt-1">
              {evaluation.conclusion.determination === null
                ? 'None recorded'
                : `${determinationLabel(evaluation.conclusion.determination) ?? ''} (run ${String(evaluation.conclusion.run_no)}, ${conclusion.text.toLowerCase()})`}
            </dd>
          </div>
        </dl>

        {(trivial.items.length > 0 || outside.not_uncorrected.length > 0) && (
          <div className="mt-4">
            <p className="text-sm font-medium text-slate-900">Not in the summary</p>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-800">
              {trivial.items.length > 0 && (
                <li>
                  Below the clearly-trivial threshold and not accumulated:{' '}
                  {trivial.items.map((item) => item.ref).join(', ')}. Together, gross:{' '}
                  <span className="tabular-nums">
                    profit before tax {rupees(trivial.total.profit_before_tax_gross)}, net assets{' '}
                    {rupees(trivial.total.net_assets_gross)}
                  </span>
                  .
                </li>
              )}
              {outside.not_uncorrected.length > 0 && (
                <li>
                  No longer uncorrected:{' '}
                  {outside.not_uncorrected
                    .map((entry) => `${entry.ref} (${STATE_LABEL[entry.state].toLowerCase()})`)
                    .join(', ')}
                  .
                </li>
              )}
            </ul>
          </div>
        )}
        <Explained summary="How this attachment is prepared">{attachment.basis}</Explained>
      </Panel>
    </div>
  )
}

function Undetermined({ rows }: { rows: TcwgRow[] }) {
  if (rows.length === 0) return null
  return (
    <div className="mt-5">
      <p className="text-sm text-amber-900">
        The effects of these uncorrected misstatements could not be determined. They are named so
        that none is left out; the totals do not include them.
      </p>
      <div className="mt-2 overflow-x-auto">
        <table className={TABLE}>
          <caption className="sr-only">
            Uncorrected misstatements whose effects could not be determined
          </caption>
          <thead className={THEAD}>
            <ItemHeads />
          </thead>
          <tbody>
            <ItemRows items={rows} />
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Schedule({ attachment }: { attachment: RepLetterAttachment }) {
  const { schedule, totals, threshold } = attachment
  const listed = schedule.by_type.filter((group) => group.items.length > 0)
  return (
    <Panel id="rep-schedule" title="Summary of uncorrected misstatements">
      {schedule.count === 0 ? (
        <p className="text-sm text-slate-700">No uncorrected misstatement is accumulated.</p>
      ) : (
        <>
          <p className="text-sm text-slate-700">
            {count(schedule.count, 'uncorrected misstatement')}, by type, with the effect of each on
            profit before tax and, separately, on net assets.
            {threshold !== null && (
              <>
                {' '}
                Thresholds version {threshold.version_no}:{' '}
                <span className="tabular-nums">
                  performance materiality {rupees(threshold.pm)} · overall materiality{' '}
                  {rupees(threshold.om)}
                </span>
                .
              </>
            )}
          </p>

          {!totals.complete && (
            <p className="mt-3 rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              These totals are short: a misstatement's effects could not be determined.
            </p>
          )}

          <div className="mt-4 overflow-x-auto">
            <table className={TABLE}>
              <caption className="sr-only">
                Uncorrected misstatements by type, with the totals gross and net
              </caption>
              <thead className={THEAD}>
                <tr>
                  <th scope="col" className={LEFT}>
                    Type
                  </th>
                  <th scope="col" className={HEAD}>
                    Number
                  </th>
                  <FigureHeads />
                </tr>
              </thead>
              <tbody>
                {schedule.by_type.map((group) => (
                  <tr key={group.type} className={ROW}>
                    <th scope="row" className="px-3 py-2 text-left font-medium">
                      {TYPE_LABEL[group.type]}
                    </th>
                    <td className={NUMBER}>{group.count}</td>
                    <Figures sums={group} />
                  </tr>
                ))}
                <tr className={`${ROW} border-t-2 border-slate-400 font-semibold`}>
                  <th scope="row" className="px-3 py-2 text-left">
                    All uncorrected misstatements
                  </th>
                  <td className={NUMBER}>{totals.count}</td>
                  <Figures sums={totals} />
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-2 max-w-3xl text-xs text-slate-600">
            Gross adds the size of every effect with no netting between misstatements; net adds them
            signed. Projected misstatements are estimates for a population, projected from a sample.
          </p>

          {listed.map((group) => (
            <div key={group.type} className="mt-5 break-inside-avoid">
              <h3 className="text-sm font-semibold text-slate-900">
                {TYPE_LABEL[group.type]} misstatements
              </h3>
              <div className="mt-2 overflow-x-auto">
                <table className={TABLE}>
                  <caption className="sr-only">
                    {TYPE_LABEL[group.type]} uncorrected misstatements listed
                  </caption>
                  <thead className={THEAD}>
                    <ItemHeads />
                  </thead>
                  <tbody>
                    <ItemRows items={group.items} />
                  </tbody>
                </table>
              </div>
            </div>
          ))}
          <Undetermined rows={schedule.undetermined} />
        </>
      )}
      <Explained summary="How the totals are computed">{totals.basis}</Explained>
    </Panel>
  )
}

function Statement({ attachment }: { attachment: RepLetterAttachment }) {
  const { representation } = attachment
  return (
    <Panel id="rep-statement" title="Representation">
      {representation.applies ? (
        <blockquote className="border-l-4 border-slate-400 pl-4 text-base font-medium text-slate-900">
          {representation.text}
        </blockquote>
      ) : (
        <p className="text-sm text-slate-700">{representation.text}</p>
      )}
      <Explained summary="Where this statement comes from">{representation.basis}</Explained>
    </Panel>
  )
}

export function RepLetterAttachmentPage({ id }: { id: string }) {
  const { resource, reload } = useResource(
    () => getRepLetterAttachment(id),
    `rep-letter-attachment:${id}`,
  )
  const label = resource.state === 'ready' ? resource.data.engagement.label : null
  usePageTitle(
    label === null ? 'Representation attachment' : `Representation attachment · ${label}`,
  )

  return (
    <section aria-labelledby="rep-heading">
      <nav aria-label="Breadcrumb" className="mb-3 text-sm text-slate-600 print:hidden">
        <a href={href({ name: 'engagements' })} className={LINK}>
          Engagements
        </a>
        <span aria-hidden="true"> / </span>
        <a href={href({ name: 'schedule', id })} className={LINK}>
          {label ?? 'Engagement'}
        </a>
        <span aria-hidden="true"> / </span>
        <span>Representation attachment</span>
      </nav>

      {resource.state === 'loading' && <Loading label="Loading the representation attachment…" />}

      {resource.state === 'error' && (
        <ErrorState
          title="This representation attachment could not be loaded"
          error={resource.error}
          onRetry={reload}
        />
      )}

      {resource.state === 'ready' && (
        <>
          <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <h1 id="rep-heading" className="text-xl font-semibold">
                  {resource.data.engagement.label}
                </h1>
                <span className="print:hidden">
                  {resource.data.status === 'ready' ? (
                    <Pill tone="good">Ready to attach</Pill>
                  ) : (
                    <Pill tone="attention">Incomplete</Pill>
                  )}
                </span>
              </div>
              <p className="mt-1 text-sm text-slate-600">
                Summary of uncorrected misstatements: attachment to the written representation (SA
                450 paragraph 14)
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                window.print()
              }}
              className={`${SECONDARY} print:hidden`}
            >
              Print or save as PDF
            </button>
          </header>
          <div className="print:hidden">
            <EngagementNav id={id} current="rep-letter-attachment" />
          </div>

          {resource.data.status !== 'ready' && (
            <div
              role="alert"
              className="mt-5 rounded-md border border-amber-300 bg-amber-50 px-5 py-4 text-sm text-amber-900"
            >
              <p className="font-semibold">
                This attachment is incomplete and is not fit to be sent as it stands.
              </p>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {resource.data.incomplete_because.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-5 space-y-5">
            <ForTheAuditor attachment={resource.data} />
            <Schedule attachment={resource.data} />
            <PriorPeriodSection id="rep-prior" prior={resource.data.prior_period} />
            <Statement attachment={resource.data} />
          </div>
        </>
      )}
    </section>
  )
}
