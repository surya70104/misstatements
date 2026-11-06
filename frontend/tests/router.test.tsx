import { act, render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'

import { href, navigate, parseRoute, useRoute, type Route } from '../src/router'

afterEach(() => {
  window.location.hash = ''
})

const ID = 'e953ca10-f25d-459e-9147-74b708daed71'

test('the empty address and the root are the engagements', () => {
  expect(parseRoute('')).toEqual({ name: 'engagements' })
  expect(parseRoute('#')).toEqual({ name: 'engagements' })
  expect(parseRoute('#/')).toEqual({ name: 'engagements' })
})

test('an engagement address is its schedule', () => {
  expect(parseRoute(`#/engagements/${ID}`)).toEqual({ name: 'schedule', id: ID })
})

test('an engagement’s evaluation has its own address under the engagement', () => {
  expect(parseRoute(`#/engagements/${ID}/evaluation`)).toEqual({ name: 'evaluation', id: ID })
  expect(href({ name: 'evaluation', id: ID })).toBe(`#/engagements/${ID}/evaluation`)
  expect(parseRoute(href({ name: 'evaluation', id: 'a/b c?d#e' }))).toEqual({
    name: 'evaluation',
    id: 'a/b c?d#e',
  })
  // Close to the address, but not it.
  for (const hash of [
    `#/engagements/${ID}/evaluation/`,
    `#/engagements/${ID}/evaluation/runs`,
    `#/engagements/${ID}/evaluations`,
    '#/engagements//evaluation',
  ]) {
    expect(parseRoute(hash)).toEqual({ name: 'engagements' })
  }
})

test('each screen of an engagement has its own address under the engagement', () => {
  const screens = {
    thresholds: `#/engagements/${ID}/thresholds`,
    spine: `#/engagements/${ID}/spine`,
    events: `#/engagements/${ID}/events`,
    raise: `#/engagements/${ID}/misstatements/new`,
  } as const
  for (const [name, address] of Object.entries(screens)) {
    const route = { name: name as keyof typeof screens, id: ID }
    expect(parseRoute(address)).toEqual(route)
    expect(href(route)).toBe(address)
  }
  // An identifier with awkward characters survives the round trip on every one of them.
  for (const name of Object.keys(screens) as (keyof typeof screens)[]) {
    const route = { name, id: 'a/b c?d#e' }
    expect(parseRoute(href(route))).toEqual(route)
  }
})

test('creating an engagement has an address of its own, not an engagement named new', () => {
  expect(parseRoute('#/engagements/new')).toEqual({ name: 'new-engagement' })
  expect(href({ name: 'new-engagement' })).toBe('#/engagements/new')
  expect(parseRoute('#/engagements/new/')).toEqual({ name: 'engagements' })
})

test('a misstatement address is its detail', () => {
  expect(parseRoute(`#/misstatements/${ID}`)).toEqual({ name: 'misstatement', id: ID })
})

test('an address that is not a screen falls back to the engagements', () => {
  for (const hash of [
    '#/misstatements',
    '#/misstatements/',
    `#/misstatements/${ID}/versions`,
    '#/engagements',
    '#/engagements/',
    `#/engagements/${ID}/`,
    `#/engagements/${ID}/unknown`,
    '#/nowhere',
    '#engagements/1',
    '#/ENGAGEMENTS/1',
  ]) {
    expect(parseRoute(hash)).toEqual({ name: 'engagements' })
  }
})

test('every route has one address, and the address leads back to the route', () => {
  const routes: Route[] = [
    { name: 'engagements' },
    { name: 'schedule', id: ID },
    { name: 'schedule', id: 'a/b c?d#e' },
    { name: 'misstatement', id: ID },
    { name: 'misstatement', id: 'a/b c?d#e' },
  ]
  expect(href({ name: 'engagements' })).toBe('#/')
  expect(href({ name: 'schedule', id: ID })).toBe(`#/engagements/${ID}`)
  expect(href({ name: 'schedule', id: 'a/b c?d#e' })).toBe('#/engagements/a%2Fb%20c%3Fd%23e')
  expect(href({ name: 'misstatement', id: ID })).toBe(`#/misstatements/${ID}`)
  for (const route of routes) {
    expect(parseRoute(href(route))).toEqual(route)
  }
})

function Where() {
  const route = useRoute()
  return <p>{'id' in route ? `${route.name} ${route.id}` : route.name}</p>
}

test('the screen follows the address as it changes', async () => {
  render(<Where />)
  expect(screen.getByText('engagements')).toBeInTheDocument()
  act(() => {
    navigate({ name: 'schedule', id: ID })
  })
  expect(await screen.findByText(`schedule ${ID}`)).toBeInTheDocument()
  expect(window.location.hash).toBe(`#/engagements/${ID}`)
  act(() => {
    navigate({ name: 'misstatement', id: ID })
  })
  expect(await screen.findByText(`misstatement ${ID}`)).toBeInTheDocument()
  expect(window.location.hash).toBe(`#/misstatements/${ID}`)
  act(() => {
    navigate({ name: 'engagements' })
  })
  expect(await screen.findByText('engagements')).toBeInTheDocument()
})

test('a screen opened on an address starts there', () => {
  window.location.hash = `#/engagements/${ID}`
  render(<Where />)
  expect(screen.getByText(`schedule ${ID}`)).toBeInTheDocument()
})
