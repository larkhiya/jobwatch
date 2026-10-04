import type { SupabaseClient } from '@supabase/supabase-js'
import { useState, type FormEvent } from 'react'

/** Passwordless sign-in: Supabase emails you a link, and opening it signs you in. */
export function Login({ client }: { client: SupabaseClient }) {
  const [email, setEmail] = useState('')
  const [state, setState] = useState<'idle' | 'sending' | 'sent'>('idle')
  const [error, setError] = useState('')

  async function sendLink(event: FormEvent) {
    event.preventDefault()
    setState('sending')
    setError('')
    const { error } = await client.auth.signInWithOtp({
      email: email.trim(),
      options: { emailRedirectTo: window.location.origin + import.meta.env.BASE_URL },
    })
    if (error) {
      setError(error.message)
      setState('idle')
    } else {
      setState('sent')
    }
  }

  return (
    <main className="panel">
      <h1>jobwatch</h1>
      {state === 'sent' ? (
        <p>
          Check <strong>{email}</strong> for a sign-in link. You can open it on this device or your phone.
        </p>
      ) : (
        <form onSubmit={sendLink}>
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <button type="submit" disabled={state === 'sending'}>
            {state === 'sending' ? 'Sending…' : 'Email me a sign-in link'}
          </button>
          {error && <p className="error">{error}</p>}
        </form>
      )}
    </main>
  )
}
