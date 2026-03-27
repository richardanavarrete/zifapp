# Zif - Inventory Management

Full-stack inventory management app built with **Next.js** and **Supabase**, deployed on **Vercel**.

## Tech Stack

- **Frontend & API**: Next.js 16 (App Router + Route Handlers)
- **UI**: React 19, Tailwind CSS 4, Shadcn UI
- **Database & Auth**: Supabase (PostgreSQL + Auth + RLS)
- **State**: Zustand, TanStack React Query
- **Charts**: Recharts
- **Deployment**: Vercel

## Features

- **Inventory Management** - Upload Excel/CSV, auto-detect columns, track items
- **Dashboard Analytics** - Usage trends, rolling averages, alerts
- **Voice Counting** - Audio transcription (OpenAI Whisper) + fuzzy matching
- **Order Recommendations** - Smart ordering based on usage patterns & forecasts
- **Multi-tenancy** - Organizations with role-based access (owner/admin/member/viewer)

## Getting Started

```bash
cd frontend
cp .env.local.example .env.local
# Fill in your Supabase credentials and OpenAI key
npm install
npm run dev
```

## Environment Variables

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Supabase project URL (server-side) |
| `SUPABASE_ANON_KEY` | Supabase anon key (server-side) |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (server-side) |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL (client-side) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key (client-side) |
| `OPENAI_API_KEY` | OpenAI API key for voice transcription |

## Project Structure

```
frontend/
  src/
    app/
      api/v1/          # Next.js API route handlers
        auth/           # Register, login, logout, refresh, organizations
        inventory/      # Upload, datasets, items, dashboard
        voice/          # Sessions, transcribe, match, records
        orders/         # Recommend, runs, export
        health/         # Health check
      (pages)/          # App pages (dashboard, inventory, orders, voice, etc.)
    components/         # React components (layout, UI)
    lib/
      supabase/         # Supabase client (server + browser) & repository
      services/         # Business logic (parser, stats, voice, orders)
      api.ts            # Frontend API client
      api-utils.ts      # Shared API route utilities
    store/              # Zustand state management
    types/              # TypeScript types
```
