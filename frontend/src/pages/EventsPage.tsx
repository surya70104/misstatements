// The event trail of one engagement (architecture D13): an append-only record of what was
// decided about the engagement as a whole: a threshold revision and its recompute, a
// reassessment of materiality, the partner's acknowledgement, the answer to the strategy
// prompt, a conclusion. Read as the backend returns it, oldest first; nothing is ever
// changed or removed. The moves of a single misstatement are not events: they are the
// versions listed on its own page.
import { getEngagement, listEvents, type Engagement, type ModuleEvent } from '../api'
import { Breadcrumb, EngagementHeader } from '../components/EngagementHeader'
import { Panel } from '../components/panels'
import { Empty, ErrorState, Loading } from '../components/states'
import { count, dateTime } from '../format'
import { eventKindLabel } from '../labels'
import { usePageTitle } from '../usePageTitle'
import { useResource } from '../useResource'

type Loaded = { engagement: Engagement; events: ModuleEvent[] }

async function load(id: string): Promise<Loaded> {
  const [engagement, events] = await Promise.allSettled([getEngagement(id), listEvents(id)])
  if (engagement.status === 'rejected') throw engagement.reason
  if (events.status === 'rejected') throw events.reason
  return { engagement: engagement.value, events: events.value }
}

/** A payload value as it was recorded: text as text, anything else as the JSON it is. */
function recorded(value: unknown): string {
  return typeof value === 'string' ? value : JSON.stringify(value)
}

function Payload({ event }: { event: ModuleEvent }) {
  const entries = Object.entries(event.payload)
  if (entries.length === 0) return <span className="text-slate-600">Nothing recorded.</span>
  return (
    <details>
      <summary className="cursor-pointer text-slate-700 underline decoration-slate-300 underline-offset-2">
        What was recorded<span className="sr-only"> with event {event.seq}</span>
      </summary>
      <dl className="mt-2 space-y-1">
        {entries.map(([key, value]) => (
          <div key={key} className="grid gap-x-3 sm:grid-cols-[12rem_minmax(0,1fr)]">
            <dt className="text-xs text-slate-500">{key}</dt>
            <dd className="text-xs break-words text-slate-800">{recorded(value)}</dd>
          </div>
        ))}
      </dl>
    </details>
  )
}

export function EventsPage({ id }: { id: string }) {
  const { resource, reload } = useResource(() => load(id), `events:${id}`)
  const label = resource.state === 'ready' ? resource.data.engagement.label : null
  usePageTitle(label === null ? 'Events' : `Events · ${label}`)

  return (
    <section aria-labelledby="events-heading">
      <Breadcrumb id={id} label={label} here="Events" />

      {resource.state === 'loading' && <Loading label="Loading the events…" />}
      {resource.state === 'error' && (
        <ErrorState
          title="The events could not be loaded"
          error={resource.error}
          onRetry={reload}
        />
      )}

      {resource.state === 'ready' && (
        <>
          <EngagementHeader
            id={id}
            label={resource.data.engagement.label}
            headingId="events-heading"
            screen="Event trail"
            tab="events"
          />
          <div className="mt-5">
            {resource.data.events.length === 0 ? (
              <Empty title="No events recorded">
                An event is recorded when thresholds are revised, materiality is reassessed before
                an evaluation, the soft gate is acknowledged, the strategy prompt is answered or a
                conclusion is recorded.
              </Empty>
            ) : (
              <Panel id="trail" title={count(resource.data.events.length, 'event')}>
                <ol aria-label="Events, oldest first" className="space-y-4">
                  {resource.data.events.map((event) => (
                    <li
                      key={event.id}
                      className="border-t border-slate-200 pt-4 text-sm first:border-t-0 first:pt-0"
                    >
                      <p className="font-medium">{eventKindLabel(event.kind)}</p>
                      <p className="text-slate-700">
                        by {event.actor}, <time dateTime={event.at}>{dateTime(event.at)}</time>
                        <span className="text-xs text-slate-500"> · {event.kind}</span>
                      </p>
                      <div className="mt-1">
                        <Payload event={event} />
                      </div>
                    </li>
                  ))}
                </ol>
              </Panel>
            )}
          </div>
        </>
      )}
    </section>
  )
}
