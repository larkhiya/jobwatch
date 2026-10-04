import type { SupabaseClient } from '@supabase/supabase-js'
import { useState, type FormEvent } from 'react'

/**
 * Passwordless sign-in. Supabase emails you a one-time code (and a link).
 *
 * The code matters on iPhone: an app added to the Home Screen keeps its login separate
 * from Safari, so tapping the emailed link would sign in Safari instead of the app.
 * Typing the code into the app signs in the app itself.
 */
export function Login({ client }: { client: SupabaseClient }) {
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [step, setStep] = useState<'email' | 'code'>('email')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function sendCode(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    const { error } = await client.auth.signInWithOtp({
      email: email.trim(),
      options: { emailRedirectTo: window.location.origin + import.meta.env.BASE_URL },
    })
    setBusy(false)
    if (error) setError(error.message)
    else setStep('code')
  }

  async function verifyCode(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    const { error } = await client.auth.verifyOtp({ email: email.trim(), token: code.trim(), type: 'email' })
    setBusy(false)
    if (error) setError(error.message) // on success, App sees the new session and switches screens
  }

  return (
    <main className="panel">
      <h1>jobwatch</h1>
      {step === 'email' ? (
        <form onSubmit={sendCode}>
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <button type="submit" disabled={busy}>
            {busy ? 'Sending…' : 'Email me a sign-in code'}
          </button>
        </form>
      ) : (
        <form onSubmit={verifyCode}>
          <p>
            We emailed a code to <strong>{email}</strong>. Type it here. (In a normal browser tab, tapping the link
            in the email works too.)
          </p>
          <label htmlFor="code">Code</label>
          <input
            id="code"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{6,10}"
            required
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
          />
          <button type="submit" disabled={busy}>
            {busy ? 'Checking…' : 'Sign in'}
          </button>
          <button type="button" className="ghost" onClick={() => setStep('email')}>
            Use a different email
          </button>
        </form>
      )}
      {error && <p className="error">{error}</p>}
    </main>
  )
}
