# Deploying LabelLens — backend on Render, frontend on Vercel

The app is two independently deployed pieces talking over HTTPS: a FastAPI backend
(Render) and a static Vite build (Vercel). Deploy the backend first — the frontend build
needs its URL.

## 0. Push what's here to GitHub

Both platforms build from your GitHub repo, not your laptop. Commit and push first,
including the deployment support added alongside this guide (`render.yaml`,
`backend/app/config.py`'s `cors_origins`/`cors_origin_regex`, `frontend/src/api.ts`'s
`VITE_API_URL`, the two `.env.example` files). `.env` itself is gitignored — the real
`NEBIUS_API_KEY` never leaves your machine this way; you'll re-enter it in each
platform's dashboard.

```bash
git add -A
git commit -m "Add deployment config for Render + Vercel"
git push
```

## 1. Backend on Render

**Storage decision first, because it changes which plan you pick:** the backend keeps
its SQLite database and every evidence photo/docket on local disk
(`backend/labellens.db`, `backend/storage/`). Render's Free plan has no persistent
disk — anything written to disk is gone on the next deploy or restart. For a quick demo
that's fine (reseed after each fresh deploy, step 5). For anything you want to survive
a redeploy — which for an evidence ledger is the whole point — attach a paid plan's
persistent Disk, covered in 1c.

### 1a. Create the service

1. [dashboard.render.com](https://dashboard.render.com) → **New +** → **Web Service** →
   connect the `SIH_Compilance` repo.
2. **Root Directory**: `backend`.
3. **Runtime**: **Docker** — Render will use `backend/Dockerfile` as-is. Don't pick the
   "Python 3" native runtime: the Dockerfile installs `tesseract-ocr` (the offline OCR
   fallback) and the Noto Devanagari font (so Hindi values render in the evidence
   docket PDF instead of empty boxes); the native runtime skips both.
4. **Plan**: Free to start (see the storage note above), or a paid instance if you're
   attaching a disk now.
5. **Health Check Path**: `/api/v1/system/health`.
6. Leave the port field alone — the Dockerfile exposes 8000, which Render reads.

Or skip 1a–1b entirely: **New +** → **Blueprint**, point it at this repo, and the root
`render.yaml` proposes this same service for you to review and deploy. If the import
errors on a field name (Render's blueprint schema shifts sometimes), fall back to the
manual steps — they're the ground truth.

### 1b. Environment variables

In the service's **Environment** tab:

| Key | Value |
|---|---|
| `NEBIUS_API_KEY` | your real key from `backend/.env` |
| `LABELLENS_CORS_ORIGINS` | your Vercel URL once you have it (step 2), e.g. `https://labellens.vercel.app` — comma-separate more than one |
| `LABELLENS_CORS_ORIGIN_REGEX` | optional: `https://.*\.vercel\.app` so every Vercel *preview* deploy (each gets its own random subdomain) is allowed too, not just production |

You won't have the Vercel URL yet on first deploy — put a placeholder
(`http://localhost:5173` is harmless) and come back to update it after step 2. Changing
an env var triggers a redeploy automatically.

### 1c. Persistent storage (skip only if you're fine reseeding after every deploy)

Render Disks require a paid instance type. Once you're on one: service → **Disks** →
**Add Disk** → mount path `/app/storage`, any size (1GB is plenty for a demo). Then add
one more env var:

```
LABELLENS_DATABASE_URL=sqlite:////app/storage/labellens.db
```

This puts the database file on the same durable disk as the evidence images and
dockets, which already write to `/app/storage` by default (that's `backend/storage`
inside the container) — no code changes needed beyond this env var. `render.yaml` has
this block ready, commented out.

SQLite-on-a-disk is fine for one instance at low traffic (this is a field-inspection
tool, not high-throughput). If you ever need to scale to multiple backend instances,
that's the point to migrate to Render's managed Postgres instead — a bigger change, not
needed now.

### 1d. Verify

Render gives you a URL like `https://labellens-backend.onrender.com`. Check
`https://<that>/api/v1/system/health` returns `{"status": "ok", ...}`. The Free plan
spins the instance down after 15 minutes idle — the first request after that takes
20–40s to respond while it wakes up; that's normal, not a failure.

## 2. Frontend on Vercel

1. [vercel.com/new](https://vercel.com/new) → import the same repo.
2. **Root Directory**: `frontend`. Framework preset (Vite) and the build command
   (`npm run build`, output `dist`) are auto-detected from `frontend/package.json`.
3. **Environment Variables** → add `VITE_API_URL` = your Render URL from 1d, **no
   trailing slash** — set it for Production, Preview, and Development so preview
   deploys also reach the real backend. (Vite only reads `VITE_`-prefixed vars, and
   only at build time — this is a build-time bake-in, not a runtime secret, so don't put
   anything sensitive here.)
4. Deploy. `frontend/vercel.json` already rewrites every path to `index.html`, which
   client-side routing (React Router) needs — nothing else to configure.

## 3. Close the loop

Go back to Render (step 1b) and set `LABELLENS_CORS_ORIGINS` to the real Vercel URL —
without this, the browser blocks every API call with a CORS error and the deployed
frontend looks broken even though both halves are up. Save it; Render redeploys the
backend automatically. If you want preview deploys to work too, add the
`LABELLENS_CORS_ORIGIN_REGEX` from 1b now that you've seen a real preview URL's shape.

## 4. Seed demo data

A fresh deploy has an empty database. To load the same demo inspections, entities, and
cases used in development:

- **Paid Render plan**: service → **Shell** tab → `python -m app.seed`.
- **Free plan** (no Shell access): there's no built-in one-off command runner. Either
  temporarily upgrade to run the seed once, or skip seeding and let real inspections
  populate it — the app works fine empty, it just starts with nothing to show.

Reminder: `app.seed` calls `reset_database()` first, which drops every table — never
run it against a deployment with real inspections you want to keep.

## 5. Ongoing

- Pushing to your connected branch redeploys both platforms automatically.
- Rotate `NEBIUS_API_KEY` in the Render dashboard if it's ever exposed — it's read
  from the environment, never from a committed file.
- Custom domains: both platforms support adding one under their respective project
  settings; update `LABELLENS_CORS_ORIGINS` to match if you add one to the frontend.
