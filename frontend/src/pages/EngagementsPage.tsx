// The engagements: the way in to each engagement's schedule. Display only. Every value in
// the table is the backend's; the list does not ask the Financial Spine about each row, so a
// stored link is shown as recorded and is verified when the engagement is opened.
import { listEngagements, type Engagement } from '../api'
import { Empty, ErrorState, Loading, Pill } from '../components/states'
import { count, dateTime } from '../format'
import { href } from '../router'
import { usePageTitle } from '../usePageTitle'
import { useResource } from '../useResource'

function SpineLink({ engagement }: { engagement: Engagement }) {
  const { spine } = engagement
  if (spine.engagement_id === null) return <Pill>Not linked</Pill>
  if (spine.version_id === null) return <Pill tone="attention">Linked, no version pinned</Pill>
  return <Pill tone="good">Linked, version pinned</Pill>
}

function Row({ engagement }: { engagement: Engagement }) {
  return (
    <tr className="border-t border-slate-200 align-top hover:bg-slate-50">
      <th scope="row" className="min-w-56 px-4 py-3 text-left font-medium">
        <a
          href={href({ name: 'schedule', id: engagement.id })}
          className="text-slate-900 underline decoration-slate-300 underline-offset-2 hover:decoration-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
        >
          {engagement.label}
        </a>
      </th>
      <td className="px-4 py-3">
        <SpineLink engagement={engagement} />
      </td>
      <td className="px-4 py-3 text-right tabular-nums">{engagement.misstatements}</td>
      <td className="px-4 py-3">
        {engagement.current_threshold_id === null ? (
          <Pill tone="attention">Not set</Pill>
        ) : (
          <Pill tone="good">Set</Pill>
        )}
      </td>
      <td className="px-4 py-3 text-slate-700">{engagement.created_by}</td>
      <td className="px-4 py-3 whitespace-nowrap text-slate-700">
        <time dateTime={engagement.created_at}>{dateTime(engagement.created_at)}</time>
      </td>
    </tr>
  )
}

export function EngagementsPage() {
  const { resource, reload } = useResource(listEngagements, 'engagements')
  usePageTitle('Engagements')

  return (
    <section aria-labelledby="engagements-heading">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h1 id="engagements-heading" className="text-xl font-semibold">
          Engagements
        </h1>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          {resource.state === 'ready' && (
            <p className="text-sm text-slate-600">{count(resource.data.length, 'engagement')}</p>
          )}
          <a
            href={href({ name: 'new-engagement' })}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
          >
            New engagement
          </a>
        </div>
      </div>

      {resource.state === 'loading' && <Loading label="Loading the engagements…" />}

      {resource.state === 'error' && (
        <ErrorState
          title="The engagements could not be loaded"
          error={resource.error}
          onRetry={reload}
        />
      )}

      {resource.state === 'ready' && resource.data.length === 0 && (
        <Empty title="No engagements yet">
          Create one with “New engagement”. Once it exists it is listed here with its schedule of
          misstatements.
        </Empty>
      )}

      {resource.state === 'ready' && resource.data.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
          <table className="w-full min-w-[44rem] border-collapse text-sm">
            <caption className="sr-only">
              Engagements, each with its Financial Spine link, its number of misstatements and
              whether its thresholds are set
            </caption>
            <thead className="bg-slate-100 text-left text-xs tracking-wide text-slate-600 uppercase">
              <tr>
                <th scope="col" className="px-4 py-2 font-semibold">
                  Engagement
                </th>
                <th scope="col" className="px-4 py-2 font-semibold">
                  Financial Spine
                </th>
                <th scope="col" className="px-4 py-2 text-right font-semibold">
                  Misstatements
                </th>
                <th scope="col" className="px-4 py-2 font-semibold">
                  Thresholds
                </th>
                <th scope="col" className="px-4 py-2 font-semibold">
                  Created by
                </th>
                <th scope="col" className="px-4 py-2 font-semibold">
                  Created
                </th>
              </tr>
            </thead>
            <tbody>
              {resource.data.map((engagement) => (
                <Row key={engagement.id} engagement={engagement} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
