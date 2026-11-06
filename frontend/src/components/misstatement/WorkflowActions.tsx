// The moves a misstatement can make (spec section 3.3):
//   raised -> communicated -> corrected | refused | withdrawn
// This screen offers the moves the specification draws from the current state and sends the
// one a person confirms. The backend decides whether it is allowed, records it as a new
// version and tells the Financial Spine; a refusal is shown in the backend's words. Nothing
// about an existing version can be edited: the record is append-only.
import { useRef, useState, type SyntheticEvent } from 'react'

import {
  transitionMisstatement,
  type Misstatement,
  type TransitionOutcome,
  type TransitionRequest,
  type TransitionTarget,
} from '../../api'
import { NEXT_STATES, REASON_MAX_LENGTH, REASON_REQUIRED, STATE_LABEL } from '../../labels'
import { ErrorState } from '../states'
import { Panel } from '../panels'

type Action = {
  button: string
  confirm: string
  explanation: string
  reasonLabel?: string
}

const ACTIONS: Record<TransitionTarget, Action> = {
  communicated: {
    button: 'Mark as communicated',
    confirm: 'Confirm: communicated',
    explanation:
      'Records that this misstatement has been communicated to management. Nothing is sent to the Financial Spine.',
  },
  corrected: {
    button: 'Record correction',
    confirm: 'Confirm: corrected',
    explanation:
      'Records that management has corrected this misstatement. Its adjustment is accepted in the Financial Spine and posts there.',
  },
  refused: {
    button: 'Record refusal',
    confirm: 'Confirm: refused',
    explanation:
      'Records that management refuses to correct this misstatement. It stays in the uncorrected schedule; its adjustment is refused in the Financial Spine and does not post.',
    reasonLabel: 'Reason for refusal',
  },
  withdrawn: {
    button: 'Withdraw',
    confirm: 'Confirm: withdrawn',
    explanation:
      'Withdraws this misstatement. It is kept, excluded from the totals, with the reason; its adjustment is refused in the Financial Spine and does not post.',
    reasonLabel: 'Reason for withdrawal',
  },
}

const BUTTON =
  'rounded border px-3 py-1.5 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700 disabled:cursor-default disabled:opacity-60'
const SECONDARY = `${BUTTON} border-slate-300 bg-white text-slate-800 hover:bg-slate-100 disabled:hover:bg-white`
const PRIMARY = `${BUTTON} border-slate-800 bg-slate-800 text-white hover:bg-slate-700 disabled:hover:bg-slate-800`

type Done = { ref: string; to: TransitionTarget; outcome: TransitionOutcome | undefined }

function Recorded({ done }: { done: Done }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="rounded border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900"
    >
      <p className="font-medium">
        Recorded: {done.ref} is now {STATE_LABEL[done.to].toLowerCase()}.
      </p>
      {done.outcome?.spine_decision != null && (
        <p className="mt-1">
          Financial Spine: adjustment{' '}
          {done.outcome.adjustment_status ?? done.outcome.spine_decision}
          {done.outcome.decided_now ? '' : ' (it had already been decided this way)'}.
          {done.outcome.note !== null && ` ${done.outcome.note}`}
        </p>
      )}
    </div>
  )
}

export function WorkflowActions({
  misstatement,
  onMoved,
}: {
  misstatement: Misstatement
  onMoved: (updated: Misstatement) => void
}) {
  const [chosen, setChosen] = useState<TransitionTarget | null>(null)
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [done, setDone] = useState<Done | null>(null)
  // A second click can arrive before the first one has re-rendered the button as disabled;
  // this guard is what makes a move go out exactly once.
  const inFlight = useRef(false)

  const state = misstatement.current.state
  const available = NEXT_STATES[state]
  const action = chosen === null ? null : ACTIONS[chosen]
  const needsReason = chosen !== null && REASON_REQUIRED.includes(chosen)
  const reasonMissing = needsReason && reason.trim() === ''

  function choose(target: TransitionTarget) {
    setChosen(target)
    setReason('')
    setError(null)
    setDone(null)
  }

  function cancel() {
    if (inFlight.current) return
    setChosen(null)
    setReason('')
    setError(null)
  }

  async function submit(event: SyntheticEvent) {
    event.preventDefault()
    if (chosen === null || reasonMissing || inFlight.current) return
    inFlight.current = true
    setSubmitting(true)
    setError(null)
    const body: TransitionRequest = needsReason
      ? { to: chosen, reason: reason.trim() }
      : { to: chosen }
    try {
      const updated = await transitionMisstatement(misstatement.id, body)
      setDone({ ref: updated.ref, to: chosen, outcome: updated.transition })
      setChosen(null)
      setReason('')
      onMoved(updated)
    } catch (caught) {
      // The move was not recorded. The form stays as it was so nothing has to be retyped.
      setError(caught instanceof Error ? caught : new Error(String(caught)))
    } finally {
      inFlight.current = false
      setSubmitting(false)
    }
  }

  return (
    <Panel id="actions" title="Workflow actions">
      {done !== null && <Recorded done={done} />}

      {available.length === 0 ? (
        <p className={`text-sm text-slate-700 ${done !== null ? 'mt-3' : ''}`}>
          This misstatement is {STATE_LABEL[state].toLowerCase()}, a final state. No further action
          is available, and the record cannot be edited.
        </p>
      ) : (
        <>
          <p className={`text-sm text-slate-700 ${done !== null ? 'mt-3' : ''}`}>
            This misstatement is {STATE_LABEL[state].toLowerCase()}. Each move adds a version to the
            history and cannot be undone.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {available.map((target) => (
              <button
                key={target}
                type="button"
                aria-pressed={chosen === target}
                disabled={submitting}
                onClick={() => {
                  choose(target)
                }}
                className={`${SECONDARY} aria-pressed:border-slate-800 aria-pressed:bg-slate-100`}
              >
                {ACTIONS[target].button}
              </button>
            ))}
          </div>
        </>
      )}

      {chosen !== null && action !== null && (
        <form
          aria-label={action.button}
          onSubmit={(event) => {
            void submit(event)
          }}
          className="mt-4 rounded border border-slate-300 bg-slate-50 px-4 py-4"
        >
          <p className="text-sm text-slate-800">{action.explanation}</p>

          {action.reasonLabel !== undefined && (
            <div className="mt-3">
              <label htmlFor="transition-reason" className="text-sm font-medium text-slate-800">
                {action.reasonLabel} <span className="font-normal text-slate-600">(required)</span>
              </label>
              <textarea
                id="transition-reason"
                value={reason}
                required
                rows={3}
                maxLength={REASON_MAX_LENGTH}
                disabled={submitting}
                aria-describedby="transition-reason-help"
                onChange={(event) => {
                  setReason(event.target.value)
                }}
                className="mt-1 block w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700 disabled:bg-slate-100"
              />
              <p id="transition-reason-help" className="mt-1 text-xs text-slate-600">
                The reason is recorded with the misstatement and sent to the Financial Spine. Up to{' '}
                {REASON_MAX_LENGTH} characters.
              </p>
            </div>
          )}

          {error !== null && (
            <div className="mt-3">
              <ErrorState title="The move was not recorded" error={error} />
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            <button type="submit" disabled={submitting || reasonMissing} className={PRIMARY}>
              {submitting ? 'Recording…' : action.confirm}
            </button>
            <button type="button" disabled={submitting} onClick={cancel} className={SECONDARY}>
              Cancel
            </button>
          </div>
        </form>
      )}
    </Panel>
  )
}
