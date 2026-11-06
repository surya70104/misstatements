// The qualitative checklist's fixtures, typed (spec section 5; backend D59). Every one is
// the backend's real answer, produced and kept honest by
// backend/tests/test_frontend_fixtures.py: one engagement with an ordinary item (M-1) and a
// clearly trivial one (M-2); M-2 is escalated on a related party, the reason is changed,
// and the factor is cleared again, with each refusal met on the way.
import type { Engagement, Evaluation, Misstatement, QualitativeChecklist } from '../src/api'
import type { Snapshot } from './evaluationFixtures'
import alreadyRecordedJson from './fixtures/qualitative-already-recorded.json'
import blankNoteJson from './fixtures/qualitative-blank-note.json'
import clearedJson from './fixtures/qualitative-cleared.json'
import detailClearJson from './fixtures/qualitative-detail-clear.json'
import detailClearedJson from './fixtures/qualitative-detail-cleared.json'
import detailEscalatedJson from './fixtures/qualitative-detail-escalated.json'
import detailReasonChangedJson from './fixtures/qualitative-detail-reason-changed.json'
import engagementJson from './fixtures/qualitative-engagement.json'
import evaluationScreenJson from './fixtures/qualitative-evaluation-screen.json'
import evaluationJson from './fixtures/qualitative-evaluation.json'
import misstatementsJson from './fixtures/qualitative-misstatements.json'
import notRecordedJson from './fixtures/qualitative-not-recorded.json'
import reasonChangedJson from './fixtures/qualitative-reason-changed.json'
import recordedJson from './fixtures/qualitative-recorded.json'

// M-2 read on its own: before any factor, escalated, after the reason was changed, and
// after the factor was cleared.
export const detailClear = detailClearJson as Misstatement
export const detailEscalated = detailEscalatedJson as Misstatement
export const detailReasonChanged = detailReasonChangedJson as Misstatement
export const detailCleared = detailClearedJson as Misstatement

// The backend's answer to each write: the checklist as it then stood.
export const recorded = recordedJson as QualitativeChecklist
export const reasonChanged = reasonChangedJson as QualitativeChecklist
export const cleared = clearedJson as QualitativeChecklist

// The backend's refusals, with the status each was sent with.
export const refusals = {
  alreadyRecorded: { status: 409, body: alreadyRecordedJson },
  notRecorded: { status: 409, body: notRecordedJson },
  blankNote: { status: 422, body: blankNoteJson },
}

// The engagement while M-2 was escalated: as the schedule and as the evaluation screen read it.
export const engagement = engagementJson as Engagement
export const misstatements = misstatementsJson as Misstatement[]
export const evaluation = evaluationJson as Evaluation
export const evaluationScreen = evaluationScreenJson as unknown as Snapshot

/** Recording a factor, or recording it again with a new reason. */
export function recordPath(misstatement: Misstatement): string {
  return `POST /api/misstatements/${misstatement.id}/qualitative`
}

export function clearPath(misstatement: Misstatement, factor: string): string {
  return `POST /api/misstatements/${misstatement.id}/qualitative/${factor}/clear`
}
