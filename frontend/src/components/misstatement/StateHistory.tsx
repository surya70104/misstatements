// The state trail (spec sections 3.3 and 10.2). A misstatement is append-only: every move
// adds a version and no version is ever changed, so the versions are the history. Each
// entry says which state was recorded, who recorded it and when, with the reason where the
// move carries one.
import type { Misstatement, MisstatementVersion } from '../../api'
import { dateTime } from '../../format'
import { STATE_LABEL, STATE_TONE } from '../../labels'
import { Pill } from '../states'
import { Panel } from '../panels'

/** When the move this version records took place. */
function movedAt(version: MisstatementVersion): string {
  if (version.state === 'raised') return version.created_at
  if (version.state === 'communicated') return version.communicated_at ?? version.created_at
  return version.decided_at ?? version.created_at
}

function Entry({ version }: { version: MisstatementVersion }) {
  const at = movedAt(version)
  return (
    <li className="relative border-l-2 border-slate-200 pb-5 pl-5 last:pb-0">
      <span
        aria-hidden="true"
        className="absolute top-1.5 -left-[5px] h-2 w-2 rounded-full bg-slate-400"
      />
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
        <Pill tone={STATE_TONE[version.state]}>{STATE_LABEL[version.state]}</Pill>
        <span className="text-slate-800">by {version.created_by}</span>
        <time dateTime={at} className="text-slate-600">
          {dateTime(at)}
        </time>
        <span className="text-xs text-slate-500">version {version.version_no}</span>
      </p>
      {version.state === 'refused' && version.refusal_reason !== null && (
        <p className="mt-1 text-sm text-slate-800">
          <span className="text-slate-500">Reason for refusal: </span>
          {version.refusal_reason}
        </p>
      )}
      {version.state === 'withdrawn' && version.withdrawal_reason !== null && (
        <p className="mt-1 text-sm text-slate-800">
          <span className="text-slate-500">Reason for withdrawal: </span>
          {version.withdrawal_reason}
        </p>
      )}
    </li>
  )
}

function Consistency({ misstatement }: { misstatement: Misstatement }) {
  const { state_consistency: consistency } = misstatement
  if (consistency.consistent === true) return null
  if (consistency.consistent === null) {
    return (
      <p className="mt-4 rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        The Financial Spine could not be read, so this state could not be compared with the
        adjustment it holds.
      </p>
    )
  }
  return (
    <p
      role="alert"
      className="mt-4 rounded border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      <span className="font-medium">This state differs from the Financial Spine. </span>
      {consistency.detail}
    </p>
  )
}

export function StateHistory({ misstatement }: { misstatement: Misstatement }) {
  // Reading one misstatement always carries its versions; the current one alone is the
  // fallback so the trail is never empty.
  const versions = misstatement.versions ?? [misstatement.current]
  return (
    <Panel id="history" title="State history">
      <ol aria-label="State history" className="ml-1">
        {versions.map((version) => (
          <Entry key={version.version_no} version={version} />
        ))}
      </ol>
      <Consistency misstatement={misstatement} />
    </Panel>
  )
}
