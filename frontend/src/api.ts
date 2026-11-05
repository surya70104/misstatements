// Typed client for the Misstatements Rollup API. Display only: every rule lives in the
// backend. Stage 0 knows the health check alone; the engagement, schedule and evaluation
// calls arrive with their stages.

export type Health = { status: string; module: string; version: string }

export class ApiError extends Error {
  readonly status: number

  constructor(path: string, status: number) {
    super(`${path} answered ${String(status)}`)
    this.status = status
  }
}

export async function getHealth(): Promise<Health> {
  const response = await fetch('/api/health')
  if (!response.ok) {
    throw new ApiError('/api/health', response.status)
  }
  return (await response.json()) as Health
}
