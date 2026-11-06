// The computed effects (spec section 3.1): on profit before tax, on net assets and on each
// caption, with the backend's own explanation of each figure. Every figure is the backend's.
// An effect it could not determine is disclosed with its reason and never shown as nil.
import type { Band, Classification, Effects, Misstatement } from '../../api'
import { count, NOT_AVAILABLE, rupees } from '../../format'
import { BAND_LABEL, BAND_TONE, natureLabel, sectionLabel } from '../../labels'
import { Pill } from '../states'
import { Basis, Panel, Unavailable } from '../panels'

function Effect({
  name,
  value,
  band,
  basis,
  unresolved,
}: {
  name: string
  value: string | null
  band: Band | null
  basis: string
  unresolved: string[]
}) {
  return (
    <div className="rounded border border-slate-200 px-4 py-3">
      <h3 className="text-xs tracking-wide text-slate-500 uppercase">{name}</h3>
      {value === null ? (
        <p className="mt-1 text-sm font-medium text-amber-900">
          Not available
          <span className="mt-1 block font-normal">
            {unresolved.length > 0
              ? `These ledgers cannot be classified: ${unresolved.join(', ')}.`
              : 'The backend could not determine this effect.'}
          </span>
        </p>
      ) : (
        <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="text-lg font-semibold tabular-nums">{rupees(value)}</span>
          {band !== null && <Pill tone={BAND_TONE[band]}>{BAND_LABEL[band]}</Pill>}
        </p>
      )}
      <Basis>{basis}</Basis>
    </div>
  )
}

function Captions({ effects }: { effects: Effects }) {
  if (effects.captions.length === 0) return null
  return (
    <div className="mt-5">
      <h3 className="text-xs font-semibold tracking-wide text-slate-600 uppercase">
        Effect on each caption
      </h3>
      <table className="mt-2 w-full max-w-3xl border-collapse text-sm">
        <caption className="sr-only">Effect on each Schedule III caption, debit positive</caption>
        <thead className="bg-slate-100 text-left text-xs tracking-wide text-slate-600 uppercase">
          <tr>
            <th scope="col" className="px-3 py-2 font-semibold">
              Schedule III head
            </th>
            <th scope="col" className="px-3 py-2 font-semibold max-sm:hidden">
              Statement
            </th>
            <th scope="col" className="px-3 py-2 text-right font-semibold">
              Movement, debit positive
            </th>
          </tr>
        </thead>
        <tbody>
          {effects.captions.map((caption, index) => (
            <tr
              key={`${caption.head_id ?? 'none'}-${String(index)}`}
              className="border-t border-slate-200"
            >
              <th scope="row" className="px-3 py-2 text-left font-normal break-all">
                {caption.head_id ?? 'Not mapped'}
              </th>
              <td className="px-3 py-2 max-sm:hidden">
                {natureLabel(caption.nature) ?? NOT_AVAILABLE}
              </td>
              <td className="px-3 py-2 text-right whitespace-nowrap tabular-nums">
                {rupees(caption.signed)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function place(where: { head_id: string | null; section: string | null }): string {
  return `${where.head_id ?? 'not mapped'} (${sectionLabel(where.section) ?? 'no section'})`
}

function ClassificationNote({ classification }: { classification: Classification }) {
  const { drift, unmatched, effects_on_current_classification: now } = classification
  const changed = drift.length > 0 || unmatched.length > 0
  return (
    <div className="mt-5 border-t border-slate-200 pt-4 text-sm">
      <h3 className="text-xs font-semibold tracking-wide text-slate-600 uppercase">
        Classification the effects are computed on
      </h3>
      <p className="mt-2 text-slate-700">
        The classification recorded when this version was raised
        {classification.tree_version_at_raise !== null &&
          ` (Schedule III tree ${classification.tree_version_at_raise})`}
        . A later change in the Financial Spine does not change these effects.
      </p>
      {!changed && (
        <p className="mt-1 text-slate-600">
          The Financial Spine classifies every line the same way now.
        </p>
      )}
      {changed && (
        <div className="mt-3 rounded border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900">
          {drift.length > 0 && (
            <>
              <p className="font-medium">
                The Financial Spine now classifies {count(drift.length, 'ledger')} differently.
              </p>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {drift.map((entry) => (
                  <li key={entry.position}>
                    {entry.ledger_name}: {place(entry.snapshot)} when raised, {place(entry.live)}{' '}
                    now.
                  </li>
                ))}
              </ul>
            </>
          )}
          {unmatched.length > 0 && (
            <p className="mt-2">
              Not matched to a ledger in the Financial Spine now: {unmatched.join(', ')}.
            </p>
          )}
          {now !== null && (
            <p className="mt-2">
              On the current classification the effects would be{' '}
              <span className="tabular-nums">{rupees(now.profit_before_tax)}</span> on profit before
              tax and <span className="tabular-nums">{rupees(now.net_assets)}</span> on net assets.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export function FinancialEffects({ misstatement }: { misstatement: Misstatement }) {
  const { effects, classification, banding, band, band_basis: bandBasis, spine } = misstatement

  return (
    <Panel id="effects" title="Financial effects">
      {effects === null ? (
        <Unavailable what="The effects are not available." why={spine.detail} />
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <Effect
              name="Effect on profit before tax"
              value={effects.profit_before_tax}
              band={banding.bands?.profit ?? null}
              basis={effects.profit_basis}
              unresolved={effects.unresolved}
            />
            <Effect
              name="Effect on net assets"
              value={effects.net_assets}
              band={banding.bands?.net_assets ?? null}
              basis={effects.net_assets_basis}
              unresolved={effects.unresolved}
            />
          </div>
          {effects.classification_only && (
            <p className="mt-3 text-sm text-slate-700">
              <Pill>Classification only</Pill>
              <span className="ml-2">
                This entry moves balances between captions and has no effect on profit before tax or
                on net assets.
              </span>
            </p>
          )}
          <Captions effects={effects} />
        </>
      )}

      <div className="mt-5 border-t border-slate-200 pt-4">
        <h3 className="text-xs font-semibold tracking-wide text-slate-600 uppercase">
          Materiality band
        </h3>
        <p className="mt-2 text-sm">
          {band === null ? (
            <Pill tone="attention">Not banded</Pill>
          ) : (
            <Pill tone={BAND_TONE[band]}>{BAND_LABEL[band]}</Pill>
          )}
          {banding.projected && (
            <span className="ml-2 text-slate-700">
              Projected from a sample: not a factual misstatement.
            </span>
          )}
        </p>
        {bandBasis !== null && <Basis>{bandBasis}</Basis>}
      </div>

      {classification !== null && <ClassificationNote classification={classification} />}
    </Panel>
  )
}
