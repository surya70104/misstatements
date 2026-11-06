// The evaluation screen's fixtures, typed. Each snapshot is everything the screen reads for
// one engagement at one moment: six answers, each exactly as its endpoint gave it. They are
// produced and kept honest by backend/tests/test_frontend_fixtures.py.
import type { Engagement, Evaluation, EvaluationRun, GateExposure } from '../src/api'
import clearNoRunJson from './fixtures/eval-clear-no-run.json'
import concludedJson from './fixtures/eval-concluded.json'
import conclusionNotAPartnerJson from './fixtures/eval-conclusion-not-a-partner.json'
import conclusionStaleJson from './fixtures/eval-conclusion-stale.json'
import emptyJson from './fixtures/eval-empty.json'
import hardGateJson from './fixtures/eval-hard-gate.json'
import itemAbovePmJson from './fixtures/eval-item-above-pm.json'
import partnerAvailableJson from './fixtures/eval-partner-available.json'
import runCurrentJson from './fixtures/eval-run-current.json'
import runNoThresholdsJson from './fixtures/eval-run-no-thresholds.json'
import runNotEvaluableJson from './fixtures/eval-run-not-evaluable.json'
import runNotReassessedJson from './fixtures/eval-run-not-reassessed.json'
import runRecordedJson from './fixtures/eval-run-recorded.json'
import runStaleJson from './fixtures/eval-run-stale.json'
import softGateJson from './fixtures/eval-soft-gate.json'
import spineDownJson from './fixtures/eval-spine-down.json'
import strategyAlreadyAnsweredJson from './fixtures/eval-strategy-already-answered.json'
import strategyRecordedJson from './fixtures/eval-strategy-recorded.json'
import strategyRequiredJson from './fixtures/eval-strategy-required.json'
import strategyResponseJson from './fixtures/eval-strategy-response.json'
import twoConclusionsJson from './fixtures/eval-two-conclusions.json'
import twoRunsJson from './fixtures/eval-two-runs.json'

export type Snapshot = {
  engagement: Engagement
  evaluation: Evaluation
  runs: EvaluationRun[]
  conclusions: EvaluationRun[]
  opinion_gate: GateExposure
  sign_off_gate: GateExposure
}

// Nothing raised and no thresholds.
export const empty = emptyJson as unknown as Snapshot

// One engagement through its history: every type raised, no gate firing.
export const clearNoRun = clearNoRunJson as unknown as Snapshot
// ... read while the Financial Spine could not be reached.
export const spineDown = spineDownJson as unknown as Snapshot
// ... after its first run.
export const runCurrent = runCurrentJson as unknown as Snapshot
// ... after a further misstatement was raised: the run no longer describes it.
export const runStale = runStaleJson as unknown as Snapshot
// ... after a second run.
export const twoRuns = twoRunsJson as unknown as Snapshot
// ... once the firm has declared what "approaching materiality" means.
export const strategyRequired = strategyRequiredJson as unknown as Snapshot
// ... after the strategy prompt was answered.
export const strategyRecorded = strategyRecordedJson as unknown as Snapshot

// Other engagements, each at one of the lines.
export const softGate = softGateJson as unknown as Snapshot
export const hardGate = hardGateJson as unknown as Snapshot
export const itemAbovePm = itemAbovePmJson as unknown as Snapshot

// An engagement read behind the authenticating proxy, where a partner can be named.
export const partnerAvailable = partnerAvailableJson as unknown as Snapshot
export const concluded = concludedJson as unknown as Snapshot
export const conclusionStale = conclusionStaleJson as unknown as Snapshot
export const twoConclusions = twoConclusionsJson as unknown as Snapshot

// The backend's answers to the two writes this screen sends.
export const runRecorded = runRecordedJson as unknown as EvaluationRun
export const strategyResponse = strategyResponseJson as unknown as Evaluation

// The backend's refusals, with the status each was sent with.
export const refusals = {
  runNoThresholds: { status: 409, body: runNoThresholdsJson },
  runNotEvaluable: { status: 409, body: runNotEvaluableJson },
  runNotReassessed: { status: 422, body: runNotReassessedJson },
  strategyAlreadyAnswered: { status: 409, body: strategyAlreadyAnsweredJson },
  conclusionNotAPartner: { status: 403, body: conclusionNotAPartnerJson },
}

const READS = {
  engagement: '',
  evaluation: '/evaluation',
  runs: '/evaluation/runs',
  conclusions: '/evaluation/conclusions',
  opinion_gate: '/gates/opinion',
  sign_off_gate: '/gates/sign-off',
} as const

/** The path of one of the six reads, as `mockApi` keys it. */
export function readPath(id: string, read: keyof typeof READS): string {
  return `GET /api/engagements/${id}${READS[read]}`
}

/** The six reads of a snapshot, keyed the way `mockApi` wants them. */
export function evaluationAnswers(snapshot: Snapshot): Record<string, unknown> {
  const id = snapshot.engagement.id
  return Object.fromEntries(
    (Object.keys(READS) as (keyof typeof READS)[]).map((read) => [
      readPath(id, read),
      snapshot[read],
    ]),
  )
}

/** The six reads answering `before` the first time each is asked and `after` from then on. */
export function evaluationAnswersInTurn(
  before: Snapshot,
  after: Snapshot,
  inTurn: (...answers: unknown[]) => () => unknown,
): Record<string, unknown> {
  const id = before.engagement.id
  return Object.fromEntries(
    (Object.keys(READS) as (keyof typeof READS)[]).map((read) => [
      readPath(id, read),
      inTurn(before[read], after[read]),
    ]),
  )
}

export function runsPath(snapshot: Snapshot): string {
  return `POST /api/engagements/${snapshot.engagement.id}/evaluation/runs`
}

export function strategyPath(snapshot: Snapshot): string {
  return `POST /api/engagements/${snapshot.engagement.id}/evaluation/strategy-responses`
}
