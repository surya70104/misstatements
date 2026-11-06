// The two writes the specification reserves to the engagement partner: the acknowledgement
// of the soft gate (section 7) and the conclusion (section 6.4; "the words are the
// partner's", section 12).
//
// Who the partner is, is not decided here. The backend accepts either write only when the
// trusted proxy's role claim names the acting identity a partner, and refuses everyone else
// with a 403 that is shown as it was sent. Where the backend reports that no role claim is
// configured at all, neither form is offered: it could only ever be refused. The gates are
// in the backend's write path too, so a conclusion the gates block is refused there, and
// the option is not offered here once the backend has said it would refuse it.
import { useState, type ReactNode, type SyntheticEvent } from 'react'

import {
  acknowledgeSoftGate,
  recordConclusion,
  type Authorisation,
  type Determination,
  type Evaluation,
} from '../../api'
import { rupees } from '../../format'
import { useSubmit } from '../../useSubmit'
import { Field, INPUT, PRIMARY, Recorded } from '../forms'
import { Basis } from '../panels'
import { ErrorState, Pill } from '../states'

/** The backend's limit on a note, a conclusion and a basis, mirrored on the fields. */
const TEXT_MAX_LENGTH = 2000

/**
 * An action the backend reserves to the engagement partner. Its form is shown only where
 * the backend says a partner can be named; otherwise the backend's reason is shown.
 */
export function PartnerOnly({
  what,
  authorisation,
  children,
}: {
  what: string
  authorisation: Authorisation
  children?: ReactNode
}) {
  const partner = authorisation.partner_actions
  return (
    <div className="rounded border border-slate-200 bg-slate-50 px-3 py-3 text-sm">
      <p className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{what}</span>
        {partner.available ? <Pill>Partner only</Pill> : <Pill tone="attention">Unavailable</Pill>}
      </p>
      <Basis>{partner.detail}</Basis>
      {partner.available && children}
    </div>
  )
}

export function AcknowledgementForm({
  engagementId,
  onRecorded,
}: {
  engagementId: string
  onRecorded: () => void
}) {
  const [note, setNote] = useState('')
  const [done, setDone] = useState(false)
  const { submitting, error, submit } = useSubmit()

  async function acknowledge(event: SyntheticEvent) {
    event.preventDefault()
    setDone(false)
    const sent = await submit(() =>
      acknowledgeSoftGate(engagementId, note.trim() === '' ? null : note.trim()),
    )
    if (!sent.ok) return
    setDone(true)
    setNote('')
    onRecorded()
  }

  return (
    <form
      aria-label="Acknowledge the soft gate"
      onSubmit={(event) => {
        void acknowledge(event)
      }}
      className="mt-3 space-y-3"
    >
      <p className="text-slate-800">
        The acknowledgement is recorded against the current figures and threshold version. It stands
        until either changes.
      </p>
      <Field id="acknowledgement-note" label="Note">
        <textarea
          id="acknowledgement-note"
          value={note}
          rows={2}
          maxLength={TEXT_MAX_LENGTH}
          disabled={submitting}
          onChange={(event) => {
            setNote(event.target.value)
          }}
          className={INPUT}
        />
      </Field>
      {error !== null && <ErrorState title="The acknowledgement was not recorded" error={error} />}
      {done && <Recorded>Recorded: the acknowledgement of the soft gate.</Recorded>}
      <button type="submit" disabled={submitting} className={PRIMARY}>
        {submitting ? 'Recording…' : 'Acknowledge the soft gate'}
      </button>
    </form>
  )
}

const KINDS: { value: Determination; label: string }[] = [
  { value: 'not_material', label: 'The uncorrected misstatements are not material' },
  { value: 'material', label: 'The uncorrected misstatements are material' },
]

export function ConclusionForm({
  engagementId,
  evaluation,
  onRecorded,
}: {
  engagementId: string
  evaluation: Evaluation
  onRecorded: () => void
}) {
  const [determination, setDetermination] = useState<Determination | null>(null)
  const [conclusion, setConclusion] = useState('')
  const [basis, setBasis] = useState('')
  const [reassessed, setReassessed] = useState(false)
  const [recorded, setRecorded] = useState<number | null>(null)
  const { submitting, error, submit } = useSubmit()

  const { allowed } = evaluation.conclusion
  const latest = evaluation.latest_run
  // The backend takes the run the partner reviewed and refuses one that is no longer
  // current. The latest run is the only one that can be, and the backend says whether it is.
  const reviewed = latest.status === 'current' ? latest.run : null
  const complete =
    determination !== null &&
    conclusion.trim() !== '' &&
    basis.trim() !== '' &&
    reassessed &&
    reviewed !== null

  async function conclude(event: SyntheticEvent) {
    event.preventDefault()
    if (!complete) return
    setRecorded(null)
    const sent = await submit(() =>
      recordConclusion(engagementId, determination, {
        conclusion: conclusion.trim(),
        basis: basis.trim(),
        reviewed_run_id: reviewed.id,
      }),
    )
    if (!sent.ok) return
    setRecorded(sent.value.run_no)
    setDetermination(null)
    setConclusion('')
    setBasis('')
    setReassessed(false)
    onRecorded()
  }

  return (
    <form
      aria-label="Record a conclusion"
      onSubmit={(event) => {
        void conclude(event)
      }}
      className="mt-3 space-y-4"
    >
      <p className="text-slate-800">
        {reviewed === null
          ? 'A conclusion names the evaluation run that was reviewed, and that run must still describe the evaluation. Record a run first.'
          : `Run reviewed: run ${String(reviewed.run_no)}, which describes the evaluation as it stands. The figures of the evaluation are saved with the conclusion by the backend; they are not entered.`}
      </p>
      {/* Spec section 6.4: "with the figures auto-inserted". They are the reviewed run's,
          which the backend has just said still describes the evaluation. */}
      {reviewed !== null && (
        <p className="text-slate-800 tabular-nums">
          Figures saved with it: profit before tax {rupees(reviewed.agg_gross_pbt)} gross and{' '}
          {rupees(reviewed.agg_net_pbt)} net; net assets {rupees(reviewed.agg_gross_na)} gross and{' '}
          {rupees(reviewed.agg_net_na)} net
          {reviewed.threshold_version_no !== null &&
            `; thresholds version ${String(reviewed.threshold_version_no)}`}
          .
        </p>
      )}

      <fieldset disabled={submitting}>
        <legend className="font-medium text-slate-900">Conclusion</legend>
        <div className="mt-2 space-y-2">
          {KINDS.map((kind) => (
            <label key={kind.value} className="flex items-start gap-2">
              <input
                type="radio"
                name="determination"
                className="mt-1"
                checked={determination === kind.value}
                disabled={!allowed[kind.value].allowed}
                onChange={() => {
                  setDetermination(kind.value)
                }}
              />
              <span>
                {kind.label}
                {!allowed[kind.value].allowed && (
                  <span className="block text-xs text-slate-600">
                    Blocked by the backend for the reasons given above.
                  </span>
                )}
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <Field
        id="conclusion-words"
        label="Conclusion, in the partner’s words"
        required
        hint="Whether the uncorrected misstatements are material individually or in aggregate."
      >
        <textarea
          id="conclusion-words"
          value={conclusion}
          required
          rows={3}
          maxLength={TEXT_MAX_LENGTH}
          disabled={submitting}
          aria-describedby="conclusion-words-hint"
          onChange={(event) => {
            setConclusion(event.target.value)
          }}
          className={INPUT}
        />
      </Field>
      <Field id="conclusion-basis" label="Basis" required>
        <textarea
          id="conclusion-basis"
          value={basis}
          required
          rows={3}
          maxLength={TEXT_MAX_LENGTH}
          disabled={submitting}
          onChange={(event) => {
            setBasis(event.target.value)
          }}
          className={INPUT}
        />
      </Field>
      <label className="flex items-start gap-2 text-slate-900">
        <input
          type="checkbox"
          checked={reassessed}
          disabled={submitting}
          onChange={(event) => {
            setReassessed(event.target.checked)
          }}
          className="mt-0.5 h-4 w-4"
        />
        <span>Materiality was reassessed before this evaluation (SA 450 paragraph 10).</span>
      </label>

      {error !== null && <ErrorState title="The conclusion was not recorded" error={error} />}
      {recorded !== null && <Recorded>Recorded: the conclusion, as run {recorded}.</Recorded>}

      <button type="submit" disabled={submitting || !complete} className={PRIMARY}>
        {submitting ? 'Recording…' : 'Record the conclusion'}
      </button>
    </form>
  )
}
