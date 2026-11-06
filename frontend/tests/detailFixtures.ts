// The misstatement detail's fixtures, typed. Every one is the backend's real answer,
// produced and kept honest by backend/tests/test_frontend_fixtures.py: one misstatement read
// in each state, the answer to each move, and each refusal a person can meet.
import type { Engagement, Evaluation, Misstatement } from '../src/api'
import classificationDriftJson from './fixtures/detail-classification-drift.json'
import classificationOnlyJson from './fixtures/detail-classification-only.json'
import communicatedJudgementalJson from './fixtures/detail-communicated-judgemental.json'
import communicatedProjectedJson from './fixtures/detail-communicated-projected.json'
import communicatedJson from './fixtures/detail-communicated.json'
import correctedJson from './fixtures/detail-corrected.json'
import raisedJson from './fixtures/detail-raised.json'
import refusedJson from './fixtures/detail-refused.json'
import spineDownJson from './fixtures/detail-spine-down.json'
import withdrawnJson from './fixtures/detail-withdrawn.json'
import blankReasonJson from './fixtures/transition-blank-reason.json'
import toCommunicatedJson from './fixtures/transition-communicated.json'
import toCorrectedJson from './fixtures/transition-corrected.json'
import fromFinalStateJson from './fixtures/transition-from-a-final-state.json'
import raisedCannotBeCorrectedJson from './fixtures/transition-raised-cannot-be-corrected.json'
import refusalWithoutReasonJson from './fixtures/transition-refusal-without-reason.json'
import toRefusedJson from './fixtures/transition-refused.json'
import spineDownTransitionJson from './fixtures/transition-spine-down.json'
import toWithdrawnJson from './fixtures/transition-withdrawn.json'
import workflowEngagementJson from './fixtures/workflow-engagement.json'
import workflowEvaluationCommunicatedJson from './fixtures/workflow-evaluation-communicated.json'
import workflowEvaluationRaisedJson from './fixtures/workflow-evaluation-raised.json'
import workflowMisstatementsCommunicatedJson from './fixtures/workflow-misstatements-communicated.json'
import workflowMisstatementsRaisedJson from './fixtures/workflow-misstatements-raised.json'

// M-1, factual: the same misstatement read as raised, communicated and corrected.
export const raised = raisedJson as Misstatement
export const communicated = communicatedJson as Misstatement
export const corrected = correctedJson as Misstatement
// M-1 again, communicated, read while the Financial Spine could not be reached.
export const spineDown = spineDownJson as Misstatement
// M-2, judgemental with its range: communicated, then refused by management.
export const communicatedJudgemental = communicatedJudgementalJson as Misstatement
export const refused = refusedJson as Misstatement
// M-3, projected from a sample: communicated, then withdrawn by the auditor.
export const communicatedProjected = communicatedProjectedJson as Misstatement
export const withdrawn = withdrawnJson as Misstatement
// M-4, classification only; and again after the Spine reclassified one of its ledgers.
export const classificationOnly = classificationOnlyJson as Misstatement
export const classificationDrift = classificationDriftJson as Misstatement

// The backend's answer to each move: the misstatement as it then stood, with `transition`.
export const toCommunicated = toCommunicatedJson as Misstatement
export const toCorrected = toCorrectedJson as Misstatement
export const toRefused = toRefusedJson as Misstatement
export const toWithdrawn = toWithdrawnJson as Misstatement

// The backend's refusals, with the status each was sent with.
export const refusals = {
  raisedCannotBeCorrected: { status: 409, body: raisedCannotBeCorrectedJson },
  fromFinalState: { status: 409, body: fromFinalStateJson },
  refusalWithoutReason: { status: 422, body: refusalWithoutReasonJson },
  blankReason: { status: 422, body: blankReasonJson },
  spineDown: { status: 503, body: spineDownTransitionJson },
}

// The schedule of the same engagement before and after M-1 was communicated.
export const workflowEngagement = workflowEngagementJson as Engagement
export const workflowScheduleRaised = {
  engagement: workflowEngagement,
  misstatements: workflowMisstatementsRaisedJson as Misstatement[],
  evaluation: workflowEvaluationRaisedJson as Evaluation,
}
export const workflowScheduleCommunicated = {
  engagement: workflowEngagement,
  misstatements: workflowMisstatementsCommunicatedJson as Misstatement[],
  evaluation: workflowEvaluationCommunicatedJson as Evaluation,
}

export function detailPath(misstatement: Misstatement): string {
  return `GET /api/misstatements/${misstatement.id}`
}

export function transitionPath(misstatement: Misstatement): string {
  return `POST /api/misstatements/${misstatement.id}/transitions`
}
