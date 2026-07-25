# Security — Circuit OS

## Environment Variables

All secrets are in `.env` (never committed). `.env.example` is committed with placeholder values.

```bash
# Required — app crashes at startup if any of these are missing (pydantic-settings enforces this)
ANTHROPIC_API_KEY=sk-ant-api03-...
DATABASE_URL=postgresql+asyncpg://circuitos:changeme@localhost:5432/circuitos
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=<minimum 32 random chars — openssl rand -hex 32>

# Optional — defaults shown
CELERY_BROKER_URL=redis://localhost:6379/1
ENVIRONMENT=development
SENTRY_DSN=
CORS_ORIGINS=http://localhost:3000
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080
```

**Never hardcode any of these.** Never commit `.env`. `.gitignore` already excludes it.

Generate a secure `SECRET_KEY`:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## CORS — Required from Day 1

FastAPI (port 8000) and Next.js (port 3000) are different origins. Without CORS, every browser API call fails silently.

`CORSMiddleware` must be added in `main.py` **before any route is registered**:

```python
# main.py — order matters
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, ...)

# THEN register routers
app.include_router(auth.router, prefix="/auth")
```

## Authentication

All design routes require a valid JWT. Routes: `/design/generate`, `/design/{id}/patch`, `/design/{id}/simulation/{job_id}`.

Token flow:
1. `POST /auth/register` or `POST /auth/login` → returns `access_token`
2. Client sends `Authorization: Bearer <token>` on all design requests
3. `get_current_user` dependency validates token, rejects expired or tampered tokens

```python
# All protected routes use this dependency
@router.post("/generate")
async def generate_design(
    request: Request,
    body: GenerateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user=Depends(get_current_user),   # ← JWT enforced here
):
```

Password hashing uses `bcrypt` directly (not `passlib` — passlib 1.7.4 is incompatible with bcrypt 4.x).

## Rate Limiting

Applied via `slowapi` on all LLM and simulation endpoints:

| Endpoint | Free tier | Reason |
|---|---|---|
| `POST /design/generate` | 10/hour | Each call uses ~$0.05–0.15 in Claude API costs |
| `POST /design/{id}/patch` | 20/hour | Each call uses ~$0.02–0.05 |
| `GET /design/{id}/simulation/{job_id}` | 100/hour | Polling endpoint — generous but bounded |

Rate limit decorator pattern:
```python
@router.post("/generate")
@limiter.limit("10/hour")
async def generate_design(request: Request, ...):
    # request parameter MUST be present for slowapi to work
```

Rate limit violations return HTTP 429 with `Retry-After` header.

## Performance Targets (Minimum for Launch)

| Operation | Target | Measurement |
|---|---|---|
| Full generation (intent → all outputs, no simulation) | < 15 seconds | Sentry performance trace |
| Simulation job completion (p95) | < 30 seconds | `simulation_runs.completed_at - started_at` |
| Patch operation | < 20 seconds | Sentry trace |
| Rule engine | < 500ms | Unit test timing |
| Load test: 100 consecutive requests | Zero HTTP 500s | Required before launch |

These are hard requirements, not aspirational. Do not launch Phase 1 if any target is missed.

## No In-Memory Storage

```python
# WRONG — dies on server restart, breaks with multiple Celery workers
design_store = {}
design_store[circuit_id] = ir

# CORRECT — persist to PostgreSQL immediately after generation
await save_design(db, ir, str(user.id))
```

The patch system, simulation polling, and audit trail all depend on persistent storage. An in-memory dict cannot survive a process restart or scale across multiple workers.

## Static BOM Pricing Only in Phase 1

```python
# CORRECT — static dict, zero external dependencies
from generators.bom.compiler import BOMCompiler
rows = BOMCompiler().compile(ir)  # reads from component_constraints.py

# WRONG — live API call in Phase 1
price = digikey_api.get_price(part_number)  # rate-limited, authenticated, slow
```

Phase 1 uses static prices from `component_constraints.py` and `component_db.json`. Live Digikey/LCSC API integration is Phase 2. Do not add it early — it creates an authenticated, rate-limited dependency that slows development.
