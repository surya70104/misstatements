import { afterEach, expect, test, vi } from 'vitest'

import { ApiError, getHealth } from '../src/api'
import { mockApi } from './mockApi'

afterEach(() => {
  vi.unstubAllGlobals()
})

test('getHealth returns the backend answer', async () => {
  mockApi({ 'GET /api/health': { status: 'ok', module: 'misstatements-rollup', version: '0.1.0' } })
  await expect(getHealth()).resolves.toEqual({
    status: 'ok',
    module: 'misstatements-rollup',
    version: '0.1.0',
  })
})

test('getHealth throws an ApiError carrying the status', async () => {
  mockApi({})
  await expect(getHealth()).rejects.toBeInstanceOf(ApiError)
  await expect(getHealth()).rejects.toMatchObject({ status: 404 })
})
