// The words the screens use for the backend's codes. A label is presentation only: the
// type, the state and the band of a misstatement are always the backend's.
import type { Band, MisstatementState, MisstatementType, TransitionTarget } from './api'

type Tone = 'neutral' | 'good' | 'attention'

export const TYPES: readonly MisstatementType[] = ['factual', 'judgemental', 'projected']
export const STATES: readonly MisstatementState[] = [
  'raised',
  'communicated',
  'corrected',
  'refused',
  'withdrawn',
]
export const BANDS: readonly Band[] = ['clearly_trivial', 'accumulated', 'individually_significant']

export const TYPE_LABEL: Record<MisstatementType, string> = {
  factual: 'Factual',
  judgemental: 'Judgemental',
  projected: 'Projected',
}

export const STATE_LABEL: Record<MisstatementState, string> = {
  raised: 'Raised',
  communicated: 'Communicated',
  corrected: 'Corrected',
  refused: 'Refused',
  withdrawn: 'Withdrawn',
}

export const STATE_TONE: Record<MisstatementState, Tone> = {
  raised: 'neutral',
  communicated: 'neutral',
  corrected: 'good',
  refused: 'attention',
  withdrawn: 'neutral',
}

export const BAND_LABEL: Record<Band, string> = {
  clearly_trivial: 'Clearly trivial',
  accumulated: 'Accumulated',
  individually_significant: 'Individually significant',
}

export const BAND_TONE: Record<Band, Tone> = {
  clearly_trivial: 'neutral',
  accumulated: 'neutral',
  individually_significant: 'attention',
}

/** What a misstatement the backend could not band is called. */
export const NOT_BANDED = 'Not banded'

// The moves the specification draws (section 3.3):
//   raised -> communicated -> corrected | refused | withdrawn
// This decides which actions a screen offers and nothing else. The backend holds the rule
// and refuses any other move, whatever a screen offers.
export const NEXT_STATES: Record<MisstatementState, readonly TransitionTarget[]> = {
  raised: ['communicated'],
  communicated: ['corrected', 'refused', 'withdrawn'],
  corrected: [],
  refused: [],
  withdrawn: [],
}

/** The two moves that must carry a reason (SA 450 paragraph 9; spec section 3.3). */
export const REASON_REQUIRED: readonly TransitionTarget[] = ['refused', 'withdrawn']

/** The backend's limit on a reason, mirrored so a person sees it before sending. */
export const REASON_MAX_LENGTH = 1500

// ---- the evaluation ----
// The backend's status codes in words. A code with no word here is shown as it was sent.

type Worded = { text: string; tone: Tone }

function status(words: Record<string, Worded>, code: string): Worded {
  return words[code] ?? { text: code, tone: 'attention' }
}

const GATE_STATUS: Record<string, Worded> = {
  clear: { text: 'Clear', tone: 'good' },
  fires: { text: 'Fires', tone: 'attention' },
  indeterminate: { text: 'Indeterminate', tone: 'attention' },
  no_thresholds: { text: 'No thresholds', tone: 'attention' },
  not_configured: { text: 'Not configured', tone: 'neutral' },
}

const EXPOSURE_STATUS: Record<string, Worded> = {
  open: { text: 'Open', tone: 'good' },
  blocked: { text: 'Blocked', tone: 'attention' },
  undetermined: { text: 'Undetermined', tone: 'attention' },
}

const RECORD_STATUS: Record<string, Worded> = {
  none: { text: 'None recorded', tone: 'neutral' },
  current: { text: 'Current', tone: 'good' },
  stale: { text: 'Stale', tone: 'attention' },
}

const RESPONSE_STATUS: Record<string, Worded> = {
  not_required: { text: 'Not required', tone: 'neutral' },
  required: { text: 'Required', tone: 'attention' },
  acknowledged: { text: 'Acknowledged', tone: 'good' },
  recorded: { text: 'Recorded', tone: 'good' },
  stale: { text: 'Stale', tone: 'attention' },
  unavailable: { text: 'Unavailable', tone: 'attention' },
}

const DETERMINATION: Record<string, string> = {
  not_material: 'Not material',
  material: 'Material',
}

// The measures a gate names in `fires_on`.
const MEASURE: Record<string, string> = {
  'profit.gross': 'profit before tax, gross',
  'profit.net': 'profit before tax, net',
  'net_assets.gross': 'net assets, gross',
  'net_assets.net': 'net assets, net',
}

/** A gate against a line: clear, fires, indeterminate, no thresholds. */
export function gateStatus(code: string): Worded {
  return status(GATE_STATUS, code)
}

/** A gate as another module reads it: open, blocked, undetermined. */
export function exposureStatus(code: string): Worded {
  return status(EXPOSURE_STATUS, code)
}

/** Whether a recorded run or conclusion still stands: none, current, stale. */
export function recordStatus(code: string): Worded {
  return status(RECORD_STATUS, code)
}

/** Whether an acknowledgement or an answer is needed, given or out of date. */
export function responseStatus(code: string): Worded {
  return status(RESPONSE_STATUS, code)
}

export function determinationLabel(code: string | null): string | null {
  return code === null ? null : (DETERMINATION[code] ?? code)
}

export function measureLabel(code: string): string {
  return MEASURE[code] ?? code
}

const RAISED_FROM: Record<string, string> = { wp: 'Working paper', manual: 'Manual entry' }
const NATURE: Record<string, string> = { PL: 'Profit and loss', BS: 'Balance sheet' }
const SECTION: Record<string, string> = {
  assets: 'Assets',
  liabilities: 'Liabilities',
  equity: 'Equity',
  pl_before_tax: 'Profit and loss, before tax',
  pl_after_tax: 'Profit and loss, below profit before tax',
  unresolved: 'Not classified',
}

// A code this screen has no word for is shown as the backend sent it, never dropped.
function worded(words: Record<string, string>, code: string | null): string | null {
  return code === null ? null : (words[code] ?? code)
}

export function raisedFromLabel(code: string): string {
  return RAISED_FROM[code] ?? code
}

export function natureLabel(code: string | null): string | null {
  return worded(NATURE, code)
}

export function sectionLabel(code: string | null): string | null {
  return worded(SECTION, code)
}

// ---- thresholds, the Financial Spine and the event trail ----

const PM_CHECK: Record<string, Worded> = {
  match: { text: 'Matches the Spine', tone: 'good' },
  mismatch: { text: 'Differs from the Spine', tone: 'attention' },
  pinned_version_changed: { text: 'Pinned version changed', tone: 'attention' },
  spine_has_no_pm: { text: 'The Spine holds no PM', tone: 'neutral' },
  not_pinned: { text: 'No Spine version pinned', tone: 'neutral' },
  not_configured: { text: 'Spine not configured', tone: 'attention' },
  unreachable: { text: 'Spine unreachable', tone: 'attention' },
}

/** Our PM against the Financial Spine's, as the backend reports the comparison. */
export function pmCheckStatus(code: string): Worded {
  return status(PM_CHECK, code)
}

const SPINE_LINK: Record<string, Worded> = {
  unlinked: { text: 'Not linked to the Financial Spine', tone: 'neutral' },
  recorded: { text: 'Financial Spine link recorded', tone: 'neutral' },
  verified: { text: 'Financial Spine link verified', tone: 'good' },
  not_configured: { text: 'Financial Spine not configured', tone: 'attention' },
  missing: { text: 'Financial Spine record missing', tone: 'attention' },
  unreachable: { text: 'Financial Spine unreachable', tone: 'attention' },
  mismatch: { text: 'Financial Spine version mismatch', tone: 'attention' },
}

/** The state of an engagement's link to the Financial Spine. */
export function spineLinkStatus(code: string): Worded {
  return status(SPINE_LINK, code)
}

const RECONCILIATION: Record<string, Worded> = {
  ok: { text: 'Read', tone: 'good' },
  unpinned: { text: 'No Spine version pinned', tone: 'neutral' },
  not_configured: { text: 'Spine not configured', tone: 'attention' },
  missing: { text: 'Spine record missing', tone: 'attention' },
  unreachable: { text: 'Spine unreachable', tone: 'attention' },
}

/** Whether the reconciliation could read the Financial Spine. */
export function reconciliationStatus(code: string): Worded {
  return status(RECONCILIATION, code)
}

const EVENT_KIND: Record<string, string> = {
  threshold_recompute: 'Thresholds revised: every band recomputes',
  soft_gate_acknowledged: 'Soft gate acknowledged by the partner',
  materiality_reassessed: 'Materiality reassessed before an evaluation',
  evaluation_concluded: 'Conclusion recorded',
  strategy_trigger_response: 'Strategy prompt answered',
}

export function eventKindLabel(code: string): string {
  return EVENT_KIND[code] ?? code
}
