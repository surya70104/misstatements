// What the misstatement is (spec sections 3.2, 6.1 and 9): its reference, type,
// description, state, band, the working paper it came from and who raised it. A judgemental
// item carries the auditor's range; a projected one names its sample and projection basis.
import type { Misstatement } from '../../api'
import { dateTime, rupees } from '../../format'
import {
  BAND_LABEL,
  BAND_TONE,
  NOT_BANDED,
  STATE_LABEL,
  STATE_TONE,
  TYPE_LABEL,
  raisedFromLabel,
} from '../../labels'
import { Pill } from '../states'
import { Basis, Fact, Panel } from '../panels'

export function Identification({ misstatement }: { misstatement: Misstatement }) {
  const { current, band, banding } = misstatement
  return (
    <Panel id="identification" title="Identification">
      <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
        <Fact label="Reference">{misstatement.ref}</Fact>
        <Fact label="Type">{TYPE_LABEL[current.type]}</Fact>
        <Fact label="Current state">
          <Pill tone={STATE_TONE[current.state]}>{STATE_LABEL[current.state]}</Pill>
        </Fact>
        <Fact label="Materiality band">
          {band === null ? (
            <Pill tone="attention">{NOT_BANDED}</Pill>
          ) : (
            <Pill tone={BAND_TONE[band]}>{BAND_LABEL[band]}</Pill>
          )}
          {banding.threshold_version_no !== null && (
            <span className="mt-1 block text-xs text-slate-600">
              Against thresholds version {banding.threshold_version_no}
            </span>
          )}
        </Fact>
        <Fact label="Description" wide>
          {current.description}
        </Fact>
        <Fact label="Working paper reference">{current.source_ref}</Fact>
        <Fact label="Raised from">{raisedFromLabel(current.raised_from)}</Fact>
        <Fact label="Raised by">{current.raised_by}</Fact>
        <Fact label="Raised">
          <time dateTime={misstatement.created_at}>{dateTime(misstatement.created_at)}</time>
        </Fact>

        {current.type === 'judgemental' && (
          <Fact label="Auditor’s range" wide>
            <span className="tabular-nums">
              {rupees(current.range_low)} to {rupees(current.range_high)}
            </span>
            {banding.range_crosses_pm === true && (
              <span className="ml-3">
                <Pill tone="attention">Range crosses PM</Pill>
              </span>
            )}
            <Basis>
              The Dr/Cr lines carry the auditor’s point estimate; the band is computed on it.
            </Basis>
          </Fact>
        )}

        {current.type === 'projected' && (
          <>
            <Fact label="Sample">{current.sample_ref ?? 'Not recorded'}</Fact>
            <Fact label="Projection basis" wide>
              {current.projection_basis ?? 'Not recorded'}
            </Fact>
          </>
        )}
      </dl>
    </Panel>
  )
}
