import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { ApiError } from '../src/api'
import { Empty, ErrorState, Loading, Pill } from '../src/components/states'

test('loading is announced politely', () => {
  render(<Loading />)
  const status = screen.getByRole('status')
  expect(status).toHaveTextContent('Loading…')
  expect(status).toHaveAttribute('aria-live', 'polite')
})

test('loading can say what is being loaded', () => {
  render(<Loading label="Loading the schedule…" />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading the schedule…')
})

test('an empty state has a title and, when given, an explanation', () => {
  const { rerender } = render(<Empty title="Nothing raised yet" />)
  expect(screen.getByText('Nothing raised yet')).toBeInTheDocument()
  rerender(<Empty title="Nothing raised yet">Raise one from a working paper.</Empty>)
  expect(screen.getByText('Raise one from a working paper.')).toBeInTheDocument()
})

test('a refusal shows the backend’s words and the request it came from', () => {
  render(<ErrorState error={new ApiError('/api/engagements/x', 404, 'no engagement x')} />)
  const alert = screen.getByRole('alert')
  expect(alert).toHaveTextContent('This could not be loaded')
  expect(alert).toHaveTextContent('no engagement x')
  expect(alert).toHaveTextContent('/api/engagements/x answered 404')
  expect(screen.queryByRole('button')).not.toBeInTheDocument() // no retry was offered
})

test('a pending decision is named beside the request', () => {
  render(
    <ErrorState error={new ApiError('/api/engagements/x/spine-link', 409, 'not decided', 'B10')} />,
  )
  expect(screen.getByRole('alert')).toHaveTextContent(
    '/api/engagements/x/spine-link answered 409 · pending decision B10',
  )
})

test('an unreachable backend shows no request line, which would mislead', () => {
  render(<ErrorState error={new ApiError('/api/engagements', 0)} />)
  const alert = screen.getByRole('alert')
  expect(alert).toHaveTextContent('The backend could not be reached.')
  expect(alert).not.toHaveTextContent('answered')
})

test('an error that did not come from the API is shown as it is', () => {
  render(<ErrorState title="The page failed" error={new Error('something else')} />)
  const alert = screen.getByRole('alert')
  expect(alert).toHaveTextContent('The page failed')
  expect(alert).toHaveTextContent('something else')
})

test('trying again calls back once per click', () => {
  const retry = vi.fn()
  render(<ErrorState error={new ApiError('/api/x', 500)} onRetry={retry} />)
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(retry).toHaveBeenCalledTimes(1)
})

test('a pill carries its meaning in words', () => {
  render(
    <>
      <Pill>Not linked</Pill>
      <Pill tone="good">Set</Pill>
      <Pill tone="attention">Not set</Pill>
    </>,
  )
  expect(screen.getByText('Not linked')).toBeInTheDocument()
  expect(screen.getByText('Set')).toBeInTheDocument()
  expect(screen.getByText('Not set')).toBeInTheDocument()
})
