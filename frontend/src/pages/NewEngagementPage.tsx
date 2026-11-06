// Create an engagement (architecture D8): how the firm names it and, optionally, the
// Financial Spine engagement and version it works on. The backend checks the link with the
// Spine and refuses one that does not exist; the link can also be set later.
import { useState, type SyntheticEvent } from 'react'

import { createEngagement, type EngagementInput } from '../api'
import { Field, INPUT, LINK_BUTTON, PRIMARY } from '../components/forms'
import { Panel } from '../components/panels'
import { ErrorState } from '../components/states'
import { href, navigate } from '../router'
import { usePageTitle } from '../usePageTitle'
import { useSubmit } from '../useSubmit'

const LINK = 'underline decoration-slate-300 underline-offset-2 hover:decoration-slate-700'

export function NewEngagementPage() {
  usePageTitle('New engagement')
  const [label, setLabel] = useState('')
  const [spineEngagement, setSpineEngagement] = useState('')
  const [spineVersion, setSpineVersion] = useState('')
  const { submitting, error, submit } = useSubmit()

  async function create(event: SyntheticEvent) {
    event.preventDefault()
    if (label.trim() === '') return
    const body: EngagementInput = {
      label: label.trim(),
      spine_engagement_id: spineEngagement.trim() === '' ? null : spineEngagement.trim(),
      spine_version_id: spineVersion.trim() === '' ? null : spineVersion.trim(),
    }
    const sent = await submit(() => createEngagement(body))
    if (sent.ok) navigate({ name: 'schedule', id: sent.value.id })
  }

  return (
    <section aria-labelledby="new-engagement-heading">
      <nav aria-label="Breadcrumb" className="mb-3 text-sm text-slate-600">
        <a href={href({ name: 'engagements' })} className={LINK}>
          Engagements
        </a>
        <span aria-hidden="true"> / </span>
        <span>New engagement</span>
      </nav>
      <h1 id="new-engagement-heading" className="text-xl font-semibold">
        New engagement
      </h1>

      <div className="mt-5 max-w-3xl">
        <Panel id="engagement-form" title="Engagement">
          <form
            aria-label="New engagement"
            onSubmit={(event) => {
              void create(event)
            }}
            className="space-y-4"
          >
            <Field id="engagement-label" label="Name" required hint="How the firm names it.">
              <input
                id="engagement-label"
                value={label}
                required
                maxLength={200}
                disabled={submitting}
                aria-describedby="engagement-label-hint"
                onChange={(event) => {
                  setLabel(event.target.value)
                }}
                className={INPUT}
              />
            </Field>
            <Field
              id="engagement-spine"
              label="Financial Spine engagement"
              hint="The identifier of the engagement in the Financial Spine. It can be set later."
            >
              <input
                id="engagement-spine"
                value={spineEngagement}
                disabled={submitting}
                aria-describedby="engagement-spine-hint"
                onChange={(event) => {
                  setSpineEngagement(event.target.value)
                }}
                className={`${INPUT} font-mono`}
              />
            </Field>
            <Field
              id="engagement-version"
              label="Financial Spine version"
              hint="The version of that engagement this work is on. Misstatements can be recorded only once a version is pinned."
            >
              <input
                id="engagement-version"
                value={spineVersion}
                disabled={submitting}
                aria-describedby="engagement-version-hint"
                onChange={(event) => {
                  setSpineVersion(event.target.value)
                }}
                className={`${INPUT} font-mono`}
              />
            </Field>

            {error !== null && <ErrorState title="The engagement was not created" error={error} />}

            <div className="flex flex-wrap gap-2">
              <button
                type="submit"
                disabled={submitting || label.trim() === ''}
                className={PRIMARY}
              >
                {submitting ? 'Creating…' : 'Create engagement'}
              </button>
              <a href={href({ name: 'engagements' })} className={LINK_BUTTON}>
                Cancel
              </a>
            </div>
          </form>
        </Panel>
      </div>
    </section>
  )
}
