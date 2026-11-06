// The TCWG extract (SA 450 paragraph 12; spec section 2 row 12, section 6 item 2;
// acceptance 9; backend D62): the uncorrected misstatements of an engagement set out for
// communication to those charged with governance. The material ones are named individually,
// the others are summarised by type and listed, and the extract states the effect on the
// opinion and the request to correct.
//
// Display only, and read-only at the backend. Which misstatements are named, why, every
// figure, the effect on the opinion and the words of the request are all the backend's,
// read from `GET /api/engagements/{id}/tcwg-extract`. Nothing is computed here.
//
// The page is laid out as a document. "Print or save as PDF" hands it to the browser's own
// print dialog; the application's header, tabs and buttons are left off the printed page.
import type { ReactNode } from 'react'

import {
  getTcwgExtract,
  type BothWays,
  type GrossNet,
  type TcwgExtract,
  type TcwgNamed,
  type TcwgRow,
} from '../api'
import { EngagementNav } from '../components/EngagementNav'
import { SECONDARY } from '../components/forms'
import { Panel } from '../components/panels'
import { ErrorState, Loading, Pill } from '../components/states'
import { count, isZero, NOT_AVAILABLE, rupees } from '../format'
import {
  BAND_LABEL,
  determinationLabel,
  NOT_BANDED,
  recordStatus,
  STATE_LABEL,
  TYPE_LABEL,
} from '../labels'
import { href } from '../router'
import { usePageTitle } from '../usePageTitle'
import { useResource } from '../useResource'

const LINK = 'underline decoration-slate-300 underline-offset-2 hover:decoration-slate-700'
const HEAD = 'px-3 py-2 text-right font-semibold'
const LEFT = 'px-3 py-2 text-left font-semibold'
const NUMBER = 'px-3 py-2 text-right tabular-nums'
const TABLE = 'w-full border-collapse text-sm'
const THEAD = 'bg-slate-100 text-xs text-slate-600 print:bg-transparent'
const ROW = 'border-t border-slate-200 align-top'

type Tone = 'neutral' | 'good' | 'attention'

// The backend's three readings of the opinion gate, in words.
const OPINION: Record<string, { text: string; tone: Tone }> = {
  blocked: { text: 'Unmodified opinion blocked', tone: 'attention' },
  not_blocked: { text: 'Unmodified opinion not blocked', tone: 'good' },
  undetermined: { text: 'Effect undetermined', tone: 'attention' },
}

function Explained({ summary, children }: { summary: string; children: ReactNode }) {
  return (
    <details className="mt-3 text-xs text-slate-600 print:hidden">
      <summary className="cursor-pointer text-slate-700 underline decoration-slate-300 underline-offset-2">
        {summary}
      </summary>
      <p className="mt-1 max-w-4xl">{children}</p>
    </details>
  )
}

/** An effect the backend could not determine is said to be so, never shown as nil. */
function Effect({ value }: { value: string | null }) {
  return value === null ? (
    <span className="text-slate-500">Not determined</span>
  ) : (
    <span className="tabular-nums">{rupees(value)}</span>
  )
}

function Reasons({ title, reasons }: { title: string; reasons: string[] }) {
  if (reasons.length === 0) return null
  return (
    <div className="mt-3">
      <p className="text-sm font-medium text-slate-900">{title}</p>
      <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-800">
        {reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
    </div>
  )
}

function OpinionEffect({ extract }: { extract: TcwgExtract }) {
  const effect = extract.opinion_effect
  const worded = OPINION[effect.unmodified_opinion] ?? {
    text: effect.unmodified_opinion,
    tone: 'attention' as const,
  }
  const hard = effect.hard_gate
  const conclusion = recordStatus(effect.conclusion.status)
  return (
    <Panel id="tcwg-opinion" title="Effect on the audit opinion">
      <p className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
        <Pill tone={worded.tone}>{worded.text}</Pill>
        <span className="font-medium text-slate-900">{effect.statement}</span>
      </p>
      <Reasons title="Blocked by" reasons={effect.blocked_by} />
      <Reasons title="Undetermined because" reasons={effect.undetermined_because} />
      <dl className="mt-4 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-xs tracking-wide text-slate-500 uppercase">Overall materiality</dt>
          <dd className="mt-1 tabular-nums">
            {hard.line === null ? 'Not set' : rupees(hard.line)}
          </dd>
        </div>
        <div>
          <dt className="text-xs tracking-wide text-slate-500 uppercase">
            Highest aggregate measure
          </dt>
          <dd className="mt-1 tabular-nums">
            {hard.highest_measure === null ? NOT_AVAILABLE : rupees(hard.highest_measure)}
          </dd>
        </div>
        <div>
          <dt className="text-xs tracking-wide text-slate-500 uppercase">Partner's conclusion</dt>
          <dd className="mt-1">
            {effect.conclusion.determination === null
              ? 'None recorded'
              : `${determinationLabel(effect.conclusion.determination) ?? ''} (run ${String(effect.conclusion.run_no)}, ${conclusion.text.toLowerCase()})`}
          </dd>
        </div>
      </dl>
      {!effect.reads_prior_period && extract.prior_period.items.length > 0 && (
        <p className="mt-3 max-w-3xl text-xs text-slate-600">
          This effect is tested on the current year's uncorrected misstatements. The prior-period
          items below are shown with it and are not part of the test.
        </p>
      )}
      <Explained summary="What this effect covers">{effect.scope}</Explained>
    </Panel>
  )
}

function Lines({ item }: { item: TcwgNamed }) {
  if (item.lines.length === 0) {
    return (
      <p className="mt-3 text-sm text-slate-600">
        Its Dr/Cr lines could not be read from the Financial Spine.
      </p>
    )
  }
  return (
    <table className={`${TABLE} mt-3 max-w-2xl`}>
      <caption className="sr-only">Dr/Cr lines of {item.ref}</caption>
      <thead className={THEAD}>
        <tr>
          <th scope="col" className={LEFT}>
            Ledger
          </th>
          <th scope="col" className={HEAD}>
            Dr
          </th>
          <th scope="col" className={HEAD}>
            Cr
          </th>
        </tr>
      </thead>
      <tbody>
        {item.lines.map((line, index) => (
          <tr key={`${line.ledger_key}-${String(index)}`} className={ROW}>
            <th scope="row" className="px-3 py-1.5 text-left font-normal">
              {line.ledger_name}
            </th>
            <td className="px-3 py-1.5 text-right tabular-nums">
              {isZero(line.dr) ? '' : rupees(line.dr)}
            </td>
            <td className="px-3 py-1.5 text-right tabular-nums">
              {isZero(line.cr) ? '' : rupees(line.cr)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function NamedItem({ item }: { item: TcwgNamed }) {
  return (
    <li className="break-inside-avoid border-t border-slate-200 py-4 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h3 className="text-base font-semibold text-slate-900">
          <a href={href({ name: 'misstatement', id: item.id })} className={LINK}>
            {item.ref}
          </a>
        </h3>
        <Pill>{TYPE_LABEL[item.type]}</Pill>
        <Pill>{STATE_LABEL[item.state]}</Pill>
        <Pill tone="attention">{item.band === null ? NOT_BANDED : BAND_LABEL[item.band]}</Pill>
      </div>
      <p className="mt-1 max-w-3xl text-sm break-words text-slate-800">{item.description}</p>

      <dl className="mt-3 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-xs tracking-wide text-slate-500 uppercase">
            Effect on profit before tax
          </dt>
          <dd className="mt-1 font-medium">
            <Effect value={item.profit_before_tax} />
          </dd>
        </div>
        <div>
          <dt className="text-xs tracking-wide text-slate-500 uppercase">Effect on net assets</dt>
          <dd className="mt-1 font-medium">
            <Effect value={item.net_assets} />
          </dd>
        </div>
        <div>
          <dt className="text-xs tracking-wide text-slate-500 uppercase">Working paper</dt>
          <dd className="mt-1">{item.source_ref}</dd>
        </div>
      </dl>

      <div className="mt-3">
        <p className="text-sm font-medium text-slate-900">Named individually because it is</p>
        <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-800">
          {item.reasons.map((reason) => (
            <li key={reason.code}>{reason.text}</li>
          ))}
        </ul>
      </div>

      {item.factors.length > 0 && (
        <div className="mt-3">
          <p className="text-sm font-medium text-slate-900">Qualitative factors recorded</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-800">
            {item.factors.map((factor) => (
              <li key={factor.factor}>
                <span className="first-letter:uppercase">{factor.text}</span>
                <span className="text-slate-500">: </span>
                {factor.note}
              </li>
            ))}
          </ul>
        </div>
      )}

      {item.range !== null && (
        <p className="mt-3 text-sm text-slate-800">
          <span className="text-slate-500">Auditor's range: </span>
          <span className="tabular-nums">
            {rupees(item.range.low)} to {rupees(item.range.high)}
          </span>
        </p>
      )}
      {item.sample_ref !== null && (
        <p className="mt-3 text-sm text-slate-800">
          <span className="text-slate-500">Projected from sample </span>
          {item.sample_ref}
          {item.projection_basis !== null && (
            <>
              <span className="text-slate-500">; basis: </span>
              {item.projection_basis}
            </>
          )}
        </p>
      )}
      {item.refusal_reason !== null && (
        <p className="mt-3 text-sm text-slate-800">
          <span className="text-slate-500">Management's reason for not correcting: </span>
          {item.refusal_reason}
        </p>
      )}
      <Lines item={item} />
    </li>
  )
}

function Named({ extract }: { extract: TcwgExtract }) {
  const named = extract.named_individually
  return (
    <Panel id="tcwg-named" title="Misstatements named individually">
      {named.length === 0 ? (
        <p className="text-sm text-slate-700">
          No uncorrected misstatement is above performance materiality or escalated on a qualitative
          factor, so none is named individually.
        </p>
      ) : (
        <>
          <p className="text-sm text-slate-700">
            {count(named.length, 'uncorrected misstatement')} named individually: each is above
            performance materiality on its own, or escalated on a qualitative factor.
          </p>
          <ul aria-label="Misstatements named individually" className="mt-4">
            {named.map((item) => (
              <NamedItem key={item.ref} item={item} />
            ))}
          </ul>
        </>
      )}
    </Panel>
  )
}

function Undetermined({ extract }: { extract: TcwgExtract }) {
  if (extract.undetermined.length === 0) return null
  return (
    <Panel id="tcwg-undetermined" title="Misstatements that could not be assessed">
      <p className="text-sm text-amber-900">
        Whether each of these is above performance materiality is not known. They are named here so
        that none is left out.
      </p>
      <table className={`${TABLE} mt-3`}>
        <caption className="sr-only">Uncorrected misstatements that could not be banded</caption>
        <thead className={THEAD}>
          <tr>
            <th scope="col" className={LEFT}>
              Ref
            </th>
            <th scope="col" className={LEFT}>
              Description
            </th>
            <th scope="col" className={LEFT}>
              State
            </th>
            <th scope="col" className={LEFT}>
              Why it could not be assessed
            </th>
          </tr>
        </thead>
        <tbody>
          {extract.undetermined.map((item) => (
            <tr key={item.ref} className={ROW}>
              <th scope="row" className="px-3 py-2 text-left font-medium whitespace-nowrap">
                {item.ref}
              </th>
              <td className="px-3 py-2 break-words">{item.description}</td>
              <td className="px-3 py-2">{STATE_LABEL[item.state]}</td>
              <td className="px-3 py-2">{item.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  )
}

function Figures({ sums }: { sums: BothWays }) {
  const cell = (pair: GrossNet, way: keyof GrossNet) => (
    <td className={NUMBER}>{rupees(pair[way])}</td>
  )
  return (
    <>
      {cell(sums.profit_before_tax, 'gross')}
      {cell(sums.profit_before_tax, 'net')}
      {cell(sums.net_assets, 'gross')}
      {cell(sums.net_assets, 'net')}
    </>
  )
}

function FigureHeads() {
  return (
    <>
      <th scope="col" className={HEAD}>
        Profit before tax, gross
      </th>
      <th scope="col" className={HEAD}>
        Profit before tax, net
      </th>
      <th scope="col" className={HEAD}>
        Net assets, gross
      </th>
      <th scope="col" className={HEAD}>
        Net assets, net
      </th>
    </>
  )
}

function ItemRows({ items }: { items: TcwgRow[] }) {
  return (
    <>
      {items.map((item) => (
        <tr key={item.ref} className={ROW}>
          <th scope="row" className="px-3 py-2 text-left font-medium whitespace-nowrap">
            <a href={href({ name: 'misstatement', id: item.id })} className={LINK}>
              {item.ref}
            </a>
          </th>
          <td className="px-3 py-2">{TYPE_LABEL[item.type]}</td>
          <td className="px-3 py-2 break-words">
            {item.description}
            {item.classification_only && (
              <span className="block text-xs text-slate-500">Classification only</span>
            )}
            {item.refusal_reason !== null && (
              <span className="block text-xs text-slate-600">
                Management's reason for not correcting: {item.refusal_reason}
              </span>
            )}
          </td>
          <td className="px-3 py-2">{STATE_LABEL[item.state]}</td>
          <td className={NUMBER}>
            <Effect value={item.profit_before_tax} />
          </td>
          <td className={NUMBER}>
            <Effect value={item.net_assets} />
          </td>
        </tr>
      ))}
    </>
  )
}

function ItemHeads() {
  return (
    <tr>
      <th scope="col" className={LEFT}>
        Ref
      </th>
      <th scope="col" className={LEFT}>
        Type
      </th>
      <th scope="col" className={LEFT}>
        Description
      </th>
      <th scope="col" className={LEFT}>
        State
      </th>
      <th scope="col" className={HEAD}>
        Effect on profit before tax
      </th>
      <th scope="col" className={HEAD}>
        Effect on net assets
      </th>
    </tr>
  )
}

function Other({ extract }: { extract: TcwgExtract }) {
  const { groups, items } = extract.other_uncorrected
  return (
    <Panel id="tcwg-other" title="Other uncorrected misstatements">
      {items.length === 0 ? (
        <p className="text-sm text-slate-700">No other uncorrected misstatement is accumulated.</p>
      ) : (
        <>
          <p className="text-sm text-slate-700">
            {count(items.length, 'other uncorrected misstatement')}, summarised by type and then
            listed.
          </p>
          <div className="mt-3 overflow-x-auto">
            <table className={TABLE}>
              <caption className="sr-only">
                Other uncorrected misstatements summarised by type
              </caption>
              <thead className={THEAD}>
                <tr>
                  <th scope="col" className={LEFT}>
                    Type
                  </th>
                  <th scope="col" className={HEAD}>
                    Number
                  </th>
                  <FigureHeads />
                </tr>
              </thead>
              <tbody>
                {groups.map((group) => (
                  <tr key={group.type} className={ROW}>
                    <th scope="row" className="px-3 py-2 text-left font-medium">
                      {TYPE_LABEL[group.type]}
                    </th>
                    <td className={NUMBER}>{group.count}</td>
                    <Figures sums={group} />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-5 overflow-x-auto">
            <table className={TABLE}>
              <caption className="sr-only">Other uncorrected misstatements listed</caption>
              <thead className={THEAD}>
                <ItemHeads />
              </thead>
              <tbody>
                <ItemRows items={items} />
              </tbody>
            </table>
          </div>
        </>
      )}
    </Panel>
  )
}

function Totals({ extract }: { extract: TcwgExtract }) {
  const { totals, threshold } = extract
  const whole = totals.all_uncorrected
  return (
    <Panel id="tcwg-totals" title="Totals">
      <p className="text-sm text-slate-700">
        {threshold === null ? (
          'Thresholds are not set.'
        ) : (
          <>
            Against thresholds version {threshold.version_no}:{' '}
            <span className="tabular-nums">
              performance materiality {rupees(threshold.pm)} · overall materiality{' '}
              {rupees(threshold.om)}
            </span>
          </>
        )}
      </p>
      {!whole.complete && (
        <p className="mt-3 rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          These totals are short: a misstatement's effects could not be determined.
        </p>
      )}
      <div className="mt-3 overflow-x-auto">
        <table className={TABLE}>
          <caption className="sr-only">
            Totals of the uncorrected misstatements: named individually, other, and all
          </caption>
          <thead className={THEAD}>
            <tr>
              <th scope="col" className={LEFT}>
                Uncorrected misstatements
              </th>
              <th scope="col" className={HEAD}>
                Number
              </th>
              <FigureHeads />
            </tr>
          </thead>
          <tbody>
            <tr className={ROW}>
              <th scope="row" className="px-3 py-2 text-left font-medium">
                Named individually
              </th>
              <td className={NUMBER}>{totals.named_individually.count}</td>
              <Figures sums={totals.named_individually} />
            </tr>
            <tr className={ROW}>
              <th scope="row" className="px-3 py-2 text-left font-medium">
                Other
              </th>
              <td className={NUMBER}>{totals.other_uncorrected.count}</td>
              <Figures sums={totals.other_uncorrected} />
            </tr>
            <tr className={`${ROW} border-t-2 border-slate-400 font-semibold`}>
              <th scope="row" className="px-3 py-2 text-left">
                All uncorrected, accumulated
              </th>
              <td className={NUMBER}>{whole.count}</td>
              <Figures sums={whole} />
            </tr>
          </tbody>
        </table>
      </div>
      <p className="mt-2 max-w-3xl text-xs text-slate-600">
        Gross adds the size of every effect with no netting between misstatements; net adds them
        signed. Of the gross effect on profit before tax,{' '}
        <span className="tabular-nums">{rupees(whole.profit_before_tax.projected_gross)}</span> is
        projected from samples.
      </p>
      <Explained summary="How the totals are computed">{totals.basis}</Explained>
    </Panel>
  )
}

function PriorPeriod({ extract }: { extract: TcwgExtract }) {
  const prior = extract.prior_period
  if (prior.items.length === 0) return null
  return (
    <Panel id="tcwg-prior" title="Prior-period uncorrected misstatements">
      <p className="max-w-3xl text-sm text-slate-700">
        Misstatements left uncorrected in prior periods and carried forward, each with its
        current-period effect and its cumulative effect. They are not in the totals above.
      </p>
      <div className="mt-3 overflow-x-auto">
        <table className={TABLE}>
          <caption className="sr-only">
            Prior-period items, each with its current-period and cumulative effect
          </caption>
          <thead className={THEAD}>
            <tr>
              <th scope="col" className={LEFT}>
                Ref
              </th>
              <th scope="col" className={LEFT}>
                Prior-period item
              </th>
              <th scope="col" className={HEAD}>
                Current period: profit before tax
              </th>
              <th scope="col" className={HEAD}>
                Current period: net assets
              </th>
              <th scope="col" className={HEAD}>
                Cumulative: profit before tax
              </th>
              <th scope="col" className={HEAD}>
                Cumulative: net assets
              </th>
            </tr>
          </thead>
          <tbody>
            {prior.items.map((item) => (
              <tr key={item.ref} className={ROW}>
                <th scope="row" className="px-3 py-2 text-left font-medium whitespace-nowrap">
                  {item.ref}
                </th>
                <td className="px-3 py-2 break-words">
                  {item.description}
                  <span className="block text-xs text-slate-600">
                    {item.prior_period} · {item.source_ref}
                  </span>
                </td>
                <td className={NUMBER}>{rupees(item.current_period.profit_before_tax)}</td>
                <td className={NUMBER}>{rupees(item.current_period.net_assets)}</td>
                <td className={NUMBER}>{rupees(item.cumulative.profit_before_tax)}</td>
                <td className={NUMBER}>{rupees(item.cumulative.net_assets)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-5 overflow-x-auto">
        <table className={TABLE}>
          <caption className="sr-only">
            The current year's uncorrected misstatements together with the prior-period items, on
            each basis
          </caption>
          <thead className={THEAD}>
            <tr>
              <th scope="col" className={LEFT}>
                Current year with prior-period items
              </th>
              <FigureHeads />
            </tr>
          </thead>
          <tbody>
            <tr className={ROW}>
              <th scope="row" className="px-3 py-2 text-left font-medium">
                Current-period basis
              </th>
              <Figures sums={prior.with_prior_period.current_period} />
            </tr>
            <tr className={ROW}>
              <th scope="row" className="px-3 py-2 text-left font-medium">
                Cumulative basis
              </th>
              <Figures sums={prior.with_prior_period.cumulative} />
            </tr>
          </tbody>
        </table>
      </div>
    </Panel>
  )
}

function Outside({ extract }: { extract: TcwgExtract }) {
  const { clearly_trivial: trivial, not_uncorrected: settled } = extract.not_communicated
  if (trivial.items.length === 0 && settled.length === 0) return null
  return (
    <Panel id="tcwg-outside" title="Not part of this communication">
      <ul className="list-disc space-y-2 pl-5 text-sm text-slate-800">
        {trivial.items.length > 0 && (
          <li>
            Below the clearly-trivial threshold and not accumulated:{' '}
            {trivial.items.map((item) => item.ref).join(', ')}. Together, gross:{' '}
            <span className="tabular-nums">
              profit before tax {rupees(trivial.total.profit_before_tax_gross)}, net assets{' '}
              {rupees(trivial.total.net_assets_gross)}
            </span>
            .
          </li>
        )}
        {settled.length > 0 && (
          <li>
            No longer uncorrected:{' '}
            {settled
              .map((entry) => `${entry.ref} (${STATE_LABEL[entry.state].toLowerCase()})`)
              .join(', ')}
            .
          </li>
        )}
      </ul>
    </Panel>
  )
}

function Request({ extract }: { extract: TcwgExtract }) {
  const { request } = extract
  return (
    <Panel id="tcwg-request" title="Request to correct">
      {request.applies ? (
        <blockquote className="border-l-4 border-slate-400 pl-4 text-base font-medium text-slate-900">
          {request.text}
        </blockquote>
      ) : (
        <p className="text-sm text-slate-700">{request.text}</p>
      )}
      <Explained summary="Where this request comes from">{request.basis}</Explained>
    </Panel>
  )
}

function Summary({ extract }: { extract: TcwgExtract }) {
  const { counts, evaluation_run: run } = extract
  const status = recordStatus(run.status)
  return (
    <Panel id="tcwg-summary" title="What is communicated">
      <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-xs tracking-wide text-slate-500 uppercase">
            Uncorrected misstatements
          </dt>
          <dd className="mt-1 text-base font-semibold tabular-nums">{counts.communicated}</dd>
        </div>
        <div>
          <dt className="text-xs tracking-wide text-slate-500 uppercase">Named individually</dt>
          <dd className="mt-1 text-base font-semibold tabular-nums">{counts.named_individually}</dd>
        </div>
        <div>
          <dt className="text-xs tracking-wide text-slate-500 uppercase">Other</dt>
          <dd className="mt-1 text-base font-semibold tabular-nums">{counts.other_uncorrected}</dd>
        </div>
        <div>
          <dt className="text-xs tracking-wide text-slate-500 uppercase">Could not be assessed</dt>
          <dd className="mt-1 text-base font-semibold tabular-nums">{counts.undetermined}</dd>
        </div>
      </dl>
      <p className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-slate-700">
        <span>Evaluation run:</span>
        <Pill tone={status.tone}>{status.text}</Pill>
        <span>{run.run_no === null ? run.detail : `run ${String(run.run_no)}: ${run.detail}`}</span>
      </p>
      <Explained summary="How this extract is prepared">{extract.basis}</Explained>
    </Panel>
  )
}

export function TcwgExtractPage({ id }: { id: string }) {
  const { resource, reload } = useResource(() => getTcwgExtract(id), `tcwg-extract:${id}`)
  const label = resource.state === 'ready' ? resource.data.engagement.label : null
  usePageTitle(label === null ? 'TCWG extract' : `TCWG extract · ${label}`)

  return (
    <section aria-labelledby="tcwg-heading">
      <nav aria-label="Breadcrumb" className="mb-3 text-sm text-slate-600 print:hidden">
        <a href={href({ name: 'engagements' })} className={LINK}>
          Engagements
        </a>
        <span aria-hidden="true"> / </span>
        <a href={href({ name: 'schedule', id })} className={LINK}>
          {label ?? 'Engagement'}
        </a>
        <span aria-hidden="true"> / </span>
        <span>TCWG extract</span>
      </nav>

      {resource.state === 'loading' && <Loading label="Loading the TCWG extract…" />}

      {resource.state === 'error' && (
        <ErrorState
          title="This TCWG extract could not be loaded"
          error={resource.error}
          onRetry={reload}
        />
      )}

      {resource.state === 'ready' && (
        <>
          <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <h1 id="tcwg-heading" className="text-xl font-semibold">
                  {resource.data.engagement.label}
                </h1>
                {resource.data.status === 'ready' ? (
                  <Pill tone="good">Ready to communicate</Pill>
                ) : (
                  <Pill tone="attention">Incomplete</Pill>
                )}
              </div>
              <p className="mt-1 text-sm text-slate-600">
                Uncorrected misstatements for communication to those charged with governance (SA 450
                paragraph 12)
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                window.print()
              }}
              className={`${SECONDARY} print:hidden`}
            >
              Print or save as PDF
            </button>
          </header>
          <div className="print:hidden">
            <EngagementNav id={id} current="tcwg-extract" />
          </div>

          {resource.data.status !== 'ready' && (
            <div
              role="alert"
              className="mt-5 rounded-md border border-amber-300 bg-amber-50 px-5 py-4 text-sm text-amber-900"
            >
              <p className="font-semibold">
                This extract is incomplete and is not fit to be communicated as it stands.
              </p>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {resource.data.incomplete_because.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-5 space-y-5">
            <Summary extract={resource.data} />
            <OpinionEffect extract={resource.data} />
            <Named extract={resource.data} />
            <Undetermined extract={resource.data} />
            <Other extract={resource.data} />
            <Totals extract={resource.data} />
            <PriorPeriod extract={resource.data} />
            <Outside extract={resource.data} />
            <Request extract={resource.data} />
          </div>
        </>
      )}
    </section>
  )
}
