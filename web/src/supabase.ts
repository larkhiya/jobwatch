// The Supabase connection, or null when the app isn't configured yet (then it runs on demo data).
// The URL and PUBLISHABLE key are safe to ship to the browser: Row Level Security decides
// what each logged-in user can see. The SECRET key never goes anywhere near this code.

import { createClient, type SupabaseClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL?.trim()
const publishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim()

export const supabase: SupabaseClient | null =
  url && publishableKey
    ? createClient(url, publishableKey, {
        // Implicit flow: the sign-in link works even if you open the email on a different
        // device (e.g. request it on your laptop, tap it on your phone).
        auth: { flowType: 'implicit', persistSession: true, detectSessionInUrl: true },
      })
    : null
