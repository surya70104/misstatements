// The generated working paper's fixtures, typed (SA 230; SA 450 paragraph 15; backend D66).
// Every one is the backend's real answer, produced and kept honest by
// backend/tests/test_frontend_fixtures.py: one engagement with every kind of record, read
// before a run, exported after one, read again, and after a further move.
import type { WorkingPaper, WorkingPaperExport, WorkingPaperSummary } from '../src/api'
import currentJson from './fixtures/working-paper-current.json'
import exportNoRunJson from './fixtures/working-paper-export-no-run.json'
import exportUnchangedJson from './fixtures/working-paper-export-unchanged.json'
import exportedJson from './fixtures/working-paper-exported.json'
import exportsJson from './fixtures/working-paper-exports.json'
import noRunJson from './fixtures/working-paper-no-run.json'
import readyJson from './fixtures/working-paper-ready.json'
import staleJson from './fixtures/working-paper-stale.json'

// Before any evaluation run: the paper generates, and cannot be exported.
export const noRun = noRunJson as unknown as WorkingPaper
// After a run: exportable, nothing registered yet.
export const ready = readyJson as unknown as WorkingPaper
// After the export: the latest registered paper matches.
export const current = currentJson as unknown as WorkingPaper
// After a further move: the export is stale and a new run is needed.
export const stale = staleJson as unknown as WorkingPaper

// The backend's answer to the export, and the registrations.
export const exported = exportedJson as unknown as WorkingPaperExport
export const registrations = exportsJson as unknown as WorkingPaperSummary[]

// The backend's refusals, with the status each was sent with.
export const refusals = {
  noRun: { status: 409, body: exportNoRunJson },
  unchanged: { status: 409, body: exportUnchangedJson },
}

export function paperPath(paper: WorkingPaper): string {
  return `GET /api/engagements/${paper.engagement.id}/working-paper`
}

export function exportsPath(paper: WorkingPaper): string {
  return `GET /api/engagements/${paper.engagement.id}/working-paper/exports`
}

export function exportPath(paper: WorkingPaper): string {
  return `POST /api/engagements/${paper.engagement.id}/working-paper/export`
}
