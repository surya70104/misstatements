// One engagement and the Financial Spine: the link between them, and the read-only
// reconciliation of the Spine's adjustments with the misstatements recorded here
// (architecture D8, D46).
//
// The link can be set, changed or cleared here; the backend checks it with the Spine and
// refuses a change once misstatements are proposed on the pinned version (pending decision
// B10). The reconciliation reads and repairs nothing: an orphan can only be dealt with in
// the Spine, by a person.
import { useState, type SyntheticEvent } from 'react'

import {
  getEngagement,
  getReconciliation,
  setSpineLink,
  type Engagement,
  type Reconciliation,
  type SpineLinkInput,
} from '../api'
import { Breadcrumb, EngagementHeader } from '../components/EngagementHeader'
import { Field, INPUT, PRIMARY, Recorded } from '../components/forms'
import { Basis, Fact, Panel, Unavailable } from '../components/panels'
import { ErrorState, Loading, Pill } from '../components/states'
import { count, dateTime, NOT_AVAILABLE, rupees } from '../format'
import { reconciliationStatus, spineLinkStatus, STATE_LABEL } from '../labels'
import { usePageTitle } from '../usePageTitle'
import { useResource } from '../useResource'
import { useSubmit } from '../useSubmit'

type Loaded = { engagement: Engagement; reconciliation: Reconciliation }

async function load(id: string): Promise<Loaded> {
  const [engagement, reconciliation] = await Promise.allSettled([
    getEngagement(id),
    getReconciliation(id),
  ])
  if (engagement.status === 'rejected') throw engagement.reason
  if (reconciliation.status === 'rejected') throw reconciliation.reason
  return { engagement: engagement.value, reconciliation: reconciliation.value }
}

function Link({ engagement, onLinked }: { engagement: Engagement; onLinked: () => void }) {
  const { spine } = engagement
  const status = spineLinkStatus(spine.status)
  const [spineEngagement, setSpineEngagement] = useState(spine.engagement_id ?? '')
  const [spineVersion, setSpineVersion] = useState(spine.version_id ?? '')
  const [saved, setSaved] = useState(false)
  const { submitting, error, submit } = useSubmit()

  async function save(event: SyntheticEvent) {
    event.preventDefault()
    const body: SpineLinkInput = {
      spine_engagement_id: spineEngagement.trim() === '' ? null : spineEngagement.trim(),
      spine_version_id: spineVersion.trim() === '' ? null : spineVersion.trim(),
    }
    setSaved(false)
    const sent = await submit(() => setSpineLink(engagement.id, body))
    if (!sent.ok) return
    setSaved(true)
    onLinked()
  }

  return (
    <Panel id="link" title="Link to the Financial Spine">
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <Pill tone={status.tone}>{status.text}</Pill>
        {spine.is_locked === true && <Pill tone="attention">Version locked</Pill>}
        {spine.detail !== null && <span className="text-slate-700">{spine.detail}</span>}
      </p>
      <dl className="mt-3 grid gap-x-8 gap-y-4 sm:grid-cols-2">
        <Fact label="Spine engagement">
          <span className="font-mono text-xs break-all">
            {spine.engagement_id ?? NOT_AVAILABLE}
          </span>
        </Fact>
        <Fact label="Spine version">
          <span className="font-mono text-xs break-all">{spine.version_id ?? NOT_AVAILABLE}</span>
        </Fact>
      </dl>

      <form
        aria-label="Financial Spine link"
        onSubmit={(event) => {
          void save(event)
        }}
        className="mt-5 space-y-4 border-t border-slate-200 pt-4"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            id="link-engagement"
            label="Financial Spine engagement"
            hint="Leave empty to clear the link; clearing it clears the version."
          >
            <input
              id="link-engagement"
              value={spineEngagement}
              disabled={submitting}
              aria-describedby="link-engagement-hint"
              onChange={(event) => {
                setSpineEngagement(event.target.value)
              }}
              className={`${INPUT} font-mono`}
            />
          </Field>
          <Field
            id="link-version"
            label="Financial Spine version"
            hint="The version this engagement works on. It needs the engagement above."
          >
            <input
              id="link-version"
              value={spineVersion}
              disabled={submitting}
              aria-describedby="link-version-hint"
              onChange={(event) => {
                setSpineVersion(event.target.value)
              }}
              className={`${INPUT} font-mono`}
            />
          </Field>
        </div>
        {error !== null && <ErrorState title="The link was not changed" error={error} />}
        {saved && <Recorded>Recorded: the Financial Spine link.</Recorded>}
        <button type="submit" disabled={submitting} className={PRIMARY}>
          {submitting ? 'Recording…' : 'Save the link'}
        </button>
      </form>
    </Panel>
  )
}

const HEAD = 'px-3 py-2 font-semibold'

function Findings({ report }: { report: Reconciliation }) {
  const orphans = report.orphans ?? []
  const missing = report.missing ?? []
  const disagreements = report.disagreements ?? []
  const duplicated = report.duplicated_references ?? []
  return (
    <>
      <p className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <span>Result:</span>
        {report.clean === true ? (
          <Pill tone="good">Clean</Pill>
        ) : (
          <Pill tone="attention">Findings</Pill>
        )}
        <span className="text-slate-700">
          {count(orphans.length, 'orphan')}, {missing.length} missing,{' '}
          {count(disagreements.length, 'disagreement')}
        </span>
      </p>

      <h3 className="mt-5 text-xs font-semibold tracking-wide text-slate-600 uppercase">
        Orphan proposals
      </h3>
      {orphans.length === 0 ? (
        <p className="mt-1 text-sm text-slate-600">
          None: every adjustment in the Spine that carries one of this module’s references is linked
          to a misstatement here.
        </p>
      ) : (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">
              Adjustments in the Financial Spine that no misstatement here links to
            </caption>
            <thead className="bg-slate-100 text-left text-xs tracking-wide text-slate-600 uppercase">
              <tr>
                <th scope="col" className={HEAD}>
                  Reference
                </th>
                <th scope="col" className={HEAD}>
                  Narration
                </th>
                <th scope="col" className={HEAD}>
                  Status in the Spine
                </th>
                <th scope="col" className={`${HEAD} text-right`}>
                  Gross size
                </th>
                <th scope="col" className={HEAD}>
                  Proposed
                </th>
              </tr>
            </thead>
            <tbody>
              {orphans.map((orphan) => (
                <tr key={orphan.adjustment_id} className="border-t border-slate-200 align-top">
                  <th scope="row" className="px-3 py-2 text-left font-medium whitespace-nowrap">
                    {orphan.finding_ref ?? NOT_AVAILABLE}
                  </th>
                  <td className="px-3 py-2">
                    {orphan.narration ?? NOT_AVAILABLE}
                    <span className="block text-xs text-slate-600">
                      {orphan.working_paper_ref !== null && `${orphan.working_paper_ref} · `}
                      <span className="font-mono break-all">{orphan.adjustment_id}</span>
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    {orphan.status} ({orphan.kind})
                  </td>
                  <td className="px-3 py-2 text-right whitespace-nowrap tabular-nums">
                    {rupees(orphan.measure)}
                  </td>
                  <td className="px-3 py-2">
                    {orphan.proposed_at === null ? (
                      NOT_AVAILABLE
                    ) : (
                      <time dateTime={orphan.proposed_at}>{dateTime(orphan.proposed_at)}</time>
                    )}
                    {orphan.proposed_by !== null && (
                      <span className="block text-xs text-slate-600">by {orphan.proposed_by}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3 className="mt-5 text-xs font-semibold tracking-wide text-slate-600 uppercase">
        Misstatements whose adjustment the Spine lacks
      </h3>
      {missing.length === 0 ? (
        <p className="mt-1 text-sm text-slate-600">None.</p>
      ) : (
        <ul aria-label="Missing adjustments" className="mt-1 list-disc space-y-1 pl-5 text-sm">
          {missing.map((entry) => (
            <li key={entry.spine_adjustment_id}>
              {entry.ref}, {STATE_LABEL[entry.state].toLowerCase()} here: the Spine has no
              adjustment{' '}
              <span className="font-mono text-xs break-all">{entry.spine_adjustment_id}</span> on
              the pinned version.
            </li>
          ))}
        </ul>
      )}

      <h3 className="mt-5 text-xs font-semibold tracking-wide text-slate-600 uppercase">
        States the two modules disagree on
      </h3>
      {disagreements.length === 0 ? (
        <p className="mt-1 text-sm text-slate-600">None.</p>
      ) : (
        <ul aria-label="Disagreements" className="mt-1 list-disc space-y-1 pl-5 text-sm">
          {disagreements.map((entry) => (
            <li key={entry.spine_adjustment_id}>
              {entry.ref} is {STATE_LABEL[entry.state].toLowerCase()} here, which expects the
              Spine’s adjustment to be {entry.expected_adjustment_status}; the Spine holds it{' '}
              {entry.adjustment_status}.
            </li>
          ))}
        </ul>
      )}

      {duplicated.length > 0 && (
        <p className="mt-4 text-sm text-amber-900">
          References the Spine holds more than once: {duplicated.join(', ')}.
        </p>
      )}
      <p className="mt-4 text-sm text-slate-700">
        Adjustments in the Spine that belong to no misstatement of this module:{' '}
        {report.not_ours ?? NOT_AVAILABLE}.
      </p>
      {report.basis !== undefined && <Basis>{report.basis}</Basis>}
    </>
  )
}

function ReconciliationPanel({ report }: { report: Reconciliation }) {
  const status = reconciliationStatus(report.status)
  return (
    <Panel id="reconciliation" title="Reconciliation with the Financial Spine">
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <span>Financial Spine:</span>
        <Pill tone={status.tone}>{status.text}</Pill>
      </p>
      {report.status === 'ok' ? (
        <Findings report={report} />
      ) : (
        <div className="mt-3">
          <Unavailable what="The reconciliation is not available." why={report.detail} />
        </div>
      )}
    </Panel>
  )
}

export function SpinePage({ id }: { id: string }) {
  const { resource, reload, refresh } = useResource(() => load(id), `spine:${id}`)
  const label = resource.state === 'ready' ? resource.data.engagement.label : null
  usePageTitle(label === null ? 'Financial Spine' : `Financial Spine · ${label}`)

  return (
    <section aria-labelledby="spine-heading">
      <Breadcrumb id={id} label={label} here="Financial Spine" />

      {resource.state === 'loading' && <Loading label="Loading the Financial Spine link…" />}
      {resource.state === 'error' && (
        <ErrorState
          title="The Financial Spine link could not be loaded"
          error={resource.error}
          onRetry={reload}
        />
      )}

      {resource.state === 'ready' && (
        <>
          <EngagementHeader
            id={id}
            label={resource.data.engagement.label}
            headingId="spine-heading"
            screen="Financial Spine"
            tab="spine"
          />
          <div className="mt-5 space-y-5">
            <Link key={`link:${id}`} engagement={resource.data.engagement} onLinked={refresh} />
            <ReconciliationPanel report={resource.data.reconciliation} />
          </div>
        </>
      )}
    </section>
  )
}
