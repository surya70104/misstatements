// The strategy trigger (spec section 7; SA 450 paragraph 6): when the aggregate approaches
// materiality, a prompt to revisit the audit strategy and plan, "recorded either way". It
// blocks nothing. Whether it fires, and whether it has been answered on the current
// figures, are the backend's. This screen offers the answer only when the backend says one
// is needed, and sends what the specification names: whether the strategy and plan were
// revised, with a note if the person wants one recorded.
import { useState, type SyntheticEvent } from 'react'

import { respondToStrategyPrompt, type Evaluation, type StrategyResponse } from '../../api'
import { rupees } from '../../format'
import { gateStatus, measureLabel, responseStatus } from '../../labels'
import { useSubmit } from '../../useSubmit'
import { Basis, Panel } from '../panels'
import { ErrorState, Pill } from '../states'

/** The backend's limit on the note, mirrored so a person sees it before sending. */
const NOTE_MAX_LENGTH = 2000

const PRIMARY =
  'rounded border border-slate-800 bg-slate-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700 disabled:cursor-default disabled:opacity-60 disabled:hover:bg-slate-800'

export function StrategyPanel({
  engagementId,
  evaluation,
  onAnswered,
}: {
  engagementId: string
  evaluation: Evaluation
  onAnswered: () => void
}) {
  const trigger = evaluation.gates.strategy_trigger
  const response = trigger.response
  const status = gateStatus(trigger.status)
  const [revised, setRevised] = useState<boolean | null>(null)
  const [note, setNote] = useState('')
  const [answered, setAnswered] = useState(false)
  const { submitting, error, submit } = useSubmit()

  // The backend asks for an answer when none stands on the current figures.
  const wanted =
    response !== null && (response.status === 'required' || response.status === 'stale')

  async function answer(event: SyntheticEvent) {
    event.preventDefault()
    if (revised === null) return
    const body: StrategyResponse =
      note.trim() === ''
        ? { strategy_revised: revised }
        : { strategy_revised: revised, note: note.trim() }
    setAnswered(false)
    const sent = await submit(() => respondToStrategyPrompt(engagementId, body))
    if (!sent.ok) return
    setAnswered(true)
    setRevised(null)
    setNote('')
    onAnswered()
  }

  return (
    <Panel id="strategy" title="Audit strategy prompt">
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <span>Strategy trigger:</span>
        <Pill tone={status.tone}>{status.text}</Pill>
      </p>
      <Basis>{trigger.detail}</Basis>

      {trigger.line != null && (
        <p className="mt-3 text-sm text-slate-800">
          Line: <span className="tabular-nums">{rupees(trigger.line)}</span>
          {trigger.fraction != null &&
            `, the declared fraction ${trigger.fraction} of overall materiality`}
          .
          {trigger.fires_on !== undefined && trigger.fires_on.length > 0 && (
            <> At or above it on: {trigger.fires_on.map(measureLabel).join('; ')}.</>
          )}
        </p>
      )}

      {response !== null && trigger.status === 'fires' && (
        <p className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <span>Answer:</span>
          <Pill tone={responseStatus(response.status).tone}>
            {responseStatus(response.status).text}
          </Pill>
          <span className="text-slate-700">{response.detail}</span>
        </p>
      )}

      {answered && (
        <p
          role="status"
          aria-live="polite"
          className="mt-3 rounded border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-900"
        >
          Recorded: the answer to the strategy prompt.
        </p>
      )}

      {wanted && (
        <form
          aria-label="Answer the strategy prompt"
          onSubmit={(event) => {
            void answer(event)
          }}
          className="mt-4 rounded border border-slate-300 bg-slate-50 px-4 py-4"
        >
          <fieldset disabled={submitting}>
            <legend className="text-sm font-medium text-slate-900">
              After revisiting them, were the audit strategy and plan revised?
            </legend>
            <div className="mt-2 flex flex-wrap gap-x-6 gap-y-2 text-sm">
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="strategy-revised"
                  checked={revised === true}
                  onChange={() => {
                    setRevised(true)
                  }}
                />
                Yes, they were revised
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="strategy-revised"
                  checked={revised === false}
                  onChange={() => {
                    setRevised(false)
                  }}
                />
                No, they were not revised
              </label>
            </div>
          </fieldset>

          <div className="mt-3">
            <label htmlFor="strategy-note" className="text-sm font-medium text-slate-800">
              Note <span className="font-normal text-slate-600">(optional)</span>
            </label>
            <textarea
              id="strategy-note"
              value={note}
              rows={2}
              maxLength={NOTE_MAX_LENGTH}
              disabled={submitting}
              onChange={(event) => {
                setNote(event.target.value)
              }}
              className="mt-1 block w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700 disabled:bg-slate-100"
            />
          </div>

          {error !== null && (
            <div className="mt-3">
              <ErrorState title="The answer was not recorded" error={error} />
            </div>
          )}

          <div className="mt-4">
            <button type="submit" disabled={submitting || revised === null} className={PRIMARY}>
              {submitting ? 'Recording…' : 'Record the answer'}
            </button>
          </div>
        </form>
      )}
    </Panel>
  )
}
