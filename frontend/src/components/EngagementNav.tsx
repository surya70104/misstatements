// The screens of one engagement, as tabs. Every one of them is reached from every other, so
// a person never has to go back to the list to move within an engagement.
import { href, type Route } from '../router'

type Tab =
  | 'schedule'
  | 'evaluation'
  | 'tcwg-extract'
  | 'rep-letter-attachment'
  | 'working-paper'
  | 'thresholds'
  | 'spine'
  | 'events'

const TABS: { name: Tab; label: string }[] = [
  { name: 'schedule', label: 'Schedule' },
  { name: 'evaluation', label: 'Evaluation' },
  { name: 'tcwg-extract', label: 'TCWG extract' },
  { name: 'rep-letter-attachment', label: 'Representation attachment' },
  { name: 'working-paper', label: 'Working paper' },
  { name: 'thresholds', label: 'Thresholds' },
  { name: 'spine', label: 'Financial Spine' },
  { name: 'events', label: 'Events' },
]

export function EngagementNav({ id, current }: { id: string; current: Tab }) {
  return (
    <nav aria-label="Engagement" className="mt-4 border-b border-slate-200">
      <ul className="-mb-px flex flex-wrap gap-x-1 text-sm">
        {TABS.map((tab) => {
          const route: Route = { name: tab.name, id }
          return (
            <li key={tab.name}>
              <a
                href={href(route)}
                aria-current={tab.name === current ? 'page' : undefined}
                className="inline-block border-b-2 border-transparent px-3 py-2 text-slate-700 hover:border-slate-300 hover:text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-slate-700 aria-[current=page]:border-slate-800 aria-[current=page]:font-semibold aria-[current=page]:text-slate-900"
              >
                {tab.label}
              </a>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
