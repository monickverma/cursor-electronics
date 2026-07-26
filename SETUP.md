# Circuit OS — Local Setup Guide (Windows)

This project isn't fully "clone and go" yet, so follow these steps in order the first time you set it up.

## 1. Prerequisites

Install these before doing anything else:

- **Docker Desktop** — must be running before you start the app. Download: https://www.docker.com/products/docker-desktop/
- **Python 3.11+** — https://www.python.org/downloads/ (check "Add python.exe to PATH" during install)
- **Node.js 18+** — https://nodejs.org/
- **Git** — https://git-scm.com/download/win
- **ngspice** — the circuit simulator. Windows doesn't have a package manager install for this:
  1. Go to https://ngspice.sourceforge.io/download.html
  2. Download the latest Windows release (a `.7z` or `.zip` archive, e.g. `ngspice-XX_64.7z`)
  3. Extract it somewhere permanent, e.g. `C:\ngspice`
  4. Add the `Spice64\bin` folder inside it to your PATH (Windows Search → "Edit the system environment variables" → Environment Variables → Path → New)
  5. Confirm it worked: open a new terminal and run `ngspice --version`

## 2. Clone the repo

```
git clone <repo-url>
cd cursor-electronics
```

## 3. Set up the backend (Python)

```
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

Keep using this same venv any time you run the backend or Celery manually. `start.bat` does **not** create or activate a venv for you — if you skip this step, `start.bat` will fail with `uvicorn is not recognized` or `ModuleNotFoundError`.

## 4. Set up the frontend (Node)

```
cd frontend
npm install
cd ..
```

## 5. Create your `.env` file

`.env` is intentionally not in the repo (it holds secrets). Copy the example and fill it in:

```
copy .env.example .env
```

Open `.env` and set:

- `ANTHROPIC_API_KEY` — your own Anthropic API key (get one at https://console.anthropic.com/). This is required — the backend crashes on startup without it.
- `SECRET_KEY` — any random 32+ character string. Generate one with:
  ```
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
- Leave `DATABASE_URL` and `REDIS_URL` as the defaults in `.env.example` — they already match what `docker-compose.yml` sets up.

## 6. Start Docker Desktop

Open Docker Desktop and wait until it says it's running. `start.bat` will fail immediately if it isn't.

## 7. Run the app

From the project root:

```
start.bat
```

This will:
1. Start Postgres + Redis in Docker
2. Open a window running the FastAPI backend (`localhost:8000`)
3. Open a window running the Celery worker
4. Open a window running the Next.js frontend (`localhost:3000`)

Give it about 15 seconds, then open http://localhost:3000.

## 8. Create an account

There is no pre-seeded login. The `test@circuitos.dev` credentials mentioned in the startup banner don't exist until you register them yourself — either through the frontend's sign-up form, or by calling the API directly:

```
POST http://localhost:8000/auth/register
{
  "email": "test@circuitos.dev",
  "password": "TestPass123!"
}
```

(You can check the exact fields at http://localhost:8000/docs.)

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `docker-compose failed. Is Docker Desktop running?` | Docker Desktop isn't open, or isn't finished starting up |
| Backend window closes immediately / `uvicorn is not recognized` | Step 3 (venv + pip install) wasn't done, or the venv isn't activated in that window |
| Frontend window fails on `npm run dev` | Step 4 (`npm install`) wasn't done |
| Backend crashes on startup with a Pydantic/settings error | `.env` is missing or missing a required field (`ANTHROPIC_API_KEY`, `SECRET_KEY`, etc.) |
| Login fails for `test@circuitos.dev` | That account was never registered — see Step 8 |
| Simulation requests fail/time out | ngspice isn't installed or isn't on PATH — run `ngspice --version` in a new terminal to check |
| Backend can't reach the database | Docker's `db` container isn't healthy yet — wait a bit longer, or run `docker-compose ps` to check |

## Shutting down

Close the three spawned terminal windows, then run:

```
docker-compose down
```
