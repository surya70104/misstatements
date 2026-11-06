// The prior-period carry-forward's fixtures, typed (SA 450 paragraph 11(b); backend D61).
// Every one is the backend's real answer, produced and kept honest by
// backend/tests/test_frontend_fixtures.py: one engagement with two misstatements of its own
// (1,90,000 together, below PM 2,50,000) and two items carried from the prior period. PY-1
// reversed in this period; PY-2 still stands. A run is recorded, PY-2 is revised upward and
// PY-1 is removed, with each refusal met on the way.
import type { PriorPeriodListing } from '../src/api'
import type { Snapshot } from './evaluationFixtures'
import blankBasisJson from './fixtures/prior-period-blank-basis.json'
import listingJson from './fixtures/prior-period-listing.json'
import noneScreenJson from './fixtures/prior-period-none-screen.json'
import notCarriedJson from './fixtures/prior-period-not-carried.json'
import reachesPmScreenJson from './fixtures/prior-period-reaches-pm-screen.json'
import recordedJson from './fixtures/prior-period-recorded.json'
import removedScreenJson from './fixtures/prior-period-removed-screen.json'
import removedJson from './fixtures/prior-period-removed.json'
import revisedJson from './fixtures/prior-period-revised.json'
import runScreenJson from './fixtures/prior-period-run-screen.json'
import screenJson from './fixtures/prior-period-screen.json'

// The evaluation screen's six reads at each moment.
// Nothing carried yet.
export const none = noneScreenJson as unknown as Snapshot
// PY-1 and PY-2 carried.
export const carried = screenJson as unknown as Snapshot
// ... after an evaluation run was recorded.
export const withRun = runScreenJson as unknown as Snapshot
// ... after PY-2 was revised: with it the two together reach PM, and the run is stale.
export const reachesPm = reachesPmScreenJson as unknown as Snapshot
// ... after PY-1 was removed.
export const afterRemoval = removedScreenJson as unknown as Snapshot

// The schedule of prior-period items, and the backend's answer to each write.
export const listing = listingJson as PriorPeriodListing
export const recorded = recordedJson as PriorPeriodListing
export const revised = revisedJson as PriorPeriodListing
export const removed = removedJson as PriorPeriodListing

// The backend's refusals, with the status each was sent with.
export const refusals = {
  blankBasis: { status: 422, body: blankBasisJson },
  notCarried: { status: 409, body: notCarriedJson },
}

export function recordPath(snapshot: Snapshot): string {
  return `POST /api/engagements/${snapshot.engagement.id}/prior-period`
}

export function removalPath(snapshot: Snapshot, ref: string): string {
  return `POST /api/engagements/${snapshot.engagement.id}/prior-period/${ref}/removal`
}
