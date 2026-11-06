// The fixtures of the screens added to close Stage 6, typed. Every one is the backend's
// real answer, produced and kept honest by backend/tests/test_frontend_fixtures.py. A
// refusal is kept as `{ status, body }`: the status and the body the backend sent.
import type {
  CurrentThreshold,
  Engagement,
  Misstatement,
  ModuleEvent,
  Reconciliation,
  Threshold,
} from '../src/api'
import type { Snapshot } from './evaluationFixtures'
import branchAcknowledgementStaleJson from './fixtures/branch-acknowledgement-stale.json'
import branchAlreadyDecidedJson from './fixtures/branch-already-decided.json'
import branchItemAtOmJson from './fixtures/branch-item-at-om.json'
import branchRangeCrossesPmJson from './fixtures/branch-range-crosses-pm.json'
import branchStateDiffersEvaluationJson from './fixtures/branch-state-differs-evaluation.json'
import branchStateDiffersRunRefusedJson from './fixtures/branch-state-differs-run-refused.json'
import branchStateDiffersScheduleJson from './fixtures/branch-state-differs-schedule.json'
import branchStateDiffersJson from './fixtures/branch-state-differs.json'
import branchStrategyStaleJson from './fixtures/branch-strategy-stale.json'
import branchUnmatchedEvaluationJson from './fixtures/branch-unmatched-evaluation.json'
import branchUnmatchedScheduleJson from './fixtures/branch-unmatched-schedule.json'
import branchUnmatchedJson from './fixtures/branch-unmatched.json'
import createBlankLabelJson from './fixtures/engagement-create-blank-label.json'
import createUnknownSpineJson from './fixtures/engagement-create-unknown-spine-engagement.json'
import createVersionWithoutEngagementJson from './fixtures/engagement-create-version-without-engagement.json'
import createdPinnedJson from './fixtures/engagement-created-pinned.json'
import createdUnlinkedJson from './fixtures/engagement-created-unlinked.json'
import eventsEvaluationJson from './fixtures/events-screen-evaluation.json'
import eventsPartnerJson from './fixtures/events-screen-partner.json'
import eventsThresholdsJson from './fixtures/events-screen-thresholds.json'
import raisedNewLedgerJson from './fixtures/misstatement-raised-new-ledger.json'
import raisedJson from './fixtures/misstatement-raised.json'
import acknowledgedJson from './fixtures/partner-acknowledged.json'
import acknowledgementNotAPartnerJson from './fixtures/partner-acknowledgement-not-a-partner.json'
import acknowledgementRecordedJson from './fixtures/partner-acknowledgement-recorded.json'
import acknowledgementRequiredJson from './fixtures/partner-acknowledgement-required.json'
import acknowledgementTwiceJson from './fixtures/partner-acknowledgement-twice.json'
import concludedMaterialJson from './fixtures/partner-concluded-material.json'
import concludedJson from './fixtures/partner-concluded.json'
import conclusionEmptyJson from './fixtures/partner-conclusion-empty.json'
import conclusionGateBlockedJson from './fixtures/partner-conclusion-gate-blocked.json'
import conclusionMaterialRecordedJson from './fixtures/partner-conclusion-material-recorded.json'
import conclusionRecordedJson from './fixtures/partner-conclusion-recorded.json'
import conclusionStaleRunJson from './fixtures/partner-conclusion-stale-run.json'
import raiseCommitFailedJson from './fixtures/raise-commit-failed.json'
import raiseJudgementalWithoutRangeJson from './fixtures/raise-judgemental-without-range.json'
import raiseOnUnlinkedJson from './fixtures/raise-on-unlinked-engagement.json'
import raiseOneLineJson from './fixtures/raise-one-line.json'
import raiseProjectedWithoutSampleJson from './fixtures/raise-projected-without-sample.json'
import raiseUnbalancedJson from './fixtures/raise-unbalanced.json'
import raiseUnknownLineJson from './fixtures/raise-unknown-line.json'
import spineLinkRefusedJson from './fixtures/spine-link-refused-after-raising.json'
import spineLinkSetJson from './fixtures/spine-link-set.json'
import spineLinkUnknownVersionJson from './fixtures/spine-link-unknown-version.json'
import spineCleanEmptyJson from './fixtures/spine-screen-clean-empty.json'
import spineCleanJson from './fixtures/spine-screen-clean.json'
import spineProblemsJson from './fixtures/spine-screen-problems.json'
import spineUnlinkedJson from './fixtures/spine-screen-unlinked.json'
import spineUnreachableJson from './fixtures/spine-screen-unreachable.json'
import thresholdFractionTooLargeJson from './fixtures/threshold-fraction-too-large.json'
import thresholdNoFractionJson from './fixtures/threshold-no-fraction.json'
import thresholdPmNotBelowOmJson from './fixtures/threshold-pm-not-below-om.json'
import thresholdRevisedJson from './fixtures/threshold-revised.json'
import thresholdSetJson from './fixtures/threshold-set.json'
import thresholdsNoneJson from './fixtures/thresholds-screen-none.json'
import thresholdsOneJson from './fixtures/thresholds-screen-one.json'
import thresholdsSpineDownJson from './fixtures/thresholds-screen-spine-down.json'
import thresholdsTwoJson from './fixtures/thresholds-screen-two.json'
import workflowSpineJson from './fixtures/workflow-spine-screen.json'
import workflowThresholdsJson from './fixtures/workflow-thresholds-screen.json'
import { refusal } from './mockApi'

export type Refused = { status: number; body: { detail: unknown; pending_decision?: string } }

/** A captured refusal as `mockApi` answers it. */
export function refuse(captured: Refused) {
  return refusal(captured.status, captured.body)
}

// ---- engagements ----
export const createdUnlinked = createdUnlinkedJson as Engagement
export const createdPinned = createdPinnedJson as Engagement
export const createRefusals = {
  blankLabel: createBlankLabelJson as Refused,
  versionWithoutEngagement: createVersionWithoutEngagementJson as Refused,
  unknownSpineEngagement: createUnknownSpineJson as Refused,
}

// ---- thresholds: what the screen reads, at four moments of one engagement ----
export type ThresholdsScreen = {
  engagement: Engagement
  current: CurrentThreshold
  history: Threshold[]
  events: ModuleEvent[]
}
export const thresholdsNone = thresholdsNoneJson as unknown as ThresholdsScreen
export const thresholdsOne = thresholdsOneJson as unknown as ThresholdsScreen
export const thresholdsTwo = thresholdsTwoJson as unknown as ThresholdsScreen
export const thresholdsSpineDown = thresholdsSpineDownJson as unknown as ThresholdsScreen
export const workflowThresholds = workflowThresholdsJson as unknown as ThresholdsScreen
export const thresholdSet = thresholdSetJson as unknown as Threshold
export const thresholdRevised = thresholdRevisedJson as unknown as Threshold
export const thresholdRefusals = {
  pmNotBelowOm: thresholdPmNotBelowOmJson as Refused,
  noFraction: thresholdNoFractionJson as Refused,
  fractionTooLarge: thresholdFractionTooLargeJson as Refused,
}

export function thresholdsAnswers(screen: ThresholdsScreen): Record<string, unknown> {
  const id = screen.engagement.id
  return {
    [`GET /api/engagements/${id}`]: screen.engagement,
    [`GET /api/engagements/${id}/thresholds`]: screen.current,
    [`GET /api/engagements/${id}/thresholds/history`]: screen.history,
    [`GET /api/engagements/${id}/events`]: screen.events,
  }
}

// ---- the Financial Spine screen ----
export type SpineScreen = { engagement: Engagement; reconciliation: Reconciliation }
export const spineUnlinked = spineUnlinkedJson as unknown as SpineScreen
export const spineCleanEmpty = spineCleanEmptyJson as unknown as SpineScreen
export const spineClean = spineCleanJson as unknown as SpineScreen
export const spineProblems = spineProblemsJson as unknown as SpineScreen
export const spineUnreachable = spineUnreachableJson as unknown as SpineScreen
export const workflowSpine = workflowSpineJson as unknown as SpineScreen
export const spineLinkSet = spineLinkSetJson as Engagement
export const spineLinkRefusals = {
  unknownVersion: spineLinkUnknownVersionJson as Refused,
  afterRaising: spineLinkRefusedJson as Refused,
}

export function spineAnswers(screen: SpineScreen): Record<string, unknown> {
  const id = screen.engagement.id
  return {
    [`GET /api/engagements/${id}`]: screen.engagement,
    [`GET /api/engagements/${id}/spine-reconciliation`]: screen.reconciliation,
  }
}

// ---- the event trail ----
export type EventsScreen = { engagement: Engagement; events: ModuleEvent[] }
export const eventsThresholds = eventsThresholdsJson as unknown as EventsScreen
export const eventsEvaluation = eventsEvaluationJson as unknown as EventsScreen
export const eventsPartner = eventsPartnerJson as unknown as EventsScreen

export function eventsAnswers(screen: EventsScreen): Record<string, unknown> {
  const id = screen.engagement.id
  return {
    [`GET /api/engagements/${id}`]: screen.engagement,
    [`GET /api/engagements/${id}/events`]: screen.events,
  }
}

// ---- recording a misstatement ----
export const misstatementRaised = raisedJson as unknown as Misstatement
export const misstatementRaisedNewLedger = raisedNewLedgerJson as unknown as Misstatement
export const raiseRefusals = {
  unbalanced: raiseUnbalancedJson as Refused,
  oneLine: raiseOneLineJson as Refused,
  unknownLine: raiseUnknownLineJson as Refused,
  judgementalWithoutRange: raiseJudgementalWithoutRangeJson as Refused,
  projectedWithoutSample: raiseProjectedWithoutSampleJson as Refused,
  onUnlinkedEngagement: raiseOnUnlinkedJson as Refused,
  commitFailed: raiseCommitFailedJson as Refused,
}

// ---- the partner's two writes, captured behind a trusted proxy with a role claim ----
export const acknowledgementRequired = acknowledgementRequiredJson as unknown as Snapshot
export const acknowledged = acknowledgedJson as unknown as Snapshot
export const partnerConcluded = concludedJson as unknown as Snapshot
export const partnerConcludedMaterial = concludedMaterialJson as unknown as Snapshot
export const acknowledgementRecorded = acknowledgementRecordedJson as unknown
export const conclusionRecorded = conclusionRecordedJson as unknown
export const conclusionMaterialRecorded = conclusionMaterialRecordedJson as unknown
export const partnerRefusals = {
  acknowledgementNotAPartner: acknowledgementNotAPartnerJson as Refused,
  acknowledgementTwice: acknowledgementTwiceJson as Refused,
  conclusionGateBlocked: conclusionGateBlockedJson as Refused,
  conclusionEmpty: conclusionEmptyJson as Refused,
  conclusionStaleRun: conclusionStaleRunJson as Refused,
}

// ---- the eight display branches no earlier fixture reached (register V11) ----
export const branch = {
  rangeCrossesPm: branchRangeCrossesPmJson as unknown as Misstatement,
  stateDiffers: branchStateDiffersJson as unknown as Misstatement,
  stateDiffersSchedule: branchStateDiffersScheduleJson as unknown as Misstatement[],
  stateDiffersEvaluation: branchStateDiffersEvaluationJson as unknown as Snapshot,
  stateDiffersRunRefused: branchStateDiffersRunRefusedJson as Refused,
  alreadyDecided: branchAlreadyDecidedJson as unknown as Misstatement,
  unmatched: branchUnmatchedJson as unknown as Misstatement,
  unmatchedSchedule: branchUnmatchedScheduleJson as unknown as Misstatement[],
  unmatchedEvaluation: branchUnmatchedEvaluationJson as unknown as Snapshot,
  acknowledgementStale: branchAcknowledgementStaleJson as unknown as Snapshot,
  strategyStale: branchStrategyStaleJson as unknown as Snapshot,
  itemAtOm: branchItemAtOmJson as unknown as Snapshot,
}
