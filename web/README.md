# jobwatch web app

React + TypeScript (Vite) inbox for the jobs the bot collects. See the main README for setup.

```bash
npm install
npm run dev      # http://localhost:5173 (uses demo data until Supabase is configured)
npm test         # unit tests (Vitest)
npm run build    # production build into dist/
```

Configuration comes from environment variables at build time (never put the SECRET key here):

- `VITE_SUPABASE_URL`: your project URL, e.g. `https://abcdefghijkl.supabase.co`
- `VITE_SUPABASE_PUBLISHABLE_KEY`: the publishable key (`sb_publishable_...`), safe for browsers
