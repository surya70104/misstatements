// One engagement's schedule of misstatements (spec sections 6.1 and 10.1): the running
// totals at the top, the filters by band, type and state, and every misstatement.
//
// Display only. The misstatements come from the misstatement API and the totals from the
// evaluation API. The filters choose which rows are shown and nothing else: the totals are
// the backend's aggregate of the whole engagement and are not recomputed for the rows shown.
import { useState } from 'react'

import {
  getEngagement,
  getEvaluation,
  listMisstatements,
  type Band,
  type Engagement,
  type Evaluation,
  type Misstatement,
  type MisstatementState,
  type MisstatementType,
  type SpineLinkState,
} from '../api'
import { EngagementNav } from '../components/EngagementNav'
import { RunningTotals } from '../components/RunningTotals'
import { ScheduleTable } from '../components/ScheduleTable'
import { Empty, ErrorState, Loading, Pill } from '../components/states'
import { count } from '../format'
import { BAND_LABEL, BANDS, NOT_BANDED, STATE_LABEL, STATES, TYPE_LABEL, TYPES } from '../labels'
import { href } from '../router'
import { usePageTitle } from '../usePageTitle'
import { useResource } from '../useResource'

const SPINE: Record<SpineLinkState, { text: string; tone: 'neutral' | 'good' | 'attention' }> = {
  unlinked: { text: 'Not linked to the Financial Spine', tone: 'neutral' },
  recorded: { text: 'Financial Spine link recorded', tone: 'neutral' },
  verified: { text: 'Financial Spine link verified', tone: 'good' },
  not_configured: { text: 'Financial Spine not configured', tone: 'attention' },
  missing: { text: 'Financial Spine record missing', tone: 'attention' },
  unreachable: { text: 'Financial Spine unreachable', tone: 'attention' },
  mismatch: { text: 'Financial Spine version mismatch', tone: 'attention' },
}

type Schedule = { engagement: Engagement; misstatements: Misstatement[]; evaluation: Evaluation }

/**
 * The three reads the schedule needs, asked for together. When more than one fails the
 * engagement's failure is reported first, so an engagement that does not exist says so.
 */
async function loadSchedule(id: string): Promise<Schedule> {
  const [engagement, misstatements, evaluation] = await Promise.allSettled([
    getEngagement(id),
    listMisstatements(id),
    getEvaluation(id),
  ])
  if (engagement.status === 'rejected') throw engagement.reason
  if (misstatements.status === 'rejected') throw misstatements.reason
  if (evaluation.status === 'rejected') throw evaluation.reason
  return {
    engagement: engagement.value,
    misstatements: misstatements.value,
    evaluation: evaluation.value,
  }
}

// What a filter is set to: one of the backend's values, 'none' for a misstatement the
// backend could not band, or '' for no filter.
type Filters = {
  band: Band | 'none' | ''
  type: MisstatementType | ''
  state: MisstatementState | ''
}

const NO_FILTERS: Filters = { band: '', type: '', state: '' }

function matches(misstatement: Misstatement, filters: Filters): boolean {
  if (filters.band !== '' && (misstatement.band ?? 'none') !== filters.band) return false
  if (filters.type !== '' && misstatement.current.type !== filters.type) return false
  if (filters.state !== '' && misstatement.current.state !== filters.state) return false
  return true
}

function Select({
  id,
  label,
  all,
  value,
  options,
  onChange,
}: {
  id: string
  label: string
  all: string
  value: string
  options: { value: string; label: string }[]
  onChange: (value: string) => void
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-medium text-slate-600">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => {
          onChange(event.target.value)
        }}
        className="rounded border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
      >
        <option value="">{all}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  )
}

function Misstatements({ misstatements }: { misstatements: Misstatement[] }) {
  const [filters, setFilters] = useState<Filters>(NO_FILTERS)
  const shown = misstatements.filter((misstatement) => matches(misstatement, filters))
  const filtered = filters.band !== '' || filters.type !== '' || filters.state !== ''

  if (misstatements.length === 0) {
    return (
      <div className="mt-6">
        <Empty title="No misstatements raised">
          Nothing has been raised on this engagement. A misstatement recorded from a working paper
          appears here with its Dr/Cr lines, its effects and its band.
        </Empty>
      </div>
    )
  }

  return (
    <section aria-labelledby="misstatements-heading" className="mt-6">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div>
          <h2 id="misstatements-heading" className="text-sm font-semibold">
            Misstatements
          </h2>
          <p role="status" aria-live="polite" className="mt-0.5 text-sm text-slate-600">
            {filtered
              ? `Showing ${String(shown.length)} of ${count(misstatements.length, 'misstatement')}`
              : count(misstatements.length, 'misstatement')}
          </p>
        </div>
        <form
          aria-label="Filters"
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault()
          }}
        >
          <Select
            id="filter-band"
            label="Band"
            all="All bands"
            value={filters.band}
            options={[
              ...BANDS.map((band) => ({ value: band, label: BAND_LABEL[band] })),
              { value: 'none', label: NOT_BANDED },
            ]}
            onChange={(value) => {
              setFilters({ ...filters, band: value as Filters['band'] })
            }}
          />
          <Select
            id="filter-type"
            label="Type"
            all="All types"
            value={filters.type}
            options={TYPES.map((type) => ({ value: type, label: TYPE_LABEL[type] }))}
            onChange={(value) => {
              setFilters({ ...filters, type: value as Filters['type'] })
            }}
          />
          <Select
            id="filter-state"
            label="State"
            all="All states"
            value={filters.state}
            options={STATES.map((state) => ({ value: state, label: STATE_LABEL[state] }))}
            onChange={(value) => {
              setFilters({ ...filters, state: value as Filters['state'] })
            }}
          />
          <button
            type="button"
            disabled={!filtered}
            onClick={() => {
              setFilters(NO_FILTERS)
            }}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700 disabled:cursor-default disabled:text-slate-400 disabled:hover:bg-white"
          >
            Clear filters
          </button>
        </form>
      </div>

      {shown.length === 0 ? (
        <Empty title="No misstatement matches these filters">
          Change a filter or clear them to see all {count(misstatements.length, 'misstatement')}.
        </Empty>
      ) : (
        <ScheduleTable misstatements={shown} />
      )}
    </section>
  )
}

function Header({ engagement }: { engagement: Engagement }) {
  const spine = SPINE[engagement.spine.status]
  return (
    <header>
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <h1 id="schedule-heading" className="text-xl font-semibold">
              {engagement.label}
            </h1>
            <Pill tone={spine.tone}>{spine.text}</Pill>
            {engagement.spine.is_locked === true && <Pill tone="attention">Version locked</Pill>}
          </div>
          <p className="mt-1 text-sm text-slate-600">Schedule of misstatements</p>
          {engagement.spine.detail !== null && (
            <p className="mt-1 text-sm text-slate-600">{engagement.spine.detail}</p>
          )}
        </div>
        <a
          href={href({ name: 'raise', id: engagement.id })}
          className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
        >
          Record a misstatement
        </a>
      </div>
      <EngagementNav id={engagement.id} current="schedule" />
    </header>
  )
}

export function SchedulePage({ id }: { id: string }) {
  const { resource, reload } = useResource(() => loadSchedule(id), `schedule:${id}`)
  const label = resource.state === 'ready' ? resource.data.engagement.label : null
  usePageTitle(label === null ? 'Schedule' : `Schedule · ${label}`)

  return (
    <section aria-labelledby="schedule-heading">
      <nav aria-label="Breadcrumb" className="mb-3 text-sm text-slate-600">
        <a
          href={href({ name: 'engagements' })}
          className="underline decoration-slate-300 underline-offset-2 hover:decoration-slate-700"
        >
          Engagements
        </a>
        <span aria-hidden="true"> / </span>
        <span>{resource.state === 'ready' ? resource.data.engagement.label : 'Engagement'}</span>
      </nav>

      {resource.state === 'loading' && <Loading label="Loading the schedule…" />}

      {resource.state === 'error' && (
        <ErrorState
          title="This schedule could not be loaded"
          error={resource.error}
          onRetry={reload}
        />
      )}

      {resource.state === 'ready' && (
        <>
          <Header engagement={resource.data.engagement} />
          <RunningTotals evaluation={resource.data.evaluation} />
          {/* Keyed by engagement so one engagement's filters never carry over to another. */}
          <Misstatements key={id} misstatements={resource.data.misstatements} />
        </>
      )}
    </section>
  )
}
