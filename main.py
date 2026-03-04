import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from cache import init_cache, get_cache
from auth import router as auth_router
from routes_daily import router as dashboard_router

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

REDIS_URL    = os.environ.get("CACHE_REDIS_URL", "redis://localhost:6379/0")
FRONTEND_DIR = Path(__file__).parent


# --- Lifespan (startup / shutdown) -------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_cache()
    print("OK  Cache inicializado con Redis")
    yield
    print("--  App cerrada")


# --- App ---------------------------------------------------------------------

app = FastAPI(
    title="App BI",
    description="Dashboard de ventas migrado de Flask a FastAPI async",
    version="2.0.0",
    lifespan=lifespan,
)

# --- CORS --------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # ✅ CORREGIDO: False ya que no usas auth todavía
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers -----------------------------------------------------------------

app.include_router(auth_router)
app.include_router(dashboard_router)

# --- Admin cache -------------------------------------------------------------

@app.post("/api/admin/cache/clear", tags=["admin"])
async def clear_cache_endpoint():
    try:
        cache = get_cache()
        await cache.clear()
        return {"success": True, "message": "Cache limpiado exitosamente"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.get("/api/admin/cache/stats", tags=["admin"])
async def cache_stats():
    try:
        from redis.asyncio import Redis
        r = Redis.from_url(REDIS_URL)
        info = await r.info()
        db_size = await r.dbsize()
        await r.aclose()
        return {
            "success": True,
            "data": {
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_keys":        db_size,
            },
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# --- Servir frontend ---------------------------------------------------------

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/{filename}")
async def serve_file(filename: str):
    file_path = FRONTEND_DIR / filename
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Not found")