// The TCWG extract's fixtures, typed (SA 450 paragraph 12; backend D62). Every one is the
// backend's real answer, produced and kept honest by
// backend/tests/test_frontend_fixtures.py.
import type { TcwgExtract } from '../src/api'
import blockedJson from './fixtures/tcwg-extract-blocked.json'
import noThresholdsJson from './fixtures/tcwg-extract-no-thresholds.json'
import notBlockedJson from './fixtures/tcwg-extract-not-blocked.json'
import nothingJson from './fixtures/tcwg-extract-nothing.json'
import spineDownJson from './fixtures/tcwg-extract-spine-down.json'

// One engagement (OM 4,00,000; PM 2,50,000; CTT 12,500) at three moments.
// Three accumulated items, one clearly trivial left outside, one corrected: nothing named.
export const notBlocked = notBlockedJson as TcwgExtract
// ... then a judgemental item above PM (M-6), a small item escalated on a related party
// (M-7), a prior-period item and a run: two named, and the aggregate at or above OM.
export const blocked = blockedJson as TcwgExtract
// ... read while the Financial Spine could not be reached.
export const spineDown = spineDownJson as TcwgExtract

// An engagement with one misstatement and no thresholds, and one with nothing raised.
export const noThresholds = noThresholdsJson as TcwgExtract
export const nothing = nothingJson as TcwgExtract

export function extractPath(extract: TcwgExtract): string {
  return `GET /api/engagements/${extract.engagement.id}/tcwg-extract`
}
