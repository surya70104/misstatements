// Sending one write and saying where it stands. A write goes out once: while it is in
// flight a second call sends nothing, even one made before the screen has re-rendered its
// button as disabled. A failure is kept so the screen can show it in the backend's words.
import { useCallback, useRef, useState } from 'react'

export type Sent<T> = { ok: true; value: T } | { ok: false }

export function useSubmit(): {
  submitting: boolean
  error: Error | null
  submit: <T>(send: () => Promise<T>) => Promise<Sent<T>>
  clearError: () => void
} {
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const inFlight = useRef(false)

  const submit = useCallback(async <T>(send: () => Promise<T>): Promise<Sent<T>> => {
    if (inFlight.current) return { ok: false }
    inFlight.current = true
    setSubmitting(true)
    setError(null)
    try {
      return { ok: true, value: await send() }
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error(String(caught)))
      return { ok: false }
    } finally {
      inFlight.current = false
      setSubmitting(false)
    }
  }, [])

  const clearError = useCallback(() => {
    setError(null)
  }, [])

  return { submitting, error, submit, clearError }
}
