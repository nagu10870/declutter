from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from app.core.database import create_tables
from app.core.config import settings

# Month 1
from app.api.v1 import auth, connections, scans, dashboard, duplicates
# Month 2
from app.api.v1 import cloud, similar
# Month 3
from app.api.v1 import classify, suggestions, billing, onedrive
# Month 4
from app.api.v1 import share
# Month 5
from app.api.v1 import api_keys, export_routes, webhooks, admin
# Month 6
from app.api.v1 import account


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(
    title="Declutter API",
    description="AI-powered duplicate file finder and cloud storage cleanup",
    version="0.6.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Route Registration ───────────────────────────────────────────────────
# Month 1
app.include_router(auth.router,        prefix="/api/v1")
app.include_router(connections.router, prefix="/api/v1")
app.include_router(scans.router,       prefix="/api/v1")
app.include_router(dashboard.router,   prefix="/api/v1")
app.include_router(duplicates.router,  prefix="/api/v1")

# Month 2
app.include_router(cloud.router,       prefix="/api/v1")
app.include_router(similar.router,     prefix="/api/v1")

# Month 3
app.include_router(classify.router,    prefix="/api/v1")
app.include_router(suggestions.router, prefix="/api/v1")
app.include_router(billing.router,     prefix="/api/v1")
app.include_router(onedrive.router,    prefix="/api/v1")

# Month 4
app.include_router(share.router,       prefix="/api/v1")

# Month 5
app.include_router(api_keys.router,    prefix="/api/v1")
app.include_router(export_routes.router, prefix="/api/v1")
app.include_router(webhooks.router,    prefix="/api/v1")
app.include_router(admin.router,       prefix="/api/v1")

# Month 6
app.include_router(account.router,     prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.6.0"}
