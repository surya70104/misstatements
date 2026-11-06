// The thresholds of one engagement (spec section 4): the three lines with the declared
// fraction and the basis, who set them and when, the check against the Financial Spine's
// performance materiality, every version, and the record of each recompute.
//
// A person declares overall materiality, performance materiality, the fraction of PM that
// is clearly trivial, and the basis. The backend computes the clearly-trivial amount and
// refuses what SA 320 does not allow. Thresholds are never edited: revising them, which is
// how materiality is reassessed, adds a version; every band then recomputes, and the
// backend records that it did (acceptance 2).
import { useState, type SyntheticEvent } from 'react'

import {
  getEngagement,
  getThresholds,
  listEvents,
  listThresholdHistory,
  setThresholds,
  type CurrentThreshold,
  type Engagement,
  type ModuleEvent,
  type Threshold,
  type ThresholdInput,
} from '../api'
import { Breadcrumb, EngagementHeader } from '../components/EngagementHeader'
import { Field, INPUT, PRIMARY, Recorded, isAmount } from '../components/forms'
import { Basis, Fact, Panel } from '../components/panels'
import { ErrorState, Loading, Pill } from '../components/states'
import { dateTime, NOT_AVAILABLE, rupees } from '../format'
import { pmCheckStatus } from '../labels'
import { href } from '../router'
import { usePageTitle } from '../usePageTitle'
import { useResource } from '../useResource'
import { useSubmit } from '../useSubmit'

type Loaded = {
  engagement: Engagement
  current: CurrentThreshold
  history: Threshold[]
  events: ModuleEvent[]
}

async function load(id: string): Promise<Loaded> {
  const [engagement, current, history, events] = await Promise.allSettled([
    getEngagement(id),
    getThresholds(id),
    listThresholdHistory(id),
    listEvents(id),
  ])
  if (engagement.status === 'rejected') throw engagement.reason
  if (current.status === 'rejected') throw current.reason
  if (history.status === 'rejected') throw history.reason
  if (events.status === 'rejected') throw events.reason
  return {
    engagement: engagement.value,
    current: current.value,
    history: history.value,
    events: events.value,
  }
}

function Current({ threshold }: { threshold: Threshold }) {
  const check = threshold.spine_pm_check
  const status = check === undefined ? null : pmCheckStatus(check.status)
  return (
    <Panel id="current" title={`Current thresholds: version ${String(threshold.version_no)}`}>
      <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
        <Fact label="Overall materiality (OM)">
          <span className="tabular-nums">{rupees(threshold.om)}</span>
        </Fact>
        <Fact label="Performance materiality (PM)">
          <span className="tabular-nums">{rupees(threshold.pm)}</span>
        </Fact>
        <Fact label="Clearly trivial (CTT)">
          <span className="tabular-nums">{rupees(threshold.ctt)}</span>
        </Fact>
        <Fact label="Declared fraction of PM">
          <span className="tabular-nums">{threshold.ctt_fraction}</span>
        </Fact>
        <Fact label="Basis" wide>
          {threshold.basis}
        </Fact>
        <Fact label="Set by">{threshold.set_by}</Fact>
        <Fact label="Set">
          <time dateTime={threshold.set_at}>{dateTime(threshold.set_at)}</time>
        </Fact>
        <Fact label="PM below OM">{threshold.checks.pm_below_om ? 'Yes' : 'No'}</Fact>
      </dl>
      <Basis>{threshold.checks.note}</Basis>

      {check !== undefined && status !== null && (
        <div className="mt-5 border-t border-slate-200 pt-4">
          <h3 className="text-xs font-semibold tracking-wide text-slate-600 uppercase">
            Check against the Financial Spine
          </h3>
          <p className="mt-2 flex flex-wrap items-center gap-2 text-sm">
            <span>Performance materiality:</span>
            <Pill tone={status.tone}>{status.text}</Pill>
          </p>
          {check.detail !== null && <Basis>{check.detail}</Basis>}
          <dl className="mt-3 grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
            <Fact label="PM held here">
              <span className="tabular-nums">{rupees(check.our_pm)}</span>
            </Fact>
            <Fact label="PM in the Spine now">
              <span className="tabular-nums">
                {check.spine_pm === null ? NOT_AVAILABLE : rupees(check.spine_pm)}
              </span>
            </Fact>
            <Fact label="PM in the Spine when set">
              <span className="tabular-nums">
                {threshold.spine.pm_at_set === null
                  ? NOT_AVAILABLE
                  : rupees(threshold.spine.pm_at_set)}
              </span>
            </Fact>
            <Fact label="Spine version">
              <span className="font-mono text-xs break-all">
                {check.recorded_version_id === null
                  ? 'None when set'
                  : `Set against ${check.recorded_version_id}`}
                {check.pinned_version_id !== check.recorded_version_id &&
                  `; now pinned to ${check.pinned_version_id ?? 'none'}`}
              </span>
            </Fact>
          </dl>
        </div>
      )}
    </Panel>
  )
}

function ThresholdForm({
  engagementId,
  revising,
  onSet,
}: {
  engagementId: string
  revising: boolean
  onSet: () => void
}) {
  const [om, setOm] = useState('')
  const [pm, setPm] = useState('')
  const [fraction, setFraction] = useState('')
  const [basis, setBasis] = useState('')
  const [recorded, setRecorded] = useState<Threshold | null>(null)
  const { submitting, error, submit } = useSubmit()
  const complete = isAmount(om) && isAmount(pm) && fraction.trim() !== '' && basis.trim() !== ''

  async function save(event: SyntheticEvent) {
    event.preventDefault()
    if (!complete) return
    const body: ThresholdInput = {
      om: om.trim(),
      pm: pm.trim(),
      ctt_fraction: fraction.trim(),
      basis: basis.trim(),
    }
    setRecorded(null)
    const sent = await submit(() => setThresholds(engagementId, body))
    if (!sent.ok) return
    setRecorded(sent.value)
    setOm('')
    setPm('')
    setFraction('')
    setBasis('')
    onSet()
  }

  return (
    <Panel id="set" title={revising ? 'Revise the thresholds' : 'Set the thresholds'}>
      <p className="max-w-3xl text-sm text-slate-700">
        {revising
          ? 'Revising the thresholds is how a reassessment of materiality is recorded. A new version is added and the current one is kept as superseded; every band then recomputes against the new version, and the recompute is recorded.'
          : 'No thresholds have been set. Until they are, no misstatement can be banded and no gate can be evaluated.'}
      </p>
      <form
        aria-label={revising ? 'Revise the thresholds' : 'Set the thresholds'}
        onSubmit={(event) => {
          void save(event)
        }}
        className="mt-4 space-y-4"
      >
        <div className="grid gap-4 sm:grid-cols-3">
          <Field id="threshold-om" label="Overall materiality" required hint="In rupees.">
            <input
              id="threshold-om"
              value={om}
              required
              inputMode="decimal"
              disabled={submitting}
              aria-describedby="threshold-om-hint"
              onChange={(event) => {
                setOm(event.target.value)
              }}
              className={`${INPUT} tabular-nums`}
            />
          </Field>
          <Field
            id="threshold-pm"
            label="Performance materiality"
            required
            hint="In rupees. Below overall materiality."
          >
            <input
              id="threshold-pm"
              value={pm}
              required
              inputMode="decimal"
              disabled={submitting}
              aria-describedby="threshold-pm-hint"
              onChange={(event) => {
                setPm(event.target.value)
              }}
              className={`${INPUT} tabular-nums`}
            />
          </Field>
          <Field
            id="threshold-fraction"
            label="Clearly-trivial fraction of PM"
            required
            hint="A fraction between 0 and 1, for example 0.05. It has no default: it is declared."
          >
            <input
              id="threshold-fraction"
              value={fraction}
              required
              inputMode="decimal"
              disabled={submitting}
              aria-describedby="threshold-fraction-hint"
              onChange={(event) => {
                setFraction(event.target.value)
              }}
              className={`${INPUT} tabular-nums`}
            />
          </Field>
        </div>
        <Field
          id="threshold-basis"
          label="Basis"
          required
          hint="How the figures were arrived at: the benchmark, the percentages, the working paper."
        >
          <textarea
            id="threshold-basis"
            value={basis}
            required
            rows={2}
            maxLength={2000}
            disabled={submitting}
            aria-describedby="threshold-basis-hint"
            onChange={(event) => {
              setBasis(event.target.value)
            }}
            className={INPUT}
          />
        </Field>

        {error !== null && <ErrorState title="The thresholds were not set" error={error} />}
        {recorded !== null && (
          <Recorded>
            Recorded: thresholds version {recorded.version_no}, clearly trivial{' '}
            {rupees(recorded.ctt)}.
            {recorded.recompute_event != null && ' The recompute of every band is recorded.'}
          </Recorded>
        )}

        <button type="submit" disabled={submitting || !complete} className={PRIMARY}>
          {submitting ? 'Recording…' : revising ? 'Revise thresholds' : 'Set thresholds'}
        </button>
      </form>
    </Panel>
  )
}

function Versions({ history }: { history: Threshold[] }) {
  const HEAD = 'px-3 py-2 font-semibold'
  const CELL =
    'px-3 py-2 max-lg:flex max-lg:gap-3 max-lg:px-0 max-lg:py-0.5 max-lg:before:w-28 max-lg:before:shrink-0 max-lg:before:text-xs max-lg:before:tracking-wide max-lg:before:text-slate-500 max-lg:before:uppercase max-lg:before:content-[attr(data-label)]'
  const MONEY = `${CELL} tabular-nums lg:text-right lg:whitespace-nowrap`
  return (
    <Panel id="versions" title="Versions">
      <table className="w-full border-collapse text-sm max-lg:block">
        <caption className="sr-only">Every version of the thresholds</caption>
        <thead className="bg-slate-100 text-left text-xs tracking-wide text-slate-600 uppercase max-lg:sr-only">
          <tr>
            <th scope="col" className={HEAD}>
              Version
            </th>
            <th scope="col" className={`${HEAD} text-right`}>
              OM
            </th>
            <th scope="col" className={`${HEAD} text-right`}>
              PM
            </th>
            <th scope="col" className={`${HEAD} text-right`}>
              CTT
            </th>
            <th scope="col" className={`${HEAD} text-right`}>
              Fraction
            </th>
            <th scope="col" className={HEAD}>
              Basis
            </th>
            <th scope="col" className={HEAD}>
              Set
            </th>
            <th scope="col" className={HEAD}>
              Status
            </th>
          </tr>
        </thead>
        <tbody className="max-lg:block">
          {history.map((version) => (
            <tr
              key={version.id}
              className="border-t border-slate-200 align-top max-lg:block max-lg:py-3"
            >
              <th
                scope="row"
                className="px-3 py-2 text-left font-medium whitespace-nowrap max-lg:block max-lg:px-0 max-lg:pt-0"
              >
                Version {version.version_no}
              </th>
              <td data-label="OM" className={MONEY}>
                {rupees(version.om)}
              </td>
              <td data-label="PM" className={MONEY}>
                {rupees(version.pm)}
              </td>
              <td data-label="CTT" className={MONEY}>
                {rupees(version.ctt)}
              </td>
              <td data-label="Fraction" className={MONEY}>
                {version.ctt_fraction}
              </td>
              <td data-label="Basis" className={CELL}>
                <span className="min-w-0 break-words">{version.basis}</span>
              </td>
              <td data-label="Set" className={CELL}>
                <span>
                  <time dateTime={version.set_at}>{dateTime(version.set_at)}</time>
                  <span className="block text-xs text-slate-600">by {version.set_by}</span>
                </span>
              </td>
              <td data-label="Status" className={CELL}>
                <span>
                  {version.is_current ? <Pill tone="good">Current</Pill> : <Pill>Superseded</Pill>}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  )
}

type Change = { from?: unknown; to?: unknown }

function changesOf(event: ModuleEvent): [string, Change][] {
  const changes = event.payload.changes
  if (typeof changes !== 'object' || changes === null) return []
  return Object.entries(changes as Record<string, Change>)
}

const CHANGED: Record<string, string> = {
  om: 'Overall materiality',
  pm: 'Performance materiality',
  ctt: 'Clearly trivial',
  ctt_fraction: 'Fraction of PM',
  basis: 'Basis',
}

function shown(field: string, value: unknown): string {
  if (typeof value !== 'string') return JSON.stringify(value)
  return field === 'om' || field === 'pm' || field === 'ctt' ? rupees(value) : value
}

function Recomputes({ events }: { events: ModuleEvent[] }) {
  const recomputes = events.filter((event) => event.kind === 'threshold_recompute')
  return (
    <Panel id="recomputes" title="Recomputes recorded">
      {recomputes.length === 0 ? (
        <p className="text-sm text-slate-600">
          No recompute has been recorded: the thresholds have not been revised.
        </p>
      ) : (
        <ol aria-label="Recomputes recorded" className="space-y-4">
          {recomputes.map((event) => (
            <li key={event.id} className="text-sm">
              <p className="font-medium">
                Version {String(event.payload.previous_version_no)} to version{' '}
                {String(event.payload.current_version_no)}
                <span className="font-normal text-slate-600">
                  {' '}
                  by {event.actor}, <time dateTime={event.at}>{dateTime(event.at)}</time>
                </span>
              </p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-slate-800">
                {changesOf(event).map(([field, change]) => (
                  <li key={field}>
                    {CHANGED[field] ?? field}: {shown(field, change.from)} to{' '}
                    {shown(field, change.to)}
                  </li>
                ))}
              </ul>
              {typeof event.payload.bands === 'string' && <Basis>{event.payload.bands}</Basis>}
            </li>
          ))}
        </ol>
      )}
    </Panel>
  )
}

export function ThresholdsPage({ id }: { id: string }) {
  const { resource, reload, refresh } = useResource(() => load(id), `thresholds:${id}`)
  const label = resource.state === 'ready' ? resource.data.engagement.label : null
  usePageTitle(label === null ? 'Thresholds' : `Thresholds · ${label}`)

  return (
    <section aria-labelledby="thresholds-heading">
      <Breadcrumb id={id} label={label} here="Thresholds" />

      {resource.state === 'loading' && <Loading label="Loading the thresholds…" />}
      {resource.state === 'error' && (
        <ErrorState
          title="The thresholds could not be loaded"
          error={resource.error}
          onRetry={reload}
        />
      )}

      {resource.state === 'ready' && (
        <>
          <EngagementHeader
            id={id}
            label={resource.data.engagement.label}
            headingId="thresholds-heading"
            screen="Thresholds"
            tab="thresholds"
          />
          <div className="mt-5 space-y-5">
            {resource.data.current.current === null ? (
              <p className="rounded-md border border-dashed border-slate-300 bg-white px-5 py-4 text-sm text-slate-700">
                {resource.data.current.detail ?? 'No thresholds have been set.'}
              </p>
            ) : (
              <Current threshold={resource.data.current.current} />
            )}
            <ThresholdForm
              key={`form:${id}`}
              engagementId={id}
              revising={resource.data.current.current !== null}
              onSet={refresh}
            />
            {resource.data.history.length > 0 && <Versions history={resource.data.history} />}
            <Recomputes events={resource.data.events} />
            <p className="text-sm text-slate-600">
              The reassessment of materiality before an evaluation is stated when a run is recorded,
              on the{' '}
              <a
                href={href({ name: 'evaluation', id })}
                className="underline decoration-slate-300 underline-offset-2 hover:decoration-slate-700"
              >
                evaluation
              </a>
              .
            </p>
          </div>
        </>
      )}
    </section>
  )
}
