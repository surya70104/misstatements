// Record a misstatement (spec sections 3.1, 3.2 and 8). A misstatement is double-entry: a
// set of Dr/Cr lines against the Financial Spine's ledgers, never a single amount. It names
// the working paper it came from; a judgemental one carries the auditor's range and a
// projected one names its sample and projection basis.
//
// This form collects what a person declares and sends it. The backend requires at least two
// lines that balance, checks every ledger with the Spine, proposes the lines there, computes
// the effects and the band, and refuses anything else in its own words. Nothing is computed
// here, and the amounts go out as the exact text that was typed.
//
// A line names a ledger of the Spine's sealed import by its line number, or introduces a
// ledger the import lacks by name, groups and Schedule III head. The backend has no route
// that lists those ledgers or heads, so they are entered, not picked.
import { useState, type SyntheticEvent } from 'react'

import {
  getEngagement,
  raiseMisstatement,
  type LineInput,
  type MisstatementInput,
  type MisstatementType,
} from '../api'
import { Breadcrumb } from '../components/EngagementHeader'
import { Field, INPUT, LINK_BUTTON, PRIMARY, SECONDARY, isAmount } from '../components/forms'
import { Panel } from '../components/panels'
import { ErrorState, Loading } from '../components/states'
import { TYPES, TYPE_LABEL } from '../labels'
import { href, navigate } from '../router'
import { usePageTitle } from '../usePageTitle'
import { useResource } from '../useResource'
import { useSubmit } from '../useSubmit'

type LineDraft = {
  key: number
  ledger: 'import' | 'new'
  lineNo: string
  ledgerName: string
  parentChain: string
  headId: string
  side: 'dr' | 'cr'
  amount: string
}

function blank(key: number, side: 'dr' | 'cr'): LineDraft {
  return {
    key,
    ledger: 'import',
    lineNo: '',
    ledgerName: '',
    parentChain: '',
    headId: '',
    side,
    amount: '',
  }
}

function lineIsComplete(line: LineDraft): boolean {
  if (!isAmount(line.amount)) return false
  if (line.ledger === 'import') return /^\d+$/.test(line.lineNo.trim())
  return line.ledgerName.trim() !== '' && line.headId.trim() !== ''
}

/** The line as the backend takes it. The amount is sent as the text that was typed. */
function lineInput(line: LineDraft): LineInput {
  const amount = line.amount.trim()
  const side = line.side === 'dr' ? { dr: amount } : { cr: amount }
  if (line.ledger === 'import') return { line_no: Number.parseInt(line.lineNo.trim(), 10), ...side }
  return {
    ledger_name: line.ledgerName.trim(),
    parent_chain: line.parentChain
      .split('>')
      .map((group) => group.trim())
      .filter((group) => group !== ''),
    head_id: line.headId.trim(),
    ...side,
  }
}

function LineFields({
  line,
  index,
  disabled,
  removable,
  onChange,
  onRemove,
}: {
  line: LineDraft
  index: number
  disabled: boolean
  removable: boolean
  onChange: (line: LineDraft) => void
  onRemove: () => void
}) {
  const n = index + 1
  const id = `line-${String(line.key)}`
  return (
    <fieldset disabled={disabled} className="rounded border border-slate-200 px-4 py-3">
      <legend className="px-1 text-sm font-medium text-slate-800">Line {n}</legend>
      <div className="grid gap-3 sm:grid-cols-[9rem_minmax(0,1fr)_7rem_10rem]">
        <div>
          <label htmlFor={`${id}-ledger`} className="text-xs font-medium text-slate-600">
            Ledger
          </label>
          <select
            id={`${id}-ledger`}
            aria-label={`Line ${String(n)} ledger`}
            value={line.ledger}
            onChange={(event) => {
              onChange({ ...line, ledger: event.target.value === 'new' ? 'new' : 'import' })
            }}
            className={INPUT}
          >
            <option value="import">In the Spine’s import</option>
            <option value="new">Not in the import</option>
          </select>
        </div>

        {line.ledger === 'import' ? (
          <div>
            <label htmlFor={`${id}-no`} className="text-xs font-medium text-slate-600">
              Import line number
            </label>
            <input
              id={`${id}-no`}
              aria-label={`Line ${String(n)} import line number`}
              value={line.lineNo}
              inputMode="numeric"
              onChange={(event) => {
                onChange({ ...line, lineNo: event.target.value })
              }}
              className={`${INPUT} tabular-nums`}
            />
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label htmlFor={`${id}-name`} className="text-xs font-medium text-slate-600">
                Ledger name
              </label>
              <input
                id={`${id}-name`}
                aria-label={`Line ${String(n)} ledger name`}
                value={line.ledgerName}
                maxLength={200}
                onChange={(event) => {
                  onChange({ ...line, ledgerName: event.target.value })
                }}
                className={INPUT}
              />
            </div>
            <div>
              <label htmlFor={`${id}-chain`} className="text-xs font-medium text-slate-600">
                Groups, outermost first, separated by &gt;
              </label>
              <input
                id={`${id}-chain`}
                aria-label={`Line ${String(n)} groups`}
                value={line.parentChain}
                onChange={(event) => {
                  onChange({ ...line, parentChain: event.target.value })
                }}
                className={INPUT}
              />
            </div>
            <div>
              <label htmlFor={`${id}-head`} className="text-xs font-medium text-slate-600">
                Schedule III head
              </label>
              <input
                id={`${id}-head`}
                aria-label={`Line ${String(n)} Schedule III head`}
                value={line.headId}
                onChange={(event) => {
                  onChange({ ...line, headId: event.target.value })
                }}
                className={`${INPUT} font-mono`}
              />
            </div>
          </div>
        )}

        <div>
          <label htmlFor={`${id}-side`} className="text-xs font-medium text-slate-600">
            Side
          </label>
          <select
            id={`${id}-side`}
            aria-label={`Line ${String(n)} side`}
            value={line.side}
            onChange={(event) => {
              onChange({ ...line, side: event.target.value === 'cr' ? 'cr' : 'dr' })
            }}
            className={INPUT}
          >
            <option value="dr">Debit</option>
            <option value="cr">Credit</option>
          </select>
        </div>
        <div>
          <label htmlFor={`${id}-amount`} className="text-xs font-medium text-slate-600">
            Amount in rupees
          </label>
          <input
            id={`${id}-amount`}
            aria-label={`Line ${String(n)} amount`}
            value={line.amount}
            inputMode="decimal"
            onChange={(event) => {
              onChange({ ...line, amount: event.target.value })
            }}
            className={`${INPUT} tabular-nums`}
          />
        </div>
      </div>
      {removable && (
        <button type="button" onClick={onRemove} className={`${SECONDARY} mt-3`}>
          Remove line {n}
        </button>
      )}
    </fieldset>
  )
}

function RaiseForm({ engagementId }: { engagementId: string }) {
  const [type, setType] = useState<MisstatementType>('factual')
  const [description, setDescription] = useState('')
  const [raisedFrom, setRaisedFrom] = useState<'wp' | 'manual'>('wp')
  const [sourceRef, setSourceRef] = useState('')
  const [lines, setLines] = useState<LineDraft[]>([blank(1, 'dr'), blank(2, 'cr')])
  const [nextKey, setNextKey] = useState(3)
  const [rangeLow, setRangeLow] = useState('')
  const [rangeHigh, setRangeHigh] = useState('')
  const [sampleRef, setSampleRef] = useState('')
  const [projectionBasis, setProjectionBasis] = useState('')
  const { submitting, error, submit } = useSubmit()

  const typeComplete =
    type === 'factual' ||
    (type === 'judgemental' && isAmount(rangeLow) && isAmount(rangeHigh)) ||
    (type === 'projected' && sampleRef.trim() !== '' && projectionBasis.trim() !== '')
  const complete =
    description.trim() !== '' &&
    sourceRef.trim() !== '' &&
    lines.length >= 2 &&
    lines.every(lineIsComplete) &&
    typeComplete

  async function record(event: SyntheticEvent) {
    event.preventDefault()
    if (!complete) return
    const body: MisstatementInput = {
      type,
      description: description.trim(),
      raised_from: raisedFrom,
      source_ref: sourceRef.trim(),
      lines: lines.map(lineInput),
      ...(type === 'judgemental'
        ? { range_low: rangeLow.trim(), range_high: rangeHigh.trim() }
        : {}),
      ...(type === 'projected'
        ? { sample_ref: sampleRef.trim(), projection_basis: projectionBasis.trim() }
        : {}),
    }
    const sent = await submit(() => raiseMisstatement(engagementId, body))
    if (sent.ok) navigate({ name: 'misstatement', id: sent.value.id })
  }

  return (
    <form
      aria-label="Record a misstatement"
      onSubmit={(event) => {
        void record(event)
      }}
      className="space-y-5"
    >
      <Panel id="what" title="What was found">
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <Field id="raise-type" label="Type" required>
              <select
                id="raise-type"
                value={type}
                disabled={submitting}
                onChange={(event) => {
                  setType(event.target.value as MisstatementType)
                }}
                className={INPUT}
              >
                {TYPES.map((option) => (
                  <option key={option} value={option}>
                    {TYPE_LABEL[option]}
                  </option>
                ))}
              </select>
            </Field>
            <Field id="raise-from" label="Raised from" required>
              <select
                id="raise-from"
                value={raisedFrom}
                disabled={submitting}
                onChange={(event) => {
                  setRaisedFrom(event.target.value === 'manual' ? 'manual' : 'wp')
                }}
                className={INPUT}
              >
                <option value="wp">A working paper</option>
                <option value="manual">Manual entry</option>
              </select>
            </Field>
            <Field
              id="raise-ref"
              label="Working paper reference"
              required
              hint="Required for a manual entry too."
            >
              <input
                id="raise-ref"
                value={sourceRef}
                required
                maxLength={200}
                disabled={submitting}
                aria-describedby="raise-ref-hint"
                onChange={(event) => {
                  setSourceRef(event.target.value)
                }}
                className={INPUT}
              />
            </Field>
          </div>
          <Field id="raise-description" label="Description" required>
            <textarea
              id="raise-description"
              value={description}
              required
              rows={2}
              maxLength={2000}
              disabled={submitting}
              onChange={(event) => {
                setDescription(event.target.value)
              }}
              className={INPUT}
            />
          </Field>

          {type === 'judgemental' && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                id="raise-low"
                label="Auditor’s range: low"
                required
                hint="In rupees. The lines carry the point estimate."
              >
                <input
                  id="raise-low"
                  value={rangeLow}
                  inputMode="decimal"
                  disabled={submitting}
                  aria-describedby="raise-low-hint"
                  onChange={(event) => {
                    setRangeLow(event.target.value)
                  }}
                  className={`${INPUT} tabular-nums`}
                />
              </Field>
              <Field id="raise-high" label="Auditor’s range: high" required hint="In rupees.">
                <input
                  id="raise-high"
                  value={rangeHigh}
                  inputMode="decimal"
                  disabled={submitting}
                  aria-describedby="raise-high-hint"
                  onChange={(event) => {
                    setRangeHigh(event.target.value)
                  }}
                  className={`${INPUT} tabular-nums`}
                />
              </Field>
            </div>
          )}

          {type === 'projected' && (
            <div className="grid gap-4 sm:grid-cols-[14rem_minmax(0,1fr)]">
              <Field id="raise-sample" label="Sample" required hint="The sample it came from.">
                <input
                  id="raise-sample"
                  value={sampleRef}
                  maxLength={200}
                  disabled={submitting}
                  aria-describedby="raise-sample-hint"
                  onChange={(event) => {
                    setSampleRef(event.target.value)
                  }}
                  className={INPUT}
                />
              </Field>
              <Field id="raise-basis" label="Projection basis" required>
                <input
                  id="raise-basis"
                  value={projectionBasis}
                  maxLength={2000}
                  disabled={submitting}
                  onChange={(event) => {
                    setProjectionBasis(event.target.value)
                  }}
                  className={INPUT}
                />
              </Field>
            </div>
          )}
        </div>
      </Panel>

      <Panel id="entry" title="Dr/Cr lines">
        <p className="max-w-3xl text-sm text-slate-700">
          At least two lines, each a debit or a credit, and the debits must equal the credits. The
          backend checks the balance and each ledger with the Financial Spine.
        </p>
        <div className="mt-4 space-y-3">
          {lines.map((line, index) => (
            <LineFields
              key={line.key}
              line={line}
              index={index}
              disabled={submitting}
              removable={lines.length > 2}
              onChange={(changed) => {
                setLines(lines.map((entry) => (entry.key === changed.key ? changed : entry)))
              }}
              onRemove={() => {
                setLines(lines.filter((entry) => entry.key !== line.key))
              }}
            />
          ))}
        </div>
        <button
          type="button"
          disabled={submitting}
          onClick={() => {
            setLines([...lines, blank(nextKey, 'dr')])
            setNextKey(nextKey + 1)
          }}
          className={`${SECONDARY} mt-3`}
        >
          Add a line
        </button>
      </Panel>

      {error !== null && <ErrorState title="The misstatement was not recorded" error={error} />}

      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={submitting || !complete} className={PRIMARY}>
          {submitting ? 'Recording…' : 'Record misstatement'}
        </button>
        <a href={href({ name: 'schedule', id: engagementId })} className={LINK_BUTTON}>
          Cancel
        </a>
      </div>
    </form>
  )
}

export function RaiseMisstatementPage({ id }: { id: string }) {
  const { resource, reload } = useResource(() => getEngagement(id), `raise:${id}`)
  const label = resource.state === 'ready' ? resource.data.label : null
  usePageTitle(label === null ? 'Record a misstatement' : `Record a misstatement · ${label}`)

  return (
    <section aria-labelledby="raise-heading">
      <Breadcrumb id={id} label={label} here="Record a misstatement" />

      {resource.state === 'loading' && <Loading label="Loading the engagement…" />}
      {resource.state === 'error' && (
        <ErrorState
          title="This engagement could not be loaded"
          error={resource.error}
          onRetry={reload}
        />
      )}

      {resource.state === 'ready' && (
        <>
          <h1 id="raise-heading" className="text-xl font-semibold">
            Record a misstatement
          </h1>
          <p className="mt-1 text-sm text-slate-600">{resource.data.label}</p>
          {resource.data.spine.version_id === null && (
            <p className="mt-4 rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              No Financial Spine version is pinned to this engagement. The lines are proposed to the
              Spine, so set the link first on the{' '}
              <a href={href({ name: 'spine', id })} className="underline underline-offset-2">
                Financial Spine
              </a>{' '}
              screen.
            </p>
          )}
          <div className="mt-5">
            <RaiseForm key={id} engagementId={id} />
          </div>
        </>
      )}
    </section>
  )
}
