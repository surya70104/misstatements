// The qualitative checklist (spec sections 5 and 10.2; acceptance 8; backend D59). A
// misstatement below the thresholds can still be material by its nature, so each of seven
// factors can be recorded against it with a reason. While one is recorded the misstatement
// is escalated: the backend lists it individually and accumulates it whatever its amount.
//
// The factors, their wording, which of them are recorded and the explanation are all the
// backend's, read with the misstatement. This screen sends what a person confirms: a factor
// with its reason, a new reason, or the reason for clearing one. Every write is a new entry
// in the history; nothing is changed or removed. Which factors apply is a person's
// judgement: nothing here suggests one.
import { useRef, useState, type SyntheticEvent } from 'react'

import {
  clearQualitativeFactor,
  recordQualitativeFactor,
  type Misstatement,
  type QualitativeChecklist,
  type QualitativeEntry,
  type QualitativeRow,
} from '../../api'
import { dateTime } from '../../format'
import { NOTE_MAX_LENGTH } from '../../labels'
import { ErrorState, Pill } from '../states'
import { Panel, Unavailable } from '../panels'

type Kind = 'record' | 'change' | 'clear'

type Wording = {
  form: string
  explanation: string
  label: string
  confirm: string
  done: string
}

const WORDS: Record<Kind, Wording> = {
  record: {
    form: 'Record a qualitative factor',
    explanation:
      'Records this factor against the misstatement, with the reason. The misstatement is escalated from then on.',
    label: 'Reason this factor applies',
    confirm: 'Confirm: record factor',
    done: 'Factor recorded',
  },
  change: {
    form: 'Record a new reason for a qualitative factor',
    explanation:
      'Records this factor again with a new reason. The earlier reason stays in the history.',
    label: 'New reason this factor applies',
    confirm: 'Confirm: new reason',
    done: 'Reason changed',
  },
  clear: {
    form: 'Clear a qualitative factor',
    explanation:
      'Records that this factor no longer applies, with the reason. The earlier entries stay in the history.',
    label: 'Reason for clearing',
    confirm: 'Confirm: clear factor',
    done: 'Factor cleared',
  },
}

const BUTTON =
  'rounded border px-3 py-1.5 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700 disabled:cursor-default disabled:opacity-60'
const SECONDARY = `${BUTTON} border-slate-300 bg-white text-slate-800 hover:bg-slate-100 disabled:hover:bg-white aria-pressed:border-slate-800 aria-pressed:bg-slate-100`
const PRIMARY = `${BUTTON} border-slate-800 bg-slate-800 text-white hover:bg-slate-700 disabled:hover:bg-slate-800`

// The backend words a factor as the end of a sentence ("relates to a related party
// transaction"); it is shown as sent, with its first letter raised by the stylesheet only.
const FACTOR_TEXT = 'first-letter:uppercase'

type Chosen = { row: QualitativeRow; kind: Kind }
type Done = { kind: Kind; ref: string; text: string; escalated: boolean }

function Recorded({ done }: { done: Done }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="mb-3 rounded border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900"
    >
      <p className="font-medium">
        {WORDS[done.kind].done}: {done.ref} is{' '}
        {done.kind !== 'clear'
          ? 'escalated'
          : done.escalated
            ? 'still escalated on another factor'
            : 'no longer escalated'}
        .
      </p>
      <p className={`mt-1 ${FACTOR_TEXT}`}>{done.text}</p>
    </div>
  )
}

function Row({
  row,
  chosen,
  disabled,
  onChoose,
}: {
  row: QualitativeRow
  chosen: Chosen | null
  disabled: boolean
  onChoose: (kind: Kind) => void
}) {
  const pressed = (kind: Kind) => chosen?.row.factor === row.factor && chosen.kind === kind
  // Each button is described by its factor's wording, so "Record" is never read out alone.
  const describedBy = `qualitative-factor-${row.factor}`
  function action(kind: Kind, text: string) {
    return (
      <button
        type="button"
        aria-describedby={describedBy}
        aria-pressed={pressed(kind)}
        disabled={disabled}
        onClick={() => {
          onChoose(kind)
        }}
        className={SECONDARY}
      >
        {text}
      </button>
    )
  }
  return (
    <li className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2 border-t border-slate-200 py-3 first:border-t-0 first:pt-0">
      <div className="min-w-0 flex-1 basis-64">
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-900">
          <span id={describedBy} className={FACTOR_TEXT}>
            {row.text}
          </span>
          {row.applies ? (
            <Pill tone="attention">Recorded</Pill>
          ) : (
            <span className="text-xs text-slate-500">Not recorded</span>
          )}
        </p>
        {row.applies && (
          <>
            <p className="mt-1 text-sm break-words text-slate-800">
              <span className="text-slate-500">Reason: </span>
              {row.note}
            </p>
            <p className="mt-0.5 text-xs text-slate-600">
              by {row.escalated_by}
              {row.at !== null && (
                <>
                  {', '}
                  <time dateTime={row.at}>{dateTime(row.at)}</time>
                </>
              )}
            </p>
          </>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        {row.applies ? (
          <>
            {action('change', 'New reason')}
            {action('clear', 'Clear')}
          </>
        ) : (
          action('record', 'Record')
        )}
      </div>
    </li>
  )
}

function History({ entries, rows }: { entries: QualitativeEntry[]; rows: QualitativeRow[] }) {
  if (entries.length === 0) return null
  // A factor is named in the backend's words; one it no longer lists is shown by its code.
  const text = (factor: string) => rows.find((row) => row.factor === factor)?.text ?? factor
  return (
    <div className="mt-5 border-t border-slate-200 pt-4">
      <h3 id="qualitative-history-heading" className="text-sm font-semibold text-slate-900">
        History of the checklist
      </h3>
      <p className="mt-0.5 text-xs text-slate-600">
        Every entry, oldest first. An entry is never changed or removed.
      </p>
      <ol aria-labelledby="qualitative-history-heading" className="mt-3 ml-1">
        {entries.map((entry) => (
          <li
            key={entry.entry_no}
            className="relative border-l-2 border-slate-200 pb-4 pl-5 last:pb-0"
          >
            <span
              aria-hidden="true"
              className="absolute top-1.5 -left-[5px] h-2 w-2 rounded-full bg-slate-400"
            />
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
              <Pill tone={entry.applies ? 'attention' : 'neutral'}>
                {entry.applies ? 'Recorded' : 'Cleared'}
              </Pill>
              <span className="text-slate-800">by {entry.escalated_by}</span>
              {entry.at !== null && (
                <time dateTime={entry.at} className="text-slate-600">
                  {dateTime(entry.at)}
                </time>
              )}
              <span className="text-xs text-slate-500">entry {entry.entry_no}</span>
            </p>
            <p className={`mt-1 text-sm text-slate-800 ${FACTOR_TEXT}`}>{text(entry.factor)}</p>
            <p className="mt-0.5 text-sm break-words text-slate-800">
              <span className="text-slate-500">
                {entry.applies ? 'Reason: ' : 'Reason for clearing: '}
              </span>
              {entry.note}
            </p>
          </li>
        ))}
      </ol>
    </div>
  )
}

export function QualitativeFactors({
  misstatement,
  onChanged,
}: {
  misstatement: Misstatement
  onChanged: (checklist: QualitativeChecklist) => void
}) {
  const [chosen, setChosen] = useState<Chosen | null>(null)
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [done, setDone] = useState<Done | null>(null)
  // A second click can arrive before the first has re-rendered the button as disabled;
  // this guard is what makes a write go out exactly once.
  const inFlight = useRef(false)

  const { escalated, checklist, history, escalation_basis: basis } = misstatement.qualitative
  const words = chosen === null ? null : WORDS[chosen.kind]
  const noteMissing = note.trim() === ''

  function choose(row: QualitativeRow, kind: Kind) {
    setChosen({ row, kind })
    setNote('')
    setError(null)
    setDone(null)
  }

  function cancel() {
    if (inFlight.current) return
    setChosen(null)
    setNote('')
    setError(null)
  }

  async function submit(event: SyntheticEvent) {
    event.preventDefault()
    if (chosen === null || noteMissing || inFlight.current) return
    inFlight.current = true
    setSubmitting(true)
    setError(null)
    const { row, kind } = chosen
    try {
      const answer =
        kind === 'clear'
          ? await clearQualitativeFactor(misstatement.id, row.factor, { note: note.trim() })
          : await recordQualitativeFactor(misstatement.id, {
              factor: row.factor,
              note: note.trim(),
            })
      setDone({ kind, ref: answer.ref, text: row.text, escalated: answer.escalated })
      setChosen(null)
      setNote('')
      onChanged(answer)
    } catch (caught) {
      // Nothing was recorded. The form stays as it was so nothing has to be retyped.
      setError(caught instanceof Error ? caught : new Error(String(caught)))
    } finally {
      inFlight.current = false
      setSubmitting(false)
    }
  }

  if (checklist === undefined) {
    return (
      <Panel id="qualitative" title="Qualitative factors">
        <Unavailable
          what="The qualitative checklist was not sent with this misstatement."
          why={null}
        />
      </Panel>
    )
  }

  return (
    <Panel id="qualitative" title="Qualitative factors">
      {done !== null && <Recorded done={done} />}

      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-700">
        {escalated ? (
          <Pill tone="attention">Escalated</Pill>
        ) : (
          <Pill tone="neutral">Not escalated</Pill>
        )}
        <span>
          {escalated
            ? 'A qualitative factor is recorded, so this misstatement is listed individually whatever its amount.'
            : 'No qualitative factor is recorded against this misstatement.'}
        </span>
      </p>
      <p className="mt-2 max-w-3xl text-sm text-slate-700">
        A misstatement below the thresholds can still be material by its nature. Record each factor
        that applies, with the reason. Which factors apply is your judgement: none is detected.
      </p>

      <ul aria-label="Qualitative checklist" className="mt-4">
        {checklist.map((row) => (
          <Row
            key={row.factor}
            row={row}
            chosen={chosen}
            disabled={submitting}
            onChoose={(kind) => {
              choose(row, kind)
            }}
          />
        ))}
      </ul>

      {chosen !== null && words !== null && (
        <form
          aria-label={words.form}
          onSubmit={(event) => {
            void submit(event)
          }}
          className="mt-4 rounded border border-slate-300 bg-slate-50 px-4 py-4"
        >
          <p className={`text-sm font-medium text-slate-900 ${FACTOR_TEXT}`}>{chosen.row.text}</p>
          <p className="mt-1 text-sm text-slate-800">{words.explanation}</p>
          {chosen.kind !== 'record' && chosen.row.note !== null && (
            <p className="mt-2 text-sm break-words text-slate-800">
              <span className="text-slate-500">Reason recorded now: </span>
              {chosen.row.note}
            </p>
          )}

          <div className="mt-3">
            <label htmlFor="qualitative-note" className="text-sm font-medium text-slate-800">
              {words.label} <span className="font-normal text-slate-600">(required)</span>
            </label>
            <textarea
              id="qualitative-note"
              value={note}
              required
              rows={3}
              maxLength={NOTE_MAX_LENGTH}
              disabled={submitting}
              aria-describedby="qualitative-note-help"
              onChange={(event) => {
                setNote(event.target.value)
              }}
              className="mt-1 block w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700 disabled:bg-slate-100"
            />
            <p id="qualitative-note-help" className="mt-1 text-xs text-slate-600">
              The reason is recorded with the misstatement and kept in the history. Up to{' '}
              {NOTE_MAX_LENGTH} characters.
            </p>
          </div>

          {error !== null && (
            <div className="mt-3">
              <ErrorState title="Nothing was recorded" error={error} />
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            <button type="submit" disabled={submitting || noteMissing} className={PRIMARY}>
              {submitting ? 'Recording…' : words.confirm}
            </button>
            <button type="button" disabled={submitting} onClick={cancel} className={SECONDARY}>
              Cancel
            </button>
          </div>
        </form>
      )}

      <History entries={history ?? []} rows={checklist} />

      {basis !== undefined && (
        <details className="mt-4 text-xs text-slate-600">
          <summary className="cursor-pointer text-slate-700 underline decoration-slate-300 underline-offset-2">
            How escalation works
          </summary>
          <p className="mt-1 max-w-3xl">{basis}</p>
        </details>
      )}
    </Panel>
  )
}
