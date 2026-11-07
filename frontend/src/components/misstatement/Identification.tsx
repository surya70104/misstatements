// What the misstatement is (spec sections 3.2, 6.1 and 9): its reference, type,
// description, state, band, the working paper it came from and who raised it. A judgemental
// item carries the auditor's range; a projected one names its sample and projection basis.
// An agent run's misstatement shows the run and its citations; a review note's, the note.
import { isRunOrigin, type Misstatement, type Origin } from '../../api'
import { count, dateTime, rupees } from '../../format'
import {
  BAND_LABEL,
  BAND_TONE,
  NOT_BANDED,
  STATE_LABEL,
  STATE_TONE,
  TYPE_LABEL,
  raisedFromLabel,
  samplingMethodLabel,
} from '../../labels'
import { Pill } from '../states'
import { Basis, Fact, Panel } from '../panels'

// Where it came from (spec section 8): the working paper; or the agent run with its id and
// source-row citations; or the review note with its reference and link.
function Source({
  raisedFrom,
  sourceRef,
  origin,
}: {
  raisedFrom: string
  sourceRef: string
  origin: Origin | null
}) {
  if (origin !== null && isRunOrigin(origin)) {
    return (
      <>
        <Fact label="Agent run">{origin.run_id}</Fact>
        <Fact label="Source-row citations" wide>
          <ul aria-label="Source-row citations" className="list-disc space-y-1 pl-5">
            {origin.citations.map((citation, index) => (
              <li key={`${citation.source}-${citation.row}-${String(index)}`}>
                <span className="font-medium">{citation.source}</span>
                <span className="text-slate-500">, row </span>
                <span className="tabular-nums">{citation.row}</span>
                {citation.detail !== undefined && (
                  <span className="text-slate-700">: {citation.detail}</span>
                )}
              </li>
            ))}
          </ul>
        </Fact>
      </>
    )
  }
  if (origin !== null) {
    return (
      <Fact label="Review note">
        {origin.note_ref}
        {origin.note_link !== null && (
          <span className="block">
            {/^https?:\/\//.test(origin.note_link) ? (
              <a
                href={origin.note_link}
                className="break-all underline decoration-slate-300 underline-offset-2 hover:decoration-slate-700"
              >
                {origin.note_link}
              </a>
            ) : (
              <span className="break-all">{origin.note_link}</span>
            )}
          </span>
        )}
      </Fact>
    )
  }
  return (
    <Fact
      label={
        raisedFrom === 'manual'
          ? 'Working paper reference (manual entry)'
          : 'Working paper reference'
      }
    >
      {sourceRef}
    </Fact>
  )
}

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
        <Fact label="Raised from">{raisedFromLabel(current.raised_from)}</Fact>
        <Source
          raisedFrom={current.raised_from}
          sourceRef={current.source_ref}
          origin={current.origin}
        />
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
            {current.sampling !== null && (
              <>
                <Fact label="Sampling method">{samplingMethodLabel(current.sampling.method)}</Fact>
                <Fact label="Population value">
                  <span className="tabular-nums">{rupees(current.sampling.population_value)}</span>
                  <span className="block text-xs text-slate-600">
                    {count(current.sampling.population_size, 'item')}
                  </span>
                </Fact>
                <Fact label="Sample value">
                  <span className="tabular-nums">{rupees(current.sampling.sample_value)}</span>
                  <span className="block text-xs text-slate-600">
                    {count(current.sampling.sample_size, 'item')}
                  </span>
                </Fact>
                <Fact label="Misstatement found in the sample">
                  <span className="tabular-nums">
                    {rupees(current.sampling.known_error_in_sample)}
                  </span>
                  <Basis>
                    The Dr/Cr lines carry the projected amount, the auditor’s best estimate for the
                    population; the band is computed on it.
                  </Basis>
                </Fact>
              </>
            )}
          </>
        )}
      </dl>
    </Panel>
  )
}
