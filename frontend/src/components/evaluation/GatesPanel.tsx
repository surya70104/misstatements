// The gates (spec section 7): the hard gate at overall materiality, the soft gate at
// performance materiality, what they mean for the opinion and for sign-off, and the items
// that block on their own. Every status and every reason is the backend's: this screen
// decides nothing and explains nothing in its own words where the backend has given its own.
// The partner's acknowledgement of the soft gate is offered where the backend asks for one.
import type { ReactNode } from 'react'

import type { Evaluation, Gate, GateExposure } from '../../api'
import { count, NOT_AVAILABLE, rupees } from '../../format'
import {
  BAND_LABEL,
  exposureStatus,
  gateStatus,
  measureLabel,
  NOT_BANDED,
  responseStatus,
} from '../../labels'
import { Panel } from '../panels'
import { Pill } from '../states'
import { AcknowledgementForm, PartnerOnly } from './PartnerForms'

function Card({ title, pill, children }: { title: string; pill: ReactNode; children: ReactNode }) {
  const id = `gate-${title.toLowerCase().replace(/[^a-z]+/g, '-')}`
  return (
    <section aria-labelledby={id} className="rounded border border-slate-200 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={id} className="text-sm font-semibold">
          {title}
        </h3>
        {pill}
      </div>
      <div className="mt-2 space-y-2 text-sm text-slate-800">{children}</div>
    </section>
  )
}

function Reasons({ title, reasons }: { title: string; reasons: string[] }) {
  if (reasons.length === 0) return null
  return (
    <div>
      <p className="font-medium">{title}</p>
      <ul className="mt-1 list-disc space-y-1 pl-5">
        {reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
    </div>
  )
}

function Explained({ summary, children }: { summary: string; children: ReactNode }) {
  return (
    <details className="text-xs text-slate-600">
      <summary className="cursor-pointer text-slate-700 underline decoration-slate-300 underline-offset-2">
        {summary}
      </summary>
      <p className="mt-1">{children}</p>
    </details>
  )
}

function Exposure({ title, exposure }: { title: string; exposure: GateExposure }) {
  const status = exposureStatus(exposure.status)
  return (
    <Card title={title} pill={<Pill tone={status.tone}>{status.text}</Pill>}>
      <Reasons title="Blocked by" reasons={exposure.blocked_by} />
      <Reasons title="Undetermined because" reasons={exposure.undetermined_because} />
      {exposure.blocked_by.length === 0 && exposure.undetermined_because.length === 0 && (
        <p className="text-slate-600">The backend gives no reason against it.</p>
      )}
      <Explained summary="What this gate covers">{exposure.scope}</Explained>
    </Card>
  )
}

function Against({ gate }: { gate: Gate }) {
  return (
    <>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2">
        <div>
          <dt className="text-xs tracking-wide text-slate-500 uppercase">Line</dt>
          <dd className="tabular-nums">{gate.line === null ? 'Not set' : rupees(gate.line)}</dd>
        </div>
        <div>
          <dt className="text-xs tracking-wide text-slate-500 uppercase">Highest measure</dt>
          <dd className="tabular-nums">
            {gate.highest_measure === null ? NOT_AVAILABLE : rupees(gate.highest_measure)}
          </dd>
        </div>
      </dl>
      {gate.fires_on.length > 0 && (
        <p>At or above the line on: {gate.fires_on.map(measureLabel).join('; ')}.</p>
      )}
      {gate.status === 'fires' && gate.depends_on_projected && (
        <p className="text-amber-900">
          It reaches the line only with the projected misstatements counted.
        </p>
      )}
      {gate.status === 'fires' && gate.fires_without_projected === true && (
        <p>It reaches the line without the projected misstatements too.</p>
      )}
    </>
  )
}

export function GatesPanel({
  engagementId,
  evaluation,
  opinionGate,
  signOffGate,
  onRecorded,
}: {
  engagementId: string
  evaluation: Evaluation
  opinionGate: GateExposure
  signOffGate: GateExposure
  onRecorded: () => void
}) {
  const { hard, soft } = evaluation.gates
  const hardStatus = gateStatus(hard.status)
  const softStatus = gateStatus(soft.status)
  const acknowledgement = responseStatus(soft.acknowledgement.status)
  const { individual } = evaluation.tests
  const { blocking, unbanded } = evaluation.individually_significant
  const { inconsistent } = evaluation.state_consistency
  const nothingIndividual =
    individual.individually_significant.length === 0 &&
    individual.at_or_above_om.length === 0 &&
    individual.escalated.length === 0 &&
    blocking.length === 0 &&
    unbanded.length === 0 &&
    inconsistent.length === 0

  return (
    <Panel id="gates" title="Gates and sign-off">
      <div className="grid gap-4 lg:grid-cols-2">
        <Exposure title="Opinion gate" exposure={opinionGate} />
        <Exposure title="Sign-off" exposure={signOffGate} />

        <Card
          title="Hard gate: overall materiality"
          pill={<Pill tone={hardStatus.tone}>{hardStatus.text}</Pill>}
        >
          <Against gate={hard} />
          <Explained summary="How this gate is tested">{hard.basis}</Explained>
        </Card>

        <Card
          title="Soft gate: performance materiality"
          pill={<Pill tone={softStatus.tone}>{softStatus.text}</Pill>}
        >
          <Against gate={soft} />
          <p>
            Firm setting for this gate: <span className="font-medium">{soft.pm_gate}</span>.
          </p>
          <p className="flex flex-wrap items-center gap-2">
            Partner acknowledgement:
            <Pill tone={acknowledgement.tone}>{acknowledgement.text}</Pill>
            <span className="text-slate-600">{soft.acknowledgement.detail}</span>
          </p>
          {(soft.acknowledgement.status === 'required' ||
            soft.acknowledgement.status === 'stale') && (
            <PartnerOnly what="Acknowledge the soft gate" authorisation={evaluation.authorisation}>
              <AcknowledgementForm engagementId={engagementId} onRecorded={onRecorded} />
            </PartnerOnly>
          )}
          <Explained summary="How this gate is tested">{soft.basis}</Explained>
        </Card>
      </div>

      <div className="mt-4">
        <Card
          title="Individual items"
          pill={
            nothingIndividual ? (
              <Pill tone="good">None</Pill>
            ) : (
              <Pill tone="attention">Present</Pill>
            )
          }
        >
          {nothingIndividual && (
            <p className="text-slate-600">
              No uncorrected item is individually significant, escalated, blocks sign-off, lacks a
              band or disagrees with the Financial Spine.
            </p>
          )}
          {individual.individually_significant.length > 0 && (
            <p>
              Individually significant (above PM): {individual.individually_significant.join(', ')}.
            </p>
          )}
          {individual.at_or_above_om.length > 0 && (
            <p>
              At or above overall materiality on their own: {individual.at_or_above_om.join(', ')}.
            </p>
          )}
          {individual.escalated.length > 0 && (
            <div>
              <p>Escalated on a qualitative factor, listed individually whatever their amount:</p>
              <ul aria-label="Escalated items" className="mt-1 list-disc space-y-1 pl-5">
                {individual.escalated.map((item) => (
                  <li key={item.ref}>
                    {item.ref}: {item.band === null ? NOT_BANDED : BAND_LABEL[item.band]} by amount;{' '}
                    {count(item.factors.length, 'factor')} recorded
                  </li>
                ))}
              </ul>
              <Explained summary="How escalation works">{individual.escalation_basis}</Explained>
            </div>
          )}
          {blocking.length > 0 && (
            <p className="text-amber-900">
              Blocking sign-off until corrected, refused with a reason or withdrawn:{' '}
              {blocking.join(', ')}.
            </p>
          )}
          {unbanded.length > 0 && (
            <p className="text-amber-900">Cannot be banded: {unbanded.join(', ')}.</p>
          )}
          {inconsistent.length > 0 && (
            <p className="text-amber-900">
              State differs from the Financial Spine: {inconsistent.join(', ')}.
            </p>
          )}
          <Explained summary="How the individual test is made">{individual.basis}</Explained>
        </Card>
      </div>
    </Panel>
  )
}
