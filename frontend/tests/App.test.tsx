import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from '../src/App'
import { failApi, mockApi } from './mockApi'

afterEach(() => {
  vi.unstubAllGlobals()
})

test('the shell renders its title and reports a healthy backend', async () => {
  mockApi({
    'GET /api/health': { status: 'ok', module: 'misstatements-rollup', version: '0.1.0' },
  })
  render(<App />)
  expect(screen.getByRole('link', { name: 'Misstatements Rollup' })).toBeInTheDocument()
  expect(screen.getByText('SA 450 · OAK Audit')).toBeInTheDocument()
  expect(await screen.findByText('Backend misstatements-rollup 0.1.0 is ok.')).toBeInTheDocument()
})

test('the shell says when the backend cannot be reached', async () => {
  failApi()
  render(<App />)
  expect(await screen.findByText('Backend unreachable: start it on port 8003.')).toBeInTheDocument()
})

test('a non-OK health answer counts as unreachable', async () => {
  mockApi({})
  render(<App />)
  expect(await screen.findByText('Backend unreachable: start it on port 8003.')).toBeInTheDocument()
})
