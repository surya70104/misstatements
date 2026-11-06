// Load something from the backend and say where the load stands. A screen is always in
// exactly one of three states, so it can never show stale data as if it were current.
import { useCallback, useEffect, useRef, useState } from 'react'

export type Resource<T> =
  { state: 'loading' } | { state: 'ready'; data: T } | { state: 'error'; error: Error }

/**
 * Calls `load` when the component mounts, whenever `key` changes, and on `reload()`.
 * A load that finishes after the component has moved on is discarded.
 */
export function useResource<T>(
  load: () => Promise<T>,
  key: string,
): {
  resource: Resource<T>
  reload: () => void
  replace: (data: T) => void
  refresh: () => void
} {
  const [resource, setResource] = useState<Resource<T>>({ state: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const quiet = useRef(false)

  useEffect(() => {
    let current = true
    if (quiet.current) quiet.current = false
    else setResource({ state: 'loading' })
    load().then(
      (data) => {
        if (current) setResource({ state: 'ready', data })
      },
      (reason: unknown) => {
        if (!current) return
        const error = reason instanceof Error ? reason : new Error(String(reason))
        setResource({ state: 'error', error })
      },
    )
    return () => {
      current = false
    }
    // `load` is rebuilt on every render by its caller, so it is deliberately not a
    // dependency: `key` and `attempt` say when to load again.
  }, [key, attempt])

  const reload = useCallback(() => {
    setAttempt((value) => value + 1)
  }, [])

  // For a write whose answer is the record as it now stands: show that answer at once,
  // without a second read and without passing through the loading state.
  const replace = useCallback((data: T) => {
    setResource({ state: 'ready', data })
  }, [])

  // Read again after a write, keeping what is shown until the new answer arrives, so the
  // screen does not blank and a message about the write stays in view. If the read fails
  // the failure is shown: what was on the screen is no longer known to be current.
  const refresh = useCallback(() => {
    quiet.current = true
    setAttempt((value) => value + 1)
  }, [])

  return { resource, reload, replace, refresh }
}
