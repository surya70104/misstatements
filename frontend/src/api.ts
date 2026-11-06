// Typed client for the Misstatements Rollup API. Display only: every rule lives in the
// backend, and the shapes here mirror what the backend answers. Nothing is computed here
// that the backend decides: a refusal is shown in the backend's own words.

export type Health = { status: string; module: string; version: string }

// The authorisation notice every answer carries (backend D36, D39).
export type Authorisation = {
  enforced: boolean
  policy: string
  identity_mode: string
  production_grade: boolean
  missing: string
  partner_actions: {
    enforced: boolean
    available: boolean
    actions: string[]
    source: string | null
    detail: string
  }
}

// The list never asks the Spine, so it answers `unlinked` or `recorded`. Opening one
// engagement verifies the link and can answer any of the others.
export type SpineLinkState =
  'unlinked' | 'not_configured' | 'recorded' | 'verified' | 'missing' | 'unreachable' | 'mismatch'

export type Engagement = {
  id: string
  label: string
  spine: {
    engagement_id: string | null
    version_id: string | null
    status: SpineLinkState
    is_locked: boolean | null
    detail: string | null
  }
  misstatements: number
  current_threshold_id: string | null
  created_by: string
  created_at: string
  authorisation: Authorisation
}

export type MisstatementType = 'factual' | 'judgemental' | 'projected'
export type MisstatementState = 'raised' | 'communicated' | 'corrected' | 'refused' | 'withdrawn'
export type Band = 'clearly_trivial' | 'accumulated' | 'individually_significant'

// One append-only version of a misstatement: what it says, and the state it is in.
export type MisstatementVersion = {
  version_no: number
  type: MisstatementType
  description: string
  raised_by: string
  raised_from: string
  source_ref: string
  state: MisstatementState
  communicated_at: string | null
  decided_at: string | null
  refusal_reason: string | null
  withdrawal_reason: string | null
  spine_adjustment_id: string
  spine_kind: string
  range_low: string | null
  range_high: string | null
  sample_ref: string | null
  projection_basis: string | null
  created_by: string
  created_at: string
}

// A Dr/Cr line as the Financial Spine holds it. Exactly one of `dr` and `cr` is above zero.
export type SpineLine = {
  ledger_key: string
  ledger_name: string
  parent_chain: string[]
  head_id: string | null
  nature: string | null
  section: string | null
  dr: string
  cr: string
}

// The computed effects. Both figures are null together when a line cannot be classified;
// the whole object is null when the Spine could not be read.
export type Effects = {
  profit_before_tax: string | null
  profit_basis: string
  net_assets: string | null
  net_assets_basis: string
  partial: boolean
  unresolved: string[]
  // The effect on each Schedule III caption the lines touch, debit positive.
  captions: { head_id: string | null; nature: string | null; signed: string }[]
  classification_only: boolean
  spine_version_at_raise: string | null
  tree_version_at_raise: string | null
}

// Where a line sits in the Schedule III tree: its head and the section the effects use.
export type HeadAndSection = { head_id: string | null; section: string | null }

// The classification the effects were computed on, recorded when the version was raised,
// compared with the Financial Spine's classification now. Null when the Spine could not
// be read.
export type Classification = {
  spine_version_at_raise: string | null
  tree_version_at_raise: string | null
  tree_version_now: string | null
  drift: {
    position: number
    ledger_name: string
    ledger_key: string
    parent_chain: string[]
    snapshot: HeadAndSection
    live: HeadAndSection
  }[]
  unmatched: string[]
  effects_on_current_classification: Effects | null
}

// What a move asked of the Financial Spine and what the Spine holds afterwards.
export type TransitionOutcome = {
  spine_decision: string | null
  decided_now: boolean
  note: string | null
  adjustment_status: string | null
}

// ---- the qualitative checklist (spec section 5; backend D59) ----

// A factor recorded against a misstatement now, with its reason. `text` is the backend's
// wording of the factor.
export type QualitativeFactor = {
  factor: string
  text: string
  note: string
  escalated_by: string
  at: string | null
}

// One factor of the checklist: whether it is recorded now and, when it is, why and by whom.
export type QualitativeRow = {
  factor: string
  text: string
  applies: boolean
  note: string | null
  escalated_by: string | null
  at: string | null
}

// One entry of the append-only history: a factor recorded (`applies`) or cleared.
export type QualitativeEntry = {
  entry_no: number
  factor: string
  applies: boolean
  note: string
  escalated_by: string
  at: string | null
}

// What a misstatement carries. Escalated while at least one factor is recorded. The whole
// checklist, its history and the backend's explanation come only when one misstatement is
// read; the schedule's rows carry `escalated` and `factors` alone.
export type Qualitative = {
  escalated: boolean
  factors: QualitativeFactor[]
  escalation_basis?: string
  checklist?: QualitativeRow[]
  history?: QualitativeEntry[]
}

// The answer to reading the checklist and to every write on it: the checklist as it stands.
export type QualitativeChecklist = Required<Qualitative> & {
  misstatement_id: string
  ref: string
  authorisation: Authorisation
}

export type Misstatement = {
  id: string
  engagement_id: string
  ref: string
  created_by: string
  created_at: string
  current: MisstatementVersion
  spine: {
    status: string
    detail: string | null
    adjustment_id: string | null
    adjustment_status: string | null
    kind: string | null
    finding_ref: string | null
    proposed_by: string | null
    proposed_at: string | null
    decided_by: string | null
    decided_at: string | null
    decision_note: string | null
    measure: string | null
    tree_version_now: string | null
    lines: SpineLine[]
  }
  // Whether the state here and the Spine's adjustment agree; `consistent` is null when the
  // Spine could not be read.
  state_consistency: {
    consistent: boolean | null
    state: MisstatementState
    expected_adjustment_status: string
    adjustment_status: string | null
    detail: string | null
  }
  effects: Effects | null
  classification: Classification | null
  // Computed by the backend on every read against the current thresholds; null, with the
  // reason in `band_basis`, when the item cannot be banded.
  band: Band | null
  band_basis: string | null
  banding: {
    band: Band | null
    // Each effect banded on its own; the item's band is the higher of the two.
    bands: { profit: Band; net_assets: Band } | null
    amounts: { profit: string; net_assets: string } | null
    threshold_id: string | null
    threshold_version_no: number | null
    basis: string | null
    projected: boolean
    range_crosses_pm: boolean | null
    classification_only: boolean
  }
  // Escalated while a factor of the qualitative checklist is recorded (spec section 5).
  qualitative: Qualitative
  authorisation: Authorisation
  // Only when one misstatement is read: every version, oldest first. The versions are the
  // state trail: each move adds one and none is ever changed.
  versions?: MisstatementVersion[]
  // Only in the answer to a move.
  transition?: TransitionOutcome
}

// The moves the backend accepts (spec section 3.3). A reason is mandatory for a refusal
// and a withdrawal and is refused for the other two.
export type TransitionTarget = 'communicated' | 'corrected' | 'refused' | 'withdrawn'
export type TransitionRequest = { to: TransitionTarget; reason?: string }

// One measure summed both ways, with and without the projected items.
export type Measure = {
  gross: string
  net: string
  gross_without_projected: string
  net_without_projected: string
  projected_gross: string
  factual_gross: string
  judgemental_gross: string
}

export type Figures = { profit_before_tax: Measure; net_assets: Measure }

export type ThresholdLines = { id: string; version_no: number; om: string; pm: string; ctt: string }

// A gate's reading of the aggregate against one line. `status` is clear, fires,
// indeterminate (an item could not be aggregated) or no_thresholds; `fires_on` names the
// measures at or above the line, as "profit.gross", "net_assets.net" and so on.
export type Gate = {
  line: string | null
  status: string
  fires_on: string[]
  fires_without_projected: boolean | null
  depends_on_projected: boolean
  highest_measure: string | null
  blocks: boolean
  basis: string
}

// A status with the backend's explanation of it.
export type StatusDetail = { status: string; detail: string }

// One evaluation row, exactly as recorded: the threshold version and the four aggregates
// it was made on. A conclusion is such a row with its determination, words and basis.
export type EvaluationRun = {
  id: string
  engagement_id: string
  run_no: number
  threshold_id: string
  threshold_version_no: number | null
  agg_gross_pbt: string
  agg_net_pbt: string
  agg_gross_na: string
  agg_net_na: string
  materiality_reassessed: boolean
  evaluated_by: string
  at: string
  concluded: boolean
  determination: string | null
  conclusion: string | null
  basis: string | null
  concluded_by: string | null
  // What the evaluation looked like when the row was written: labels and aggregates only.
  detail: {
    threshold?: { version_no: number; om: string; pm: string; ctt: string }
    figures?: Figures
    items?: {
      ref: string
      version_no: number
      state: MisstatementState
      type: MisstatementType
      band: Band | null
      classification_only: boolean
      uncorrected: boolean
      // Absent on a run recorded before the qualitative checklist was built (D59).
      escalated?: boolean
    }[]
    counted?: string[]
    projected?: string[]
    classification_only?: string[]
    // Absent on a run recorded before clearly trivial items were left out (D53).
    not_accumulated?: string[]
    not_accumulated_total?: NotAccumulatedTotal
    excluded?: { ref: string; state: MisstatementState }[]
    gates?: {
      hard: { status: string; fires_on: string[]; depends_on_projected: boolean }
      soft: {
        status: string
        fires_on: string[]
        depends_on_projected: boolean
        pm_gate: string
        acknowledgement: string
      }
    }
    sign_off?: { blocked: boolean; reasons: string[] }
    reviewed_run?: { id: string; run_no: number }
  }
  authorisation?: Authorisation
}

// What the clearly trivial items come to together, gross, and whether together they reach
// the clearly-trivial threshold (backend D56). Information: no figure or gate follows from it.
export type NotAccumulatedTotal = {
  profit_before_tax_gross: string
  net_assets_gross: string
  ctt: string | null
  at_or_above_ctt: boolean
  // Clearly trivial one by one, accumulated because together they reach the threshold (D57).
  accumulated_together: string[]
  basis: string
}

// Whether a recorded row still describes the evaluation: none, current or stale.
export type RunStatus = StatusDetail & { run: EvaluationRun | null }

// Whether a conclusion of one kind would be accepted right now, and why not.
export type ConclusionAllowed = { allowed: boolean; reasons: string[] }

// The evaluation of an engagement (spec sections 4.1, 7 and 10.3). Computed by the backend
// on every read: the aggregate, the gates, the sign-off decision and the conclusion.
export type Evaluation = {
  engagement_id: string
  threshold: ThresholdLines | null
  aggregate: Figures & {
    complete: boolean
    counted: string[]
    projected: string[]
    classification_only: string[]
    // Uncorrected and clearly trivial: listed in the schedule, in no total (spec section 4).
    not_accumulated: string[]
    not_accumulated_total: NotAccumulatedTotal
    unresolved: string[]
    excluded: { ref: string; state: MisstatementState }[]
    basis: string
  }
  gates: {
    hard: Gate
    soft: Gate & { pm_gate: string; acknowledgement: StatusDetail }
    strategy_trigger: {
      status: string
      fraction?: string | null
      line?: string | null
      fires_on?: string[]
      highest_measure?: string | null
      detail: string
      response: StatusDetail | null
    }
  }
  tests: {
    individual: {
      individually_significant: string[]
      at_or_above_om: string[]
      // Uncorrected items with a qualitative factor recorded: listed individually whatever
      // their size (spec section 5; acceptance 8), each with its factors and its band.
      escalated: { ref: string; factors: string[]; band: Band | null }[]
      escalation_basis: string
      basis: string
    }
    aggregate: { status: string; depends_on_projected: boolean; basis: string }
  }
  individually_significant: { blocking: string[]; unbanded: string[] }
  state_consistency: { inconsistent: string[] }
  sign_off: { blocked: boolean; reasons: string[] }
  conclusion: StatusDetail & {
    run: EvaluationRun | null
    allowed: { not_material: ConclusionAllowed; material: ConclusionAllowed }
    requires: string
  }
  latest_run: RunStatus
  authorisation: Authorisation
}

// A gate as another module reads it (architecture D18): open, blocked or undetermined.
export type GateExposure = {
  gate: string
  status: string
  blocked_by: string[]
  undetermined_because: string[]
  scope: string
  engagement_id: string
}

// The answer to the strategy prompt (spec section 7: "recorded either way").
export type StrategyResponse = { strategy_revised: boolean; note?: string }

/**
 * A request the backend refused, or could not be asked. `message` is what a person should
 * read: the backend's own explanation when it gave one. `status` is 0 when the backend could
 * not be reached at all.
 */
export class ApiError extends Error {
  readonly path: string
  readonly status: number
  readonly pendingDecision: string | null

  constructor(
    path: string,
    status: number,
    detail: string | null = null,
    pendingDecision: string | null = null,
  ) {
    super(ApiError.describe(path, status, detail))
    this.name = 'ApiError'
    this.path = path
    this.status = status
    this.pendingDecision = pendingDecision
  }

  /** True when no answer came back: the backend is down or unreachable. */
  get unreachable(): boolean {
    return this.status === 0
  }

  private static describe(path: string, status: number, detail: string | null): string {
    if (status === 0) {
      return 'The backend could not be reached. Check that it is running on port 8003.'
    }
    if (detail !== null && detail.trim() !== '') return detail
    return `${path} answered ${String(status)}`
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** One validation problem as FastAPI reports it, as "field: message". */
function problem(entry: unknown): string | null {
  if (!isRecord(entry) || typeof entry.msg !== 'string') return null
  const where = Array.isArray(entry.loc)
    ? entry.loc.filter((part) => part !== 'body').map((part) => String(part))
    : []
  return where.length > 0 ? `${where.join('.')}: ${entry.msg}` : entry.msg
}

/**
 * The explanation in an error body. The backend answers `{"detail": "..."}` for its own
 * refusals and `{"detail": [{loc, msg}, ...]}` for a request that failed validation.
 */
export function errorDetail(body: unknown): { detail: string | null; pending: string | null } {
  if (!isRecord(body)) return { detail: null, pending: null }
  const pending = typeof body.pending_decision === 'string' ? body.pending_decision : null
  if (typeof body.detail === 'string') return { detail: body.detail, pending }
  if (Array.isArray(body.detail)) {
    const problems = body.detail.map(problem).filter((text): text is string => text !== null)
    return { detail: problems.length > 0 ? problems.join('; ') : null, pending }
  }
  return { detail: null, pending }
}

async function readBody(response: Response): Promise<unknown> {
  try {
    return (await response.json()) as unknown
  } catch {
    return null // an empty or non-JSON error body: the status is all there is
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, init)
  } catch {
    throw new ApiError(path, 0)
  }
  if (!response.ok) {
    const { detail, pending } = errorDetail(await readBody(response))
    throw new ApiError(path, response.status, detail, pending)
  }
  return (await response.json()) as T
}

export function getHealth(): Promise<Health> {
  return request<Health>('/api/health')
}

export function listEngagements(): Promise<Engagement[]> {
  return request<Engagement[]>('/api/engagements')
}

export function getEngagement(id: string): Promise<Engagement> {
  return request<Engagement>(`/api/engagements/${encodeURIComponent(id)}`)
}

/** Every misstatement of an engagement, at its current version, in the order raised. */
export function listMisstatements(engagementId: string): Promise<Misstatement[]> {
  return request<Misstatement[]>(
    `/api/engagements/${encodeURIComponent(engagementId)}/misstatements`,
  )
}

/** The aggregate of an engagement's uncorrected misstatements against its thresholds. */
export function getEvaluation(engagementId: string): Promise<Evaluation> {
  return request<Evaluation>(`/api/engagements/${encodeURIComponent(engagementId)}/evaluation`)
}

export function getMisstatement(id: string): Promise<Misstatement> {
  return request<Misstatement>(`/api/misstatements/${encodeURIComponent(id)}`)
}

function evaluationPath(engagementId: string, rest = ''): string {
  return `/api/engagements/${encodeURIComponent(engagementId)}/evaluation${rest}`
}

/** Every evaluation row of an engagement, newest first, conclusions included. */
export function listEvaluationRuns(engagementId: string): Promise<EvaluationRun[]> {
  return request<EvaluationRun[]>(evaluationPath(engagementId, '/runs'))
}

/** Every conclusion of an engagement, newest first. */
export function listConclusions(engagementId: string): Promise<EvaluationRun[]> {
  return request<EvaluationRun[]>(evaluationPath(engagementId, '/conclusions'))
}

/** Whether an unmodified opinion is blocked by the size of the uncorrected misstatements. */
export function getOpinionGate(engagementId: string): Promise<GateExposure> {
  return request<GateExposure>(`/api/engagements/${encodeURIComponent(engagementId)}/gates/opinion`)
}

/** Whether sign-off is blocked for any reason the backend knows. */
export function getSignOffGate(engagementId: string): Promise<GateExposure> {
  return request<GateExposure>(
    `/api/engagements/${encodeURIComponent(engagementId)}/gates/sign-off`,
  )
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
}

/**
 * Record the evaluation as it stands. The figures are the backend's and are never sent:
 * the only thing a person states is that materiality was reassessed first (SA 450
 * paragraph 10), which the backend requires to be true.
 */
export function recordEvaluationRun(engagementId: string): Promise<EvaluationRun> {
  return post<EvaluationRun>(evaluationPath(engagementId, '/runs'), {
    materiality_reassessed: true,
  })
}

/** Record whether the audit strategy and plan were revised after the strategy prompt. */
export function respondToStrategyPrompt(
  engagementId: string,
  body: StrategyResponse,
): Promise<Evaluation> {
  return post<Evaluation>(evaluationPath(engagementId, '/strategy-responses'), body)
}

/**
 * Move a misstatement to its next state. The backend decides whether the move is allowed
 * and records it as a new version; the answer is the misstatement as it now stands, with
 * every version and what the move asked of the Financial Spine.
 */
export function transitionMisstatement(id: string, body: TransitionRequest): Promise<Misstatement> {
  return post<Misstatement>(`/api/misstatements/${encodeURIComponent(id)}/transitions`, body)
}

function qualitativePath(id: string, rest = ''): string {
  return `/api/misstatements/${encodeURIComponent(id)}/qualitative${rest}`
}

/**
 * Record a factor of the qualitative checklist against a misstatement, with its reason, or
 * record it again with a new reason. The misstatement is escalated from then on. Who acts is
 * never sent: the backend takes it from the authenticated identity.
 */
export function recordQualitativeFactor(
  id: string,
  body: { factor: string; note: string },
): Promise<QualitativeChecklist> {
  return post<QualitativeChecklist>(qualitativePath(id), body)
}

/** Clear a recorded factor, with the reason. The earlier entries stay in the history. */
export function clearQualitativeFactor(
  id: string,
  factor: string,
  body: { note: string },
): Promise<QualitativeChecklist> {
  return post<QualitativeChecklist>(
    qualitativePath(id, `/${encodeURIComponent(factor)}/clear`),
    body,
  )
}

// ---- thresholds (spec section 4) ----

// Our PM against the Financial Spine's PM on the version the thresholds were set against.
// `status` is match, mismatch, pinned_version_changed, spine_has_no_pm, not_pinned,
// not_configured or unreachable; a disagreement is reported, never resolved.
export type SpinePmCheck = {
  status: string
  our_pm: string
  spine_pm: string | null
  recorded_version_id: string | null
  pinned_version_id: string | null
  detail: string | null
}

// One version of the three lines. The clearly-trivial amount is computed by the backend
// from PM and the declared fraction; a revision adds a version and supersedes this one.
export type Threshold = {
  id: string
  engagement_id: string
  version_no: number
  om: string
  pm: string
  ctt: string
  ctt_fraction: string
  basis: string
  set_by: string
  set_at: string
  superseded_by: string | null
  is_current: boolean
  spine: { version_id: string | null; pm_at_set: string | null; pm_status_at_set: string | null }
  checks: { pm_below_om: boolean; note: string }
  spine_pm_check?: SpinePmCheck
  // Only in the answer to setting a version: the record that every band now recomputes.
  recompute_event?: ModuleEvent | null
}

export type CurrentThreshold = { current: Threshold | null; detail?: string }

// What a person declares. Amounts and the fraction are exact decimal strings.
export type ThresholdInput = { om: string; pm: string; ctt_fraction: string; basis: string }

// One entry of the engagement's append-only event trail.
export type ModuleEvent = {
  seq: number
  id: string
  engagement_id: string
  kind: string
  payload: Record<string, unknown>
  actor: string
  at: string
}

// ---- engagements and the Financial Spine link ----

export type SpineLinkInput = { spine_engagement_id: string | null; spine_version_id: string | null }
export type EngagementInput = SpineLinkInput & { label: string }

// An adjustment the Financial Spine holds, as the reconciliation reports it.
export type SpineAdjustmentReport = {
  adjustment_id: string
  finding_ref: string | null
  kind: string
  status: string
  narration: string | null
  working_paper_ref: string | null
  proposed_by: string | null
  proposed_at: string | null
  decision_note: string | null
  measure: string
}

// The read-only reconciliation with the Financial Spine. `status` is ok, or the reason the
// Spine could not be read, in which case every list is null.
export type Reconciliation = {
  engagement_id: string
  spine_version_id: string | null
  status: string
  detail: string | null
  clean: boolean | null
  orphans: SpineAdjustmentReport[] | null
  missing: { ref: string; state: MisstatementState; spine_adjustment_id: string }[] | null
  disagreements:
    | {
        ref: string
        state: MisstatementState
        expected_adjustment_status: string
        adjustment_status: string
        spine_adjustment_id: string
      }[]
    | null
  duplicated_references: string[] | null
  not_ours: number | null
  basis?: string
}

// ---- recording a misstatement (spec sections 3.1, 3.2 and 8) ----

// A Dr/Cr line as the backend takes it: a ledger of the Spine's import by its line number,
// or a ledger the import lacks by name, groups and Schedule III head; exactly one side.
export type LineInput = {
  line_no?: number
  ledger_name?: string
  parent_chain?: string[]
  head_id?: string
  dr?: string
  cr?: string
}

export type MisstatementInput = {
  type: MisstatementType
  description: string
  raised_from: 'wp' | 'manual'
  source_ref: string
  lines: LineInput[]
  range_low?: string
  range_high?: string
  sample_ref?: string
  projection_basis?: string
}

// ---- the two writes reserved to the engagement partner (spec sections 6.4 and 7) ----

export type Determination = 'not_material' | 'material'

export type ConclusionInput = {
  conclusion: string
  basis: string
  reviewed_run_id: string
}

export function createEngagement(body: EngagementInput): Promise<Engagement> {
  return post<Engagement>('/api/engagements', body)
}

/** Set, change or clear the link to the Financial Spine. */
export function setSpineLink(engagementId: string, body: SpineLinkInput): Promise<Engagement> {
  return post<Engagement>(`/api/engagements/${encodeURIComponent(engagementId)}/spine-link`, body)
}

export function getReconciliation(engagementId: string): Promise<Reconciliation> {
  return request<Reconciliation>(
    `/api/engagements/${encodeURIComponent(engagementId)}/spine-reconciliation`,
  )
}

export function getThresholds(engagementId: string): Promise<CurrentThreshold> {
  return request<CurrentThreshold>(
    `/api/engagements/${encodeURIComponent(engagementId)}/thresholds`,
  )
}

/** Every threshold version of an engagement, as the backend orders them. */
export function listThresholdHistory(engagementId: string): Promise<Threshold[]> {
  return request<Threshold[]>(
    `/api/engagements/${encodeURIComponent(engagementId)}/thresholds/history`,
  )
}

/** Set the first thresholds, or revise them: a new version, never a change to an old one. */
export function setThresholds(engagementId: string, body: ThresholdInput): Promise<Threshold> {
  return post<Threshold>(`/api/engagements/${encodeURIComponent(engagementId)}/thresholds`, body)
}

export function listEvents(engagementId: string): Promise<ModuleEvent[]> {
  return request<ModuleEvent[]>(`/api/engagements/${encodeURIComponent(engagementId)}/events`)
}

/** Record a misstatement. The backend proposes its lines to the Financial Spine. */
export function raiseMisstatement(
  engagementId: string,
  body: MisstatementInput,
): Promise<Misstatement> {
  return post<Misstatement>(
    `/api/engagements/${encodeURIComponent(engagementId)}/misstatements`,
    body,
  )
}

/**
 * The partner's acknowledgement of the soft gate. Partner only: the backend refuses it
 * unless the trusted proxy's role claim names the acting identity a partner.
 */
export function acknowledgeSoftGate(
  engagementId: string,
  note: string | null,
): Promise<Evaluation> {
  return post<Evaluation>(
    evaluationPath(engagementId, '/soft-gate-acknowledgements'),
    note === null ? {} : { note },
  )
}

/**
 * The conclusion. Partner only, and gated by the backend in the write path. The figures
 * are never sent: the backend saves the ones it computed with the words it is given.
 */
export function recordConclusion(
  engagementId: string,
  determination: Determination,
  body: ConclusionInput,
): Promise<EvaluationRun> {
  const kind = determination === 'material' ? 'material' : 'not-material'
  return post<EvaluationRun>(evaluationPath(engagementId, `/conclusions/${kind}`), {
    ...body,
    materiality_reassessed: true,
  })
}
