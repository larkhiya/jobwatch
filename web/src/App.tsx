import type { Session, SupabaseClient } from '@supabase/supabase-js'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { demoApi, supabaseApi, type JobsApi } from './api'
import { Inbox } from './Inbox'
import { Login } from './Login'
import { supabase } from './supabase'

export default function App() {
  return supabase ? <SignedInApp client={supabase} /> : <DemoApp />
}

function DemoApp() {
  const api = useMemo(() => demoApi(), [])
  return <Inbox api={api} banner="Demo data: Supabase isn't configured yet, and changes reset on reload." />
}

function SignedInApp({ client }: { client: SupabaseClient }) {
  const [session, setSession] = useState<Session | null | undefined>(undefined)
  const api = useMemo(() => supabaseApi(client), [client])

  useEffect(() => {
    client.auth.getSession().then(({ data }) => setSession(data.session))
    const { data } = client.auth.onAuthStateChange((_event, newSession) => setSession(newSession))
    return () => data.subscription.unsubscribe()
  }, [client])

  if (session === undefined) return <p className="center muted">Loading…</p>
  if (!session) return <Login client={client} />

  const email = session.user.email ?? 'your account'
  const signOut = () => void client.auth.signOut()
  return (
    <AllowListGate api={api} email={email} onSignOut={signOut}>
      <Inbox api={api} email={email} onSignOut={signOut} />
    </AllowListGate>
  )
}

/** Shows setup help instead of a confusingly empty inbox until you're on the allow-list. */
function AllowListGate({
  api,
  email,
  onSignOut,
  children,
}: {
  api: JobsApi
  email: string
  onSignOut: () => void
  children: ReactNode
}) {
  const [allowed, setAllowed] = useState<boolean | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.amIAllowed().then(setAllowed, (e: Error) => setError(e.message))
  }, [api])

  if (error) return <p className="center error">Couldn't check access: {error}</p>
  if (allowed === null) return <p className="center muted">Checking access…</p>
  if (allowed) return <>{children}</>
  return (
    <main className="panel">
      <h1>Almost there</h1>
      <p>
        You're signed in as <strong>{email}</strong>, but this account isn't on the allow-list yet, so the
        database won't show it any jobs.
      </p>
      <p>In the Supabase dashboard, open <strong>SQL Editor</strong>, run this once, then reload this page:</p>
      <pre>{`insert into private.allowed_users (user_id)
select id from auth.users where email = '${email}'
on conflict do nothing;`}</pre>
      <button onClick={onSignOut}>Sign out</button>
    </main>
  )
}
