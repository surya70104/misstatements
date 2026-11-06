// Prior-period uncorrected misstatements carried forward (SA 450 paragraph 11(b); spec
// sections 4.1 and 10.3; acceptance 5; backend D61).
//
// Each carried item is shown with its current-period effect and its cumulative effect side
// by side, on profit before tax and on net assets. Below them: the current year's own
// aggregate, the prior-period totals on each basis, and the two together on each basis, so
// the evaluation is seen both ways and no one method is chosen.
//
// Every figure is the backend's. The four effects of an item are what a person recorded: the
// backend does not compute how a prior period's misstatement affects this one, and neither
// does this screen. Whether a figure is at or above a line is the backend's too. The only
// arithmetic here is the percentage, which is presentation and exact (`format.ts`).
//
// No gate reads these figures: the backend says so, and this screen repeats it.
import { useState, type SyntheticEvent } from 'react'

import {
  recordPriorPeriodItem,
  removePriorPeriodItem,
  type BothWays,
  type Evaluation,
  type PriorPeriodBasis,
  type PriorPeriodItem,
} from '../../api'
import { count, dateTime, NOT_AVAILABLE, percentOf, rupees } from '../../format'
import { NOTE_MAX_LENGTH } from '../../labels'
import { useSubmit } from '../../useSubmit'
import { Field, INPUT, isSignedAmount, PRIMARY, Recorded, SECONDARY } from '../forms'
import { Panel } from '../panels'
import { ErrorState, Pill } from '../states'

const HEAD = 'px-3 py-2 text-right font-semibold'
const GROUP = 'px-3 py-2 text-center font-semibold border-l border-slate-200'

// Below the `lg` width a cell is a labelled value: its column's name, then the figure.
const CELL =
  'px-3 py-2 text-right tabular-nums max-lg:flex max-lg:justify-between max-lg:gap-3 max-lg:px-0 max-lg:py-0.5 max-lg:text-left max-lg:before:text-xs max-lg:before:text-slate-500 max-lg:before:content-[attr(data-label)]'

const BASIS_LABEL: Record<PriorPeriodBasis, string> = {
  current_period: 'current-period basis',
  cumulative: 'cumulative basis',
}

function ItemRow({
  item,
  removing,
  disabled,
  onRemove,
}: {
  item: PriorPeriodItem
  removing: boolean
  disabled: boolean
  onRemove: () => void
}) {
  return (
    <tr className="border-t border-slate-200 align-top max-lg:block max-lg:py-3">
      <th
        scope="row"
        className="px-3 py-2 text-left font-medium whitespace-nowrap max-lg:block max-lg:px-0"
      >
        {item.ref}
      </th>
      <td className="px-3 py-2 max-lg:block max-lg:px-0 max-lg:py-1">
        <p className="break-words text-slate-900">{item.description}</p>
        <p className="mt-0.5 text-xs text-slate-600">
          {item.prior_period} · {item.source_ref}
          {item.rolled_forward && ' · rolled forward'}
        </p>
        {item.prior !== null && (
          <p className="mt-0.5 text-xs text-slate-600">
            Uncorrected there: profit before tax{' '}
            <span className="tabular-nums">{rupees(item.prior.profit_before_tax)}</span>, net assets{' '}
            <span className="tabular-nums">{rupees(item.prior.net_assets)}</span>
          </p>
        )}
        <p className="mt-1 text-xs break-words text-slate-700">
          <span className="text-slate-500">Basis of the effects: </span>
          {item.basis}
        </p>
        <p className="mt-0.5 text-xs text-slate-500">
          by {item.recorded_by}
          {item.at !== null && (
            <>
              {', '}
              <time dateTime={item.at}>{dateTime(item.at)}</time>
            </>
          )}
          {' · '}version {item.version_no}
        </p>
      </td>
      <td
        data-label="Current period: profit before tax"
        className={`${CELL} lg:border-l lg:border-slate-200`}
      >
        {rupees(item.current_period.profit_before_tax)}
      </td>
      <td data-label="Current period: net assets" className={CELL}>
        {rupees(item.current_period.net_assets)}
      </td>
      <td
        data-label="Cumulative: profit before tax"
        className={`${CELL} lg:border-l lg:border-slate-200`}
      >
        {rupees(item.cumulative.profit_before_tax)}
      </td>
      <td data-label="Cumulative: net assets" className={CELL}>
        {rupees(item.cumulative.net_assets)}
      </td>
      <td className="px-3 py-2 text-right max-lg:block max-lg:px-0 max-lg:text-left">
        <button
          type="button"
          aria-label={`Stop carrying ${item.ref}`}
          aria-pressed={removing}
          disabled={disabled}
          onClick={onRemove}
          className={`${SECONDARY} aria-pressed:border-slate-800 aria-pressed:bg-slate-100`}
        >
          Stop carrying
        </button>
      </td>
    </tr>
  )
}

function Items({
  items,
  removing,
  disabled,
  onRemove,
}: {
  items: PriorPeriodItem[]
  removing: string | null
  disabled: boolean
  onRemove: (ref: string) => void
}) {
  return (
    <table className="mt-4 w-full border-collapse text-sm max-lg:block">
      <caption className="sr-only">
        Prior-period items carried forward, each with its current-period effect and its cumulative
        effect
      </caption>
      <thead className="bg-slate-100 text-xs text-slate-600 max-lg:sr-only">
        <tr>
          <th scope="col" rowSpan={2} className="px-3 py-2 text-left align-bottom font-semibold">
            Ref
          </th>
          <th scope="col" rowSpan={2} className="px-3 py-2 text-left align-bottom font-semibold">
            Prior-period item
          </th>
          <th scope="colgroup" colSpan={2} className={GROUP}>
            Current-period effect
          </th>
          <th scope="colgroup" colSpan={2} className={GROUP}>
            Cumulative effect
          </th>
          <th scope="col" rowSpan={2} className="px-3 py-2">
            <span className="sr-only">Actions</span>
          </th>
        </tr>
        <tr>
          <th scope="col" className={`${HEAD} border-l border-slate-200`}>
            Profit before tax
          </th>
          <th scope="col" className={HEAD}>
            Net assets
          </th>
          <th scope="col" className={`${HEAD} border-l border-slate-200`}>
            Profit before tax
          </th>
          <th scope="col" className={HEAD}>
            Net assets
          </th>
        </tr>
      </thead>
      <tbody className="max-lg:block">
        {items.map((item) => (
          <ItemRow
            key={item.ref}
            item={item}
            removing={removing === item.ref}
            disabled={disabled}
            onRemove={() => {
              onRemove(item.ref)
            }}
          />
        ))}
      </tbody>
    </table>
  )
}

type Way = 'gross' | 'net'

function Together({
  figure,
  basis,
  name,
  evaluation,
}: {
  figure: string
  basis: PriorPeriodBasis
  name: string
  evaluation: Evaluation
}) {
  const { threshold, prior_period: prior } = evaluation
  // Which lines this figure is at or above is the backend's reading, never this screen's.
  const reached = prior.reaches?.[basis]
  return (
    <span>
      {rupees(figure)}
      <span className="block text-xs font-normal text-slate-600">
        {percentOf(figure, threshold?.pm) ?? NOT_AVAILABLE} of PM ·{' '}
        {percentOf(figure, threshold?.om) ?? NOT_AVAILABLE} of OM
      </span>
      {reached?.om.includes(name) === true ? (
        <span className="mt-0.5 block">
          <Pill tone="attention">At or above OM</Pill>
        </span>
      ) : (
        reached?.pm.includes(name) === true && (
          <span className="mt-0.5 block">
            <Pill tone="attention">At or above PM</Pill>
          </span>
        )
      )}
    </span>
  )
}

function SummaryRow({
  label,
  measure,
  measureKey,
  way,
  evaluation,
}: {
  label: string
  measure: keyof BothWays
  measureKey: 'profit' | 'net_assets'
  way: Way
  evaluation: Evaluation
}) {
  const prior = evaluation.prior_period
  const name = `${measureKey}.${way}`
  return (
    <tr className="border-t border-slate-200 align-top max-lg:block max-lg:py-2">
      <th scope="row" className="px-3 py-2 text-left font-medium max-lg:block max-lg:px-0">
        {label} <span className="font-normal text-slate-500">{way}</span>
      </th>
      <td data-label="Current year" className={CELL}>
        {rupees(prior.current_year[measure][way])}
      </td>
      <td
        data-label="Prior period: current-period effect"
        className={`${CELL} lg:border-l lg:border-slate-200`}
      >
        {rupees(prior.totals.current_period[measure][way])}
      </td>
      <td data-label="Prior period: cumulative effect" className={CELL}>
        {rupees(prior.totals.cumulative[measure][way])}
      </td>
      <td
        data-label="With prior period: current-period basis"
        className={`${CELL} font-medium lg:border-l lg:border-slate-200`}
      >
        <Together
          figure={prior.with_prior_period.current_period[measure][way]}
          basis="current_period"
          name={name}
          evaluation={evaluation}
        />
      </td>
      <td data-label="With prior period: cumulative basis" className={`${CELL} font-medium`}>
        <Together
          figure={prior.with_prior_period.cumulative[measure][way]}
          basis="cumulative"
          name={name}
          evaluation={evaluation}
        />
      </td>
    </tr>
  )
}

function Summary({ evaluation }: { evaluation: Evaluation }) {
  return (
    <table className="mt-2 w-full border-collapse text-sm max-lg:block">
      <caption className="sr-only">
        The current year's aggregate, the prior-period totals on each basis, and the two together on
        each basis
      </caption>
      <thead className="bg-slate-100 text-xs text-slate-600 max-lg:sr-only">
        <tr>
          <th scope="col" rowSpan={2} className="px-3 py-2 text-left align-bottom font-semibold">
            Effect
          </th>
          <th scope="col" rowSpan={2} className={`${HEAD} align-bottom`}>
            Current year
          </th>
          <th scope="colgroup" colSpan={2} className={GROUP}>
            Prior-period items
          </th>
          <th scope="colgroup" colSpan={2} className={GROUP}>
            Current year with prior-period items
          </th>
        </tr>
        <tr>
          <th scope="col" className={`${HEAD} border-l border-slate-200`}>
            Current-period effect
          </th>
          <th scope="col" className={HEAD}>
            Cumulative effect
          </th>
          <th scope="col" className={`${HEAD} border-l border-slate-200`}>
            Current-period basis
          </th>
          <th scope="col" className={HEAD}>
            Cumulative basis
          </th>
        </tr>
      </thead>
      <tbody className="max-lg:block">
        <SummaryRow
          label="Profit before tax"
          measure="profit_before_tax"
          measureKey="profit"
          way="gross"
          evaluation={evaluation}
        />
        <SummaryRow
          label="Profit before tax"
          measure="profit_before_tax"
          measureKey="profit"
          way="net"
          evaluation={evaluation}
        />
        <SummaryRow
          label="Net assets"
          measure="net_assets"
          measureKey="net_assets"
          way="gross"
          evaluation={evaluation}
        />
        <SummaryRow
          label="Net assets"
          measure="net_assets"
          measureKey="net_assets"
          way="net"
          evaluation={evaluation}
        />
      </tbody>
    </table>
  )
}

/** The bases on which the two together are at or above a line, in the backend's reading. */
function reachedOn(evaluation: Evaluation, line: 'pm' | 'om'): string[] {
  const reaches = evaluation.prior_period.reaches
  if (reaches === null) return []
  return (['current_period', 'cumulative'] as const)
    .filter((basis) => reaches[basis][line].length > 0)
    .map((basis) => BASIS_LABEL[basis])
}

const BLANK = {
  description: '',
  prior_period: '',
  source_ref: '',
  current_profit_before_tax: '',
  current_net_assets: '',
  cumulative_profit_before_tax: '',
  cumulative_net_assets: '',
  basis: '',
}

type Draft = typeof BLANK

const AMOUNTS: { key: keyof Draft; label: string }[] = [
  { key: 'current_profit_before_tax', label: 'Current-period effect on profit before tax' },
  { key: 'current_net_assets', label: 'Current-period effect on net assets' },
  { key: 'cumulative_profit_before_tax', label: 'Cumulative effect on profit before tax' },
  { key: 'cumulative_net_assets', label: 'Cumulative effect on net assets' },
]

const AMOUNT_HINT =
  'In rupees, signed as the schedule signs an effect: negative when correcting it lowers the figure. Enter 0 when there is none.'

function RecordForm({
  engagementId,
  onRecorded,
  onClose,
}: {
  engagementId: string
  onRecorded: (ref: string) => void
  onClose: () => void
}) {
  const [draft, setDraft] = useState<Draft>(BLANK)
  const { submitting, error, submit } = useSubmit()

  const complete =
    draft.description.trim() !== '' &&
    draft.prior_period.trim() !== '' &&
    draft.source_ref.trim() !== '' &&
    draft.basis.trim() !== '' &&
    AMOUNTS.every(({ key }) => isSignedAmount(draft[key]))

  function set(key: keyof Draft, value: string) {
    setDraft({ ...draft, [key]: value })
  }

  async function send(event: SyntheticEvent) {
    event.preventDefault()
    if (!complete) return
    // Each amount goes out as the exact decimal string that was typed: never a number.
    const sent = await submit(() =>
      recordPriorPeriodItem(engagementId, {
        description: draft.description.trim(),
        prior_period: draft.prior_period.trim(),
        source_ref: draft.source_ref.trim(),
        current_profit_before_tax: draft.current_profit_before_tax.trim(),
        current_net_assets: draft.current_net_assets.trim(),
        cumulative_profit_before_tax: draft.cumulative_profit_before_tax.trim(),
        cumulative_net_assets: draft.cumulative_net_assets.trim(),
        basis: draft.basis.trim(),
      }),
    )
    if (!sent.ok) return
    onRecorded(sent.value.recorded?.ref ?? 'the item')
  }

  return (
    <form
      aria-label="Record a prior-period item"
      onSubmit={(event) => {
        void send(event)
      }}
      className="mt-4 rounded border border-slate-300 bg-slate-50 px-4 py-4"
    >
      <p className="text-sm text-slate-800">
        Records a misstatement left uncorrected in a prior period, with its effect on this period
        and its cumulative effect. Both are your figures: the system does not compute them.
      </p>
      <div className="mt-3 grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Field id="py-description" label="What it is" required>
            <input
              id="py-description"
              type="text"
              value={draft.description}
              required
              maxLength={NOTE_MAX_LENGTH}
              disabled={submitting}
              onChange={(event) => {
                set('description', event.target.value)
              }}
              className={INPUT}
            />
          </Field>
        </div>
        <Field id="py-period" label="Prior period" required hint="For example FY 2024-25.">
          <input
            id="py-period"
            type="text"
            value={draft.prior_period}
            required
            maxLength={200}
            disabled={submitting}
            aria-describedby="py-period-hint"
            onChange={(event) => {
              set('prior_period', event.target.value)
            }}
            className={INPUT}
          />
        </Field>
        <Field
          id="py-source"
          label="Source reference"
          required
          hint="The prior period's schedule or working paper."
        >
          <input
            id="py-source"
            type="text"
            value={draft.source_ref}
            required
            maxLength={200}
            disabled={submitting}
            aria-describedby="py-source-hint"
            onChange={(event) => {
              set('source_ref', event.target.value)
            }}
            className={INPUT}
          />
        </Field>
        {AMOUNTS.map(({ key, label }) => (
          <Field key={key} id={`py-${key}`} label={label} required>
            <input
              id={`py-${key}`}
              type="text"
              inputMode="decimal"
              value={draft[key]}
              required
              disabled={submitting}
              aria-describedby="py-amount-hint"
              aria-invalid={draft[key].trim() !== '' && !isSignedAmount(draft[key])}
              onChange={(event) => {
                set(key, event.target.value)
              }}
              className={`${INPUT} tabular-nums`}
            />
          </Field>
        ))}
        <p id="py-amount-hint" className="text-xs text-slate-600 sm:col-span-2">
          {AMOUNT_HINT}
        </p>
        <div className="sm:col-span-2">
          <Field
            id="py-basis"
            label="Basis of the effects"
            required
            hint="How the current-period and cumulative effects were arrived at. It is recorded with the item."
          >
            <textarea
              id="py-basis"
              value={draft.basis}
              required
              rows={3}
              maxLength={NOTE_MAX_LENGTH}
              disabled={submitting}
              aria-describedby="py-basis-hint"
              onChange={(event) => {
                set('basis', event.target.value)
              }}
              className={INPUT}
            />
          </Field>
        </div>
      </div>

      {error !== null && (
        <div className="mt-3">
          <ErrorState title="The item was not recorded" error={error} />
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <button type="submit" disabled={submitting || !complete} className={PRIMARY}>
          {submitting ? 'Recording…' : 'Confirm: record item'}
        </button>
        <button type="button" disabled={submitting} onClick={onClose} className={SECONDARY}>
          Cancel
        </button>
      </div>
    </form>
  )
}

function RemoveForm({
  engagementId,
  item,
  onRemoved,
  onClose,
}: {
  engagementId: string
  item: PriorPeriodItem
  onRemoved: (ref: string) => void
  onClose: () => void
}) {
  const [reason, setReason] = useState('')
  const { submitting, error, submit } = useSubmit()
  const missing = reason.trim() === ''

  async function send(event: SyntheticEvent) {
    event.preventDefault()
    if (missing) return
    const sent = await submit(() => removePriorPeriodItem(engagementId, item.ref, reason.trim()))
    if (!sent.ok) return
    onRemoved(item.ref)
  }

  return (
    <form
      aria-label={`Stop carrying ${item.ref}`}
      onSubmit={(event) => {
        void send(event)
      }}
      className="mt-4 rounded border border-slate-300 bg-slate-50 px-4 py-4"
    >
      <p className="text-sm font-medium text-slate-900">
        {item.ref}: {item.description}
      </p>
      <p className="mt-1 text-sm text-slate-800">
        Records that this item is no longer carried forward, with the reason. It leaves the totals;
        the item and its figures stay in the record.
      </p>
      <div className="mt-3">
        <Field id="py-removal-reason" label="Reason it is no longer carried" required>
          <textarea
            id="py-removal-reason"
            value={reason}
            required
            rows={2}
            maxLength={NOTE_MAX_LENGTH}
            disabled={submitting}
            onChange={(event) => {
              setReason(event.target.value)
            }}
            className={INPUT}
          />
        </Field>
      </div>

      {error !== null && (
        <div className="mt-3">
          <ErrorState title="Nothing was recorded" error={error} />
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <button type="submit" disabled={submitting || missing} className={PRIMARY}>
          {submitting ? 'Recording…' : 'Confirm: stop carrying'}
        </button>
        <button type="button" disabled={submitting} onClick={onClose} className={SECONDARY}>
          Cancel
        </button>
      </div>
    </form>
  )
}

type Open = { form: 'record' } | { form: 'remove'; ref: string } | null

export function PriorPeriodPanel({
  engagementId,
  evaluation,
  onRecorded,
}: {
  engagementId: string
  evaluation: Evaluation
  onRecorded: () => void
}) {
  const prior = evaluation.prior_period
  const [open, setOpen] = useState<Open>(null)
  const [done, setDone] = useState<string | null>(null)
  const removing = open?.form === 'remove' ? open.ref : null
  const toRemove = removing === null ? undefined : prior.items.find((item) => item.ref === removing)
  const atOm = reachedOn(evaluation, 'om')
  const atPm = reachedOn(evaluation, 'pm')

  function finished(message: string) {
    setDone(message)
    setOpen(null)
    onRecorded()
  }

  return (
    <Panel id="prior-period" title="Prior-period uncorrected misstatements">
      {done !== null && (
        <div className="mb-3">
          <Recorded>{done}</Recorded>
        </div>
      )}

      <p className="max-w-3xl text-sm text-slate-700">
        Misstatements left uncorrected in prior periods and carried forward (SA 450 paragraph
        11(b)). Each is shown with its current-period effect and its cumulative effect, so the
        evaluation can be read both ways.
      </p>

      {prior.items.length === 0 ? (
        <p className="mt-3 text-sm text-slate-700">
          No prior-period item is carried forward on this engagement.
        </p>
      ) : (
        <>
          <p className="mt-3 text-sm text-slate-700">
            {count(prior.items.length, 'prior-period item')} carried forward.
          </p>
          <Items
            items={prior.items}
            removing={removing}
            disabled={false}
            onRemove={(ref) => {
              setDone(null)
              setOpen({ form: 'remove', ref })
            }}
          />

          <h3 className="mt-6 text-xs font-semibold tracking-wide text-slate-600 uppercase">
            Current year and prior-period items
          </h3>
          {!prior.complete && (
            <p className="mt-2 rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              The current year's aggregate is incomplete, so every figure here that includes it is
              short.
            </p>
          )}
          <Summary evaluation={evaluation} />

          {(atOm.length > 0 || atPm.length > 0) && (
            <p
              role="note"
              className="mt-3 rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
            >
              With the prior-period items, a figure is at or above{' '}
              {atOm.length > 0
                ? `overall materiality on the ${atOm.join(' and the ')}`
                : `performance materiality on the ${atPm.join(' and the ')}`}
              . The gates do not test this.
            </p>
          )}
        </>
      )}

      {!prior.read_by_gates && (
        <p className="mt-3 max-w-3xl text-xs text-slate-600">
          The gates and the sign-off decision test the current year's aggregate. They do not read
          the prior-period figures: these are shown for the conclusion.
        </p>
      )}

      {open?.form !== 'record' && (
        <div className="mt-4">
          <button
            type="button"
            onClick={() => {
              setDone(null)
              setOpen({ form: 'record' })
            }}
            className={SECONDARY}
          >
            Record a prior-period item
          </button>
        </div>
      )}

      {open?.form === 'record' && (
        <RecordForm
          engagementId={engagementId}
          onRecorded={(ref) => {
            finished(`Recorded: ${ref} is carried forward.`)
          }}
          onClose={() => {
            setOpen(null)
          }}
        />
      )}

      {toRemove !== undefined && (
        <RemoveForm
          key={toRemove.ref}
          engagementId={engagementId}
          item={toRemove}
          onRemoved={(ref) => {
            finished(`Recorded: ${ref} is no longer carried forward.`)
          }}
          onClose={() => {
            setOpen(null)
          }}
        />
      )}

      <details className="mt-4 text-xs text-slate-600">
        <summary className="cursor-pointer text-slate-700 underline decoration-slate-300 underline-offset-2">
          How prior-period items are shown
        </summary>
        <p className="mt-1 max-w-4xl">{prior.basis}</p>
      </details>
    </Panel>
  )
}
