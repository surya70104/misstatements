// The schedule's fixtures, typed. Every one is the backend's real answer, produced and kept
// honest by backend/tests/test_frontend_fixtures.py: one engagement carrying every type,
// state and band, one with nothing raised, and the first again with the Spine unreachable.
import type { Engagement, Evaluation, Misstatement } from '../src/api'
import emptyEngagementJson from './fixtures/empty-engagement.json'
import emptyEvaluationJson from './fixtures/empty-evaluation.json'
import emptyMisstatementsJson from './fixtures/empty-misstatements.json'
import misstatementJson from './fixtures/misstatement.json'
import engagementJson from './fixtures/schedule-engagement.json'
import evaluationJson from './fixtures/schedule-evaluation.json'
import misstatementsJson from './fixtures/schedule-misstatements.json'
import spineDownEvaluationJson from './fixtures/spine-down-evaluation.json'
import spineDownMisstatementsJson from './fixtures/spine-down-misstatements.json'

export const engagement = engagementJson as Engagement
export const misstatements = misstatementsJson as Misstatement[]
export const evaluation = evaluationJson as Evaluation
export const misstatement = misstatementJson as Misstatement

export const emptyEngagement = emptyEngagementJson as Engagement
export const emptyMisstatements = emptyMisstatementsJson as Misstatement[]
export const emptyEvaluation = emptyEvaluationJson as Evaluation

export const spineDownMisstatements = spineDownMisstatementsJson as Misstatement[]
export const spineDownEvaluation = spineDownEvaluationJson as Evaluation

/** The three answers a schedule page asks for, keyed the way `mockApi` wants them. */
export function scheduleAnswers(
  id: string,
  answers: { engagement: unknown; misstatements: unknown; evaluation: unknown },
): Record<string, unknown> {
  return {
    [`GET /api/engagements/${id}`]: answers.engagement,
    [`GET /api/engagements/${id}/misstatements`]: answers.misstatements,
    [`GET /api/engagements/${id}/evaluation`]: answers.evaluation,
  }
}

export const SCHEDULE = scheduleAnswers(engagement.id, { engagement, misstatements, evaluation })
