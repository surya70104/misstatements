// The written representation attachment's fixtures, typed (SA 450 paragraph 14; backend
// D63). Every one is the backend's real answer, produced and kept honest by
// backend/tests/test_frontend_fixtures.py.
import type { RepLetterAttachment } from '../src/api'
import cautionsJson from './fixtures/rep-letter-attachment-cautions.json'
import noThresholdsJson from './fixtures/rep-letter-attachment-no-thresholds.json'
import nothingJson from './fixtures/rep-letter-attachment-nothing.json'
import readyJson from './fixtures/rep-letter-attachment-ready.json'
import spineDownJson from './fixtures/rep-letter-attachment-spine-down.json'

// Four misstatements, all communicated to management, one refused and one the reverse of
// another; the aggregate below PM and a run recording it: no caution.
export const ready = readyJson as RepLetterAttachment
// The TCWG scenario's engagement with an item above PM, an escalated item, a prior-period
// item and the aggregate at or above OM: every caution but a stale run.
export const withCautions = cautionsJson as RepLetterAttachment
// ... read while the Financial Spine could not be reached.
export const spineDown = spineDownJson as RepLetterAttachment
// One misstatement and no thresholds; and an engagement with nothing raised.
export const noThresholds = noThresholdsJson as RepLetterAttachment
export const nothing = nothingJson as RepLetterAttachment

export function attachmentPath(attachment: RepLetterAttachment): string {
  return `GET /api/engagements/${attachment.engagement.id}/rep-letter-attachment`
}
