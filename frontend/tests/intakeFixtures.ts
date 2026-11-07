// The intake hooks' fixtures, typed (spec section 8; backend D64). Every one is the backend's
// real answer, produced and kept honest by backend/tests/test_frontend_fixtures.py: one
// misstatement from each source, the schedule that shows them, and each refusal.
import type { Engagement, Evaluation, Misstatement } from '../src/api'
import detailRunJson from './fixtures/intake-detail-run.json'
import engagementJson from './fixtures/intake-engagement.json'
import evaluationJson from './fixtures/intake-evaluation.json'
import generalNoteJson from './fixtures/intake-general-note.json'
import generalRunWithoutDetailsJson from './fixtures/intake-general-run-without-details.json'
import manualJson from './fixtures/intake-manual.json'
import misstatementsJson from './fixtures/intake-misstatements.json'
import noteJson from './fixtures/intake-note.json'
import runJson from './fixtures/intake-run.json'
import wpJson from './fixtures/intake-wp.json'

// The backend's answer to each hook: the misstatement as raised, with every version.
export const fromWorkingPaper = wpJson as Misstatement
export const fromRun = runJson as Misstatement
export const fromNote = noteJson as Misstatement
export const fromManual = manualJson as Misstatement
// ... and to the general endpoint with the source named.
export const fromNoteGeneral = generalNoteJson as Misstatement
// The run's misstatement read on its own.
export const detailRun = detailRunJson as Misstatement

// The engagement's schedule with one misstatement from each source.
export const engagement = engagementJson as Engagement
export const misstatements = misstatementsJson as Misstatement[]
export const evaluation = evaluationJson as Evaluation

// The backend's refusal of a run sent to the general endpoint without its details.
export const refusals = {
  runWithoutDetails: { status: 422, body: generalRunWithoutDetailsJson },
}
