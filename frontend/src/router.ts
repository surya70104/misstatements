// A hash router with no dependency, the same shape the Working Paper Binder uses.
//   #/                                    the engagements
//   #/engagements/new                     create an engagement
//   #/engagements/<id>                    one engagement's schedule of misstatements
//   #/engagements/<id>/evaluation         the engagement's evaluation
//   #/engagements/<id>/tcwg-extract       its extract for those charged with governance
//   #/engagements/<id>/thresholds         its thresholds, their history and their revision
//   #/engagements/<id>/spine              its Financial Spine link and the reconciliation
//   #/engagements/<id>/events             its event trail
//   #/engagements/<id>/misstatements/new  record a misstatement
//   #/misstatements/<id>                  one misstatement's detail
import { useEffect, useState } from 'react'

// The screens that belong to one engagement, by the last part of their address.
const ENGAGEMENT_SCREENS = {
  evaluation: 'evaluation',
  'tcwg-extract': 'tcwg-extract',
  thresholds: 'thresholds',
  spine: 'spine',
  events: 'events',
  'misstatements/new': 'raise',
} as const

type EngagementScreen = (typeof ENGAGEMENT_SCREENS)[keyof typeof ENGAGEMENT_SCREENS]

export type Route =
  | { name: 'engagements' }
  | { name: 'new-engagement' }
  | { name: 'schedule'; id: string }
  | { name: EngagementScreen; id: string }
  | { name: 'misstatement'; id: string }

export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#/, '')
  if (path === '/engagements/new') return { name: 'new-engagement' }
  const schedule = /^\/engagements\/([^/]+)$/.exec(path)
  if (schedule?.[1]) return { name: 'schedule', id: decodeURIComponent(schedule[1]) }
  const screen = /^\/engagements\/([^/]+)\/(.+)$/.exec(path)
  if (screen?.[1] && screen[2] && screen[2] in ENGAGEMENT_SCREENS) {
    const name = ENGAGEMENT_SCREENS[screen[2] as keyof typeof ENGAGEMENT_SCREENS]
    return { name, id: decodeURIComponent(screen[1]) }
  }
  const misstatement = /^\/misstatements\/([^/]+)$/.exec(path)
  if (misstatement?.[1]) return { name: 'misstatement', id: decodeURIComponent(misstatement[1]) }
  // Anything unknown, the empty hash included, is the list: a mistyped address lands
  // somewhere useful and never on a blank page.
  return { name: 'engagements' }
}

export function href(route: Route): string {
  switch (route.name) {
    case 'engagements':
      return '#/'
    case 'new-engagement':
      return '#/engagements/new'
    case 'schedule':
      return `#/engagements/${encodeURIComponent(route.id)}`
    case 'misstatement':
      return `#/misstatements/${encodeURIComponent(route.id)}`
    case 'raise':
      return `#/engagements/${encodeURIComponent(route.id)}/misstatements/new`
    default:
      return `#/engagements/${encodeURIComponent(route.id)}/${route.name}`
  }
}

export function navigate(route: Route): void {
  window.location.hash = href(route)
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash))
  useEffect(() => {
    const onChange = () => {
      setRoute(parseRoute(window.location.hash))
    }
    window.addEventListener('hashchange', onChange)
    return () => {
      window.removeEventListener('hashchange', onChange)
    }
  }, [])
  return route
}
