import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from cache import init_cache, get_cache
from auth import router as auth_router, get_current_user, CurrentUser
from routes_daily import router as dashboard_router

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("CACHE_REDIS_URL", "redis://localhost:6379/0")
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")

# --- Lifespan (startup / shutdown) -------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_cache()
    logger.info("Cache inicializado")
    yield
    logger.info("App cerrada")

# --- App ---------------------------------------------------------------------

app = FastAPI(
    title="App BI",
    description="Dashboard de ventas migrado de Flask a FastAPI async",
    version="2.0.0",
    lifespan=lifespan,
)

# --- CORS - PERMITIR TODOS LOS ORIGENES PARA PRUEBAS -------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers -----------------------------------------------------------------

app.include_router(auth_router)
app.include_router(dashboard_router)

# --- Admin cache -------------------------------------------------------------

@app.get("/health", tags=["infra"])
async def health():
    return {"status": "ok"}


@app.post("/api/admin/cache/clear", tags=["admin"])
async def clear_cache_endpoint(current_user: CurrentUser):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admins")
    try:
        cache = get_cache()
        await cache.clear()
        return {"success": True, "message": "Cache limpiado exitosamente"}
    except Exception as exc:
        logger.error("Error limpiando cache: %s", exc)
        return {"success": False, "error": str(exc)}


@app.get("/api/admin/cache/stats", tags=["admin"])
async def cache_stats(current_user: CurrentUser):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admins")
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
                "total_keys": db_size,
            },
        }
    except Exception as exc:
        logger.error("Error obteniendo stats de cache: %s", exc)
        return {"success": False, "error": str(exc)}


# --- Manejo global de errores ------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("Error no capturado: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})

# --- Servir frontend ---------------------------------------------------------

# Obtener directorio actual
FRONTEND_DIR = Path(__file__).parent

# Servir archivos estáticos
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/login.html")
async def serve_login():
    return FileResponse(FRONTEND_DIR / "login.html")

# Servir otros archivos estáticos (JS, CSS)
@app.get("/{filename}")
async def serve_file(filename: str):
    # No servir rutas de API como archivos estáticos
    if filename.startswith("api/") or filename.startswith("auth/"):
        raise HTTPException(status_code=404, detail="Not found")
    
    file_path = FRONTEND_DIR / filename
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Not found")