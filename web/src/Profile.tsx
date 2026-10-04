import { useEffect, useState } from 'react'
import type { JobsApi } from './api'

const PLACEHOLDER = `Example:
Web developer from Cebu, 3 years of experience.
Skills: React, TypeScript, Laravel, WordPress (themes, Elementor), REST APIs, MySQL.
Recent work: rebuilt a Shopify store's landing pages; Laravel booking app for a clinic.
Portfolio: https://...
Looking for: full time or part time, remote, PH or US hours.
Expected rate: $6–10/hour.
Not interested in: sales, cold calling, video editing.`

/** Your profile: what Claude compares every job against. Stored in your private database. */
export function Profile({ api, onClose }: { api: JobsApi; onClose: () => void }) {
  const [content, setContent] = useState('')
  const [state, setState] = useState<'loading' | 'ready' | 'saving' | 'saved'>('loading')
  const [error, setError] = useState('')

  useEffect(() => {
    api.getProfile().then(
      (text) => {
        setContent(text)
        setState('ready')
      },
      (e: Error) => {
        setError(e.message)
        setState('ready')
      },
    )
  }, [api])

  async function save() {
    setState('saving')
    setError('')
    try {
      await api.saveProfile(content.trim())
      setState('saved')
    } catch (e) {
      setError((e as Error).message)
      setState('ready')
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>Your profile</h1>
        <button className="ghost" onClick={onClose}>
          Back to jobs
        </button>
      </header>
      <p className="muted">
        Claude compares every job against this. Be specific: skills, years, real projects, the hours and pay you
        want, and what you don't want. Don't include passwords, ID numbers or other private details.
      </p>
      <textarea
        className="profile"
        rows={14}
        placeholder={PLACEHOLDER}
        value={content}
        disabled={state === 'loading'}
        onChange={(e) => {
          setContent(e.target.value)
          if (state === 'saved') setState('ready')
        }}
      />
      <div className="actions">
        <button className="action on" onClick={() => void save()} disabled={state === 'loading' || state === 'saving'}>
          {state === 'saving' ? 'Saving…' : state === 'saved' ? 'Saved' : 'Save profile'}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </div>
  )
}
