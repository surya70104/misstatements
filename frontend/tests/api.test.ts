import { afterEach, expect, test, vi } from 'vitest'

import {
  ApiError,
  acknowledgeSoftGate,
  createEngagement,
  errorDetail,
  getEngagement,
  getEvaluation,
  getHealth,
  getMisstatement,
  getOpinionGate,
  getReconciliation,
  getSignOffGate,
  getThresholds,
  listConclusions,
  listEvaluationRuns,
  listEvents,
  listThresholdHistory,
  raiseMisstatement,
  recordConclusion,
  recordEvaluationRun,
  respondToStrategyPrompt,
  setSpineLink,
  setThresholds,
  transitionMisstatement,
  listEngagements,
  listMisstatements,
  type Engagement,
} from '../src/api'
import notFound from './fixtures/engagement-not-found.json'
import engagements from './fixtures/engagements.json'
import { raised, refusals, toCommunicated, transitionPath } from './detailFixtures'
import {
  acknowledgementRecorded,
  acknowledgementRequired,
  conclusionRecorded,
  createdPinned,
  misstatementRaised,
  partnerRefusals,
  refuse,
  spineAnswers,
  spineProblems,
  thresholdSet,
  thresholdsAnswers,
  thresholdsTwo,
} from './closureFixtures'
import {
  clearNoRun,
  evaluationAnswers,
  refusals as evaluationRefusals,
  runCurrent,
  runRecorded,
  runsPath,
  strategyPath,
  strategyRequired,
  strategyResponse,
} from './evaluationFixtures'
import { answered, failApi, mockApi, refusal, requested, sent } from './mockApi'
import { engagement, evaluation, misstatement, misstatements, SCHEDULE } from './scheduleFixtures'

afterEach(() => {
  vi.unstubAllGlobals()
})

async function failure(action: Promise<unknown>): Promise<ApiError> {
  try {
    await action
  } catch (error) {
    if (error instanceof ApiError) return error
    throw error
  }
  throw new Error('the request was expected to fail')
}

test('getHealth returns the backend answer', async () => {
  mockApi({ 'GET /api/health': { status: 'ok', module: 'misstatements-rollup', version: '0.1.0' } })
  await expect(getHealth()).resolves.toEqual({
    status: 'ok',
    module: 'misstatements-rollup',
    version: '0.1.0',
  })
})

test('getHealth throws an ApiError carrying the status', async () => {
  mockApi({})
  await expect(getHealth()).rejects.toBeInstanceOf(ApiError)
  await expect(getHealth()).rejects.toMatchObject({ status: 404 })
})

test('listEngagements returns the list exactly as the backend sent it', async () => {
  mockApi({ 'GET /api/engagements': engagements })
  const listed = await listEngagements()
  expect(listed).toEqual(engagements)
  expect(listed.map((entry: Engagement) => entry.spine.status)).toEqual([
    'recorded',
    'recorded',
    'unlinked',
  ])
  expect(requested()).toEqual(['GET /api/engagements'])
})

test('a refusal is reported in the backend’s own words', async () => {
  mockApi({ 'GET /api/engagements/abc': refusal(404, notFound) })
  const error = await failure(getEngagement('abc'))
  expect(error.status).toBe(404)
  expect(error.message).toBe(notFound.detail)
  expect(error.path).toBe('/api/engagements/abc')
  expect(error.unreachable).toBe(false)
  expect(error.pendingDecision).toBeNull()
})

test('a refusal that names a pending decision carries it', async () => {
  mockApi({
    'GET /api/engagements': refusal(409, {
      detail: 'whether it may be re-pointed is not decided (pending decision B10)',
      pending_decision: 'B10',
    }),
  })
  const error = await failure(listEngagements())
  expect(error.status).toBe(409)
  expect(error.pendingDecision).toBe('B10')
  expect(error.message).toContain('not decided')
})

test('a validation failure names each field and what is wrong with it', async () => {
  mockApi({
    'GET /api/engagements': refusal(422, {
      detail: [
        { type: 'missing', loc: ['body', 'label'], msg: 'Field required' },
        { type: 'value_error', loc: ['body', 'lines', 0, 'dr'], msg: 'Input should be above 0' },
        { type: 'value_error', loc: ['body'], msg: 'Value error, the lines must balance' },
      ],
    }),
  })
  const error = await failure(listEngagements())
  expect(error.message).toBe(
    'label: Field required; lines.0.dr: Input should be above 0; ' +
      'Value error, the lines must balance',
  )
})

test('an error with no usable body falls back to the path and the status', async () => {
  mockApi({ 'GET /api/engagements': refusal(500) })
  const error = await failure(listEngagements())
  expect(error.message).toBe('/api/engagements answered 500')
  mockApi({ 'GET /api/engagements': refusal(503, { detail: '   ' }) })
  expect((await failure(listEngagements())).message).toBe('/api/engagements answered 503')
  mockApi({ 'GET /api/engagements': refusal(502, ['not', 'an', 'object']) })
  expect((await failure(listEngagements())).message).toBe('/api/engagements answered 502')
})

test('a backend that cannot be reached is told apart from one that refused', async () => {
  failApi()
  const error = await failure(listEngagements())
  expect(error.status).toBe(0)
  expect(error.unreachable).toBe(true)
  expect(error.message).toBe(
    'The backend could not be reached. Check that it is running on port 8003.',
  )
})

test('an identifier is encoded into the path', async () => {
  mockApi({})
  await failure(getEngagement('a/b c'))
  expect(requested()).toEqual(['GET /api/engagements/a%2Fb%20c'])
})

test('the schedule’s three reads return the backend’s answers unchanged', async () => {
  mockApi({ ...SCHEDULE, [`GET /api/misstatements/${misstatement.id}`]: misstatement })
  expect(await listMisstatements(engagement.id)).toEqual(misstatements)
  expect(await getEvaluation(engagement.id)).toEqual(evaluation)
  expect(await getMisstatement(misstatement.id)).toEqual(misstatement)
  expect(requested()).toEqual([
    `GET /api/engagements/${engagement.id}/misstatements`,
    `GET /api/engagements/${engagement.id}/evaluation`,
    `GET /api/misstatements/${misstatement.id}`,
  ])
})

test('amounts arrive as exact decimal strings and are never turned into numbers', async () => {
  mockApi(SCHEDULE)
  const [first] = await listMisstatements(engagement.id)
  expect(first?.effects?.profit_before_tax).toBe('-60000.00')
  expect(first?.spine.lines.map((line) => [line.dr, line.cr])).toEqual([
    ['60000.00', '0.00'],
    ['0.00', '60000.00'],
  ])
  const answer = await getEvaluation(engagement.id)
  expect(answer.aggregate.profit_before_tax.gross).toBe('195000.00')
  expect(answer.threshold).toMatchObject({ om: '400000.00', pm: '250000.00', ctt: '12500.00' })
})

test('the evaluation’s reads return the backend’s answers unchanged', async () => {
  const id = runCurrent.engagement.id
  mockApi(evaluationAnswers(runCurrent))
  expect(await listEvaluationRuns(id)).toEqual(runCurrent.runs)
  expect(await listConclusions(id)).toEqual(runCurrent.conclusions)
  expect(await getOpinionGate(id)).toEqual(runCurrent.opinion_gate)
  expect(await getSignOffGate(id)).toEqual(runCurrent.sign_off_gate)
  expect(requested()).toEqual([
    `GET /api/engagements/${id}/evaluation/runs`,
    `GET /api/engagements/${id}/evaluation/conclusions`,
    `GET /api/engagements/${id}/gates/opinion`,
    `GET /api/engagements/${id}/gates/sign-off`,
  ])
  // A run's aggregates stay the exact strings the backend stored.
  expect(runCurrent.runs[0]).toMatchObject({
    agg_gross_pbt: '195000.00',
    agg_net_pbt: '-195000.00',
  })
})

test('recording a run sends the reassessment and no figure', async () => {
  mockApi({ [runsPath(clearNoRun)]: answered(201, runRecorded) })
  const run = await recordEvaluationRun(clearNoRun.engagement.id)
  expect(run).toEqual(runRecorded)
  expect(sent()).toEqual([
    {
      request: `POST /api/engagements/${clearNoRun.engagement.id}/evaluation/runs`,
      body: { materiality_reassessed: true },
      contentType: 'application/json',
    },
  ])
})

test('a run the backend refuses is reported in the backend’s words', async () => {
  mockApi({
    [runsPath(clearNoRun)]: refusal(
      evaluationRefusals.runNotEvaluable.status,
      evaluationRefusals.runNotEvaluable.body,
    ),
  })
  const error = await failure(recordEvaluationRun(clearNoRun.engagement.id))
  expect(error.status).toBe(409)
  expect(error.message).toBe(evaluationRefusals.runNotEvaluable.body.detail)
})

test('the strategy answer is sent as given and answers with the evaluation', async () => {
  mockApi({ [strategyPath(strategyRequired)]: answered(201, strategyResponse) })
  const evaluation = await respondToStrategyPrompt(strategyRequired.engagement.id, {
    strategy_revised: false,
    note: 'No change needed',
  })
  expect(evaluation.gates.strategy_trigger.response?.status).toBe('recorded')
  expect(sent().map((entry) => entry.body)).toEqual([
    { strategy_revised: false, note: 'No change needed' },
  ])
})

test('the two partner-only writes go to the partner-only endpoints, and carry no identity', async () => {
  const id = acknowledgementRequired.engagement.id
  mockApi({
    [`POST /api/engagements/${id}/evaluation/soft-gate-acknowledgements`]: answered(
      201,
      acknowledgementRecorded,
    ),
    [`POST /api/engagements/${id}/evaluation/conclusions/not-material`]: answered(
      201,
      conclusionRecorded,
    ),
    [`POST /api/engagements/${id}/evaluation/conclusions/material`]: answered(
      201,
      conclusionRecorded,
    ),
  })
  await acknowledgeSoftGate(id, 'Reviewed')
  await acknowledgeSoftGate(id, null)
  const words = { conclusion: 'Not material.', basis: 'Below PM.', reviewed_run_id: 'run-1' }
  await recordConclusion(id, 'not_material', words)
  await recordConclusion(id, 'material', words)
  expect(sent().map((entry) => [entry.request.replace(id, ':id'), entry.body])).toEqual([
    ['POST /api/engagements/:id/evaluation/soft-gate-acknowledgements', { note: 'Reviewed' }],
    ['POST /api/engagements/:id/evaluation/soft-gate-acknowledgements', {}],
    [
      'POST /api/engagements/:id/evaluation/conclusions/not-material',
      { ...words, materiality_reassessed: true },
    ],
    [
      'POST /api/engagements/:id/evaluation/conclusions/material',
      { ...words, materiality_reassessed: true },
    ],
  ])
  // Who is acting is never sent by the client: no role, no user, no figure. The proxy says
  // who it is, and the backend decides.
  for (const [, init] of vi.mocked(fetch).mock.calls) {
    expect([...new Headers(init?.headers).keys()]).toEqual(['content-type'])
    const body = typeof init?.body === 'string' ? init.body : ''
    expect(body).not.toBe('')
    expect(body).not.toMatch(/partner|role|user|agg_|gross|net/i)
  }
})

test('a partner-only write by someone who is not the partner is refused by the backend', async () => {
  const id = acknowledgementRequired.engagement.id
  mockApi({
    [`POST /api/engagements/${id}/evaluation/soft-gate-acknowledgements`]: refuse(
      partnerRefusals.acknowledgementNotAPartner,
    ),
  })
  const error = await failure(acknowledgeSoftGate(id, null))
  expect(error.status).toBe(403)
  expect(error.message).toContain("does not hold the partner role 'engagement-partner'")
})

test('the setup calls send what a person declared, as exact text', async () => {
  mockApi({
    'POST /api/engagements': answered(201, createdPinned),
    [`POST /api/engagements/${createdPinned.id}/spine-link`]: answered(200, createdPinned),
    [`POST /api/engagements/${createdPinned.id}/thresholds`]: answered(201, thresholdSet),
    [`POST /api/engagements/${createdPinned.id}/misstatements`]: answered(201, misstatementRaised),
  })
  expect(
    await createEngagement({ label: 'FY26', spine_engagement_id: null, spine_version_id: null }),
  ).toEqual(createdPinned)
  await setSpineLink(createdPinned.id, { spine_engagement_id: 'e', spine_version_id: 'v' })
  const threshold = await setThresholds(createdPinned.id, {
    om: '400000.00',
    pm: '250000.00',
    ctt_fraction: '0.05',
    basis: 'C-1',
  })
  expect(threshold.ctt).toBe('12500.00')
  const raised = await raiseMisstatement(createdPinned.id, {
    type: 'factual',
    description: 'Rent',
    raised_from: 'wp',
    source_ref: 'E-4.2',
    lines: [
      { line_no: 5, dr: '60000.00' },
      { line_no: 3, cr: '60000.00' },
    ],
  })
  expect(raised.effects?.profit_before_tax).toBe('-60000.00')
  expect(sent().map((entry) => entry.body)).toEqual([
    { label: 'FY26', spine_engagement_id: null, spine_version_id: null },
    { spine_engagement_id: 'e', spine_version_id: 'v' },
    { om: '400000.00', pm: '250000.00', ctt_fraction: '0.05', basis: 'C-1' },
    {
      type: 'factual',
      description: 'Rent',
      raised_from: 'wp',
      source_ref: 'E-4.2',
      lines: [
        { line_no: 5, dr: '60000.00' },
        { line_no: 3, cr: '60000.00' },
      ],
    },
  ])
})

test('the reads of the new screens return the backend’s answers unchanged', async () => {
  const id = thresholdsTwo.engagement.id
  mockApi({ ...thresholdsAnswers(thresholdsTwo), ...spineAnswers(spineProblems) })
  expect(await getThresholds(id)).toEqual(thresholdsTwo.current)
  expect(await listThresholdHistory(id)).toEqual(thresholdsTwo.history)
  expect(await listEvents(id)).toEqual(thresholdsTwo.events)
  expect(await getReconciliation(spineProblems.engagement.id)).toEqual(spineProblems.reconciliation)
})

test('the schedule’s reads encode their identifiers and report refusals like any other', async () => {
  mockApi({ 'GET /api/misstatements/x': refusal(404, { detail: 'no misstatement x' }) })
  await failure(listMisstatements('a/b'))
  await failure(getEvaluation('a/b'))
  const error = await failure(getMisstatement('x'))
  expect(error.message).toBe('no misstatement x')
  expect(error.status).toBe(404)
  expect(requested()).toEqual([
    'GET /api/engagements/a%2Fb/misstatements',
    'GET /api/engagements/a%2Fb/evaluation',
    'GET /api/misstatements/x',
  ])
})

test('a move is posted as JSON and answers with the misstatement as it now stands', async () => {
  mockApi({ [transitionPath(raised)]: answered(201, toCommunicated) })
  const updated = await transitionMisstatement(raised.id, { to: 'communicated' })
  expect(updated).toEqual(toCommunicated)
  expect(updated.current.state).toBe('communicated')
  expect(updated.versions).toHaveLength(2)
  expect(sent()).toEqual([
    {
      request: `POST /api/misstatements/${raised.id}/transitions`,
      body: { to: 'communicated' },
      contentType: 'application/json',
    },
  ])
})

test('a move carries its reason exactly as given, and nothing else', async () => {
  mockApi({ 'POST /api/misstatements/a%2Fb/transitions': answered(201, toCommunicated) })
  await transitionMisstatement('a/b', { to: 'refused', reason: 'Management disagrees' })
  expect(sent().map((entry) => entry.body)).toEqual([
    { to: 'refused', reason: 'Management disagrees' },
  ])
})

test('a move the backend refuses is reported in the backend’s words', async () => {
  mockApi({
    [transitionPath(raised)]: refusal(
      refusals.raisedCannotBeCorrected.status,
      refusals.raisedCannotBeCorrected.body,
    ),
  })
  const error = await failure(transitionMisstatement(raised.id, { to: 'corrected' }))
  expect(error.status).toBe(409)
  expect(error.message).toBe(
    'a raised misstatement cannot become corrected; from raised the only move is to communicated (spec section 3.3)',
  )

  mockApi({
    [transitionPath(raised)]: refusal(
      refusals.refusalWithoutReason.status,
      refusals.refusalWithoutReason.body,
    ),
  })
  const invalid = await failure(transitionMisstatement(raised.id, { to: 'refused' }))
  expect(invalid.status).toBe(422)
  expect(invalid.message).toBe(
    'Value error, a refusal needs a reason: SA 450 paragraph 9, no blank refusals (spec section 2; acceptance 3)',
  )
})

test('errorDetail reads only what the backend actually sends', () => {
  expect(errorDetail({ detail: 'no engagement x' })).toEqual({
    detail: 'no engagement x',
    pending: null,
  })
  expect(errorDetail({ detail: [{ msg: 'Field required' }] })).toEqual({
    detail: 'Field required',
    pending: null,
  })
  expect(errorDetail({ detail: [] })).toEqual({ detail: null, pending: null })
  expect(errorDetail({ detail: [{ loc: ['body'] }, 7] })).toEqual({ detail: null, pending: null })
  expect(errorDetail({ detail: 42 })).toEqual({ detail: null, pending: null })
  expect(errorDetail(null)).toEqual({ detail: null, pending: null })
  expect(errorDetail('text')).toEqual({ detail: null, pending: null })
})
